"""Passive privacy diagnostics for shareable FaultPack capsules."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .core import FaultPackError, load_manifest, safe_pack_path, verify_manifest


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    line: int
    message: str

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "private-key",
        "error",
        "Private key material detected",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    (
        "github-token",
        "error",
        "GitHub token-like value detected",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "aws-access-key",
        "error",
        "AWS access key-like value detected",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "bearer-token",
        "error",
        "Bearer token detected",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "secret-assignment",
        "warning",
        "Secret-like assignment detected",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^\s'\"]{12,}"),
    ),
    (
        "email-address",
        "info",
        "Email address detected; review whether it is safe to share",
        re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    ),
)


def diagnose_pack(pack_dir: Path, *, max_bytes: int = 2_000_000) -> list[Finding]:
    """Inspect a verified pack's textual evidence without executing its command."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    try:
        manifest = load_manifest(pack_dir / "faultpack.json")
        verify_manifest(manifest)
    except (FaultPackError, OSError) as exc:
        raise FaultPackError(f"cannot diagnose invalid pack: {exc}") from exc

    paths = [manifest.observed.stdout_path, manifest.observed.stderr_path]
    paths.extend(f"artifacts/inputs/{entry.path}" for entry in manifest.input_files)
    findings: list[Finding] = []
    for relative in paths:
        path = safe_pack_path(pack_dir, relative)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise FaultPackError(f"cannot read diagnostic target: {relative}") from exc
        if len(data) > max_bytes:
            findings.append(
                Finding(
                    "size-limit",
                    "warning",
                    relative,
                    0,
                    f"Evidence exceeds {max_bytes} bytes; skipped",
                )
            )
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, severity, message, pattern in _PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(code, severity, relative, line_number, message))
    return findings
