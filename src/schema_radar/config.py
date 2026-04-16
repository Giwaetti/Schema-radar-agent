from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_sources(path: str | Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    return list(data.get("sources", []))


def load_keywords(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)
