from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import Manifest


class FaultPackError(Exception):
    """Base class for expected FaultPack failures."""


class PackIntegrityError(FaultPackError):
    """Raised when a manifest or artifact fingerprint is invalid."""


class PolicyError(FaultPackError):
    """Raised when a path or execution policy is unsafe."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def manifest_fingerprint(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json", exclude={"fingerprint", "created_at"})
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
    raw = root / relative
    if raw.is_symlink():
        raise PolicyError(f"symlink is not allowed: {relative}")
    candidate = raw.resolve()
    root_resolved = root.resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise PolicyError(f"unsafe path: {relative}")
    return candidate
