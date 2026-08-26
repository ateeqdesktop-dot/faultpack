"""Deterministic, digest-first event evidence for agent and tool runs."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .core import sha256_bytes
from .models import EvidenceEvent


def digest_payload(payload: str | bytes) -> str:
    """Return a stable SHA-256 digest without retaining the payload."""
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return sha256_bytes(raw)


def build_event(
    sequence: int,
    kind: str,
    name: str,
    payload: str | bytes | None = None,
    attributes: Mapping[str, str] | None = None,
) -> EvidenceEvent:
    """Create an event whose payload is represented by a digest only."""
    return EvidenceEvent(
        sequence=sequence,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        payload_sha256=digest_payload(payload) if payload is not None else None,
        attributes=dict(sorted((attributes or {}).items())),
    )


def validate_events(events: Iterable[EvidenceEvent]) -> list[EvidenceEvent]:
    """Validate and return events in declared order without mutating them."""
    result = list(events)
    sequences = [event.sequence for event in result]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise ValueError("events must have strictly increasing unique sequence values")
    return result


def event_summary(events: Iterable[EvidenceEvent]) -> dict[str, Any]:
    """Return a stable, payload-free summary suitable for reports and diffs."""
    ordered = validate_events(events)
    kinds: dict[str, int] = {}
    for event in ordered:
        kinds[event.kind] = kinds.get(event.kind, 0) + 1
    return {
        "count": len(ordered),
        "first_sequence": ordered[0].sequence if ordered else None,
        "last_sequence": ordered[-1].sequence if ordered else None,
        "kinds": dict(sorted(kinds.items())),
        "names": [event.name for event in ordered],
        "payloads_digest_only": True,
    }
