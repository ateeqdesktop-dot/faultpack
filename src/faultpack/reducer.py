from __future__ import annotations

import shutil
from pathlib import Path

from .core import FaultPackError, canonical_json, safe_pack_path, verify_pack
from .models import Manifest
from .replay import compare, replay


class ReductionLimitReached(FaultPackError):
    """Raised when reduction reaches its execution budget."""


def _is_failure(pack_dir: Path, manifest: Manifest) -> bool:
    status, code, duration, stdout, stderr = replay(pack_dir, manifest)
    reasons = compare(manifest, status, code, duration, stdout, stderr)
    if manifest.observed.status == "timeout" and status == "timeout":
        reasons = [reason for reason in reasons if not reason.startswith("command status")]
    return (
        not reasons and status == manifest.observed.status and manifest.observed.status != "passed"
    )


def reduce_text_input(
    pack_dir: Path,
    input_path: str,
    out_dir: Path,
    max_runs: int = 100,
) -> tuple[Manifest, int]:
    if max_runs < 1:
        raise FaultPackError("max_runs must be positive")
    source_manifest = verify_pack(pack_dir)
    entry = next((item for item in source_manifest.input_files if item.path == input_path), None)
    if entry is None:
        raise FaultPackError(f"input is not declared in pack: {input_path}")
    source = safe_pack_path(pack_dir, f"artifacts/inputs/{input_path}")
    try:
        original = source.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        raise FaultPackError("reducer only supports UTF-8 text inputs") from exc
    if not original:
        raise FaultPackError("input is empty")
    if not _is_failure(pack_dir, source_manifest):
        raise FaultPackError("reduction requires a pack whose oracle currently fails")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(pack_dir, out_dir)
    candidate_path = safe_pack_path(out_dir, f"artifacts/inputs/{input_path}")
    manifest = source_manifest
    runs = 1
    lines = original[:]
    granularity = 2
    while len(lines) >= 2 and runs < max_runs:
        chunk_size = max(1, (len(lines) + granularity - 1) // granularity)
        changed = False
        start = 0
        while start < len(lines) and runs < max_runs:
            candidate = lines[:start] + lines[start + chunk_size :]
            if not candidate:
                start += chunk_size
                continue
            candidate_path.write_text("".join(candidate), encoding="utf-8")
            runs += 1
            candidate_manifest = manifest
            if _is_failure(out_dir, candidate_manifest):
                lines = candidate
                manifest = candidate_manifest
                changed = True
                break
            candidate_path.write_text("".join(lines), encoding="utf-8")
            start += chunk_size
        if runs >= max_runs:
            raise ReductionLimitReached(f"reduction reached max_runs={max_runs}")
        if changed:
            granularity = max(2, granularity - 1)
        elif granularity < len(lines):
            granularity = min(len(lines), granularity * 2)
        else:
            break
    candidate_path.write_text("".join(lines), encoding="utf-8")
    # Recompute the input hash and manifest fingerprint after the final accepted bytes.
    from .core import manifest_fingerprint, sha256_file

    updated_entries = [
        item.model_copy(update={"sha256": sha256_file(candidate_path)})
        if item.path == input_path
        else item
        for item in manifest.input_files
    ]
    manifest = manifest.model_copy(
        update={
            "input_files": updated_entries,
            "fingerprint": None,
        }
    )
    manifest = manifest.model_copy(update={"fingerprint": manifest_fingerprint(manifest)})
    (out_dir / "faultpack.json").write_bytes(canonical_json(manifest.model_dump(mode="json")))
    verify_pack(out_dir)
    return manifest, runs
