from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .catalog import catalog_markdown, catalog_packs
from .core import FaultPackError, verify_pack
from .diagnostics import diagnose_pack
from .diff import diff_observations, observe
from .evidence_diff import evidence_diff
from .interop import (
    InteropError,
    bundle_result,
    diff_bundles,
    load_bundle,
    normalize_file,
    write_bundle,
    write_reports,
)
from .issue import build_issue_body
from .matrix import run_matrix, write_matrix_reports
from .models import MatrixProfile
from .pack import capture_pack, write_zip
from .reducer import reduce_text_input
from .replay import compare, replay
from .report import html_report, junit_report, markdown_report, sarif_report, write_json
from .signing import generate_keypair

VERSION = "1.7.0"

app = typer.Typer(
    no_args_is_help=True,
    help="Portable, privacy-first, verifiable reproduction packs.",
)


@app.command()
def capture(
    command: Annotated[list[str], typer.Argument(help="Command and arguments after --")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output pack directory")],
    cwd: Annotated[str, typer.Option(help="Relative command working directory")] = ".",
    timeout: Annotated[float, typer.Option(help="Maximum execution time in seconds")] = 30.0,
    input_file: Annotated[
        list[str] | None, typer.Option("--input", help="Relative input file to include")
    ] = None,
    env: Annotated[
        list[str] | None, typer.Option("--env", help="Environment name allowed in child process")
    ] = None,
    redact_pattern: Annotated[
        list[str] | None, typer.Option("--redact-pattern", help="Additional redaction regex")
    ] = None,
    ed25519_private_key: Annotated[
        Path | None,
        typer.Option("--ed25519-private-key", help="PEM private key for detached signing"),
    ] = None,
) -> None:
    """Capture a command result into a portable pack directory."""
    try:
        manifest = capture_pack(
            Path.cwd(),
            command,
            out,
            cwd,
            timeout,
            input_files=input_file or [],
            env_allowlist=env or [],
            extra_patterns=redact_pattern or [],
            ed25519_private_key=ed25519_private_key,
        )
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc
    typer.echo(
        json.dumps(
            {
                "pack": str(out),
                "fingerprint": manifest.fingerprint,
                "status": manifest.observed.status,
                "signed": (out / "signature.ed25519").exists() or (out / "signature.hmac").exists(),
            },
            ensure_ascii=False,
        )
    )


@app.command()
def inspect(
    pack: Annotated[Path, typer.Argument(exists=True)],
    html: Annotated[
        bool, typer.Option("--html", help="Render a self-contained offline HTML report")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write HTML to a file")
    ] = None,
) -> None:
    """Inspect a pack passively, optionally rendering a verified offline HTML report."""
    try:
        if html:
            manifest = verify_pack(pack)
            rendered = html_report(manifest)
            if output:
                output.write_text(rendered, encoding="utf-8")
                typer.echo(json.dumps({"html": str(output), "verified": True}))
            else:
                typer.echo(rendered, nl=False)
        else:
            typer.echo((pack / "faultpack.json").read_text(encoding="utf-8"))
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4 if html else 3) from exc


@app.command()
def diagnose(
    pack: Annotated[Path, typer.Argument(exists=True)],
    fail_on_findings: Annotated[
        bool, typer.Option("--fail-on-findings", help="Exit 6 when any privacy finding exists")
    ] = False,
    max_bytes: Annotated[int, typer.Option("--max-bytes", min=1, max=50_000_000)] = 2_000_000,
) -> None:
    """Passively scan a verified pack for share-before-you-send privacy findings."""
    try:
        findings = diagnose_pack(pack, max_bytes=max_bytes)
    except (FaultPackError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    payload = {
        "clean": not findings,
        "finding_count": len(findings),
        "findings": [item.as_dict() for item in findings],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))
    if findings and fail_on_findings:
        raise typer.Exit(6)


@app.command()
def verify(
    pack: Annotated[Path, typer.Argument(exists=True)],
    require_signature: Annotated[bool, typer.Option("--require-signature")] = False,
    public_key: Annotated[
        Path | None, typer.Option("--public-key", help="PEM Ed25519 public key")
    ] = None,
) -> None:
    """Verify manifest, inputs, artifacts, and optional signature without execution."""
    try:
        manifest = verify_pack(pack, require_signature=require_signature, public_key=public_key)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"verified": True, "fingerprint": manifest.fingerprint}))


