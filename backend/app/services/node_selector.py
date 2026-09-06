from __future__ import annotations

import json
import time
from typing import Any


def _float_or_default(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def node_score(node: dict[str, Any], measurement: dict[str, Any] | None = None) -> float:
    """Lower score is better."""
    measurement = measurement or {}
    rtt = _float_or_default(measurement.get("rtt_ms"), 999)
    loss = _float_or_default(measurement.get("loss_percent"), 0)
    jitter = _float_or_default(measurement.get("jitter_ms"), 0)

    capacity = max(1, int(node.get("capacity") or 1))
    health_penalty = 0.0
    if node.get("last_health_json"):
        try:
            health = json.loads(node["last_health_json"])
            peers = int(health.get("peer_count") or 0)
            load = _float_or_default(health.get("load1"), 0)
            memory_used = _float_or_default(health.get("memory_used_percent"), 0)
            health_penalty += (peers / capacity) * 80
            health_penalty += load * 3
            if memory_used > 85:
                health_penalty += (memory_used - 85) * 2
        except Exception:
            health_penalty += 25
    else:
        health_penalty += 10

    last_health_at = int(node.get("last_health_at") or 0)
    if last_health_at:
        age = max(0, int(time.time()) - last_health_at)
        if age > 300:
            health_penalty += min(60, (age - 300) / 30)

    return rtt + loss * 40 + jitter * 1.5 + health_penalty


def rank_nodes(nodes: list[dict[str, Any]], measurements: dict[str, dict] | None = None) -> list[dict[str, Any]]:
    measurements = measurements or {}
    ranked: list[dict[str, Any]] = []
    for node in nodes:
        item = dict(node)
        item["_score"] = round(node_score(item, measurements.get(item["id"])), 3)
        ranked.append(item)
    return sorted(ranked, key=lambda n: n["_score"])


def select_node(nodes: list[dict[str, Any]], measurements: dict[str, dict] | None = None, desired_node_id: str | None = None) -> dict[str, Any]:
    enabled = [n for n in nodes if int(n.get("enabled", 0)) == 1]
    if not enabled:
        raise ValueError("no enabled nodes")
    if desired_node_id:
        for node in enabled:
            if node["id"] == desired_node_id:
                item = dict(node)
                item["_score"] = round(node_score(item, (measurements or {}).get(item["id"])), 3)
                return item
    return rank_nodes(enabled, measurements)[0]
