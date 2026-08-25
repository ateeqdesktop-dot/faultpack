import hashlib
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import VERSION, app
from faultpack.core import (
    FaultPackError,
    PackIntegrityError,
    PolicyError,
    canonical_json,
    manifest_fingerprint,
    safe_pack_path,
    verify_pack,
)
from faultpack.models import CommandSpec, Environment, Expectation, Manifest, Observed
from faultpack.pack import capture_pack, execution_environment, write_zip
from faultpack.reducer import reduce_text_input
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


def test_redaction_and_environment_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from faultpack.redact import redact_environment, redact_value

    monkeypatch.setenv("FAULTPACK_TEST_SECRET", "do-not-leak")
    monkeypatch.setenv("FAULTPACK_TEST_VISIBLE", "visible")
    env = execution_environment(["FAULTPACK_TEST_VISIBLE", "FAULTPACK_TEST_SECRET"])
    assert env["FAULTPACK_TEST_SECRET"] == "[REDACTED]"
    assert env["FAULTPACK_TEST_VISIBLE"] == "visible"
    assert "UNDECLARED_SECRET" not in execution_environment([])
    assert redact_value("Authorization: Bearer abcdefghijklmnop user@example.com 192.168.1.2") == (
        "Authorization: [REDACTED] [REDACTED_EMAIL] [REDACTED_IP]"
    )
    assert redact_environment({"API_TOKEN": "secret", "MODE": "ok"})["API_TOKEN"] == "[REDACTED]"


def test_canonical_json_is_stable_and_v02_fingerprint_ignores_volatile_values() -> None:
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}\n'
    first = manifest_for().model_copy(update={"format_version": "0.2", "pack_id": "one"})
    second = first.model_copy(
        update={
            "pack_id": "two",
            "observed": first.observed.model_copy(update={"duration_ms": 999}),
        }
    )
    assert manifest_fingerprint(first) == manifest_fingerprint(second)


def test_safe_pack_path_rejects_traversal_symlink_and_backslash(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        safe_pack_path(tmp_path, "../outside")
    with pytest.raises(PolicyError):
        safe_pack_path(tmp_path, "nested\\outside")
    target = tmp_path / "target"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(PolicyError):
        safe_pack_path(tmp_path, "link")


def test_capture_verify_replay_inputs_and_deterministic_zip(tmp_path: Path) -> None:
    (tmp_path / "fixture.txt").write_text("hello\n", encoding="utf-8")
    command = [
        sys.executable,
        "-c",
        "import pathlib; print(pathlib.Path('fixture.txt').read_text().strip())",
    ]
    out = tmp_path / "pack"
    manifest = capture_pack(tmp_path, command, out, input_files=["fixture.txt"])
    assert manifest.format_version == "0.2"
    assert "PATH" not in manifest.environment.variables
    assert manifest.observed.exit_code == 0
    assert verify_pack(out).fingerprint == manifest.fingerprint
    status, code, duration, stdout, stderr = replay(out, manifest)
    assert status == "passed" and code == 0 and stdout.strip() == "hello" and not stderr
    assert compare(manifest, status, code, duration, stdout, stderr) == []
    archive = tmp_path / "pack.zip"
    write_zip(out, archive)
    assert archive.exists()
    assert hashlib.sha256(archive.read_bytes()).hexdigest()


def test_capture_preserves_failure_and_redacts_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_TOKEN", "secret-value")
    command = [sys.executable, "-c", "import os,sys; print(os.getenv('API_TOKEN')); sys.exit(2)"]
    out = tmp_path / "pack"
    manifest = capture_pack(tmp_path, command, out, env_allowlist=["API_TOKEN"])
    assert manifest.observed.status == "failed"
    assert manifest.observed.exit_code == 2
    assert (out / "artifacts/stdout.txt").read_text(encoding="utf-8").strip() == "[REDACTED]"
    status, code, duration, stdout, stderr = replay(out, manifest)
    assert compare(manifest, status, code, duration, stdout, stderr) == []


def test_timeout_and_manifest_validation(tmp_path: Path) -> None:
    out = tmp_path / "pack"
    manifest = capture_pack(
        tmp_path, [sys.executable, "-c", "import time; time.sleep(0.2)"], out, timeout=0.01
    )
    assert manifest.observed.status == "timeout"
    with pytest.raises(FaultPackError):
        verify_pack(tmp_path / "missing")


def test_integrity_and_signature_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "pack"
    monkeypatch.setenv("FAULTPACK_SIGNING_KEY", "unit-test-key")
    manifest = capture_pack(tmp_path, [sys.executable, "-c", "print('signed')"], out)
    assert verify_pack(out, require_signature=True).fingerprint == manifest.fingerprint
    (out / "artifacts/stdout.txt").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PackIntegrityError):
        verify_pack(out)


