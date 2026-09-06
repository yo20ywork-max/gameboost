from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import db, init_db
from .deps import get_current_user, require_admin
from .schemas import LoginRequest, LoginResponse, NodeIn, LatencyReportIn, RoutePlanRequest, RouteEvaluateRequest, ProbeRunRequest, LeaseStartRequest, LeaseStopRequest
from .security import sign_token, verify_password
from .services.game_profiles import get_profile, load_profiles
from .services.ip_allocator import allocate_ip
from .services.node_agent import delete_peer, fetch_health, probe_targets, upsert_peer
from .services.node_selector import select_node
from .services.probe_store import create_probe_run, finish_probe_run, latest_probe_measurements, latest_probe_rows, probe_scoreboard, save_probe_result
from .services.route_evaluator import build_probe_targets, evaluate_route as evaluate_acceleration_route, summarize_probe
from .services.route_planner import build_allowed_targets
from .settings import DEFAULT_LEASE_SECONDS

app = FastAPI(title="GameBoost API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "gameboost-backend", "time": int(time.time())}


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest) -> dict[str, Any]:
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (req.email.lower().strip(),)).fetchone()
    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if row["disabled"]:
        raise HTTPException(status_code=403, detail="account disabled")
    token = sign_token({"sub": row["id"], "email": row["email"], "role": row["role"]})
    return {
        "token": token,
        "email": row["email"],
        "role": row["role"],
        "plan": row["plan"],
        "plan_expires_at": row["plan_expires_at"],
    }


