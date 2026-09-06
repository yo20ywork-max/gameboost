import os
import tempfile
from pathlib import Path

os.environ["GAMEBOOST_DB"] = str(Path(tempfile.gettempdir()) / "gameboost-pytest-smoke.sqlite3")
Path(os.environ["GAMEBOOST_DB"]).unlink(missing_ok=True)

from fastapi.testclient import TestClient

from app.db import init_db, seed_demo
import app.main as main


NODE_PAYLOAD = {
    "id": "tokyo-test-1",
    "name": "Tokyo Test 1",
    "region": "apac",
    "country": "JP",
    "city": "Tokyo",
    "public_endpoint": "203.0.113.20",
    "wg_port": 51820,
    "wg_public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "vpn_prefix": "10.66.10",
    "mtu": 1280,
    "agent_url": "http://127.0.0.1:18081",
    "agent_secret": "secret",
    "health_url": "http://127.0.0.1:18081/health",
    "capacity": 500,
    "enabled": True,
}


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_route_plan_handles_empty_nodes_and_records_metrics():
    init_db()
    seed_demo()
    with TestClient(main.app, raise_server_exceptions=False) as client:
        user_headers = auth_headers(client, "demo@example.com", "demo123456")
        admin_headers = auth_headers(client, "admin@example.com", "change-this-admin-password")

        response = client.post(
            "/routes/plan",
            headers=user_headers,
            json={"game_id": "generic-full-tunnel", "mode": "auto", "measurements": {}},
        )
        assert response.status_code == 503

        response = client.post("/admin/nodes", headers=admin_headers, json=NODE_PAYLOAD)
        assert response.status_code == 200

        response = client.post(
            "/routes/plan",
            headers=user_headers,
            json={
                "game_id": "generic-full-tunnel",
                "mode": "auto",
                "measurements": {"tokyo-test-1": {"rtt_ms": 24, "loss_percent": 0, "jitter_ms": 2}},
                "direct_measurement": {"rtt_ms": 42, "loss_percent": 0, "target_count": 2},
            },
        )
        assert response.status_code == 200
        assert response.json()["selected_node_id"] == "tokyo-test-1"
        assert response.json()["decision"]["reason"] == "lowest_weighted_score"

        response = client.post(
            "/routes/evaluate",
            headers=user_headers,
            json={
                "game_id": "generic-full-tunnel",
                "mode": "auto",
                "measurements": {"tokyo-test-1": {"rtt_ms": 24, "loss_percent": 0, "jitter_ms": 2}},
                "direct_measurement": {"rtt_ms": 42, "loss_percent": 0, "target_count": 2},
                "probe_agents": False,
            },
        )
        assert response.status_code == 200
        assert response.json()["selected_node_id"] == "tokyo-test-1"
        assert response.json()["recommendation"]["action"] in {"accelerate", "optional", "avoid"}

        response = client.get("/admin/route-metrics", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()[0]["direct_measurement_json"]


def test_probe_matrix_feeds_route_evaluation_cache(monkeypatch):
    async def fake_probe_targets(node, targets, samples=2):
        return {
            "ok": True,
            "results": [
                {"host": targets[0]["host"], "port": targets[0]["port"], "rtt_ms": 18 if node["id"] == "tokyo-test-1" else 80, "loss_percent": 0}
            ],
        }

    monkeypatch.setattr(main, "probe_targets", fake_probe_targets)
    init_db()
    seed_demo()
    with TestClient(main.app, raise_server_exceptions=False) as client:
        user_headers = auth_headers(client, "demo@example.com", "demo123456")
        admin_headers = auth_headers(client, "admin@example.com", "change-this-admin-password")
        response = client.post("/admin/nodes", headers=admin_headers, json=NODE_PAYLOAD)
        assert response.status_code == 200

        response = client.post(
            "/admin/probes/run",
            headers=admin_headers,
            json={"game_ids": ["valorant-apac-sample"], "samples": 1},
        )
        assert response.status_code == 200
        assert response.json()["runs"][0]["results"][0]["summary"]["rtt_ms"] == 18

        response = client.get("/admin/probes/scoreboard?game_id=valorant-apac-sample", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["scoreboard"][0]["node_id"] == "tokyo-test-1"

        response = client.post(
            "/routes/evaluate",
            headers=user_headers,
            json={
                "game_id": "valorant-apac-sample",
                "mode": "auto",
                "measurements": {"tokyo-test-1": {"rtt_ms": 24, "loss_percent": 0, "jitter_ms": 1}},
                "direct_measurement": {"rtt_ms": 70, "loss_percent": 0, "target_count": 1},
                "probe_agents": False,
                "use_probe_cache": True,
            },
        )
        assert response.status_code == 200
        assert response.json()["cache_used"] is True
        assert response.json()["candidates"][0]["agent_measurement"]["rtt_ms"] == 18
