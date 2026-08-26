from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

# The self-contained viewer intentionally keeps its CSS/HTML inline for offline portability.
# ruff: noqa: E501


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


def html_report(manifest: object) -> str:
    """Render a self-contained, dependency-free report for a verified manifest."""
    from html import escape

    data = manifest.model_dump(mode="json")  # type: ignore[attr-defined]
    pack_id = escape(str(data.get("pack_id", "unknown")))
    fingerprint = escape(str(data.get("fingerprint") or "not recorded"))
    observed = data.get("observed", {})
    status = escape(str(observed.get("status", "unknown")))
    producer = data.get("producer") or {}
    producer_name = escape(str(producer.get("name") or "unspecified"))
    source = data.get("source") or {}
    source_value = escape(str(source.get("repository") or "local workspace"))
    command = data.get("command") or {}
    argv = command.get("argv") or []
    argv_html = " ".join(f"<code>{escape(str(token))}</code>" for token in argv)
    inputs = data.get("input_files") or []
    events = data.get("events") or []
    event_rows = "".join(
        "<tr>"
        f"<td>{escape(str(event.get('sequence', '')))}</td>"
        f"<td>{escape(str(event.get('kind', '')))}</td>"
        f"<td>{escape(str(event.get('name', '')))}</td>"
        f"<td><code>{escape(str(event.get('payload_sha256') or 'digest omitted'))}</code></td>"
        "</tr>"
        for event in events
    ) or '<tr><td colspan="4" class="muted">No evidence events recorded.</td></tr>'
    input_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td><code>{escape(str(item.get('sha256', '')))}</code></td>"
        "</tr>"
        for item in inputs
    ) or '<tr><td colspan="2" class="muted">No selected input files.</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FaultPack — {pack_id}</title><style>
:root{{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--line:#293653;--text:#e8edf7;--muted:#9aa8c2;--accent:#7dd3fc;--good:#86efac}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#0b1020,#101b35);color:var(--text);font:15px/1.6 ui-sans-serif,system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:48px 24px 72px}}header{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:28px}}h1,h2{{line-height:1.2;margin:0 0 12px}}h1{{font-size:clamp(28px,5vw,48px);letter-spacing:-.04em}}h2{{font-size:19px}}p{{color:var(--muted)}}.eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px}}.badge{{border:1px solid #2d6a4f;color:var(--good);border-radius:999px;padding:6px 12px;font-weight:700;white-space:nowrap}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:24px 0}}.card,section{{background:rgba(18,26,45,.86);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 12px 40px #05081455}}.label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}.value{{font-size:19px;margin-top:4px;overflow-wrap:anywhere}}code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em;color:#d8b4fe;overflow-wrap:anywhere}}table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}th{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}}.muted{{color:var(--muted)}}.notice{{border-left:4px solid var(--accent);padding:12px 16px;background:#0d2236;color:#c9e9fa;margin:24px 0}}footer{{color:var(--muted);font-size:12px;margin-top:28px}}@media(max-width:650px){{header{{display:block}}.badge{{display:inline-block;margin-top:14px}}main{{padding:28px 16px 48px}}th,td{{padding:8px 4px;font-size:13px}}}}
</style></head><body><main>
<header><div><div class="eyebrow">FaultPack evidence capsule</div><h1>{pack_id}</h1><p>Offline inspection of a verified, portable failure contract.</p></div><div class="badge">VERIFIED MANIFEST</div></header>
<div class="notice">This report is passive. It does not execute the declared command, fetch URLs, load plugins, or upload evidence. Replay remains an explicit, caller-sandboxed action.</div>
<div class="grid"><div class="card"><div class="label">Observed status</div><div class="value">{status}</div></div><div class="card"><div class="label">Producer</div><div class="value">{producer_name}</div></div><div class="card"><div class="label">Source</div><div class="value">{source_value}</div></div><div class="card"><div class="label">Selected inputs</div><div class="value">{len(inputs)}</div></div></div>
<section><h2>Execution contract</h2><p><span class="label">Command</span><br>{argv_html or '<span class="muted">not recorded</span>'}</p><p><span class="label">Working directory</span><br><code>{escape(str(command.get('cwd', '.')))}</code> · timeout <code>{escape(str(command.get('timeout_seconds', '')))}s</code></p><p><span class="label">Logical fingerprint</span><br><code>{fingerprint}</code></p></section>
<section style="margin-top:14px"><h2>Selected inputs and digests</h2><table><thead><tr><th>Path</th><th>SHA-256</th></tr></thead><tbody>{input_rows}</tbody></table></section>
<section style="margin-top:14px"><h2>Evidence timeline</h2><table><thead><tr><th>#</th><th>Kind</th><th>Name</th><th>Payload</th></tr></thead><tbody>{event_rows}</tbody></table></section>
<footer>Generated by FaultPack. Review sensitive content before sharing a report or its underlying pack.</footer>
</main></body></html>
"""
