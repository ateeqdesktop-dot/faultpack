from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.core import (
    FaultPackError,
    PackIntegrityError,
    PolicyError,
    canonical_json,
    load_manifest,
    manifest_fingerprint,
    safe_pack_path,
    verify_manifest,
)
from faultpack.models import CommandSpec, Environment, Expectation, Manifest, Observed
from faultpack.pack import capture_pack, inspect_pack, write_zip
from faultpack.redact import redact_environment, redact_value
from faultpack.replay import compare, replay
from faultpack.report import junit_report, markdown_report, sarif_report


def manifest_for(argv: list[str] | None = None) -> Manifest:
    return Manifest(
        command=CommandSpec(argv=argv or ["true"]),
        environment=Environment(os="Linux", platform="x", python="3.12"),
        observed=Observed(
            status="passed",
            exit_code=0,
            duration_ms=1,
            stdout_sha256="0" * 64,
            stderr_sha256="0" * 64,
        ),
        pack_id="p",
    )


def test_redaction_hides_secrets_and_identity() -> None:
    assert (
        redact_value("Authorization: Bearer abcdefghijklmnop user@example.com 192.168.1.2")
        == "Authorization: [REDACTED] [REDACTED_EMAIL] [REDACTED_IP]"
    )
    assert redact_environment({"API_TOKEN": "secret", "MODE": "ok"})["API_TOKEN"] == "[REDACTED]"
    assert redact_value("custom-value", ["custom-value"]) == "[REDACTED]"


def test_canonical_json_is_stable() -> None:
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}\n'


def test_safe_pack_path_rejects_traversal_and_symlink(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        safe_pack_path(tmp_path, "../outside")
    target = tmp_path / "target"
    target.write_text("x")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(PolicyError):
        safe_pack_path(tmp_path, "link")


def test_capture_inspect_zip_and_fingerprint(tmp_path: Path) -> None:
    out = tmp_path / "pack"
    manifest = capture_pack(tmp_path, ["python", "-c", "print('hello')"], out)
    assert manifest.observed.exit_code == 0
    assert manifest.fingerprint == manifest_fingerprint(manifest)
    assert inspect_pack(out).pack_id == manifest.pack_id
    assert (out / "artifacts/stdout.txt").read_text().strip() == "hello"
    archive = tmp_path / "pack.zip"
    write_zip(out, archive)
    assert archive.exists()


def test_replay_matches_and_compare_reports_mismatch(tmp_path: Path) -> None:
    out = tmp_path / "pack"
    manifest = capture_pack(tmp_path, ["python", "-c", "print('hello')"], out)
    status, code, _, stdout, stderr = replay(out, manifest)
    assert status == "passed" and code == 0
    assert compare(manifest, status, code, stdout, stderr) == []
    mismatch = manifest.model_copy(
        update={"expectation": Expectation(exit_code=0, stdout_regex="missing")}
    )
    assert compare(mismatch, status, code, stdout, stderr) == ["stdout regex did not match"]


def test_timeout_and_manifest_validation(tmp_path: Path) -> None:
    out = tmp_path / "pack"
    manifest = capture_pack(
        tmp_path, ["python", "-c", "import time; time.sleep(0.2)"], out, timeout=0.01
    )
    assert manifest.observed.status == "timeout"
    with pytest.raises(FaultPackError):
        load_manifest(tmp_path / "missing.json")


def test_manifest_integrity_error() -> None:
    with pytest.raises(PackIntegrityError):
        verify_manifest(manifest_for().model_copy(update={"fingerprint": "1" * 64}))


def test_reports() -> None:
    assert "REPRODUCED" in markdown_report("p", True, [], "passed", 0, 3)
    assert "NOT REPRODUCED" in markdown_report("p", False, ["bad"], "failed", 1, 3)
    assert sarif_report(True, [])["runs"][0]["results"] == []
    assert len(sarif_report(False, ["bad"])["runs"][0]["results"]) == 1
    assert "testsuite" in junit_report(True, [], 3)
    assert "failure" in junit_report(False, ["bad"], 3)


def test_cli_version_and_capture(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["version"]).exit_code == 0
    out = tmp_path / "cli-pack"
    result = runner.invoke(
        app, ["capture", "--out", str(out), "--", "python", "-c", "print('cli')"]
    )
    assert result.exit_code == 0
    assert runner.invoke(app, ["verify", str(out)]).exit_code == 0
    replay_result = runner.invoke(
        app, ["replay", str(out), "--report-dir", str(tmp_path / "reports")]
    )
    assert replay_result.exit_code == 0
