import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("GAMEBOOST_DB", BASE_DIR / "gameboost.sqlite3"))
JWT_SECRET = os.getenv("GAMEBOOST_JWT_SECRET", "dev-change-this-secret-before-production")
TOKEN_TTL_SECONDS = int(os.getenv("GAMEBOOST_TOKEN_TTL_SECONDS", "604800"))
GAME_PROFILE_DIR = Path(os.getenv("GAMEBOOST_PROFILE_DIR", BASE_DIR / "app" / "data" / "game_profiles"))
NODE_AGENT_TIMEOUT_SECONDS = float(os.getenv("GAMEBOOST_NODE_AGENT_TIMEOUT_SECONDS", "8"))
DEFAULT_LEASE_SECONDS = int(os.getenv("GAMEBOOST_DEFAULT_LEASE_SECONDS", "21600"))
