from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .core import FaultPackError, canonical_json, sha256_bytes
from .redact import redact_value

MAX_INPUT_BYTES = 10_000_000
MAX_LINE_BYTES = 2_000_000
MAX_EVENTS = 10_000
MAX_ATTRIBUTES = 32
MAX_TEXT = 512

InteropKind = Literal[
    "agent",
    "model",
    "tool_call",
    "tool_result",
    "retrieval",
    "policy",
    "evaluation",
    "assertion",
    "annotation",
    "unknown",
]
InteropStatus = Literal["passed", "failed", "timeout", "error", "unknown"]
Severity = Literal["info", "warning", "error"]


class InteropError(FaultPackError):
    """Raised for invalid or unsafe evidence-interchange input."""


class InteropFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^[a-z0-9]+(?:\.[a-z0-9_-]+)+$")
    severity: Severity
    message: str = Field(min_length=1, max_length=MAX_TEXT)
    path: str = Field(min_length=1, max_length=MAX_TEXT)
    remediation: str = Field(min_length=1, max_length=MAX_TEXT)


class InteropSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str = Field(min_length=1, max_length=64)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str | None = Field(default=None, max_length=128)


class InteropEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    kind: InteropKind
    source_kind: str = Field(min_length=1, max_length=96)
    name: str = Field(min_length=1, max_length=MAX_TEXT)
    trace_id: str | None = Field(default=None, max_length=128)
    span_id: str | None = Field(default=None, max_length=128)
    parent_id: str | None = Field(default=None, max_length=128)
    status: InteropStatus = "unknown"
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attributes: dict[str, str] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["faultpack-evidence"] = "faultpack-evidence"
    format_version: Literal["0.1"] = "0.1"
    source: InteropSource
    event_count: int = Field(ge=1, le=MAX_EVENTS)
    events: list[InteropEvent] = Field(min_length=1, max_length=MAX_EVENTS)
    findings: list[InteropFinding] = Field(default_factory=list, max_length=MAX_EVENTS)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @staticmethod
    def _payload_without_digest(value: dict[str, Any]) -> dict[str, Any]:
        return {key: item for key, item in value.items() if key != "bundle_sha256"}

    def canonical_payload(self) -> bytes:
        return canonical_json(self._payload_without_digest(self.model_dump(mode="json")))

    def verify_digest(self) -> None:
        expected = sha256_bytes(self.canonical_payload())
        if self.bundle_sha256 != expected:
            raise InteropError(f"bundle digest mismatch: expected {expected}")

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.findings)


_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
_KIND_MAP = {
    "agent": "agent",
    "agent_turn": "agent",
    "agent_span": "agent",
    "llm": "model",
    "model": "model",
    "chat": "model",
    "tool": "tool_call",
    "tool_call": "tool_call",
    "tool-use": "tool_call",
    "tool_result": "tool_result",
    "tool_response": "tool_result",
    "retriever": "retrieval",
    "retrieval": "retrieval",
    "guardrail": "policy",
    "policy": "policy",
    "evaluator": "evaluation",
    "evaluation": "evaluation",
    "assertion": "assertion",
    "annotation": "annotation",
}


def _text(value: Any, patterns: list[str] | None = None, limit: int = MAX_TEXT) -> str:
    result = redact_value(str(value), patterns)
    return result[:limit]


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value)
    return candidate if _ID_PATTERN.fullmatch(candidate) else None