@app.get("/games")
def games(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    return load_profiles()


@app.get("/nodes")
def nodes(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    with db() as con:
        rows = con.execute(
            "SELECT id,name,region,country,city,public_endpoint,wg_port,wg_public_key,vpn_prefix,mtu,health_url,capacity,enabled,last_health_json,last_health_at FROM nodes WHERE enabled=1 ORDER BY region, city, name"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/admin/nodes")
def admin_add_node(req: NodeIn, admin: dict = Depends(require_admin)) -> dict[str, Any]:
    now = int(time.time())
    with db() as con:
        con.execute(
            """
            INSERT INTO nodes(id,name,region,country,city,public_endpoint,wg_port,wg_public_key,vpn_prefix,mtu,agent_url,agent_secret,health_url,capacity,enabled,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, region=excluded.region, country=excluded.country, city=excluded.city,
                public_endpoint=excluded.public_endpoint, wg_port=excluded.wg_port, wg_public_key=excluded.wg_public_key,
                vpn_prefix=excluded.vpn_prefix, mtu=excluded.mtu, agent_url=excluded.agent_url,
                agent_secret=excluded.agent_secret, health_url=excluded.health_url,
                capacity=excluded.capacity, enabled=excluded.enabled
            """,
            (
                req.id, req.name, req.region, req.country, req.city, req.public_endpoint, req.wg_port,
                req.wg_public_key, req.vpn_prefix, req.mtu, req.agent_url, req.agent_secret, req.health_url,
                req.capacity, 1 if req.enabled else 0, now,
            ),
        )
    return {"ok": True, "node_id": req.id}


@app.post("/admin/nodes/refresh-health")
async def admin_refresh_node_health(admin: dict = Depends(require_admin)) -> dict[str, Any]:
    now = int(time.time())
    with db() as con:
        rows = con.execute("SELECT * FROM nodes WHERE enabled=1 ORDER BY region, city, name").fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        node = dict(row)
        try:
            health = await fetch_health(node)
            with db() as con:
                con.execute(
                    "UPDATE nodes SET last_health_json=?, last_health_at=? WHERE id=?",
                    (json.dumps(health, ensure_ascii=False), now, node["id"]),
                )
            results.append({"node_id": node["id"], "ok": True, "health": health})
        except Exception as exc:
            results.append({"node_id": node["id"], "ok": False, "error": str(exc)})
    return {"ok": True, "checked": len(results), "results": results}


@app.get("/admin/route-metrics")
def admin_route_metrics(limit: int = Query(default=50, ge=1, le=500), admin: dict = Depends(require_admin)) -> list[dict[str, Any]]:
    with db() as con:
        rows = con.execute(
            """
            SELECT id,user_id,game_id,requested_mode,resolved_mode,selected_node_id,selected_score,
            measurements_json,direct_measurement_json,agent_measurements_json,targets_json,decision_reason,created_at
            FROM route_metrics
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/admin/probes/run")
async def admin_run_probes(req: ProbeRunRequest, admin: dict = Depends(require_admin)) -> dict[str, Any]:
    profiles = load_profiles()
    if req.all_games:
        selected_profiles = profiles
    else:
        requested = set(req.game_ids)
        selected_profiles = [profile for profile in profiles if profile.get("id") in requested]
    if not selected_profiles:
        raise HTTPException(status_code=400, detail="no game profiles selected")

    with db() as con:
        rows = con.execute("SELECT * FROM nodes WHERE enabled=1 ORDER BY region, city, name").fetchall()
    node_rows = [dict(row) for row in rows]
    if req.node_ids:
        allowed_nodes = set(req.node_ids)
        node_rows = [node for node in node_rows if node["id"] in allowed_nodes]
    if not node_rows:
        raise HTTPException(status_code=503, detail="no enabled nodes")

    output: list[dict[str, Any]] = []
    for profile in selected_profiles:
        targets = build_probe_targets(profile)
        if not targets:
            output.append({"game_id": profile["id"], "ok": False, "error": "profile has no probe targets", "results": []})
            continue
        with db() as con:
            run_id = create_probe_run(con, profile["id"], targets, req.samples, admin["id"])

        results: list[dict[str, Any]] = []
        for node in node_rows:
            try:
                summary = summarize_probe(await probe_targets(node, targets, samples=req.samples))
                summary["ok"] = True
            except Exception as exc:
                summary = {"ok": False, "error": str(exc), "rtt_ms": None, "loss_percent": None, "jitter_ms": None, "target_count": len(targets), "raw": {}}
            with db() as con:
                save_probe_result(con, run_id, node["id"], summary)
            results.append({"node_id": node["id"], "summary": summary})

        with db() as con:
            finish_probe_run(con, run_id)
        output.append({"game_id": profile["id"], "run_id": run_id, "targets": targets, "results": results})
    return {"ok": True, "games_checked": len(output), "nodes_checked": len(node_rows), "runs": output}


@app.get("/admin/probes/latest")
def admin_latest_probes(game_id: str, limit: int = Query(default=100, ge=1, le=500), admin: dict = Depends(require_admin)) -> dict[str, Any]:
    with db() as con:
        rows = latest_probe_rows(con, game_id, limit)
    return {"game_id": game_id, "results": rows}


@app.get("/admin/probes/scoreboard")
def admin_probe_scoreboard(game_id: str, max_age_seconds: int = Query(default=3600, ge=60, le=604800), admin: dict = Depends(require_admin)) -> dict[str, Any]:
    with db() as con:
        rows = probe_scoreboard(con, game_id, max_age_seconds)
    return {"game_id": game_id, "max_age_seconds": max_age_seconds, "scoreboard": rows}


@app.post("/telemetry/latency")
def report_latency(req: LatencyReportIn, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    with db() as con:
        con.execute(
            "INSERT INTO latency_reports(user_id,node_id,rtt_ms,loss_percent,jitter_ms,created_at) VALUES(?,?,?,?,?,?)",
            (user["id"], req.node_id, req.rtt_ms, req.loss_percent, req.jitter_ms, int(time.time())),
        )
    return {"ok": True}


@app.post("/routes/plan")
def route_plan(req: RoutePlanRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    profile = get_profile(req.game_id)
    if not profile:
        raise HTTPException(status_code=404, detail="game profile not found")
    with db() as con:
        rows = con.execute("SELECT * FROM nodes WHERE enabled=1").fetchall()
    node_rows = [dict(r) for r in rows]
    if not node_rows:
        raise HTTPException(status_code=503, detail="no enabled nodes")
    node = select_node(node_rows, req.measurements)
    targets = build_allowed_targets(profile, req.mode)
    record_route_metric(user, profile, req.mode, node, req.measurements, req.direct_measurement, targets, "lowest_weighted_score")
    return {
        "game": profile,
        "selected_node_id": node["id"],
        "node": public_node(node),
        "targets": targets,
        "decision": {
            "reason": "lowest_weighted_score",
            "score": node.get("_score"),
            "inputs": ["client_rtt", "client_loss", "client_jitter", "node_peer_load", "node_system_load", "node_health_age"],
        },
    }


@app.post("/routes/evaluate")
async def route_evaluate(req: RouteEvaluateRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    profile = get_profile(req.game_id)
    if not profile:
        raise HTTPException(status_code=404, detail="game profile not found")
    with db() as con:
        rows = con.execute("SELECT * FROM nodes WHERE enabled=1").fetchall()
    node_rows = [dict(r) for r in rows]
    if not node_rows:
        raise HTTPException(status_code=503, detail="no enabled nodes")

    cached_agent_measurements: dict[str, dict[str, Any]] = {}
    if req.use_probe_cache:
        with db() as con:
            cached_agent_measurements = latest_probe_measurements(con, profile["id"], req.cache_max_age_seconds)

    evaluation = await evaluate_acceleration_route(
        profile,
        req.mode,
        node_rows,
        req.measurements,
        req.direct_measurement,
        probe_agents=req.probe_agents,
        samples=req.samples,
        cached_agent_measurements=cached_agent_measurements,
    )
    selected = evaluation["selected"]
    agent_measurements = {item["node"]["id"]: item["agent_measurement"] for item in evaluation["candidates"]}
    record_route_metric(
        user,
        profile,
        req.mode,
        selected["node"],
        req.measurements,
        req.direct_measurement,
        evaluation["targets"],
        "multi_hop_route_evaluation",
        agent_measurements,
    )

    return {
        "game": profile,
        "selected_node_id": evaluation["selected_node_id"],
        "node": public_node(selected["node"]),
        "targets": evaluation["targets"],
        "direct_measurement": evaluation["direct_measurement"],
        "direct_score": evaluation["direct_score"],
        "probe_targets": evaluation["probe_targets"],
        "cache_used": bool(cached_agent_measurements) and not req.probe_agents,
        "recommendation": evaluation["recommendation"],
        "decision": {
            "reason": "multi_hop_route_evaluation",
            "score": selected["route_score"],
            "inputs": [
                "client_to_node_rtt",
                "client_to_node_loss",
                "client_to_node_jitter",
                "node_to_game_rtt",
                "node_to_game_loss",
                "node_health_load",
                "direct_game_probe",
            ],
        },
        "candidates": [
            {
                "node": public_node(item["node"]),
                "route_score": item["route_score"],
                "client_measurement": item["client_measurement"],
                "agent_measurement": item["agent_measurement"],
            }
            for item in evaluation["candidates"]
        ],
    }


@app.post("/lease/start")
async def lease_start(req: LeaseStartRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    now = int(time.time())
    if user["plan_expires_at"] and int(user["plan_expires_at"]) < now:
        raise HTTPException(status_code=402, detail="plan expired")

    profile = get_profile(req.game_id)
    if not profile:
        raise HTTPException(status_code=404, detail="game profile not found")

    with db() as con:
        rows = con.execute("SELECT * FROM nodes WHERE enabled=1").fetchall()
        if not rows:
            raise HTTPException(status_code=503, detail="no enabled nodes")
        node = select_node([dict(r) for r in rows], req.measurements, req.desired_node_id)
        client_vpn_ip = allocate_ip(con, node["id"], node["vpn_prefix"])
        lease_id = str(uuid.uuid4())
        targets = build_allowed_targets(profile, req.mode)
        decision_reason = "desired_node_id" if req.desired_node_id else "lowest_weighted_score"
        con.execute(
            """
            INSERT INTO leases(id,user_id,node_id,game_id,client_public_key,client_vpn_ip,allowed_ips_json,mode,status,created_at,expires_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                lease_id, user["id"], node["id"], profile["id"], req.client_public_key, client_vpn_ip,
                json.dumps(targets, ensure_ascii=False), targets["mode"], "active", now, now + DEFAULT_LEASE_SECONDS,
            ),
        )
        insert_route_metric(con, user, profile, req.mode, node, req.measurements, req.direct_measurement, targets, decision_reason)

    try:
        await upsert_peer(node, req.client_public_key, client_vpn_ip, lease_id)
    except Exception as exc:
        with db() as con:
            con.execute("UPDATE leases SET status='agent_failed', stopped_at=? WHERE id=?", (int(time.time()), lease_id))
        raise HTTPException(status_code=502, detail=f"node agent failed: {exc}") from exc

    return {
        "lease_id": lease_id,
        "expires_at": now + DEFAULT_LEASE_SECONDS,
        "game": profile,
        "node": public_node(node),
        "wireguard": {
            "address": f"{client_vpn_ip}/32",
            "dns": profile.get("dns", ["1.1.1.1"]),
            "peer_public_key": node["wg_public_key"],
            "endpoint": f"{node['public_endpoint']}:{node['wg_port']}",
            "mtu": node["mtu"],
            "persistent_keepalive": 15,
            "targets": targets,
        },
    }


@app.post("/lease/stop")
async def lease_stop(req: LeaseStopRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    with db() as con:
        row = con.execute(
            "SELECT leases.*, nodes.agent_url, nodes.agent_secret FROM leases JOIN nodes ON nodes.id=leases.node_id WHERE leases.id=? AND leases.user_id=?",
            (req.lease_id, user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="lease not found")
        con.execute("UPDATE leases SET status='stopped', stopped_at=? WHERE id=?", (int(time.time()), req.lease_id))
        node = con.execute("SELECT * FROM nodes WHERE id=?", (row["node_id"],)).fetchone()
    if node:
        try:
            await delete_peer(dict(node), row["client_public_key"], req.lease_id)
        except Exception:
            pass
    return {"ok": True}


def public_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node["id"], "name": node["name"], "region": node["region"], "country": node["country"],
        "city": node["city"], "public_endpoint": node["public_endpoint"], "wg_port": node["wg_port"],
        "wg_public_key": node["wg_public_key"], "vpn_prefix": node["vpn_prefix"], "mtu": node["mtu"],
        "health_url": node.get("health_url"), "capacity": node.get("capacity"), "last_health_at": node.get("last_health_at"),
        "score": node.get("_score"),
    }


def record_route_metric(
    user: dict[str, Any],
    profile: dict[str, Any],
    requested_mode: str,
    node: dict[str, Any],
    measurements: dict[str, dict],
    direct_measurement: dict[str, Any],
    targets: dict[str, Any],
    decision_reason: str,
    agent_measurements: dict[str, Any] | None = None,
) -> None:
    with db() as con:
        insert_route_metric(con, user, profile, requested_mode, node, measurements, direct_measurement, targets, decision_reason, agent_measurements)


def insert_route_metric(
    con,
    user: dict[str, Any],
    profile: dict[str, Any],
    requested_mode: str,
    node: dict[str, Any],
    measurements: dict[str, dict],
    direct_measurement: dict[str, Any],
    targets: dict[str, Any],
    decision_reason: str,
    agent_measurements: dict[str, Any] | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO route_metrics(user_id,game_id,requested_mode,resolved_mode,selected_node_id,selected_score,measurements_json,direct_measurement_json,agent_measurements_json,targets_json,decision_reason,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            user["id"],
            profile["id"],
            requested_mode,
            targets["mode"],
            node["id"],
            node.get("_score"),
            json.dumps(measurements or {}, ensure_ascii=False),
            json.dumps(direct_measurement or {}, ensure_ascii=False),
            json.dumps(agent_measurements or {}, ensure_ascii=False),
            json.dumps(targets, ensure_ascii=False),
            decision_reason,
            int(time.time()),
        ),
    )
