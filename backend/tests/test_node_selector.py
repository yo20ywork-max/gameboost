from app.services.node_selector import rank_nodes, select_node


def test_select_node_uses_client_measurements():
    nodes = [
        {"id": "slow", "enabled": 1, "capacity": 100},
        {"id": "fast", "enabled": 1, "capacity": 100},
    ]
    selected = select_node(
        nodes,
        {
            "slow": {"rtt_ms": 90, "loss_percent": 0, "jitter_ms": 1},
            "fast": {"rtt_ms": 20, "loss_percent": 0, "jitter_ms": 1},
        },
    )
    assert selected["id"] == "fast"
    assert selected["_score"] < 40


def test_rank_nodes_penalizes_packet_loss():
    nodes = [
        {"id": "low-loss", "enabled": 1, "capacity": 100},
        {"id": "lossy", "enabled": 1, "capacity": 100},
    ]
    ranked = rank_nodes(
        nodes,
        {
            "low-loss": {"rtt_ms": 40, "loss_percent": 0, "jitter_ms": 1},
            "lossy": {"rtt_ms": 20, "loss_percent": 5, "jitter_ms": 1},
        },
    )
    assert [node["id"] for node in ranked] == ["low-loss", "lossy"]
