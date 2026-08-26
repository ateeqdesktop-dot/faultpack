"""Semantic, deterministic diffing for FaultPack evidence manifests."""
from __future__ import annotations

from typing import Any

from .events import event_summary
from .models import Manifest


def _producer_payload(manifest: Manifest) -> dict[str, Any] | None:
    return manifest.producer.model_dump(mode="json") if manifest.producer else None


def evidence_diff(left: Manifest, right: Manifest) -> dict[str, Any]:
    """Compare stable evidence fields while excluding volatile creation metadata."""
    changes: list[dict[str, Any]] = []
    fields = (
        ("format_version", left.format_version, right.format_version),
        ("source", left.source.model_dump(mode="json"), right.source.model_dump(mode="json")),
        ("producer", _producer_payload(left), _producer_payload(right)),
        ("command", left.command.model_dump(mode="json"), right.command.model_dump(mode="json")),
        (
            "environment",
            left.environment.model_dump(mode="json"),
            right.environment.model_dump(mode="json"),
        ),
        (
            "input_files",
            [item.model_dump(mode="json") for item in left.input_files],
            [item.model_dump(mode="json") for item in right.input_files],
        ),
        (
            "expectation",
            left.expectation.model_dump(mode="json"),
            right.expectation.model_dump(mode="json"),
        ),
        ("events", event_summary(left.events), event_summary(right.events)),
    )
    for field, old, new in fields:
        if old != new:
            changes.append({"field": field, "left": old, "right": new})
    return {
        "identical_evidence": not changes,
        "changes": changes,
        "left_fingerprint": left.fingerprint,
        "right_fingerprint": right.fingerprint,
        "volatile_fields_ignored": ["pack_id", "created_at", "observed.duration_ms"],
    }
