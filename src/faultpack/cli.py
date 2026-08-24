from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .core import (
    FaultPackError,
    PackIntegrityError,
    load_manifest,
    safe_pack_path,
    verify_manifest,
)
from .pack import capture_pack
from .replay import compare, replay
from .report import junit_report, markdown_report, sarif_report, write_json

app = typer.Typer(
    no_args_is_help=True, help="Portable, privacy-first, verifiable reproduction packs."
)


@app.command()
def capture(
    command: Annotated[list[str], typer.Argument(help="Command and arguments after --")],
    out: Annotated[Path, typer.Option("--out", "-o")],
    cwd: Annotated[str, typer.Option()] = ".",
    timeout: Annotated[float, typer.Option()] = 30.0,
) -> None:
    """Capture a command result into a portable pack directory."""
    try:
        manifest = capture_pack(Path.cwd(), command, out, cwd, timeout)
    except FaultPackError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc
    typer.echo(
        json.dumps(
            {
                "pack": str(out),
                "fingerprint": manifest.fingerprint,
                "status": manifest.observed.status,
            }
        )
    )


@app.command()
def inspect(pack: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Print a pack manifest."""
    try:
        typer.echo((pack / "faultpack.json").read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.Exit(3) from exc


@app.command()
def verify(pack: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Verify manifest and artifact hashes without executing the command."""
    try:
        manifest = load_manifest(pack / "faultpack.json")
        verify_manifest(manifest)
        for relative, expected in [
            (manifest.observed.stdout_path, manifest.observed.stdout_sha256),
            (manifest.observed.stderr_path, manifest.observed.stderr_sha256),
        ]:
            actual = (
                __import__("hashlib")
                .sha256(safe_pack_path(pack, relative).read_bytes())
                .hexdigest()
            )
            if actual != expected:
                raise PackIntegrityError(f"artifact fingerprint mismatch: {relative}")
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"verified": True, "fingerprint": manifest.fingerprint}))


@app.command("replay")
def replay_cmd(
    pack: Annotated[Path, typer.Argument(exists=True)],
    report_dir: Annotated[Path | None, typer.Option("--report-dir")] = None,
) -> None:
    """Replay a pack and emit Markdown, SARIF, and JUnit reports."""
    try:
        manifest = load_manifest(pack / "faultpack.json")
        verify_manifest(manifest)
        status, code, duration, stdout, stderr = replay(pack, manifest)
        reasons = compare(manifest, status, code, stdout, stderr)
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
            }
        )
    )
    raise typer.Exit(0 if reproduced else 5)


@app.command("version")
def version() -> None:
    typer.echo("faultpack 0.1.0")
