import asyncio

from app.services.route_evaluator import build_probe_targets, evaluate_route


def test_build_probe_targets_uses_domains_and_host_cidrs():
    profile = {
        "domains": ["game.example"],
        "cidrs": ["203.0.113.10/32", "203.0.113.0/24", "bad"],
        "ports": [{"proto": "tcp", "range": "443,5000-5005"}, {"proto": "udp", "range": "7000-8000"}],
    }
    targets = build_probe_targets(profile, max_targets=4)
    assert targets == [
        {"host": "game.example", "port": 443},
        {"host": "game.example", "port": 5000},
        {"host": "game.example", "port": 80},
        {"host": "203.0.113.10", "port": 443},
    ]


def test_evaluate_route_ranks_multi_hop_score():
    profile = {"id": "generic-full-tunnel", "recommended_mode": "full", "domains": [], "ports": []}
    nodes = [
        {"id": "slow", "enabled": 1, "capacity": 100},
        {"id": "fast", "enabled": 1, "capacity": 100},
    ]
    measurements = {
        "slow": {"rtt_ms": 80, "loss_percent": 0, "jitter_ms": 1},
        "fast": {"rtt_ms": 20, "loss_percent": 0, "jitter_ms": 1},
    }
    result = asyncio.run(evaluate_route(profile, "auto", nodes, measurements, {"rtt_ms": 70, "loss_percent": 0}, probe_agents=False))
    assert result["selected_node_id"] == "fast"
    assert result["selected"]["route_score"] < result["candidates"][1]["route_score"]


def test_evaluate_route_uses_node_to_game_probe(monkeypatch):
    async def fake_probe_targets(node, targets, samples=2):
        rtt = 120 if node["id"] == "near-player" else 20
        return {"ok": True, "results": [{"host": "game.example", "port": 443, "rtt_ms": rtt, "loss_percent": 0}]}

    monkeypatch.setattr("app.services.route_evaluator.probe_targets", fake_probe_targets)
    profile = {"id": "game", "recommended_mode": "split", "domains": ["game.example"], "ports": [{"proto": "tcp", "range": "443"}]}
    nodes = [
        {"id": "near-player", "enabled": 1, "capacity": 100},
        {"id": "near-game", "enabled": 1, "capacity": 100},
    ]
    measurements = {
        "near-player": {"rtt_ms": 10, "loss_percent": 0, "jitter_ms": 1},
        "near-game": {"rtt_ms": 40, "loss_percent": 0, "jitter_ms": 1},
    }
    result = asyncio.run(evaluate_route(profile, "auto", nodes, measurements, {"rtt_ms": 100, "loss_percent": 0}, probe_agents=True))
    assert result["selected_node_id"] == "near-game"
    assert result["recommendation"]["action"] in {"accelerate", "optional"}
