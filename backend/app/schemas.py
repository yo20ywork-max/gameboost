from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str
    role: str
    plan: str
    plan_expires_at: int


class NodeIn(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{2,48}$")
    name: str
    region: str
    country: str
    city: str
    public_endpoint: str
    wg_port: int = 51820
    wg_public_key: str
    vpn_prefix: str = "10.66.1"
    mtu: int = 1280
    agent_url: str
    agent_secret: str
    health_url: str
    capacity: int = 500
    enabled: bool = True


class LatencyReportIn(BaseModel):
    node_id: str
    rtt_ms: float | None = None
    loss_percent: float | None = None
    jitter_ms: float | None = None


class RoutePlanRequest(BaseModel):
    game_id: str
    mode: Literal["auto", "full", "split"] = "auto"
    measurements: dict[str, dict] = Field(default_factory=dict)
    direct_measurement: dict = Field(default_factory=dict)


class RouteEvaluateRequest(RoutePlanRequest):
    probe_agents: bool = True
    samples: int = Field(default=2, ge=1, le=5)
    use_probe_cache: bool = True
    cache_max_age_seconds: int = Field(default=900, ge=0, le=86400)


class ProbeRunRequest(BaseModel):
    game_ids: list[str] = Field(default_factory=list)
    all_games: bool = False
    node_ids: list[str] = Field(default_factory=list)
    samples: int = Field(default=2, ge=1, le=5)


class LeaseStartRequest(BaseModel):
    game_id: str
    mode: Literal["auto", "full", "split"] = "auto"
    client_public_key: str
    desired_node_id: str | None = None
    client_os: str = "windows"
    measurements: dict[str, dict] = Field(default_factory=dict)
    direct_measurement: dict = Field(default_factory=dict)


class LeaseStopRequest(BaseModel):
    lease_id: str
