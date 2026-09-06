from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..settings import GAME_PROFILE_DIR


def load_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(Path(GAME_PROFILE_DIR).glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("source_file", path.name)
        profiles.append(data)
    return profiles


def get_profile(game_id: str) -> dict[str, Any] | None:
    for profile in load_profiles():
        if profile.get("id") == game_id:
            return profile
    return None
