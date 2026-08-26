from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.core import PackIntegrityError, PolicyError, verify_pack
from faultpack.diff import diff_observations, observe
from faultpack.pack import capture_pack
from faultpack.redact import RedactionPolicyError, redact_value
from faultpack.replay import replay
from faultpack.signing import generate_keypair


def _capture(root: Path, command: list[str], name: str) -> Path:
    pack = root / name
    capture_pack(root, command, pack)
    return pack


def test_ed25519_signing_and_explicit_verification(tmp_path: Path) -> None:
    keys = tmp_path / "keys"
    generate_keypair(keys / "private.pem", keys / "public.pem")
    pack = tmp_path / "signed"
    manifest = capture_pack(
        tmp_path,
        [sys.executable, "-c", "print('signed')"],
        pack,
        ed25519_private_key=keys / "private.pem",
    )
    assert (pack / "signature.ed25519").exists()
    assert verify_pack(pack, public_key=keys / "public.pem").fingerprint == manifest.fingerprint
    (pack / "signature.ed25519").write_text("invalid\n", encoding="ascii")
    with pytest.raises(PackIntegrityError, match="Ed25519"):
        verify_pack(pack, public_key=keys / "public.pem")


def test_diff_reports_behavioral_changes_but_not_timing(tmp_path: Path) -> None:
    left = _capture(tmp_path, [sys.executable, "-c", "print('left')"], "left")
    right = _capture(tmp_path, [sys.executable, "-c", "print('right')"], "right")
    left_manifest = verify_pack(left)
    right_manifest = verify_pack(right)
    result = diff_observations(
        observe(left_manifest, replay(left, left_manifest)),
        observe(right_manifest, replay(right, right_manifest)),
    )
    assert result["identical_behavior"] is False
    assert any(change["field"] == "stdout_sha256" for change in result["changes"])
    assert result["timing_is_diagnostic_only"] is True


def test_cli_keys_bundle_and_diff_contract(tmp_path: Path) -> None:
    runner = CliRunner()
    keys = tmp_path / "keys"
    key_result = runner.invoke(app, ["keys", "--output-dir", str(keys)])
    assert key_result.exit_code == 0
    assert json.loads(key_result.stdout)["public_key"].endswith("public.pem")

    pack = _capture(tmp_path, [sys.executable, "-c", "print('ok')"], "pack")
    bundle = tmp_path / "pack.zip"
    bundle_result = runner.invoke(app, ["bundle", str(pack), "--output", str(bundle)])
    assert bundle_result.exit_code == 0
    assert bundle.exists()

    same = runner.invoke(app, ["diff", str(pack), str(pack)])
    assert same.exit_code == 0
    assert json.loads(same.stdout)["identical_behavior"] is True


def test_invalid_redaction_and_nested_output_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(RedactionPolicyError):
        redact_value("data", ["["])
    with pytest.raises(PolicyError, match="contain"):
        capture_pack(tmp_path, [sys.executable, "-c", "print('x')"], tmp_path.parent)


def test_cli_diff_non_matching_result_uses_replay_exit_code(tmp_path: Path) -> None:
    runner = CliRunner()
    left = _capture(tmp_path, [sys.executable, "-c", "print('left')"], "left")
    right = _capture(tmp_path, [sys.executable, "-c", "print('right')"], "right")
    result = runner.invoke(app, ["diff", str(left), str(right)])
    assert result.exit_code == 5
    assert json.loads(result.stdout)["identical_behavior"] is False


