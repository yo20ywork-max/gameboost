from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_db, seed_demo

if __name__ == "__main__":
    init_db()
    seed_demo()
    print("Seeded demo users:")
    print("  demo@example.com / demo123456")
    print("  admin@example.com / change-this-admin-password")
