"""Deterministic comparison helpers for replay observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import sha256_bytes
from .models import Manifest
from .replay import compare


@dataclass(frozen=True)
class ReplayObservation:
    status: str
    exit_code: int | None
    duration_ms: int
    stdout: str
    stderr: str
    reasons: tuple[str, ...]

    @property
    def stdout_sha256(self) -> str:
        return sha256_bytes(self.stdout.encode())

    @property
    def stderr_sha256(self) -> str:
        return sha256_bytes(self.stderr.encode())

    @property
    def reproduced(self) -> bool:
        return not self.reasons


def observe(manifest: Manifest, result: tuple[str, int | None, int, str, str]) -> ReplayObservation:
    status, exit_code, duration_ms, stdout, stderr = result
    return ReplayObservation(
        status=status,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
        reasons=tuple(compare(manifest, status, exit_code, duration_ms, stdout, stderr)),
    )


def diff_observations(left: ReplayObservation, right: ReplayObservation) -> dict[str, Any]:
    """Return a stable JSON-compatible diff; duration is informative, not behavioral."""
    changes: list[dict[str, Any]] = []
    fields = (
        ("status", left.status, right.status),
        ("exit_code", left.exit_code, right.exit_code),
        ("stdout_sha256", left.stdout_sha256, right.stdout_sha256),
        ("stderr_sha256", left.stderr_sha256, right.stderr_sha256),
        ("reproduced", left.reproduced, right.reproduced),
    )
    for field, old, new in fields:
        if old != new:
            changes.append({"field": field, "left": old, "right": new})
    return {
        "identical_behavior": not changes,
        "changes": changes,
        "left": {
            "status": left.status,
            "exit_code": left.exit_code,
            "duration_ms": left.duration_ms,
            "stdout_sha256": left.stdout_sha256,
            "stderr_sha256": left.stderr_sha256,
            "reproduced": left.reproduced,
            "reasons": list(left.reasons),
        },
        "right": {
            "status": right.status,
            "exit_code": right.exit_code,
            "duration_ms": right.duration_ms,
            "stdout_sha256": right.stdout_sha256,
            "stderr_sha256": right.stderr_sha256,
            "reproduced": right.reproduced,
            "reasons": list(right.reasons),
        },
        "timing_delta_ms": right.duration_ms - left.duration_ms,
        "timing_is_diagnostic_only": True,
    }
