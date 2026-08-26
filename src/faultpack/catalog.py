from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import FaultPackError, verify_pack
from .diagnostics import diagnose_pack


def discover_packs(root: Path) -> list[Path]:
    """Return deterministic pack directories below root, including root itself."""
    candidates = []
    if (root / "faultpack.json").is_file():
        candidates.append(root)
    candidates.extend(path.parent for path in root.rglob("faultpack.json"))
    return sorted(set(candidates), key=lambda path: path.relative_to(root).as_posix())


def catalog_packs(root: Path, *, max_bytes: int = 2_000_000) -> dict[str, Any]:
    """Passively inventory packs without executing declared commands."""
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    for pack in discover_packs(root):
        relative = pack.relative_to(root).as_posix() or "."
        try:
            manifest = verify_pack(pack)
            findings = diagnose_pack(pack, max_bytes=max_bytes)
            entries.append(
                {
                    "path": relative,
                    "verified": True,
                    "fingerprint": manifest.fingerprint,
                    "status": manifest.observed.status,
                    "producer": manifest.producer.name if manifest.producer else None,
                    "finding_count": len(findings),
                    "privacy_clean": not findings,
                    "error": None,
                }
            )
        except (FaultPackError, OSError, ValueError) as exc:
            entries.append(
                {
                    "path": relative,
                    "verified": False,
                    "fingerprint": None,
                    "status": None,
                    "producer": None,
                    "finding_count": None,
                    "privacy_clean": False,
                    "error": str(exc),
                }
            )
    verified = sum(bool(item["verified"]) for item in entries)
    clean = sum(bool(item["verified"] and item["privacy_clean"]) for item in entries)
    return {
        "root": str(root),
        "pack_count": len(entries),
        "verified_count": verified,
        "invalid_count": len(entries) - verified,
        "privacy_clean_count": clean,
        "all_verified": len(entries) == verified,
        "all_privacy_clean": len(entries) == clean,
        "packs": entries,
    }


def catalog_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FaultPack catalog",
        "",
        "> Passive inventory: declared commands were never executed.",
        "",
        f"- **Packs:** {payload['pack_count']}",
        f"- **Verified:** {payload['verified_count']}",
        f"- **Invalid:** {payload['invalid_count']}",
        f"- **Privacy-clean:** {payload['privacy_clean_count']}",
        "",
        "| Path | Verified | Privacy-clean | Observed | Fingerprint | Error |",
        "|---|---:|---:|---|---|---|",
    ]
    for item in payload["packs"]:
        fingerprint = item["fingerprint"] or "—"
        error = (item["error"] or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{item['path']}` | {'yes' if item['verified'] else 'no'} | "
            f"{'yes' if item['privacy_clean'] else 'no'} | {item['status'] or '—'} | "
            f"`{fingerprint}` | {error or '—'} |"
        )
    return "\n".join(lines) + "\n"
