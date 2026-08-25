"""Optional Ed25519 signing for portable FaultPack fingerprints."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .core import FaultPackError


class SigningUnavailable(FaultPackError):
    """Raised when the optional cryptography dependency is not installed."""


def _crypto() -> tuple[Any, Any, Any, Any]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:  # pragma: no cover - depends on installation extras
        raise SigningUnavailable(
            "Ed25519 support requires the optional dependency: pip install 'faultpack[signing]'"
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey, serialization, InvalidSignature


def generate_keypair(private_path: Path, public_path: Path) -> None:
    """Generate PEM-encoded Ed25519 keys without overwriting existing files."""
    Ed25519PrivateKey, _, serialization, _ = _crypto()
    if private_path.exists() or public_path.exists():
        raise FaultPackError("refusing to overwrite an existing signing key")
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    private_path.chmod(0o600)


def sign_fingerprint(fingerprint: str, private_path: Path) -> str:
    """Sign the ASCII fingerprint and return a strict base64 signature."""
    Ed25519PrivateKey, _, serialization, _ = _crypto()
    try:
        key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("key is not Ed25519")
        signature = key.sign(fingerprint.encode("ascii"))
    except (OSError, ValueError, TypeError) as exc:
        raise FaultPackError(f"invalid Ed25519 private key: {exc}") from exc
    return base64.b64encode(signature).decode("ascii")


def verify_fingerprint_signature(fingerprint: str, signature_text: str, public_path: Path) -> bool:
    """Verify a base64 Ed25519 signature over the ASCII fingerprint."""
    _, Ed25519PublicKey, serialization, InvalidSignature = _crypto()
    try:
        signature = base64.b64decode(signature_text.strip(), validate=True)
        key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("key is not Ed25519")
        key.verify(signature, fingerprint.encode("ascii"))
    except (OSError, ValueError, TypeError, InvalidSignature) as exc:
        raise FaultPackError(f"Ed25519 signature verification failed: {exc}") from exc
    return True
