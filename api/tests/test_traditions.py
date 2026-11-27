from pathlib import Path

import pytest

from app.config import Settings
from app.traditions import PackError, load_packs

LAUNCH = {"mindfulness", "buddhist", "christian", "yogic", "raja-yoga"}


def test_launch_packs_load(settings: Settings) -> None:
    packs = load_packs(settings.traditions_dir)
    assert set(packs) == LAUNCH
    assert packs["raja-yoga"].display_name.startswith("Raja Yoga")


def _write(root: Path, folder: str, body: str) -> None:
    (root / folder).mkdir()
    (root / folder / "pack.yaml").write_text(body)


def test_id_must_match_folder(tmp_path: Path) -> None:
    _write(tmp_path, "stoic", "id: other\ndisplay_name: X\ndescription: Y\n")
    with pytest.raises(PackError, match="must match folder"):
        load_packs(tmp_path)


def test_invalid_pack_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "stoic", "id: stoic\ndisplay_name: ''\ndescription: Y\n")
    with pytest.raises(PackError):
        load_packs(tmp_path)
