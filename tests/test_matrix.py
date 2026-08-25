import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from faultpack.cli import app
from faultpack.core import verify_pack
from faultpack.matrix import MatrixPolicyError, run_matrix
from faultpack.models import MatrixProfile
from faultpack.pack import capture_pack


def _pack(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    capture_pack(
        tmp_path,
        [sys.executable, "-c", "import os; print(os.getenv('FP_MODE', 'default'))"],
        pack,
    )
    return pack


def test_matrix_profiles_are_ordered_and_env_overlay_is_supported(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    manifest = verify_pack(pack)
    result = run_matrix(
        pack,
        manifest,
        [
            MatrixProfile(name="baseline"),
            MatrixProfile(name="explicit-default", env={"FP_MODE": "default"}),
        ],
    )
    assert result["all_reproduced"] is True
    assert [item["profile"] for item in result["results"]] == ["baseline", "explicit-default"]
    assert result["counts"] == {"profiles": 2, "reproduced": 2, "mismatch": 0, "execution_error": 0}


def test_matrix_reports_mismatch_and_cli_exit_code_five(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps([{"name": "bad", "argv": [sys.executable, "-c", "raise SystemExit(7)"]}]),
        encoding="utf-8",
    )
    report_dir = tmp_path / "report"
    result = CliRunner().invoke(
        app,
        ["matrix", str(pack), "--profiles", str(profiles), "--report-dir", str(report_dir)],
    )
    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["counts"]["mismatch"] == 1
    assert (report_dir / "faultpack-matrix.md").exists()
    assert (report_dir / "faultpack-matrix.json").exists()
    assert (report_dir / "faultpack-matrix.sarif").exists()
    assert (report_dir / "faultpack-matrix.junit.xml").exists()


def test_matrix_rejects_duplicate_profiles_and_timeout_expansion(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    manifest = verify_pack(pack)
    with pytest.raises(MatrixPolicyError, match="duplicate"):
        run_matrix(pack, manifest, [MatrixProfile(name="same"), MatrixProfile(name="same")])
    with pytest.raises(MatrixPolicyError, match="cannot exceed"):
        run_matrix(
            pack,
            manifest,
            [MatrixProfile(name="slow", timeout_seconds=manifest.command.timeout_seconds + 1)],
        )


def test_matrix_classifies_missing_command_as_execution_error(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    manifest = verify_pack(pack)
    result = run_matrix(
        pack,
        manifest,
        [MatrixProfile(name="missing", argv=["faultpack-command-does-not-exist"])],
    )
    assert result["all_reproduced"] is False
    assert result["results"][0]["outcome"] == "execution_error"
    assert result["counts"]["execution_error"] == 1