def test_html_inspection_is_verified_and_self_contained(tmp_path: Path) -> None:
    runner = CliRunner()
    pack = _capture(tmp_path, [sys.executable, "-c", "print('<unsafe>')"], "html-pack")
    output = tmp_path / "report.html"
    result = runner.invoke(app, ["inspect", str(pack), "--html", "--output", str(output)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["verified"] is True
    rendered = output.read_text(encoding="utf-8")
    assert "<!doctype html>" in rendered
    assert "FaultPack evidence capsule" in rendered
    assert "&#x27;&lt;unsafe&gt;&#x27;" in rendered  # argv is escaped, not executed
    assert "<unsafe>" not in rendered  # raw HTML never appears in the report
    assert "Replay remains an explicit" in rendered


def test_html_inspection_rejects_tampered_pack(tmp_path: Path) -> None:
    runner = CliRunner()
    pack = _capture(tmp_path, [sys.executable, "-c", "print('ok')"], "tampered")
    manifest_path = pack / "faultpack.json"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace('"status":"passed"', '"status":"failed"'),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["inspect", str(pack), "--html", "--output", str(tmp_path / "bad.html")],
    )
    assert result.exit_code == 4
    assert not (tmp_path / "bad.html").exists()


def test_issue_command_is_metadata_only_and_reproducible(tmp_path: Path) -> None:
    runner = CliRunner()
    pack = _capture(tmp_path, [sys.executable, "-c", "print('safe')"], "issue-pack")
    output = tmp_path / "issue.md"
    result = runner.invoke(
        app,
        ["issue", str(pack), "--output", str(output), "--bundle-name", "failure.zip"],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["finding_count"] == 0
    body = output.read_text(encoding="utf-8")
    assert "Failure reproduction report" in body
    assert "failure.zip" in body
    assert "secret-like-token" not in body
    assert "stdout" not in body.lower() or "captured stdout/stderr" in body
    assert "faultpack verify" in body


def test_issue_command_surfaces_privacy_findings_without_values(tmp_path: Path) -> None:
    runner = CliRunner()
    pack = _capture(tmp_path, [sys.executable, "-c", "print('safe')"], "privacy-issue")
    stdout = pack / "artifacts" / "stdout.txt"
    stdout.write_text("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")
    from faultpack.core import load_manifest, manifest_fingerprint

    loaded = load_manifest(pack / "faultpack.json")
    loaded.observed.stdout_sha256 = __import__("hashlib").sha256(stdout.read_bytes()).hexdigest()
    loaded.fingerprint = manifest_fingerprint(loaded)
    (pack / "faultpack.json").write_text(
        __import__("json").dumps(loaded.model_dump(mode="json"), separators=(",", ":")),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["issue", str(pack), "--fail-on-findings"])
    assert result.exit_code == 6
    assert "bearer-token" in result.stdout
    assert "abcdefghijklmnopqrstuvwxyz123456" not in result.stdout


def test_issue_body_includes_contract_metadata_and_findings() -> None:
    from faultpack.diagnostics import Finding
    from faultpack.issue import build_issue_body
    from faultpack.models import (
        CommandSpec,
        Environment,
        EvidenceEvent,
        Expectation,
        FileEntry,
        Manifest,
        Observed,
        Producer,
        Source,
    )

    manifest = Manifest(
        source=Source(repository="https://github.com/example/demo", commit="abc123", branch="main"),
        producer=Producer(name="pytest", version="8.3", runtime="python3.12"),
        command=CommandSpec(argv=["python", "-m", "demo"], cwd="src"),
        environment=Environment(os="Linux", platform="x", python="3.12"),
        input_files=[FileEntry(path="fixtures/case.txt", sha256="a" * 64)],
        events=[EvidenceEvent(sequence=1, kind="assertion", name="regression")],
        expectation=Expectation(stdout_regex="required"),
        observed=Observed(
            status="passed",
            exit_code=0,
            duration_ms=1,
            stdout_sha256="0" * 64,
            stderr_sha256="0" * 64,
        ),
        pack_id="issue-test",
    )
    body = build_issue_body(
        manifest,
        [Finding("email-address", "info", "artifacts/stdout.txt", 4, "Email address detected")],
        bundle_name="case.zip",
    )
    assert "https://github.com/example/demo" in body
    assert "pytest 8.3 (python3.12)" in body
    assert "cd src" in body
    assert "fixtures/case.txt" in body
    assert "regression" in body
    assert "email-address" in body
    assert "line 4" in body
    assert "case.zip" in body
    assert "output patterns" in body
