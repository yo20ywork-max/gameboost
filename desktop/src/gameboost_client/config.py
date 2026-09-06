from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / "AppData" / "Local" / "GameBoost"
CONFIG_PATH = APP_DIR / "config.json"
TUNNEL_NAME = "GameBoostTunnel"
WG_CONFIG_PATH = APP_DIR / f"{TUNNEL_NAME}.conf"


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(data: dict[str, Any]) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
