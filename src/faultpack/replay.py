from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from .core import safe_pack_path
from .models import Manifest


def replay(pack_dir: Path, manifest: Manifest) -> tuple[str, int | None, int, str, str]:
    cwd = (
        safe_pack_path(pack_dir, manifest.command.cwd)
        if manifest.command.cwd != "."
        else pack_dir.resolve()
    )
    start = time.monotonic()
    try:
        proc = subprocess.run(
            manifest.command.argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=manifest.command.timeout_seconds,
        )
        return (
            "passed",
            proc.returncode,
            int((time.monotonic() - start) * 1000),
            proc.stdout,
            proc.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            "timeout",
            None,
            int((time.monotonic() - start) * 1000),
            str(exc.stdout or ""),
            str(exc.stderr or ""),
        )


def compare(
    manifest: Manifest, status: str, exit_code: int | None, stdout: str, stderr: str
) -> list[str]:
    reasons: list[str] = []
    expected = manifest.expectation
    if expected.exit_code != exit_code:
        reasons.append(f"exit code: expected {expected.exit_code}, got {exit_code}")
    if expected.stdout_regex and not re.search(expected.stdout_regex, stdout, re.MULTILINE):
        reasons.append("stdout regex did not match")
    if expected.stderr_regex and not re.search(expected.stderr_regex, stderr, re.MULTILINE):
        reasons.append("stderr regex did not match")
    if status == "timeout":
        reasons.append("command timed out")
    return reasons