@app.command("replay")
def replay_cmd(
    pack: Annotated[Path, typer.Argument(exists=True)],
    report_dir: Annotated[Path | None, typer.Option("--report-dir")] = None,
    require_signature: Annotated[bool, typer.Option("--require-signature")] = False,
    public_key: Annotated[
        Path | None, typer.Option("--public-key", help="PEM Ed25519 public key")
    ] = None,
) -> None:
    """Replay a verified pack and emit Markdown, SARIF, and JUnit reports."""
    try:
        manifest = verify_pack(pack, require_signature=require_signature, public_key=public_key)
        status, code, duration, stdout, stderr = replay(pack, manifest)
        reasons = compare(manifest, status, code, duration, stdout, stderr)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    reproduced = not reasons
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "faultpack-report.md").write_text(
            markdown_report(manifest.pack_id, reproduced, reasons, status, code, duration),
            encoding="utf-8",
        )
        write_json(report_dir / "faultpack.sarif", sarif_report(reproduced, reasons))
        (report_dir / "faultpack.junit.xml").write_text(
            junit_report(reproduced, reasons, duration), encoding="utf-8"
        )
    typer.echo(
        json.dumps(
            {
                "reproduced": reproduced,
                "status": status,
                "exit_code": code,
                "duration_ms": duration,
                "reasons": reasons,
            },
            ensure_ascii=False,
        )
    )
    raise typer.Exit(0 if reproduced else 5)


@app.command("diff")
def diff(
    left: Annotated[Path, typer.Argument(exists=True)],
    right: Annotated[Path, typer.Argument(exists=True)],
    public_key: Annotated[
        Path | None, typer.Option("--public-key", help="PEM Ed25519 public key for both packs")
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Replay two verified packs and report behavioral differences."""
    try:
        left_manifest = verify_pack(left, public_key=public_key)
        right_manifest = verify_pack(right, public_key=public_key)
        result = diff_observations(
            observe(left_manifest, replay(left, left_manifest)),
            observe(right_manifest, replay(right, right_manifest)),
        )
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    if output:
        write_json(output, result)
    typer.echo(json.dumps(result, ensure_ascii=False))
    raise typer.Exit(0 if result["identical_behavior"] else 5)


@app.command("evidence-diff")
def evidence_diff_cmd(
    left: Annotated[Path, typer.Argument(exists=True)],
    right: Annotated[Path, typer.Argument(exists=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Compare two verified manifests without executing their commands."""
    try:
        left_manifest = verify_pack(left)
        right_manifest = verify_pack(right)
        result = evidence_diff(left_manifest, right_manifest)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    if output:
        write_json(output, result)
    typer.echo(json.dumps(result, ensure_ascii=False))
    raise typer.Exit(0 if result["identical_evidence"] else 5)


@app.command("matrix")
def matrix(
    pack: Annotated[Path, typer.Argument(exists=True)],
    profiles: Annotated[
        Path, typer.Option("--profiles", help="JSON file containing an array of profiles")
    ],
    report_dir: Annotated[Path | None, typer.Option("--report-dir")] = None,
    require_signature: Annotated[bool, typer.Option("--require-signature")] = False,
    public_key: Annotated[Path | None, typer.Option("--public-key")] = None,
) -> None:
    """Replay one verified pack across ordered, bounded local profiles."""
    try:
        manifest = verify_pack(pack, require_signature=require_signature, public_key=public_key)
        raw_profiles = json.loads(profiles.read_text(encoding="utf-8"))
        if not isinstance(raw_profiles, list):
            raise ValueError("profiles JSON must contain an array")
        parsed = [MatrixProfile.model_validate(item) for item in raw_profiles]
        payload = run_matrix(pack, manifest, parsed)
        if report_dir:
            write_matrix_reports(report_dir, payload)
    except (FaultPackError, OSError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False))
    raise typer.Exit(0 if payload["all_reproduced"] else 5)


@app.command("issue")
def issue(
    pack: Annotated[Path, typer.Argument(exists=True)],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write a GitHub issue body to a file")
    ] = None,
    bundle_name: Annotated[
        str | None, typer.Option("--bundle-name", help="Suggested attachment name")
    ] = None,
    fail_on_findings: Annotated[
        bool, typer.Option("--fail-on-findings", help="Exit 6 when privacy review is required")
    ] = False,
) -> None:
    """Generate a safe, metadata-only GitHub issue body from a verified pack."""
    try:
        manifest = verify_pack(pack)
        findings = diagnose_pack(pack)
        body = build_issue_body(manifest, findings, bundle_name=bundle_name)
        if output:
            output.write_text(body, encoding="utf-8")
            typer.echo(
                json.dumps({"issue": str(output), "verified": True, "finding_count": len(findings)})
            )
        else:
            typer.echo(body, nl=False)
    except (FaultPackError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    if findings and fail_on_findings:
        raise typer.Exit(6)


@app.command("catalog")
def catalog(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON catalog")
    ] = None,
    markdown: Annotated[
        Path | None, typer.Option("--markdown", help="Write Markdown catalog")
    ] = None,
    fail_on_findings: Annotated[
        bool, typer.Option("--fail-on-findings", help="Exit 6 if any pack needs privacy review")
    ] = False,
) -> None:
    """Inventory nested packs passively for regression-corpus and CI review."""
    try:
        payload = catalog_packs(root)
        if output:
            write_json(output, payload)
        if markdown:
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(catalog_markdown(payload), encoding="utf-8")
    except (FaultPackError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False))
    if (not payload["all_verified"]) or (fail_on_findings and not payload["all_privacy_clean"]):
        raise typer.Exit(6 if fail_on_findings and not payload["all_privacy_clean"] else 4)


