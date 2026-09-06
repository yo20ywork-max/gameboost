from __future__ import annotations

import httpx

from ..settings import NODE_AGENT_TIMEOUT_SECONDS


def _headers(node: dict) -> dict[str, str]:
    return {"X-Agent-Secret": node["agent_secret"]}


async def upsert_peer(node: dict, client_public_key: str, client_vpn_ip: str, lease_id: str) -> None:
    url = node["agent_url"].rstrip("/") + "/peers/upsert"
    payload = {
        "lease_id": lease_id,
        "public_key": client_public_key,
        "allowed_ip": f"{client_vpn_ip}/32",
    }
    async with httpx.AsyncClient(timeout=NODE_AGENT_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, headers=_headers(node), json=payload)
        resp.raise_for_status()


async def delete_peer(node: dict, client_public_key: str, lease_id: str) -> None:
    url = node["agent_url"].rstrip("/") + "/peers/delete"
    payload = {"lease_id": lease_id, "public_key": client_public_key}
    async with httpx.AsyncClient(timeout=NODE_AGENT_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, headers=_headers(node), json=payload)
        resp.raise_for_status()


async def fetch_health(node: dict) -> dict:
    url = node["agent_url"].rstrip("/") + "/health"
    async with httpx.AsyncClient(timeout=NODE_AGENT_TIMEOUT_SECONDS) as client:
        resp = await client.get(url, headers=_headers(node))
        resp.raise_for_status()
        return resp.json()


async def probe_targets(node: dict, targets: list[dict], samples: int = 3) -> dict:
    url = node["agent_url"].rstrip("/") + "/probe/tcp"
    payload = {"targets": targets, "samples": samples}
    async with httpx.AsyncClient(timeout=NODE_AGENT_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, headers=_headers(node), json=payload)
        resp.raise_for_status()
        return resp.json()
