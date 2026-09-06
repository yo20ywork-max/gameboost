from __future__ import annotations

import ipaddress
from typing import Any


def _valid_cidr(value: str) -> bool:
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


def build_allowed_targets(profile: dict[str, Any], mode: str) -> dict[str, Any]:
    """
    Returns route targets for the client.

    WireGuard client-side AllowedIPs is IP/CIDR based. Domains must be resolved
    by the desktop client shortly before connect. This is deliberate: many game
    endpoints are geo-DNS based, so resolving from the player's network gives a
    more useful route set than resolving in the backend region.
    """
    if mode == "auto":
        mode = profile.get("recommended_mode", "full")

    if mode == "full" or profile.get("id") == "generic-full-tunnel":
        return {
            "mode": "full",
            "allowed_ips": ["0.0.0.0/0"],
            "domains": [],
            "ports": profile.get("ports", []),
            "notes": "Full tunnel mode routes all IPv4 traffic through the selected node. This works for any game but also routes normal browsing while connected.",
        }

    cidrs = []
    for value in profile.get("cidrs", []):
        if _valid_cidr(value):
            cidrs.append(value)

    domains = profile.get("domains", [])
    if not cidrs and not domains:
        return {
            "mode": "full",
            "allowed_ips": ["0.0.0.0/0"],
            "domains": [],
            "ports": profile.get("ports", []),
            "notes": "Split tunnel profile has no usable targets, so GameBoost falls back to full tunnel for universal compatibility.",
        }

    return {
        "mode": "split",
        "allowed_ips": cidrs,
        "domains": domains,
        "ports": profile.get("ports", []),
        "notes": "Split tunnel mode routes only known game targets. Domains are resolved by the desktop client at connection time.",
    }