def _first(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


def _nested(raw: dict[str, Any], *keys: str) -> Any:
    context = raw.get("context")
    if isinstance(context, dict):
        value = _first(context, *keys)
        if value is not None:
            return value
    return _first(raw, *keys)


def _kind(value: Any) -> InteropKind:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_")
    return _KIND_MAP.get(normalized, "unknown")  # type: ignore[return-value]


def _status(value: Any) -> InteropStatus:
    if isinstance(value, dict):
        value = _first(value, "code", "status", "value", "message")
    normalized = str(value or "unknown").strip().lower()
    if normalized in {"ok", "success", "passed", "pass", "completed", "complete"}:
        return "passed"
    if normalized in {"error", "failed", "failure", "fail", "denied", "blocked"}:
        return "failed"
    if normalized in {"timeout", "timed_out"}:
        return "timeout"
    return "unknown"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _duration_ms(raw: dict[str, Any]) -> int | None:
    direct = _first(raw, "duration_ms", "durationMs", "elapsed_ms", "elapsedMs")
    if direct is not None and _number(direct) is not None:
        return max(0, min(int(float(direct)), 86_400_000))
    duration_ns = _number(_first(raw, "duration_ns", "durationNs"))
    if duration_ns is not None:
        return max(0, min(int(duration_ns / 1_000_000), 86_400_000))
    start = _number(_first(raw, "startTimeUnixNano", "start_time_unix_nano"))
    end = _number(_first(raw, "endTimeUnixNano", "end_time_unix_nano"))
    if start is not None and end is not None and end >= start:
        return max(0, min(int((end - start) / 1_000_000), 86_400_000))
    return None


def _otlp_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
        if key in value:
            return value[key]
    if "arrayValue" in value and isinstance(value["arrayValue"], dict):
        values = value["arrayValue"].get("values", [])
        return [_otlp_value(item) for item in values[:MAX_ATTRIBUTES]]
    if "kvlistValue" in value and isinstance(value["kvlistValue"], dict):
        return {
            str(item.get("key")): _otlp_value(item.get("value"))
            for item in value["kvlistValue"].get("values", [])[:MAX_ATTRIBUTES]
            if isinstance(item, dict) and item.get("key") is not None
        }
    return value


def _attributes(raw: Any, patterns: list[str] | None = None) -> dict[str, str]:
    if not isinstance(raw, dict):
        if not isinstance(raw, list):
            return {}
        mapped: dict[str, Any] = {}
        for item in raw[:MAX_ATTRIBUTES]:
            if isinstance(item, dict) and item.get("key") is not None:
                mapped[str(item["key"])] = _otlp_value(item.get("value"))
        raw = mapped
    result: dict[str, str] = {}
    for key in sorted(raw, key=str)[:MAX_ATTRIBUTES]:
        value = raw[key]
        safe_key = _text(key, patterns, 96)
        if re.search(
            r"(token|secret|password|api[_-]?key|private[_-]?key|cookie|auth)", str(key), re.I
        ):
            result[safe_key] = "[REDACTED]"
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        result[safe_key] = _text(value, patterns)
    return result


def _payload(raw: dict[str, Any]) -> Any:
    for key in (
        "payload",
        "input",
        "output",
        "body",
        "result",
        "params",
        "arguments",
        "tool_input",
        "response",
    ):
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


def _payload_digest(raw: dict[str, Any]) -> str | None:
    payload = _payload(raw)
    if payload is None:
        return None
    if isinstance(payload, (dict, list, int, float, bool)):
        data = canonical_json(payload)
    else:
        data = str(payload).encode("utf-8")
    return sha256_bytes(data)


def _normal_event(
    raw: dict[str, Any], index: int, patterns: list[str] | None = None, source_kind: Any = None
) -> tuple[InteropEvent, list[InteropFinding]]:
    findings: list[InteropFinding] = []
    source_value = (
        source_kind
        if source_kind is not None
        else _first(raw, "kind", "type", "event", "span_kind")
    )
    source_text = _text(source_value or "unknown", patterns, 96)
    name_value = _first(raw, "name", "operationName", "operation_name", "method", "tool_name")
    if name_value is None and isinstance(raw.get("params"), dict):
        name_value = _first(raw["params"], "name", "tool_name")
    if name_value is None:
        name_value = source_text
        findings.append(
            InteropFinding(
                rule_id="interop.event.missing_name",
                severity="warning",
                message="Event has no explicit operation name; adapter used its source kind.",
                path=f"events[{index}].name",
                remediation=(
                    "Export a stable operation or tool name when the producer can provide one."
                ),
            )
        )
    trace_id = _identifier(_nested(raw, "trace_id", "traceId", "traceID"))
    span_id = _identifier(_nested(raw, "span_id", "spanId", "spanID"))
    parent_id = _identifier(_nested(raw, "parent_id", "parentId", "parentSpanId"))
    status_value = _first(raw, "status", "outcome", "result_status", "resultStatus")
    event = InteropEvent(
        sequence=index + 1,
        kind=_kind(source_value),
        source_kind=source_text,
        name=_text(name_value, patterns),
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent_id,
        status=_status(status_value),
        duration_ms=_duration_ms(raw),
        payload_sha256=_payload_digest(raw),
        attributes=_attributes(_first(raw, "attributes", "attrs"), patterns),
    )
    return event, findings


def _parse_jsonl(
    data: bytes, adapter: str, patterns: list[str] | None = None
) -> tuple[list[InteropEvent], list[InteropFinding], str | None]:
    events: list[InteropEvent] = []
    findings: list[InteropFinding] = []
    producer: str | None = None
    for line_number, line in enumerate(data.splitlines(), start=1):
        if not line.strip():
            continue
        if len(line) > MAX_LINE_BYTES:
            raise InteropError(f"line {line_number} exceeds the {MAX_LINE_BYTES}-byte limit")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InteropError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
        if not isinstance(raw, dict):
            raise InteropError(f"line {line_number} must contain a JSON object")
        if producer is None:
            candidate = _first(raw, "producer", "producer_name", "producerName", "service_name")
            if candidate is not None:
                producer = _text(candidate, patterns, 128)
        mcp_kind = None
        if adapter == "mcp-jsonl":
            method = str(raw.get("method", "")).lower()
            if "call" in method or "request" in method:
                mcp_kind = "tool_call"
            elif "result" in method or "response" in method:
                mcp_kind = "tool_result"
        event, event_findings = _normal_event(raw, len(events), patterns, source_kind=mcp_kind)
        events.append(event)
        findings.extend(event_findings)
    if adapter == "mcp-jsonl":
        for index, event in enumerate(events):
            if event.kind == "unknown" and (
                event.source_kind == "unknown" or "tool" not in event.source_kind.lower()
            ):
                findings.append(
                    InteropFinding(
                        rule_id="interop.mcp.unknown_event",
                        severity="info",
                        message="MCP record did not map to a known tool-call or tool-result kind.",
                        path=f"events[{index}].kind",
                        remediation=(
                            "Include an explicit method or tool event kind for classification."
                        ),
                    )
                )
    return events, findings, producer


def _parse_otlp(
    data: bytes, patterns: list[str] | None = None
) -> tuple[list[InteropEvent], list[InteropFinding], str | None]:
    try:
        document = json.loads(data)
    except json.JSONDecodeError as exc:
        raise InteropError(f"invalid OTLP JSON: {exc.msg}") from exc
    if not isinstance(document, dict):
        raise InteropError("OTLP input must be a JSON object")
    resource_spans = document.get("resourceSpans")
    if not isinstance(resource_spans, list):
        raise InteropError("OTLP JSON must contain a resourceSpans array")
    events: list[InteropEvent] = []
    findings: list[InteropFinding] = []
    producer: str | None = None
    for resource_index, resource in enumerate(resource_spans):
        if not isinstance(resource, dict):
            raise InteropError(f"resourceSpans[{resource_index}] must be an object")
        resource_value = resource.get("resource")
        resource_attrs = _attributes(
            resource_value.get("attributes", []) if isinstance(resource_value, dict) else [],
            patterns,
        )
        if producer is None:
            producer = resource_attrs.get("service.name") or resource_attrs.get(
                "telemetry.sdk.name"
            )
        scopes = resource.get("scopeSpans")
        if not isinstance(scopes, list):
            scopes = resource.get("instrumentationLibrarySpans", [])
        if not isinstance(scopes, list):
            scopes = []
        for scope in scopes:
            if not isinstance(scope, dict):
                continue
            for span in scope.get("spans", []):
                if not isinstance(span, dict):
                    continue
                attrs = _attributes(span.get("attributes", []), patterns)
                span_kind = attrs.get("openinference.span.kind") or attrs.get(
                    "gen_ai.operation.name"
                )
                event, event_findings = _normal_event(
                    {
                        **span,
                        "attributes": attrs,
                        "traceId": span.get("traceId"),
                        "spanId": span.get("spanId"),
                        "parentSpanId": span.get("parentSpanId"),
                        "status": span.get("status"),
                    },
                    len(events),
                    patterns,
                    source_kind=span_kind or span.get("kind") or "unknown",
                )
                events.append(event)
                findings.extend(event_findings)
    return events, findings, producer


def detect_format(data: bytes) -> str:
    try:
        document = json.loads(data)
    except json.JSONDecodeError:
        first_line = next((line for line in data.splitlines() if line.strip()), b"")
        if b"jsonrpc" in first_line or b"method" in first_line or b"tool" in first_line:
            return "mcp-jsonl"
        return "generic-jsonl"
    if isinstance(document, dict) and "resourceSpans" in document:
        return "openinference-otlp-json"
    if isinstance(document, list):
        records = document
    else:
        records = [document]
    first = records[0] if records and isinstance(records[0], dict) else {}
    keys = {str(key).lower() for key in first}
    method_value = str(first.get("method", "")).lower()
    if "tool_name" in keys or (
        "method" in keys
        and (
            "jsonrpc" in keys
            or "params" in keys
            or "tool" in method_value
            or "call" in method_value
            or "result" in method_value
        )
    ):
        return "mcp-jsonl"
    if keys & {"job", "workflow", "step", "check_run", "check"}:
        return "ci-jsonl"
    return "generic-jsonl"


def _validate_events(events: list[InteropEvent], findings: list[InteropFinding]) -> None:
    if not events:
        raise InteropError("input produced no events")
    if len(events) > MAX_EVENTS:
        raise InteropError(f"input exceeds the {MAX_EVENTS}-event limit")
    for index, event in enumerate(events):
        if event.sequence != index + 1:
            raise InteropError("normalized events must have contiguous sequences")
    if not any(event.trace_id or event.span_id for event in events):
        findings.append(
            InteropFinding(
                rule_id="interop.trace.missing_identity",
                severity="warning",
                message="No trace_id or span_id was present in the imported evidence.",
                path="events",
                remediation=(
                    "Export stable trace or span identifiers when the producer supports them."
                ),
            )
        )
    duplicates = [event.span_id for event in events if event.span_id]
    if len(duplicates) != len(set(duplicates)):
        findings.append(
            InteropFinding(
                rule_id="interop.trace.duplicate_span_id",
                severity="warning",
                message="Multiple events reuse the same span_id.",
                path="events",
                remediation=(
                    "Preserve producer span identity or omit it rather than reusing an identifier."
                ),
            )
        )


def normalize_bytes(
    data: bytes, source_format: str = "auto", patterns: list[str] | None = None
) -> EvidenceBundle:
    if len(data) > MAX_INPUT_BYTES:
        raise InteropError(f"input exceeds the {MAX_INPUT_BYTES}-byte limit")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InteropError("input must be valid UTF-8") from exc
    selected = detect_format(data) if source_format == "auto" else source_format
    allowed = {"generic-jsonl", "mcp-jsonl", "ci-jsonl", "openinference-otlp-json"}
    if selected not in allowed:
        raise InteropError(f"unsupported format: {selected}")
    if selected == "openinference-otlp-json":
        events, findings, producer = _parse_otlp(data, patterns)
    else:
        events, findings, producer = _parse_jsonl(data, selected, patterns)
    _validate_events(events, findings)
    source = InteropSource(adapter=selected, input_sha256=sha256_bytes(data), producer=producer)
    draft = EvidenceBundle(
        source=source,
        event_count=len(events),
        events=events,
        findings=findings,
        bundle_sha256="0" * 64,
    )
    digest = sha256_bytes(draft.canonical_payload())
    return draft.model_copy(update={"bundle_sha256": digest})


def normalize_file(
    path: Path, source_format: str = "auto", patterns: list[str] | None = None
) -> EvidenceBundle:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InteropError(f"cannot read input: {path}") from exc
    return normalize_bytes(data, source_format, patterns)


def load_bundle(path: Path) -> EvidenceBundle:
    try:
        data = path.read_bytes()
        if len(data) > MAX_INPUT_BYTES:
            raise InteropError(f"bundle exceeds the {MAX_INPUT_BYTES}-byte limit")
        bundle = EvidenceBundle.model_validate_json(data)
    except InteropError:
        raise
    except (OSError, UnicodeDecodeError, ValidationError, ValueError) as exc:
        raise InteropError(f"invalid evidence bundle: {exc}") from exc
    if bundle.event_count != len(bundle.events):
        raise InteropError("bundle event_count does not match events")
    _validate_events(bundle.events, bundle.findings.copy())
    bundle.verify_digest()
    return bundle


def write_bundle(path: Path, bundle: EvidenceBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(canonical_json(bundle.model_dump(mode="json")))
    temporary.replace(path)


def bundle_result(bundle: EvidenceBundle, verified: bool = True) -> dict[str, Any]:
    by_severity = {
        level: sum(item.severity == level for item in bundle.findings)
        for level in ("info", "warning", "error")
    }
    return {
        "verified": verified,
        "format": bundle.format,
        "format_version": bundle.format_version,
        "adapter": bundle.source.adapter,
        "event_count": bundle.event_count,
        "finding_count": len(bundle.findings),
        "findings_by_severity": by_severity,
        "bundle_sha256": bundle.bundle_sha256,
    }


def sarif_report(bundle: EvidenceBundle) -> dict[str, Any]:
    results = [
        {
            "ruleId": finding.rule_id,
            "level": "error"
            if finding.severity == "error"
            else "warning"
            if finding.severity == "warning"
            else "note",
            "message": {"text": finding.message},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": finding.path}}}],
        }
        for finding in bundle.findings
    ]
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {"driver": {"name": "FaultPack Interop", "version": "0.1.0"}},
                "results": results,
            }
        ],
    }


