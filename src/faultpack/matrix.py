from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Literal, cast

from .core import FaultPackError
from .models import Manifest, MatrixProfile, MatrixResult
from .replay import compare, replay


class MatrixPolicyError(FaultPackError):
    """Raised when a replay profile violates the pack execution policy."""


def validate_profiles(manifest: Manifest, profiles: list[MatrixProfile]) -> list[MatrixProfile]:
    if not profiles:
        raise MatrixPolicyError("matrix requires at least one profile")
    names: set[str] = set()
    validated: list[MatrixProfile] = []
    for profile in profiles:
        if profile.name in names:
            raise MatrixPolicyError(f"duplicate matrix profile: {profile.name}")
        names.add(profile.name)
        timeout_expands = (
            profile.timeout_seconds is not None
            and profile.timeout_seconds > manifest.command.timeout_seconds
        )
        if timeout_expands:
            raise MatrixPolicyError(
                f"profile {profile.name} timeout cannot exceed pack timeout "
                f"({manifest.command.timeout_seconds}s)"
            )
        validated.append(profile)
    return validated


def run_matrix(pack_dir: Path, manifest: Manifest, profiles: list[MatrixProfile]) -> dict[str, Any]:
    validated = validate_profiles(manifest, profiles)
    results: list[MatrixResult] = []
    for profile in validated:
        outcome: Literal["reproduced", "mismatch", "execution_error"]
        try:
            status, exit_code, duration_ms, stdout, stderr = replay(
                pack_dir,
                manifest,
                argv=profile.argv,
                timeout_seconds=profile.timeout_seconds,
                env_overrides=profile.env,
            )
            reasons = compare(manifest, status, exit_code, duration_ms, stdout, stderr)
            typed_status = cast(Literal["passed", "failed", "timeout", "error"], status)
            outcome = (
                "execution_error"
                if status == "error"
                else ("reproduced" if not reasons else "mismatch")
            )
        except (OSError, ValueError) as exc:
            status, exit_code, duration_ms, reasons = "error", None, 0, [str(exc)]
            outcome = "execution_error"
        results.append(
            MatrixResult(
                profile=profile.name,
                outcome=outcome,
                status=typed_status if outcome != "execution_error" else "error",
                exit_code=exit_code,
                duration_ms=duration_ms,
                reasons=reasons,
            )
        )
    payload = {
        "format_version": "1",
        "tool": "faultpack",
        "fingerprint": manifest.fingerprint,
        "all_reproduced": all(item.outcome == "reproduced" for item in results),
        "counts": {
            "profiles": len(results),
            "reproduced": sum(item.outcome == "reproduced" for item in results),
            "mismatch": sum(item.outcome == "mismatch" for item in results),
            "execution_error": sum(item.outcome == "execution_error" for item in results),
        },
        "results": [item.model_dump(mode="json") for item in results],
    }
    return payload


def markdown_matrix_report(payload: dict[str, Any]) -> str:
    lines = [
        "# FaultPack replay matrix",
        "",
        f"- Fingerprint: `{payload['fingerprint']}`",
        f"- All profiles reproduced: **{payload['all_reproduced']}**",
        "",
        "| Profile | Outcome | Status | Exit code | Duration (ms) | Reasons |",
        "|---|---|---|---:|---:|---|",
    ]
    for result in payload["results"]:
        reasons = "; ".join(result["reasons"]) or "—"
        lines.append(
            f"| `{result['profile']}` | {result['outcome']} | {result['status']} | "
            f"{result['exit_code'] if result['exit_code'] is not None else '—'} | "
            f"{result['duration_ms']} | {reasons} |"
        )
    lines.extend(
        ["", "This report records behavior; timing is diagnostic only and is not causal proof.", ""]
    )
    return "\n".join(lines)


def matrix_sarif(payload: dict[str, Any]) -> dict[str, Any]:
    results = []
    for item in payload["results"]:
        if item["outcome"] != "reproduced":
            results.append(
                {
                    "ruleId": "faultpack.matrix.reproduction",
                    "level": "error",
                    "message": {
                        "text": f"Profile {item['profile']}: " + "; ".join(item["reasons"])
                    },
                    "properties": {"profile": item["profile"], "status": item["status"]},
                }
            )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "FaultPack", "version": "1.1.0"}},
                "results": results,
            }
        ],
    }


def matrix_junit(payload: dict[str, Any]) -> str:
    failures = sum(item["outcome"] != "reproduced" for item in payload["results"])
    lines = [
        f'<testsuite name="faultpack-matrix" tests="{len(payload["results"])}" '
        f'failures="{failures}">'
    ]
    for item in payload["results"]:
        lines.append(
            f'  <testcase classname="faultpack" name="{escape(item["profile"])}" '
            f'time="{item["duration_ms"] / 1000:.3f}">'
        )
        if item["outcome"] != "reproduced":
            lines.append(f'    <failure message="{escape("; ".join(item["reasons"]))}" />')
        lines.append("  </testcase>")
    lines.extend(["</testsuite>", ""])
    return "\n".join(lines)


def write_matrix_reports(report_dir: Path, payload: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "faultpack-matrix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (report_dir / "faultpack-matrix.md").write_text(
        markdown_matrix_report(payload), encoding="utf-8"
    )
    (report_dir / "faultpack-matrix.sarif").write_text(
        json.dumps(matrix_sarif(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (report_dir / "faultpack-matrix.junit.xml").write_text(matrix_junit(payload), encoding="utf-8")
