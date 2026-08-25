import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import Manifest


class FaultPackError(Exception):
    """Base class for expected FaultPack failures."""


class PackIntegrityError(FaultPackError):
    """Raised when a manifest, artifact, or signature is invalid."""


class PolicyError(FaultPackError):
    """Raised when a path or execution policy is unsafe."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def manifest_fingerprint(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"fingerprint", "created_at"})
    if manifest.format_version == "0.2":
        payload.pop("pack_id", None)
        payload.get("observed", {}).pop("duration_ms", None)
    return sha256_bytes(canonical_json(payload))


def load_manifest(path: Path) -> Manifest:
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise FaultPackError(f"invalid manifest: {exc}") from exc


def verify_manifest(manifest: Manifest) -> None:
    expected = manifest_fingerprint(manifest)
    if manifest.fingerprint != expected:
        raise PackIntegrityError(f"manifest fingerprint mismatch: expected {expected}")


def safe_pack_path(root: Path, relative: str) -> Path:
    if "\\" in relative:
        raise PolicyError(f"unsafe path: {relative}")
    raw = root / relative
    if raw.is_symlink():
        raise PolicyError(f"symlink is not allowed: {relative}")
    candidate = raw.resolve()
    root_resolved = root.resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise PolicyError(f"unsafe path: {relative}")
    return candidate


def signature_for(fingerprint: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), fingerprint.encode("ascii"), hashlib.sha256).hexdigest()


def verify_signature(pack_dir: Path, fingerprint: str, key: str, required: bool = False) -> bool:
    signature_path = pack_dir / "signature.hmac"
    if not signature_path.exists():
        if required:
            raise PackIntegrityError("signature required but signature.hmac is missing")
        return False
    try:
        actual = signature_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise PackIntegrityError("invalid signature file") from exc
    expected = signature_for(fingerprint, key)
    if not hmac.compare_digest(actual, expected):
        raise PackIntegrityError("signature mismatch")
    return True


def verify_pack(
    pack_dir: Path,
    signing_key: str | None = None,
    require_signature: bool = False,
    public_key: Path | None = None,
) -> Manifest:
    manifest = load_manifest(pack_dir / "faultpack.json")
    verify_manifest(manifest)
    for relative, expected in [
        (manifest.observed.stdout_path, manifest.observed.stdout_sha256),
        (manifest.observed.stderr_path, manifest.observed.stderr_sha256),
    ]:
        actual = sha256_file(safe_pack_path(pack_dir, relative))
        if actual != expected:
            raise PackIntegrityError(f"artifact fingerprint mismatch: {relative}")
    for entry in manifest.input_files:
        actual = sha256_file(safe_pack_path(pack_dir, f"artifacts/inputs/{entry.path}"))
        if actual != entry.sha256:
            raise PackIntegrityError(f"input fingerprint mismatch: {entry.path}")
    key = signing_key or os.getenv("FAULTPACK_SIGNING_KEY")
    if public_key is not None:
        signature_path = pack_dir / "signature.ed25519"
        if not signature_path.exists():
            raise PackIntegrityError("Ed25519 signature required but signature.ed25519 is missing")
        try:
            from .signing import verify_fingerprint_signature

            verify_fingerprint_signature(
                manifest.fingerprint or "", signature_path.read_text(encoding="ascii"), public_key
            )
        except FaultPackError as exc:
            raise PackIntegrityError(str(exc)) from exc
    elif key:
        verify_signature(pack_dir, manifest.fingerprint or "", key, require_signature)
    elif require_signature:
        raise PackIntegrityError(
            "signature required but provide --public-key or set FAULTPACK_SIGNING_KEY"
        )
    return manifest