def junit_report(bundle: EvidenceBundle) -> str:
    suite = Element(
        "testsuite",
        name="faultpack-interop",
        tests="1",
        failures="1" if bundle.has_errors else "0",
        errors="1" if bundle.has_errors else "0",
    )
    case = SubElement(suite, "testcase", name="evidence-conformance")
    if bundle.has_errors:
        messages = "; ".join(item.message for item in bundle.findings if item.severity == "error")
        SubElement(case, "failure", message=messages or "evidence bundle is invalid")
    return tostring(suite, encoding="unicode")


def markdown_report(bundle: EvidenceBundle) -> str:
    lines = [
        "# FaultPack interoperability report",
        "",
        f"- Adapter: `{bundle.source.adapter}`",
        f"- Events: `{bundle.event_count}`",
        f"- Bundle SHA-256: `{bundle.bundle_sha256}`",
        "",
        "> This report is passive. Imported commands, URLs, payloads, and tool arguments "
        "are never executed or uploaded.",
        "",
        "## Findings",
        "",
    ]
    if bundle.findings:
        lines.extend(
            f"- **{item.severity}** `{item.rule_id}` — {item.message} ({item.path})"
            for item in bundle.findings
        )
    else:
        lines.append("No conformance findings.")
    lines.extend(
        [
            "",
            "## Event summary",
            "",
            "| # | Kind | Name | Status | Payload |",
            "|---:|---|---|---|---|",
        ]
    )
    lines.extend(
        (
            f"| {event.sequence} | `{event.kind}` | `{event.name}` | "
            f"`{event.status}` | `{event.payload_sha256 or 'digest omitted'}` |"
        )
        for event in bundle.events
    )
    return "\n".join(lines) + "\n"


def write_reports(directory: Path, bundle: EvidenceBundle) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "faultpack-interop.md").write_text(markdown_report(bundle), encoding="utf-8")
    (directory / "faultpack-interop.junit.xml").write_text(junit_report(bundle), encoding="utf-8")
    (directory / "faultpack-interop.sarif").write_bytes(canonical_json(sarif_report(bundle)))


def diff_bundles(left: EvidenceBundle, right: EvidenceBundle) -> dict[str, Any]:
    left_events = [event.model_dump(mode="json", exclude={"sequence"}) for event in left.events]
    right_events = [event.model_dump(mode="json", exclude={"sequence"}) for event in right.events]
    common = min(len(left_events), len(right_events))
    changes = []
    for index in range(common):
        if left_events[index] != right_events[index]:
            changes.append(
                {"sequence": index + 1, "left": left_events[index], "right": right_events[index]}
            )
    return {
        "identical": not changes and len(left_events) == len(right_events),
        "left_bundle_sha256": left.bundle_sha256,
        "right_bundle_sha256": right.bundle_sha256,
        "left_event_count": len(left_events),
        "right_event_count": len(right_events),
        "changed_events": changes,
        "trailing_left": left_events[common:],
        "trailing_right": right_events[common:],
    }
