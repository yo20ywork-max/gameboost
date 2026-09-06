from __future__ import annotations

import ipaddress
from sqlite3 import Connection


def allocate_ip(con: Connection, node_id: str, vpn_prefix: str) -> str:
    """Allocate an IPv4 address inside a /24 prefix like 10.66.1."""
    network = ipaddress.ip_network(f"{vpn_prefix}.0/24", strict=False)
    used_rows = con.execute(
        "SELECT client_vpn_ip FROM leases WHERE node_id=? AND status='active'",
        (node_id,),
    ).fetchall()
    used = {row["client_vpn_ip"] for row in used_rows}
    for host in list(network.hosts())[9:240]:
        ip = str(host)
        if ip not in used:
            return ip
    raise RuntimeError(f"no free IPs left in {network}")