@app.command("bundle")
def bundle(
    pack: Annotated[Path, typer.Argument(exists=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
) -> None:
    """Verify a pack and write a deterministic ZIP bundle."""
    try:
        verify_pack(pack)
        write_zip(pack, output)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"bundle": str(output), "verified": True}))


@app.command("keys")
def keys(
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")],
) -> None:
    """Generate an Ed25519 keypair for local signing experiments."""
    try:
        private_path = output_dir / "faultpack-ed25519-private.pem"
        public_path = output_dir / "faultpack-ed25519-public.pem"
        generate_keypair(private_path, public_path)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"private_key": str(private_path), "public_key": str(public_path)}))


@app.command("reduce")
def reduce(
    pack: Annotated[Path, typer.Argument(exists=True)],
    input_file: Annotated[str, typer.Option("--input", help="Declared UTF-8 input to reduce")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output reduced pack directory")],
    max_runs: Annotated[int, typer.Option("--max-runs", min=1, max=10000)] = 100,
) -> None:
    """Minimize a text input while preserving the pack's failure oracle."""
    try:
        manifest, runs = reduce_text_input(pack, input_file, out, max_runs=max_runs)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"pack": str(out), "fingerprint": manifest.fingerprint, "runs": runs}))


@app.command("interop")
def interop(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o", help="Canonical evidence bundle JSON")],
    source_format: Annotated[
        str,
        typer.Option(
            "--format", help="auto, generic-jsonl, mcp-jsonl, ci-jsonl, or openinference-otlp-json"
        ),
    ] = "auto",
    report_dir: Annotated[
        Path | None, typer.Option("--report-dir", help="Write JSON/SARIF/JUnit/Markdown reports")
    ] = None,
    redact_pattern: Annotated[list[str] | None, typer.Option("--redact-pattern")] = None,
) -> None:
    """Normalize external agent, MCP, OTLP, or CI evidence into a verified bundle."""
    try:
        bundle = normalize_file(source, source_format, redact_pattern or [])
        write_bundle(output, bundle)
        if report_dir:
            write_reports(report_dir, bundle)
    except (InteropError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"bundle": str(output), **bundle_result(bundle)}, ensure_ascii=False))
    if bundle.has_errors:
        raise typer.Exit(4)


@app.command("interop-verify")
def interop_verify(
    bundle: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    report_dir: Annotated[Path | None, typer.Option("--report-dir")] = None,
    fail_on_findings: Annotated[bool, typer.Option("--fail-on-findings")] = False,
) -> None:
    """Verify a canonical evidence bundle without executing or uploading anything."""
    try:
        parsed = load_bundle(bundle)
        if report_dir:
            write_reports(report_dir, parsed)
    except (InteropError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"bundle": str(bundle), **bundle_result(parsed)}, ensure_ascii=False))
    if fail_on_findings and parsed.findings:
        raise typer.Exit(6)


@app.command("interop-diff")
def interop_diff(
    left: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    right: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Compare two verified canonical evidence bundles without executing them."""
    try:
        result = diff_bundles(load_bundle(left), load_bundle(right))
    except (InteropError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    if output:
        write_json(output, result)
    typer.echo(json.dumps(result, ensure_ascii=False))
    raise typer.Exit(0 if result["identical"] else 5)


@app.command("version")
def version() -> None:
    typer.echo(f"faultpack {VERSION}")