def test_compare_regex_hash_and_duration_mismatches() -> None:
    manifest = manifest_for().model_copy(
        update={
            "expectation": Expectation(
                exit_code=0,
                stdout_regex="required",
                stderr_regex="error",
                stdout_sha256="0" * 64,
                duration_max_ms=2,
            )
        }
    )
    reasons = compare(manifest, "passed", 0, 3, "nope", "none")
    assert any("stdout regex" in reason for reason in reasons)
    assert any("stderr regex" in reason for reason in reasons)
    assert any("stdout hash" in reason for reason in reasons)
    assert any("duration" in reason for reason in reasons)


def test_reduce_text_input_preserves_failure_oracle(tmp_path: Path) -> None:
    (tmp_path / "case.txt").write_text("noise-1\nKEEP\nnoise-2\nnoise-3\n", encoding="utf-8")
    command = [
        sys.executable,
        "-c",
        "import pathlib,sys; sys.exit(1 if 'KEEP' in pathlib.Path('case.txt').read_text() else 0)",
    ]
    pack = tmp_path / "pack"
    capture_pack(tmp_path, command, pack, input_files=["case.txt"])
    reduced = tmp_path / "reduced"
    manifest, runs = reduce_text_input(pack, "case.txt", reduced, max_runs=50)
    assert runs > 1
    assert "KEEP" in (reduced / "artifacts/inputs/case.txt").read_text(encoding="utf-8")
    assert len((reduced / "artifacts/inputs/case.txt").read_text(encoding="utf-8").splitlines()) < 4
    assert verify_pack(reduced).fingerprint == manifest.fingerprint


def test_reports_and_cli(tmp_path: Path) -> None:
    assert VERSION == "0.2.0"
    assert "REPRODUCED" in markdown_report("p", True, [], "passed", 0, 3)
    assert "not a sandbox" in markdown_report("p", True, [], "passed", 0, 3)
    assert len(sarif_report(False, ["bad"])["runs"][0]["results"]) == 1
    assert "testsuite" in junit_report(True, [], 3)
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0 and "0.2.0" in result.stdout
    out = tmp_path / "cli-pack"
    result = runner.invoke(
        app,
        [
            "capture",
            "--out",
            str(out),
            "--input",
            "fixture.txt",
            "--",
            sys.executable,
            "-c",
            "print('cli')",
        ],
    )
    # Missing input must fail closed without leaving a partial pack.
    assert result.exit_code != 0


