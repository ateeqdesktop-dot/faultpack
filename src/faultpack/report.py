from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring


def markdown_report(
    pack_id: str,
    reproduced: bool,
    reasons: list[str],
    status: str,
    exit_code: int | None,
    duration_ms: int,
) -> str:
    result = "REPRODUCED" if reproduced else "NOT REPRODUCED"
    lines = [
        f"# FaultPack report: {result}",
        "",
        f"- Pack: `{pack_id}`",
        f"- Replay status: `{status}`",
        f"- Exit code: `{exit_code}`",
        f"- Duration: `{duration_ms} ms`",
        "",
        "> Replay is bounded but is not a sandbox; use an isolated runner for untrusted packs.",
        "",
    ]
    if reasons:
        lines += ["## Differences", ""] + [f"- {reason}" for reason in reasons]
    else:
        lines += ["Replay matched the declared expectation."]
    return "\n".join(lines) + "\n"


def sarif_report(
    reproduced: bool, reasons: list[str], uri: str = "faultpack.json"
) -> dict[str, object]:
    results = (
        []
        if reproduced
        else [
            {
                "ruleId": "faultpack.reproduction",
                "level": "error",
                "message": {"text": "; ".join(reasons) or "reproduction failed"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri}}}],
            }
        ]
    )
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {"tool": {"driver": {"name": "FaultPack", "version": "1.1.0"}}, "results": results}
        ],
    }


def junit_report(reproduced: bool, reasons: list[str], duration_ms: int) -> str:
    suite = Element(
        "testsuite",
        name="faultpack",
        tests="1",
        failures="0" if reproduced else "1",
        time=f"{duration_ms / 1000:.3f}",
    )
    case = SubElement(suite, "testcase", name="reproduction", time=f"{duration_ms / 1000:.3f}")
    if not reproduced:
        SubElement(case, "failure", message="; ".join(reasons) or "reproduction failed")
    return tostring(suite, encoding="unicode")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
