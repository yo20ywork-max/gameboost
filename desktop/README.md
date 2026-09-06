# GameBoost — Windows Desktop Client

A PySide6 client for the GameBoost backend. It loads game profiles and nodes, measures routes, requests an evaluation, obtains a tunnel lease, and integrates with the official WireGuard for Windows service.

## Development setup

From this directory, using Python 3.10+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m gameboost_client.main
```

Start the backend separately using the [root README](../README.md). The default API address is `http://127.0.0.1:8080`; demonstration credentials are prefilled in the current interface.

## Tunnel behavior

Full mode uses `AllowedIPs = 0.0.0.0/0`. Split mode uses profile CIDRs plus resolved domain addresses. Real connection requires a configured Linux node and WireGuard for Windows; managing the tunnel service requires administrator privileges. Route evaluation alone does not establish actual game performance.

## Packaging

Inspect `package/build_windows.ps1`, then run it from the package directory to build with PyInstaller. Inno Setup and MSIX files are release templates requiring your own publisher and signing configuration. No private signing material is included.

The assets in `package/store-assets/` are original promotional mockups, not recorded test sessions. See the repository [validation record](../VALIDATION.md) for the checks performed on this snapshot.
