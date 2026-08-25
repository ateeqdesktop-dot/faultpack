from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.diagnostics import diagnose_pack
from faultpack.pack import capture_pack


def make_pack(tmp_path: Path, body: str) -> Path:
    source = tmp_path / "case.txt"
    source.write_text(body, encoding="utf-8")
    pack = tmp_path / "pack"
    capture_pack(
        tmp_path,
        ["python", "-c", "print(open('case.txt').read())"],
        pack,
        ".",
        10,
        input_files=["case.txt"],
    )
    return pack


def test_diagnose_clean_pack(tmp_path: Path) -> None:
    assert diagnose_pack(make_pack(tmp_path, "safe diagnostic text")) == []


def test_diagnose_reports_secret_and_email(tmp_path: Path) -> None:
    findings = diagnose_pack(
        make_pack(tmp_path, "token = ghp_123456789012345678901234\nowner@example.com")
    )
    assert {finding.code for finding in findings} == {
        "github-token",
        "secret-assignment",
        "email-address",
    }
    assert {finding.path for finding in findings} <= {
        "artifacts/inputs/case.txt",
        "artifacts/stdout.txt",
        "artifacts/stderr.txt",
    }


def test_diagnose_cli_returns_machine_readable_payload(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["diagnose", str(make_pack(tmp_path, "safe"))])
    assert result.exit_code == 0
    assert '"clean": true' in result.stdout


def test_diagnose_skips_binary_and_reports_size_limit(tmp_path: Path) -> None:
    pack = make_pack(tmp_path, "safe")
    binary = pack / "artifacts" / "inputs" / "binary.bin"
    binary.write_bytes(b"\xff\x00secret")
    findings = diagnose_pack(pack, max_bytes=1)
    assert any(finding.code == "size-limit" for finding in findings)


def test_diagnose_rejects_invalid_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        diagnose_pack(make_pack(tmp_path, "safe"), max_bytes=0)
