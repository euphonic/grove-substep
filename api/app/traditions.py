"""Tradition skill packs are content: everything here is read from traditions/<id>/."""

import re
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


class Pack(BaseModel):
    id: str = Field(pattern=ID_PATTERN.pattern)
    display_name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=200)
    status: Literal["draft", "reviewed"] = "draft"


class PackError(ValueError):
    pass


def load_packs(root: Path) -> dict[str, Pack]:
    packs: dict[str, Pack] = {}
    for pack_file in sorted(root.glob("*/pack.yaml")):
        folder = pack_file.parent.name
        try:
            pack = Pack.model_validate(yaml.safe_load(pack_file.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError) as exc:
            raise PackError(f"{pack_file}: {exc}") from exc
        if pack.id != folder:
            raise PackError(f"{pack_file}: id '{pack.id}' must match folder '{folder}'")
        packs[pack.id] = pack
    return packs


@cache
def get_packs(root: Path) -> dict[str, Pack]:
    """Cached per traditions directory. Packs change only on deploy."""
    return load_packs(root)
