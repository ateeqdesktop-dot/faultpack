import json
from pathlib import Path
from typing import Annotated

import typer

from .core import FaultPackError, verify_pack
from .pack import capture_pack
from .reducer import reduce_text_input
from .replay import compare, replay
from .report import junit_report, markdown_report, sarif_report, write_json

VERSION = "0.2.0"

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
) -> None:
    """Capture a command result into a portable pack directory."""
    input_file = input_file or []
    env = env or []
    redact_pattern = redact_pattern or []
    try:
        manifest = capture_pack(
            Path.cwd(),
            command,
            out,
            cwd,
            timeout,
            input_files=input_file,
            env_allowlist=env,
            extra_patterns=redact_pattern,
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
            },
            ensure_ascii=False,
        )
    )


@app.command()
def inspect(pack: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Print a pack manifest without executing its command."""
    try:
        typer.echo((pack / "faultpack.json").read_text(encoding="utf-8"))
    except OSError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc


@app.command()
def verify(
    pack: Annotated[Path, typer.Argument(exists=True)],
    require_signature: Annotated[bool, typer.Option("--require-signature")] = False,
) -> None:
    """Verify manifest, inputs, artifacts, and optional signature without execution."""
    try:
        manifest = verify_pack(pack, require_signature=require_signature)
    except (FaultPackError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    typer.echo(json.dumps({"verified": True, "fingerprint": manifest.fingerprint}))


@app.command("replay")
def replay_cmd(
    pack: Annotated[Path, typer.Argument(exists=True)],
    report_dir: Annotated[Path | None, typer.Option("--report-dir")] = None,
    require_signature: Annotated[bool, typer.Option("--require-signature")] = False,
) -> None:
    """Replay a verified pack and emit Markdown, SARIF, and JUnit reports."""
    try:
        manifest = verify_pack(pack, require_signature=require_signature)
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


@app.command("version")
def version() -> None:
    typer.echo(f"faultpack {VERSION}")
