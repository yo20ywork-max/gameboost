from __future__ import annotations

import argparse
import json
import sys

import httpx


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    response = client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()["token"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GameBoost node-to-game probe matrix.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="change-this-admin-password")
    parser.add_argument("--game-id", action="append", dest="game_ids", default=[])
    parser.add_argument("--all-games", action="store_true")
    parser.add_argument("--node-id", action="append", dest="node_ids", default=[])
    parser.add_argument("--samples", type=int, default=2)
    args = parser.parse_args()

    payload = {
        "game_ids": args.game_ids,
        "all_games": args.all_games or not args.game_ids,
        "node_ids": args.node_ids,
        "samples": args.samples,
    }

    with httpx.Client(timeout=120) as client:
        token = login(client, args.base_url.rstrip("/"), args.email, args.password)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(f"{args.base_url.rstrip('/')}/admin/probes/run", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
