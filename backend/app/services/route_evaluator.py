from __future__ import annotations

import asyncio
import ipaddress
import statistics
from typing import Any

from .node_agent import probe_targets
from .node_selector import node_score, rank_nodes
from .route_planner import build_allowed_targets


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _tcp_ports(profile: dict[str, Any]) -> list[int]:
    ports: list[int] = []
    for item in profile.get("ports", []):
        if item.get("proto") != "tcp":
            continue
        for part in str(item.get("range", "")).split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, _, _ = part.partition("-")
                part = start.strip()
            try:
                port = int(part)
            except ValueError:
                continue
            if 1 <= port <= 65535 and port not in ports:
                ports.append(port)
    for fallback in (443, 80):
        if fallback not in ports:
            ports.append(fallback)
    return ports[:3]


def build_probe_targets(profile: dict[str, Any], max_targets: int = 8) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    ports = _tcp_ports(profile)
    hosts: list[str] = []

    for domain in profile.get("domains", []):
        if domain not in hosts:
            hosts.append(domain)

    for cidr in profile.get("cidrs", []):
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if network.version == 4 and network.prefixlen == 32:
            host = str(network.network_address)
            if host not in hosts:
                hosts.append(host)

    for host in hosts:
        for port in ports:
            targets.append({"host": host, "port": port})
            if len(targets) >= max_targets:
                return targets
    return targets


def metric_score(metric: dict[str, Any] | None, missing_penalty: float | None = 35.0) -> float | None:
    metric = metric or {}
    rtt = _float_or_none(metric.get("rtt_ms"))
    if rtt is None:
        return missing_penalty
    loss = _float_or_none(metric.get("loss_percent")) or 0
    jitter = _float_or_none(metric.get("jitter_ms")) or 0
    return rtt + loss * 40 + jitter * 1.5


def summarize_probe(raw: dict[str, Any]) -> dict[str, Any]:
    results = raw.get("results") or []
    values: list[float] = []
    losses: list[float] = []
    for result in results:
        rtt = _float_or_none(result.get("rtt_ms"))
        if rtt is not None:
            values.append(rtt)
        loss = _float_or_none(result.get("loss_percent"))
        if loss is not None:
            losses.append(loss)

    if values:
        rtt = round(statistics.mean(values), 1)
        jitter = round(statistics.pstdev(values), 1) if len(values) > 1 else 0.0
    else:
        rtt = None
        jitter = None

    return {
        "ok": bool(raw.get("ok", True)),
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "loss_percent": round(statistics.mean(losses), 1) if losses else None,
        "target_count": len(results),
        "raw": raw,
    }


async def _probe_node(node: dict[str, Any], targets: list[dict[str, Any]], samples: int) -> dict[str, Any]:
    if not targets:
        return {"ok": True, "rtt_ms": None, "jitter_ms": None, "loss_percent": None, "target_count": 0, "raw": {"results": []}}
    try:
        return summarize_probe(await probe_targets(node, targets, samples=samples))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rtt_ms": None, "jitter_ms": None, "loss_percent": None, "target_count": len(targets), "raw": {}}


def build_recommendation(selected: dict[str, Any], direct_score: float | None, probe_targets_count: int) -> dict[str, Any]:
    route_score = selected["route_score"]
    client_loss = _float_or_none(selected["client_measurement"].get("loss_percent")) or 0
    agent_loss = _float_or_none(selected["agent_measurement"].get("loss_percent")) or 0

    if direct_score is not None and probe_targets_count:
        delta = round(direct_score - route_score, 1)
        if delta >= 8 and client_loss <= 5 and agent_loss <= 10:
            return {"action": "accelerate", "confidence": "high", "delta_score": delta, "message": "加速路徑明顯優於直連"}
        if delta >= 3:
            return {"action": "accelerate", "confidence": "medium", "delta_score": delta, "message": "加速路徑略優於直連"}
        if delta <= -8:
            return {"action": "avoid", "confidence": "high", "delta_score": delta, "message": "目前直連較佳，不建議啟用"}
        return {"action": "optional", "confidence": "medium", "delta_score": delta, "message": "改善幅度不明顯，可依遊戲內 ping 決定"}

    if client_loss <= 5 and route_score < 120:
        return {"action": "accelerate", "confidence": "low", "delta_score": None, "message": "缺少遊戲 endpoint 直連資料，但節點入口品質可用"}
    return {"action": "avoid", "confidence": "medium", "delta_score": None, "message": "節點入口品質不足或資料不足"}


async def evaluate_route(
    profile: dict[str, Any],
    mode: str,
    nodes: list[dict[str, Any]],
    measurements: dict[str, dict],
    direct_measurement: dict[str, Any],
    probe_agents: bool = True,
    samples: int = 2,
    cached_agent_measurements: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = build_allowed_targets(profile, mode)
    probe_target_list = build_probe_targets(profile)
    ranked = rank_nodes(nodes, measurements)

    cached_agent_measurements = cached_agent_measurements or {}
    if probe_agents and probe_target_list:
        probe_results = await asyncio.gather(*[_probe_node(node, probe_target_list, samples) for node in ranked])
    else:
        probe_results = [cached_agent_measurements.get(node["id"]) or await _probe_node(node, [], samples) for node in ranked]

    candidates: list[dict[str, Any]] = []
    for node, agent_measurement in zip(ranked, probe_results):
        client_measurement = measurements.get(node["id"], {})
        client_score = node_score(node, client_measurement)
        agent_score = metric_score(agent_measurement, missing_penalty=45.0 if probe_target_list else 0.0) or 0.0
        route_score = round(client_score + agent_score, 3)
        candidates.append(
            {
                "node": node,
                "public_node_score": node.get("_score"),
                "client_measurement": client_measurement,
                "agent_measurement": agent_measurement,
                "route_score": route_score,
            }
        )

    selected = sorted(candidates, key=lambda item: item["route_score"])[0]
    direct_score = metric_score(direct_measurement, missing_penalty=None)
    recommendation = build_recommendation(selected, direct_score, len(probe_target_list))

    return {
        "targets": targets,
        "probe_targets": probe_target_list,
        "direct_measurement": direct_measurement or {},
        "direct_score": round(direct_score, 3) if direct_score is not None else None,
        "selected_node_id": selected["node"]["id"],
        "selected": selected,
        "candidates": candidates,
        "recommendation": recommendation,
    }
