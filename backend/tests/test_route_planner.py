from app.services.route_planner import build_allowed_targets


def test_full_tunnel():
    p = {"id": "x", "recommended_mode": "full", "cidrs": ["203.0.113.1/32"]}
    result = build_allowed_targets(p, "auto")
    assert result["mode"] == "full"
    assert result["allowed_ips"] == ["0.0.0.0/0"]


def test_split_tunnel_filters_bad_cidr():
    p = {"id": "x", "recommended_mode": "split", "cidrs": ["203.0.113.1/32", "bad"]}
    result = build_allowed_targets(p, "auto")
    assert result["mode"] == "split"
    assert result["allowed_ips"] == ["203.0.113.1/32"]
