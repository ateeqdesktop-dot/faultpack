from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.interop import (
    InteropError,
    diff_bundles,
    load_bundle,
    normalize_bytes,
    write_bundle,
)

runner = CliRunner()


def test_generic_jsonl_is_deterministic_and_redacts_sensitive_attributes() -> None:
    data = (
        json.dumps(
            {
                "type": "tool_call",
                "name": "lookup",
                "trace_id": "trace-1",
                "span_id": "span-1",
                "status": "ok",
                "attributes": {"api_key": "secret", "email": "a@example.com", "count": 3},
                "payload": {"q": "hello"},
            }
        ).encode()
        + b"\n"
    )
    first = normalize_bytes(data, "generic-jsonl")
    second = normalize_bytes(data, "generic-jsonl")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.events[0].kind == "tool_call"
    assert first.events[0].status == "passed"
    assert first.events[0].attributes["api_key"] == "[REDACTED]"
    assert first.events[0].attributes["email"] == "[REDACTED_EMAIL]"
    assert first.events[0].payload_sha256
    assert len(first.bundle_sha256) == 64
    first.verify_digest()


def test_mcp_and_ci_classify_without_executing_commands() -> None:
    mcp = (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "name": "delete_record",
                "params": {"arguments": {"id": 1}},
                "id": "1",
            }
        ).encode()
        + b"\n"
    )
    bundle = normalize_bytes(mcp, "mcp-jsonl")
    assert bundle.events[0].kind == "tool_call"
    assert bundle.events[0].payload_sha256
    assert "id" not in bundle.events[0].attributes

    ci = (
        b'{"workflow":"tests","job":"unit","step":"pytest","type":"assertion",'
        b'"status":"failed","exit_code":1}\n'
    )
    ci_bundle = normalize_bytes(ci, "ci-jsonl")
    assert ci_bundle.events[0].kind == "assertion"
    assert ci_bundle.events[0].status == "failed"


def test_otlp_json_projects_openinference_attributes() -> None:
    document = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "demo-agent"}}]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abc123",
                                "spanId": "def456",
                                "name": "search",
                                "startTimeUnixNano": "1000000000",
                                "endTimeUnixNano": "1120000000",
                                "attributes": [
                                    {
                                        "key": "openinference.span.kind",
                                        "value": {"stringValue": "TOOL"},
                                    },
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": "model-x"},
                                    },
                                ],
                                "status": {"code": "STATUS_CODE_OK"},
                            }
                        ]
                    }
                ],
            }
        ]
    }
    bundle = normalize_bytes(json.dumps(document).encode(), "openinference-otlp-json")
    event = bundle.events[0]
    assert bundle.source.producer == "demo-agent"
    assert event.kind == "tool_call"
    assert event.duration_ms == 120
    assert event.trace_id == "abc123"
    assert event.attributes["gen_ai.request.model"] == "model-x"


def test_auto_detection_and_limits() -> None:
    assert normalize_bytes(b'{"kind":"model","name":"auto"}\n', "auto").events[0].name == "auto"
    with pytest.raises(InteropError, match="no events"):
        normalize_bytes(b"", "generic-jsonl")
    with pytest.raises(InteropError, match="invalid JSON"):
        normalize_bytes(b"{not-json}\n", "generic-jsonl")
    with pytest.raises(InteropError, match="unsupported format"):
        normalize_bytes(b"{}", "nope")


