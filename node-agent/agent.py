from __future__ import annotations

import os
import re
import socket
import statistics
import subprocess
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
AGENT_SECRET = os.getenv("AGENT_SECRET", "change-this-agent-secret")
STATE_DIR = Path(os.getenv("GAMEBOOST_NODE_STATE", "/var/lib/gameboost-node"))
STATE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="GameBoost Node Agent", version="2.0.0")

KEY_RE = re.compile(r"^[A-Za-z0-9+/]{42,44}={0,2}$")
CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}/32$")


class PeerUpsert(BaseModel):
    lease_id: str = Field(min_length=8, max_length=80)
    public_key: str
    allowed_ip: str


class PeerDelete(BaseModel):
    lease_id: str = Field(min_length=8, max_length=80)
    public_key: str


class ProbeTarget(BaseModel):
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)


class TcpProbeRequest(BaseModel):
    targets: list[ProbeTarget] = Field(min_length=1, max_length=64)
    samples: int = Field(default=3, ge=1, le=5)
    timeout_seconds: float = Field(default=1.5, ge=0.1, le=5.0)


def auth(x_agent_secret: str | None = Header(default=None)) -> None:
    if x_agent_secret != AGENT_SECRET:
        raise HTTPException(status_code=401, detail="bad agent secret")


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def validate_public_key(key: str) -> None:
    if not KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="invalid public key format")


def validate_allowed_ip(value: str) -> None:
    if not CIDR_RE.match(value):
        raise HTTPException(status_code=400, detail="allowed_ip must be IPv4 /32")
    octets = value.split("/", 1)[0].split(".")
    if any(int(o) > 255 for o in octets):
        raise HTTPException(status_code=400, detail="invalid IPv4 octet")


def read_memory() -> dict:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {}
    values: dict[str, int] = {}
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values[parts[0].rstrip(":")] = int(parts[1]) * 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return {}
    used_percent = round((1 - available / total) * 100, 1)
    return {"memory_total_bytes": total, "memory_available_bytes": available, "memory_used_percent": used_percent}


def read_interface_counters(interface: str) -> dict:
    base = Path("/sys/class/net") / interface / "statistics"
    try:
        return {
            "rx_bytes": int((base / "rx_bytes").read_text(encoding="utf-8").strip()),
            "tx_bytes": int((base / "tx_bytes").read_text(encoding="utf-8").strip()),
        }
    except Exception:
        return {}


def tcp_probe(host: str, port: int, timeout: float) -> float | None:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def measure_tcp_target(target: ProbeTarget, samples: int, timeout: float) -> dict:
    values: list[float] = []
    lost = 0
    for _ in range(samples):
        value = tcp_probe(target.host, target.port, timeout)
        if value is None:
            lost += 1
        else:
            values.append(value)
        time.sleep(0.05)
    if values:
        rtt = round(statistics.mean(values), 1)
        jitter = round(statistics.pstdev(values), 1) if len(values) > 1 else 0.0
    else:
        rtt = None
        jitter = None
    return {
        "host": target.host,
        "port": target.port,
        "rtt_ms": rtt,
        "jitter_ms": jitter,
        "loss_percent": round(lost / samples * 100, 1),
        "samples": samples,
    }


@app.get("/health")
def health() -> dict:
    peer_count = 0
    try:
        out = run(["wg", "show", WG_INTERFACE, "peers"])
        peer_count = 0 if not out else len(out.splitlines())
    except Exception:
        pass
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
    result = {
        "ok": True,
        "interface": WG_INTERFACE,
        "peer_count": peer_count,
        "load1": load1,
        "cpu_count": os.cpu_count() or 1,
        "time": int(time.time()),
    }
    result.update(read_memory())
    result.update(read_interface_counters(WG_INTERFACE))
    return result


@app.post("/peers/upsert", dependencies=[Depends(auth)])
def peers_upsert(req: PeerUpsert) -> dict:
    validate_public_key(req.public_key)
    validate_allowed_ip(req.allowed_ip)
    run(["wg", "set", WG_INTERFACE, "peer", req.public_key, "allowed-ips", req.allowed_ip])
    (STATE_DIR / f"{req.lease_id}.peer").write_text(f"{req.public_key}\n{req.allowed_ip}\n", encoding="utf-8")
    return {"ok": True, "lease_id": req.lease_id}


@app.post("/peers/delete", dependencies=[Depends(auth)])
def peers_delete(req: PeerDelete) -> dict:
    validate_public_key(req.public_key)
    run(["wg", "set", WG_INTERFACE, "peer", req.public_key, "remove"])
    state_file = STATE_DIR / f"{req.lease_id}.peer"
    if state_file.exists():
        state_file.unlink()
    return {"ok": True, "lease_id": req.lease_id}


@app.post("/probe/tcp", dependencies=[Depends(auth)])
def probe_tcp(req: TcpProbeRequest) -> dict:
    return {
        "ok": True,
        "interface": WG_INTERFACE,
        "time": int(time.time()),
        "results": [measure_tcp_target(target, req.samples, req.timeout_seconds) for target in req.targets],
    }
