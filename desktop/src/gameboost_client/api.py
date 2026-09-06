from __future__ import annotations

import requests


class GameBoostAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def login(self, email: str, password: str) -> dict:
        r = requests.post(f"{self.base_url}/auth/login", json={"email": email, "password": password}, timeout=15)
        r.raise_for_status()
        data = r.json()
        self.token = data["token"]
        return data

    def games(self) -> list[dict]:
        r = requests.get(f"{self.base_url}/games", headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def nodes(self) -> list[dict]:
        r = requests.get(f"{self.base_url}/nodes", headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def route_plan(self, game_id: str, mode: str, measurements: dict, direct_measurement: dict | None = None) -> dict:
        payload = {
            "game_id": game_id,
            "mode": mode,
            "measurements": measurements,
            "direct_measurement": direct_measurement or {},
        }
        r = requests.post(f"{self.base_url}/routes/plan", headers=self._headers(), json=payload, timeout=20)
        r.raise_for_status()
        return r.json()

    def route_evaluate(self, game_id: str, mode: str, measurements: dict, direct_measurement: dict | None = None, probe_agents: bool = False) -> dict:
        payload = {
            "game_id": game_id,
            "mode": mode,
            "measurements": measurements,
            "direct_measurement": direct_measurement or {},
            "probe_agents": probe_agents,
            "samples": 2,
        }
        r = requests.post(f"{self.base_url}/routes/evaluate", headers=self._headers(), json=payload, timeout=45)
        r.raise_for_status()
        return r.json()

    def start_lease(self, game_id: str, mode: str, client_public_key: str, desired_node_id: str | None, measurements: dict, direct_measurement: dict | None = None) -> dict:
        payload = {
            "game_id": game_id,
            "mode": mode,
            "client_public_key": client_public_key,
            "desired_node_id": desired_node_id,
            "client_os": "windows",
            "measurements": measurements,
            "direct_measurement": direct_measurement or {},
        }
        r = requests.post(f"{self.base_url}/lease/start", headers=self._headers(), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def stop_lease(self, lease_id: str) -> dict:
        r = requests.post(f"{self.base_url}/lease/stop", headers=self._headers(), json={"lease_id": lease_id}, timeout=15)
        r.raise_for_status()
        return r.json()
