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