def test_cli_full_lifecycle_and_failure_exit_codes(tmp_path: Path) -> None:
    runner = CliRunner()
    (tmp_path / "case.txt").write_text("KEEP\nnoise\n", encoding="utf-8")
    command = [
        sys.executable,
        "-c",
        "import pathlib,sys; print(pathlib.Path('case.txt').read_text().strip()); sys.exit(1)",
    ]
    pack = tmp_path / "pack"
    capture_pack(tmp_path, command, pack, input_files=["case.txt"])
    assert runner.invoke(app, ["inspect", str(pack)]).exit_code == 0
    assert runner.invoke(app, ["verify", str(pack)]).exit_code == 0
    replay_result = runner.invoke(
        app, ["replay", str(pack), "--report-dir", str(tmp_path / "report")]
    )
    assert replay_result.exit_code == 0
    assert (tmp_path / "report" / "faultpack.sarif").exists()
    reduced_result = runner.invoke(
        app, ["reduce", str(pack), "--input", "case.txt", "--out", str(tmp_path / "reduced")]
    )
    assert reduced_result.exit_code == 0

    passing = tmp_path / "passing"
    passing_manifest = capture_pack(tmp_path, [sys.executable, "-c", "print('ok')"], passing)
    mismatch = passing_manifest.model_copy(
        update={"expectation": Expectation(stdout_regex="never-matches"), "fingerprint": None}
    )
    mismatch = mismatch.model_copy(update={"fingerprint": manifest_fingerprint(mismatch)})
    (passing / "faultpack.json").write_bytes(canonical_json(mismatch.model_dump(mode="json")))
    assert runner.invoke(app, ["replay", str(passing)]).exit_code == 5
    assert runner.invoke(app, ["verify", str(passing), "--require-signature"]).exit_code == 4

    missing_input = runner.invoke(
        app,
        [
            "capture",
            "--out",
            str(tmp_path / "invalid"),
            "--input",
            "missing.txt",
            "--",
            sys.executable,
            "-c",
            "print(1)",
        ],
    )
    assert missing_input.exit_code == 3
    assert not (tmp_path / "invalid").exists()
    assert runner.invoke(app, ["inspect", str(tmp_path / "pack")]).exit_code == 0
    successful_capture = runner.invoke(
        app,
        [
            "capture",
            "--out",
            str(tmp_path / "successful"),
            "--",
            sys.executable,
            "-c",
            "print('ok')",
        ],
    )
    assert successful_capture.exit_code == 0


def test_replay_error_and_reducer_rejection_paths(tmp_path: Path) -> None:
    manifest = manifest_for(["definitely-not-a-command"])
    status, code, _, _, stderr = replay(tmp_path, manifest)
    assert status == "error" and code is None and stderr
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    passing = tmp_path / "passing"
    capture_pack(
        tmp_path, [sys.executable, "-c", "print('ok')"], passing, input_files=["empty.txt"]
    )
    with pytest.raises(FaultPackError, match="input is empty"):
        reduce_text_input(passing, "empty.txt", tmp_path / "out")
    with pytest.raises(FaultPackError, match="input is not declared"):
        reduce_text_input(passing, "missing.txt", tmp_path / "out")


def test_model_validation_and_signature_errors(tmp_path: Path) -> None:
    from pydantic import ValidationError

    from faultpack.core import signature_for, verify_signature
    from faultpack.models import FileEntry

    with pytest.raises(ValidationError):
        CommandSpec(argv=["x"], cwd="../bad")
    with pytest.raises(ValidationError):
        FileEntry(path="../bad", sha256="0" * 64)
    with pytest.raises(PackIntegrityError):
        verify_signature(tmp_path, "f" * 64, "key", required=True)
    (tmp_path / "signature.hmac").write_text(signature_for("f" * 64, "other"), encoding="ascii")
    with pytest.raises(PackIntegrityError):
        verify_signature(tmp_path, "f" * 64, "key")


def test_cli_rejects_broken_pack_with_stable_codes(tmp_path: Path) -> None:
    runner = CliRunner()
    broken = tmp_path / "broken"
    broken.mkdir()
    assert runner.invoke(app, ["inspect", str(broken)]).exit_code == 3
    assert runner.invoke(app, ["verify", str(broken)]).exit_code == 4
    assert runner.invoke(app, ["replay", str(broken)]).exit_code == 4
    assert (
        runner.invoke(
            app,
            ["reduce", str(broken), "--input", "case.txt", "--out", str(tmp_path / "reduced")],
        ).exit_code
        == 4
    )
