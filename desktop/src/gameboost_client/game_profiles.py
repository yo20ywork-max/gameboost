from __future__ import annotations

import ipaddress
import socket
from typing import Iterable


def resolve_domains_to_cidrs(domains: Iterable[str], max_ips: int = 128) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for domain in domains:
        try:
            infos = socket.getaddrinfo(domain, None, family=socket.AF_INET)
        except OSError:
            continue
        for info in infos:
            ip = info[4][0]
            cidr = f"{ip}/32"
            if cidr not in seen:
                seen.add(cidr)
                results.append(cidr)
            if len(results) >= max_ips:
                return results
    return results


def normalize_allowed_ips(server_allowed_ips: list[str], domains: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in server_allowed_ips:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            continue
        text = str(network)
        if text not in seen:
            out.append(text)
            seen.add(text)
    for cidr in resolve_domains_to_cidrs(domains):
        if cidr not in seen:
            out.append(cidr)
            seen.add(cidr)
    return out