def test_bundle_round_trip_and_digest_tamper_detection(tmp_path: Path) -> None:
    bundle = normalize_bytes(b'{"kind":"model","name":"answer","status":"passed"}\n')
    path = tmp_path / "bundle.json"
    write_bundle(path, bundle)
    loaded = load_bundle(path)
    assert loaded.bundle_sha256 == bundle.bundle_sha256
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["events"][0]["name"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(InteropError, match="digest mismatch"):
        load_bundle(path)


def test_diff_reports_changed_and_trailing_events() -> None:
    left = normalize_bytes(b'{"kind":"model","name":"answer","status":"passed"}\n')
    right = normalize_bytes(
        b'{"kind":"model","name":"different","status":"passed"}\n{"kind":"tool_call","name":"search"}\n'
    )
    result = diff_bundles(left, right)
    assert not result["identical"]
    assert result["changed_events"][0]["sequence"] == 1
    assert result["trailing_right"][0]["name"] == "search"


def test_cli_normalize_verify_and_fail_on_findings(tmp_path: Path) -> None:
    source = tmp_path / "trace.jsonl"
    source.write_text('{"kind":"tool_call","name":"search"}\n', encoding="utf-8")
    output = tmp_path / "bundle.json"
    result = runner.invoke(
        app,
        [
            "interop",
            str(source),
            "--output",
            str(output),
            "--report-dir",
            str(tmp_path / "reports"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert output.exists()
    verified = runner.invoke(app, ["interop-verify", str(output)])
    assert verified.exit_code == 0, verified.stdout
    warned = runner.invoke(app, ["interop-verify", str(output), "--fail-on-findings"])
    assert warned.exit_code == 6


def test_cli_diff_exit_code(tmp_path: Path) -> None:
    left = normalize_bytes(b'{"kind":"model","name":"a"}\n')
    right = normalize_bytes(b'{"kind":"model","name":"b"}\n')
    left_path, right_path = tmp_path / "left.json", tmp_path / "right.json"
    write_bundle(left_path, left)
    write_bundle(right_path, right)
    result = runner.invoke(app, ["interop-diff", str(left_path), str(right_path)])
    assert result.exit_code == 5
    assert '"identical": false' in result.stdout


def test_edge_mapping_and_conformance_findings() -> None:
    data = (
        b'{"type":"tool_call","context":{"trace_id":"bad id","parent_id":"parent-1"},'
        b'"span_id":"same","duration_ms":"7","payload":"text"}\n'
        b'{"type":"unknown_kind","span_id":"same","duration_ns":3000000}\n'
    )
    bundle = normalize_bytes(data, "generic-jsonl")
    assert bundle.events[0].duration_ms == 7
    assert bundle.events[0].trace_id is None
    assert bundle.events[0].parent_id == "parent-1"
    assert bundle.events[0].payload_sha256
    assert any(item.rule_id == "interop.event.missing_name" for item in bundle.findings)
    assert any(item.rule_id == "interop.trace.duplicate_span_id" for item in bundle.findings)

    unknown_mcp = normalize_bytes(
        b'{"jsonrpc":"2.0","method":"notifications/updated"}\n', "mcp-jsonl"
    )
    assert any(item.rule_id == "interop.mcp.unknown_event" for item in unknown_mcp.findings)


def test_otlp_edge_values_and_malformed_shapes() -> None:
    document = {
        "resourceSpans": [
            {"resource": {"attributes": []}, "scopeSpans": ["ignored", {"spans": ["ignored"]}]},
            {"resource": {}, "scopeSpans": "not-a-list", "instrumentationLibrarySpans": []},
        ]
    }
    with pytest.raises(InteropError, match="no events"):
        normalize_bytes(json.dumps(document).encode(), "openinference-otlp-json")
    for payload in (b"not-json", b"[]", b"{}", b'{"resourceSpans": [1]}'):
        with pytest.raises(InteropError):
            normalize_bytes(payload, "openinference-otlp-json")

    valid = {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "name": "model",
                                "attributes": [
                                    {
                                        "key": "arr",
                                        "value": {"arrayValue": {"values": [{"stringValue": "x"}]}},
                                    },
                                    {
                                        "key": "map",
                                        "value": {
                                            "kvlistValue": {
                                                "values": [
                                                    {"key": "x", "value": {"boolValue": True}}
                                                ]
                                            }
                                        },
                                    },
                                ],
                            }
                        ]
                    }
                ],
            }
        ]
    }
    bundle = normalize_bytes(json.dumps(valid).encode(), "openinference-otlp-json")
    assert bundle.events[0].attributes["arr"] == '["x"]'
    assert '"x":true' in bundle.events[0].attributes["map"]


def test_input_limits_and_invalid_jsonl(tmp_path: Path) -> None:
    from faultpack.interop import MAX_INPUT_BYTES, MAX_LINE_BYTES, detect_format, normalize_file

    assert detect_format(b'{"method":"tools/call"}\n') == "mcp-jsonl"
    assert detect_format(b'{"workflow":"ci"}\n') == "ci-jsonl"
    assert detect_format(b"{}") == "generic-jsonl"
    with pytest.raises(InteropError, match="UTF-8"):
        normalize_bytes(b"\xff")
    with pytest.raises(InteropError, match="input exceeds"):
        normalize_bytes(b"x" * (MAX_INPUT_BYTES + 1))
    with pytest.raises(InteropError, match="line 1 exceeds"):
        normalize_bytes(b'{"name":"' + b"x" * MAX_LINE_BYTES + b'"}\n', "generic-jsonl")
    with pytest.raises(InteropError, match="JSON object"):
        normalize_bytes(b"[]\n", "generic-jsonl")
    with pytest.raises(InteropError, match="cannot read input"):
        normalize_file(tmp_path / "missing.jsonl")


def test_reports_cover_clean_and_error_findings(tmp_path: Path) -> None:
    from faultpack.interop import (
        InteropFinding,
        bundle_result,
        junit_report,
        markdown_report,
        sarif_report,
        write_reports,
    )

    clean = normalize_bytes(b'{"trace_id":"t","span_id":"s","kind":"model","name":"answer"}\n')
    assert bundle_result(clean)["finding_count"] == 0
    assert "No conformance findings" in markdown_report(clean)
    assert "<testsuite" in junit_report(clean)
    noisy = clean.model_copy(
        update={
            "findings": [
                InteropFinding(
                    rule_id="interop.test.error",
                    severity="error",
                    message="bad evidence",
                    path="events[0]",
                    remediation="fix it",
                ),
                InteropFinding(
                    rule_id="interop.test.info",
                    severity="info",
                    message="note",
                    path="events",
                    remediation="review it",
                ),
            ]
        }
    )
    assert noisy.has_errors
    assert "bad evidence" in junit_report(noisy)
    assert len(sarif_report(noisy)["runs"][0]["results"]) == 2
    write_reports(tmp_path / "reports", noisy)
    assert (tmp_path / "reports" / "faultpack-interop.sarif").exists()


def test_cli_error_paths_and_equal_diff(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "bundle.json"
    assert (
        runner.invoke(
            app, ["interop", str(bad), "--format", "unsupported", "--output", str(output)]
        ).exit_code
        == 4
    )
    assert runner.invoke(app, ["interop-verify", str(bad)]).exit_code == 4
    bundle = normalize_bytes(b'{"trace_id":"t","span_id":"s","kind":"model","name":"same"}\n')
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    write_bundle(left, bundle)
    write_bundle(right, bundle)
    equal = runner.invoke(app, ["interop-diff", str(left), str(right)])
    assert equal.exit_code == 0
