from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from typing import Literal

from .core import canonical_json, manifest_fingerprint, safe_pack_path, sha256_bytes
from .models import CommandSpec, Environment, Expectation, Manifest, Observed, Source
from .redact import redact_environment, redact_value


def _run(
    command: CommandSpec, root: Path, extra_patterns: list[str] | None = None
) -> tuple[Observed, bytes, bytes]:
    status: Literal["passed", "failed", "timeout", "error"]
    cwd = safe_pack_path(root, command.cwd) if command.cwd != "." else root.resolve()
    env = {key: os.environ[key] for key in command.env_allowlist if key in os.environ}
    env = redact_environment(env, extra_patterns)
    # Redacted values are intentionally used for the child too; secrets never enter the pack.
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command.argv,
            cwd=cwd,
            env={**os.environ, **env},
            capture_output=True,
            timeout=command.timeout_seconds,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        status, code = "timeout", None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        duration = int((time.monotonic() - start) * 1000)
        return (
            Observed(
                status=status,
                exit_code=code,
                duration_ms=duration,
                stdout_sha256=sha256_bytes(
                    redact_value(stdout.decode(errors="replace"), extra_patterns).encode()
                ),
                stderr_sha256=sha256_bytes(
                    redact_value(stderr.decode(errors="replace"), extra_patterns).encode()
                ),
            ),
            redact_value(stdout.decode(errors="replace"), extra_patterns).encode(),
            redact_value(stderr.decode(errors="replace"), extra_patterns).encode(),
        )
    duration = int((time.monotonic() - start) * 1000)
    stdout = redact_value(proc.stdout.decode(errors="replace"), extra_patterns).encode()
    stderr = redact_value(proc.stderr.decode(errors="replace"), extra_patterns).encode()
    return (
        Observed(
            status=status,
            exit_code=code,
            duration_ms=duration,
            stdout_sha256=sha256_bytes(stdout),
            stderr_sha256=sha256_bytes(stderr),
        ),
        stdout,
        stderr,
    )


def capture_pack(
    root: Path,
    argv: list[str],
    out: Path,
    cwd: str = ".",
    timeout: float = 30.0,
    source: Source | None = None,
    extra_patterns: list[str] | None = None,
) -> Manifest:
    command = CommandSpec(argv=argv, cwd=cwd, timeout_seconds=timeout)
    observed, stdout, stderr = _run(command, root, extra_patterns)
    manifest = Manifest(
        pack_id=str(uuid.uuid4()),
        source=source or Source(),
        command=command,
        environment=Environment(
            os=platform.system(),
            platform=platform.platform(),
            python=sys.version.split()[0],
            variables=redact_environment({}),
        ),
        observed=observed,
        expectation=Expectation(exit_code=observed.exit_code),
    )
    manifest = manifest.model_copy(update={"fingerprint": manifest_fingerprint(manifest)})
    if out.exists():
        shutil.rmtree(out)
    (out / "artifacts").mkdir(parents=True)
    (out / "artifacts" / "stdout.txt").write_bytes(stdout)
    (out / "artifacts" / "stderr.txt").write_bytes(stderr)
    (out / "faultpack.json").write_bytes(canonical_json(manifest.model_dump(mode="json")))
    return manifest


def write_zip(pack_dir: Path, destination: Path) -> None:
    files = sorted(p for p in pack_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(
                path.relative_to(pack_dir).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def inspect_pack(pack_dir: Path) -> Manifest:
    manifest = Manifest.model_validate_json(
        (pack_dir / "faultpack.json").read_text(encoding="utf-8")
    )
    return manifest
