# GameBoost — Network Route Evaluation & Tunnel Prototype

A multi-component networking project combining a FastAPI control plane, a Windows desktop client, and a Linux WireGuard node agent.

**By Daniel Tang.** The project explores how to compare direct and node-assisted routes, provision temporary tunnel leases, and present route decisions in a desktop application.

## Implementation

| Component | Responsibilities |
|---|---|
| [`backend`](backend) | Authentication, SQLite persistence, game profiles, node ranking, route evaluation, probe caching, and tunnel leases |
| [`desktop`](desktop) | PySide6 interface, API client, latency measurements, key generation, and WireGuard for Windows integration |
| [`node-agent`](node-agent) | Authenticated peer management, health reporting, and TCP probes on a Linux node |
| [`infra`](infra) | Development Compose configuration and example network configuration |
| [`docs`](docs) | Routing design, profile maintenance, packaging, and operational drafts |

Routing supports a full IPv4 tunnel (`0.0.0.0/0`) or profile-based IP/CIDR routes. Route scores combine available measurements; they are estimates rather than proof of in-game latency improvement. Sample profiles require maintenance and real network evaluation.

## Run the backend locally

Use Python 3.10 or newer; Python 3.11+ is recommended for the provided packaging workflow.

```bash
cd backend
python -m venv .venv
# Activate the virtual environment for your shell.
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The seed script creates local demonstration accounts:

| Account | Demo password |
|---|---|
| `demo@example.com` | `demo123456` |
| `admin@example.com` | `change-this-admin-password` |

These are intentional test credentials, not private account credentials. Keep this seeded backend on loopback. The prototype includes development signing secrets and administrative demo access; replace these and review authentication, authorization, and network boundaries before any deployment.

## Windows client

Follow the [desktop README](desktop/README.md) to install the editable Python package and launch it. Login and route evaluation can be explored against the local backend. Creating a real tunnel additionally requires [WireGuard for Windows](https://www.wireguard.com/install/), a configured node, and administrator privileges.

`GameBoost-OneClick.cmd` is an optional launcher for an already packaged desktop executable; it requests elevation and starts a local demo backend. It is not required for code review or automated tests.

## Node deployment boundary

`node-agent/install_node.sh` changes WireGuard, IP forwarding, NAT, and system services. Inspect and adapt it for a dedicated test node before use. Do not expose an agent with example credentials. The installer and infrastructure examples are not executed by the test suite.

## Evidence and limitations

See [validation scope](VALIDATION.md) for the recorded test result. Existing tests cover route planning, loss-aware ranking, probe evaluation, and backend API behavior using synthetic data and mocked agent calls.

The project has not established measured gameplay improvements, universal game compatibility, anti-cheat certification, or store approval. Original `desktop/package/store-assets` images are promotional mockups with sample values, not benchmark evidence; some contain missing font glyphs. The current transport work concerns IPv4 and does not establish IPv6 routing or leak protection.

See [publication notes](PUBLICATION.md). Third-party components include FastAPI, Pydantic, PySide6, and WireGuard, each with its own licensing terms.

[Daniel Tang's software and AI portfolio](https://github.com/yo20ywork-max/research-portfolio)
