from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.core import canonical_json, manifest_fingerprint
from faultpack.events import build_event, digest_payload, event_summary, validate_events
from faultpack.evidence_diff import evidence_diff
from faultpack.models import EvidenceEvent, Manifest, Producer

runner = CliRunner()


def test_digest_payload_is_stable_and_utf8() -> None:
    assert digest_payload("سلام") == digest_payload("سلام".encode())
    assert len(digest_payload("payload")) == 64


def test_build_event_is_digest_only() -> None:
    event = build_event(1, "tool_call", "search", "secret payload", {"provider": "local"})
    assert event.payload_sha256 == digest_payload("secret payload")
    assert "secret payload" not in event.model_dump_json()
    assert event.attributes == {"provider": "local"}


def test_validate_events_rejects_duplicate_or_out_of_order() -> None:
    valid = [build_event(1, "assertion", "check"), build_event(2, "annotation", "note")]
    assert validate_events(valid) == valid
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_events([valid[1], valid[0]])
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_events([valid[0], valid[0]])


def test_event_summary_is_sorted_and_payload_free() -> None:
    events = [
        build_event(1, "tool_call", "search"),
        build_event(2, "tool_call", "fetch"),
        build_event(3, "assertion", "oracle"),
    ]
    assert event_summary(events) == {
        "count": 3,
        "first_sequence": 1,
        "last_sequence": 3,
        "kinds": {"assertion": 1, "tool_call": 2},
        "names": ["search", "fetch", "oracle"],
        "payloads_digest_only": True,
    }


def _manifest(events: list[EvidenceEvent], producer: Producer | None = None) -> Manifest:
    raw = json.loads(
        Path("fixtures/failure-pack/faultpack.json").read_text(encoding="utf-8")
    )
    raw["format_version"] = "0.3"
    raw["producer"] = producer.model_dump(mode="json") if producer else None
    raw["events"] = [event.model_dump(mode="json") for event in events]
    raw["fingerprint"] = None
    model = Manifest.model_validate(raw)
    return model.model_copy(update={"fingerprint": manifest_fingerprint(model)})


def test_legacy_fingerprint_ignores_new_optional_fields() -> None:
    raw = json.loads(Path("fixtures/failure-pack/faultpack.json").read_text(encoding="utf-8"))
    legacy = Manifest.model_validate(raw)
    enriched = legacy.model_copy(
        update={
            "producer": Producer(name="legacy-adapter"),
            "events": [build_event(1, "annotation", "compatibility")],
        }
    )
    assert manifest_fingerprint(legacy) == manifest_fingerprint(enriched)


def test_evidence_diff_detects_producer_and_event_changes() -> None:
    left = _manifest([build_event(1, "assertion", "oracle")], Producer(name="pytest", version="8"))
    right = _manifest(
        [build_event(1, "assertion", "oracle"), build_event(2, "tool_call", "search")],
        Producer(name="pytest", version="9"),
    )
    result = evidence_diff(left, right)
    assert result["identical_evidence"] is False
    assert {item["field"] for item in result["changes"]} == {"producer", "events"}
    assert result["volatile_fields_ignored"] == ["pack_id", "created_at", "observed.duration_ms"]


def test_evidence_diff_cli_verifies_without_execution(tmp_path: Path) -> None:
    left = _manifest([])
    right = _manifest([])
    left_dir = tmp_path / "left"
    right_dir = tmp_path / "right"
    for directory, model in ((left_dir, left), (right_dir, right)):
        (directory / "artifacts").mkdir(parents=True)
        source = Path("fixtures/failure-pack")
        for name in ("stdout.txt", "stderr.txt"):
            (directory / "artifacts" / name).write_bytes((source / "artifacts" / name).read_bytes())
        input_dir = directory / "artifacts" / "inputs" / "fixtures"
        input_dir.mkdir(parents=True)
        for name in ("repro_case.py", "repro_input.txt"):
            source_file = source / "artifacts" / "inputs" / "fixtures" / name
            (input_dir / name).write_bytes(source_file.read_bytes())
        (directory / "faultpack.json").write_bytes(canonical_json(model.model_dump(mode="json")))
    result = runner.invoke(app, ["evidence-diff", str(left_dir), str(right_dir)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["identical_evidence"] is True
