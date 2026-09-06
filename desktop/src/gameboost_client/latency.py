from __future__ import annotations

import socket
import statistics
import time
from typing import Any
from urllib.parse import urlparse


def tcp_probe(host: str, port: int, timeout: float = 1.5) -> float | None:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def measure_health_url(url: str, samples: int = 4) -> dict:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    values: list[float] = []
    lost = 0
    for _ in range(samples):
        ms = tcp_probe(host or "", port)
        if ms is None:
            lost += 1
        else:
            values.append(ms)
        time.sleep(0.08)
    if values:
        rtt = round(statistics.mean(values), 1)
        jitter = round(statistics.pstdev(values), 1) if len(values) > 1 else 0.0
    else:
        rtt, jitter = None, None
    return {
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "loss_percent": round(lost / samples * 100, 1),
    }


def _candidate_tcp_ports(profile: dict[str, Any]) -> list[int]:
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


def build_profile_probe_targets(profile: dict[str, Any], max_targets: int = 8) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    ports = _candidate_tcp_ports(profile)
    for domain in profile.get("domains", []):
        for port in ports:
            targets.append({"host": domain, "port": port})
            if len(targets) >= max_targets:
                return targets
    return targets


def measure_tcp_targets(targets: list[dict[str, Any]], samples: int = 2) -> dict[str, Any]:
    all_values: list[float] = []
    lost = 0
    total = 0
    results: list[dict[str, Any]] = []
    for target in targets:
        host = str(target.get("host", ""))
        port = int(target.get("port", 0))
        values: list[float] = []
        target_lost = 0
        for _ in range(samples):
            total += 1
            ms = tcp_probe(host, port)
            if ms is None:
                lost += 1
                target_lost += 1
            else:
                values.append(ms)
                all_values.append(ms)
            time.sleep(0.05)
        results.append(
            {
                "host": host,
                "port": port,
                "rtt_ms": round(statistics.mean(values), 1) if values else None,
                "loss_percent": round(target_lost / samples * 100, 1),
            }
        )
    if all_values:
        rtt = round(statistics.mean(all_values), 1)
        jitter = round(statistics.pstdev(all_values), 1) if len(all_values) > 1 else 0.0
    else:
        rtt, jitter = None, None
    return {
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "loss_percent": round(lost / total * 100, 1) if total else None,
        "target_count": len(targets),
        "results": results,
    }
