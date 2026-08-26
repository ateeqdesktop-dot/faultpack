from pathlib import Path

from faultpack.catalog import catalog_markdown, catalog_packs, discover_packs
from faultpack.pack import capture_pack


def make_pack(root: Path, name: str, *, command: list[str]) -> Path:
    source = root / f"{name}.py"
    source.write_text("print('ok')\n", encoding="utf-8")
    pack = root / name
    capture_pack(root, command, pack, ".", 10.0, input_files=[source.name])
    return pack


def test_catalog_is_deterministic_and_passive(tmp_path: Path) -> None:
    make_pack(tmp_path, "zeta", command=["python", "zeta.py"])
    make_pack(tmp_path, "alpha", command=["python", "alpha.py"])

    assert [p.relative_to(tmp_path).as_posix() for p in discover_packs(tmp_path)] == [
        "alpha",
        "zeta",
    ]
    result = catalog_packs(tmp_path)
    assert result["pack_count"] == 2
    assert result["verified_count"] == 2
    assert result["invalid_count"] == 0
    assert result["all_verified"] is True
    assert result["all_privacy_clean"] is True
    assert [item["path"] for item in result["packs"]] == ["alpha", "zeta"]

    markdown = catalog_markdown(result)
    assert "Passive inventory" in markdown
    assert "`alpha`" in markdown
    assert "`zeta`" in markdown


def test_catalog_reports_invalid_pack_without_executing(tmp_path: Path) -> None:
    pack = make_pack(tmp_path, "valid", command=["python", "valid.py"])
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "faultpack.json").write_text("{}", encoding="utf-8")

    result = catalog_packs(tmp_path)
    assert result["pack_count"] == 2
    assert result["verified_count"] == 1
    assert result["invalid_count"] == 1
    invalid = next(item for item in result["packs"] if item["path"] == "broken")
    assert invalid["verified"] is False
    assert invalid["error"]
    assert pack.exists()
