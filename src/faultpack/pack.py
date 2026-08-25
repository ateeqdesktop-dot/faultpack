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

from .core import (
    PolicyError,
    canonical_json,
    manifest_fingerprint,
    safe_pack_path,
    sha256_bytes,
    signature_for,
)
from .models import CommandSpec, Environment, Expectation, FileEntry, Manifest, Observed, Source
from .redact import redact_environment, redact_value

_DEFAULT_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


def execution_environment(
    allowlist: list[str],
    extra_patterns: list[str] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    names = list(dict.fromkeys([*_DEFAULT_ENV, *allowlist, *(overrides or {}).keys()]))
    values = {name: os.environ[name] for name in names if name in os.environ}
    values.update(overrides or {})
    return redact_environment(values, extra_patterns)


def _run(
    command: CommandSpec, root: Path, extra_patterns: list[str] | None = None
) -> tuple[Observed, bytes, bytes]:
    status: Literal["passed", "failed", "timeout", "error"]
    cwd = safe_pack_path(root, command.cwd) if command.cwd != "." else root.resolve()
    env = execution_environment(command.env_allowlist, extra_patterns)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command.argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=command.timeout_seconds,
            check=False,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        code = proc.returncode
        stdout = redact_value(proc.stdout.decode(errors="replace"), extra_patterns).encode()
        stderr = redact_value(proc.stderr.decode(errors="replace"), extra_patterns).encode()
    except subprocess.TimeoutExpired as exc:
        status, code = "timeout", None
        stdout = redact_value((exc.stdout or b"").decode(errors="replace"), extra_patterns).encode()
        stderr = redact_value((exc.stderr or b"").decode(errors="replace"), extra_patterns).encode()
    except (OSError, ValueError) as exc:
        status, code = "error", None
        stdout = b""
        stderr = redact_value(str(exc), extra_patterns).encode()
    duration = int((time.monotonic() - start) * 1000)
    observed = Observed(
        status=status,
        exit_code=code,
        duration_ms=duration,
        stdout_sha256=sha256_bytes(stdout),
        stderr_sha256=sha256_bytes(stderr),
    )
    return observed, stdout, stderr


def _copy_input(root: Path, out: Path, relative: str) -> FileEntry:
    source = safe_pack_path(root, relative)
    if not source.is_file():
        raise OSError(f"input file does not exist: {relative}")
    destination = safe_pack_path(out / "artifacts" / "inputs", relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return FileEntry(path=relative, sha256=sha256_bytes(destination.read_bytes()))


def capture_pack(
    root: Path,
    argv: list[str],
    out: Path,
    cwd: str = ".",
    timeout: float = 30.0,
    source: Source | None = None,
    extra_patterns: list[str] | None = None,
    input_files: list[str] | None = None,
    env_allowlist: list[str] | None = None,
    ed25519_private_key: Path | None = None,
) -> Manifest:
    root = root.resolve()
    output_root = out.resolve()
    if output_root == root or output_root in root.parents:
        raise PolicyError("output pack must not contain the capture root")
    if out.exists():
        shutil.rmtree(out)
    (out / "artifacts").mkdir(parents=True)
    command = CommandSpec(
        argv=argv,
        cwd=cwd,
        timeout_seconds=timeout,
        env_allowlist=env_allowlist or [],
    )
    try:
        entries = [_copy_input(root, out, relative) for relative in sorted(input_files or [])]
    except OSError:
        shutil.rmtree(out, ignore_errors=True)
        raise
    observed, stdout, stderr = _run(command, root, extra_patterns)
    selected_env = redact_environment(
        {name: os.environ[name] for name in command.env_allowlist if name in os.environ},
        extra_patterns,
    )
    manifest = Manifest(
        pack_id=str(uuid.uuid4()),
        source=source or Source(),
        command=command,
        environment=Environment(
            os=platform.system(),
            platform=platform.platform(),
            python=sys.version.split()[0],
            variables=selected_env,
        ),
        input_files=entries,
        observed=observed,
        expectation=Expectation(exit_code=observed.exit_code),
    )
    manifest = manifest.model_copy(update={"fingerprint": manifest_fingerprint(manifest)})
    (out / "artifacts" / "stdout.txt").write_bytes(stdout)
    (out / "artifacts" / "stderr.txt").write_bytes(stderr)
    (out / "faultpack.json").write_bytes(canonical_json(manifest.model_dump(mode="json")))
    signing_key = os.getenv("FAULTPACK_SIGNING_KEY")
    if signing_key:
        (out / "signature.hmac").write_text(
            signature_for(manifest.fingerprint or "", signing_key) + "\n", encoding="ascii"
        )
    if ed25519_private_key is not None:
        from .signing import sign_fingerprint

        (out / "signature.ed25519").write_text(
            sign_fingerprint(manifest.fingerprint or "", ed25519_private_key) + "\n",
            encoding="ascii",
        )
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
    from .core import load_manifest

    return load_manifest(pack_dir / "faultpack.json")
