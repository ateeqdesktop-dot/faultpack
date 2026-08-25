import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .core import safe_pack_path
from .models import Manifest
from .pack import execution_environment


def replay(
    pack_dir: Path,
    manifest: Manifest,
    workspace: Path | None = None,
) -> tuple[str, int | None, int, str, str]:
    if workspace is None:
        owns_workspace = True
        run_root = Path(tempfile.mkdtemp(prefix="faultpack-replay-"))
    else:
        owns_workspace = False
        run_root = workspace
    try:
        for entry in manifest.input_files:
            source = safe_pack_path(pack_dir, f"artifacts/inputs/{entry.path}")
            destination = safe_pack_path(run_root, entry.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        cwd = (
            safe_pack_path(run_root, manifest.command.cwd)
            if manifest.command.cwd != "."
            else run_root
        )
        start = time.monotonic()
        try:
            proc = subprocess.run(
                manifest.command.argv,
                cwd=cwd,
                env=execution_environment(manifest.command.env_allowlist),
                capture_output=True,
                text=True,
                timeout=manifest.command.timeout_seconds,
                check=False,
            )
            status = "passed" if proc.returncode == 0 else "failed"
            return (
                status,
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
        except OSError as exc:
            return (
                "error",
                None,
                int((time.monotonic() - start) * 1000),
                "",
                str(exc),
            )
    finally:
        if owns_workspace:
            shutil.rmtree(run_root, ignore_errors=True)


def compare(
    manifest: Manifest,
    status: str,
    exit_code: int | None,
    duration_ms: int,
    stdout: str,
    stderr: str,
) -> list[str]:
    reasons: list[str] = []
    expected = manifest.expectation
    if expected.exit_code != exit_code:
        reasons.append(f"exit code: expected {expected.exit_code}, got {exit_code}")
    if expected.stdout_regex:
        try:
            matched = re.search(expected.stdout_regex, stdout, re.MULTILINE)
        except re.error as exc:
            reasons.append(f"invalid stdout regex: {exc}")
        else:
            if not matched:
                reasons.append("stdout regex did not match")
    if expected.stderr_regex:
        try:
            matched = re.search(expected.stderr_regex, stderr, re.MULTILINE)
        except re.error as exc:
            reasons.append(f"invalid stderr regex: {exc}")
        else:
            if not matched:
                reasons.append("stderr regex did not match")
    if expected.stdout_sha256:
        from .core import sha256_bytes

        if sha256_bytes(stdout.encode()) != expected.stdout_sha256:
            reasons.append("stdout hash did not match")
    if expected.stderr_sha256:
        from .core import sha256_bytes

        if sha256_bytes(stderr.encode()) != expected.stderr_sha256:
            reasons.append("stderr hash did not match")
    if expected.duration_max_ms is not None and duration_ms > expected.duration_max_ms:
        reasons.append(f"duration exceeded {expected.duration_max_ms}ms")
    if status in {"timeout", "error"}:
        reasons.append(f"command status was {status}")
    return reasons
