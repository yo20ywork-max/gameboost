from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import WG_CONFIG_PATH, TUNNEL_NAME, ensure_dirs
from .game_profiles import normalize_allowed_ips


def program_files_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "WireGuard")
    return candidates


def find_exe(name: str) -> Path | None:
    for d in program_files_candidates():
        p = d / name
        if p.exists():
            return p
    for part in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(part) / name
        if p.exists():
            return p
    return None


def require_wireguard() -> tuple[Path, Path]:
    wg_exe = find_exe("wg.exe")
    wireguard_exe = find_exe("wireguard.exe")
    if not wg_exe or not wireguard_exe:
        raise RuntimeError("找不到 WireGuard for Windows。請先安裝官方 WireGuard，再重新開啟本 App。")
    return wg_exe, wireguard_exe


def run_capture(cmd: list[str], input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def generate_keypair() -> tuple[str, str]:
    wg_exe, _ = require_wireguard()
    private_key = run_capture([str(wg_exe), "genkey"])
    public_key = run_capture([str(wg_exe), "pubkey"], input_text=private_key + "\n")
    return private_key, public_key


def build_config(private_key: str, lease: dict) -> str:
    wg = lease["wireguard"]
    targets = wg["targets"]
    allowed_ips = normalize_allowed_ips(targets.get("allowed_ips", []), targets.get("domains", []))
    if not allowed_ips:
        allowed_ips = ["0.0.0.0/0"]
    dns = ", ".join(wg.get("dns") or ["1.1.1.1"])
    return f"""[Interface]
PrivateKey = {private_key}
Address = {wg['address']}
DNS = {dns}
MTU = {wg.get('mtu', 1280)}

[Peer]
PublicKey = {wg['peer_public_key']}
Endpoint = {wg['endpoint']}
AllowedIPs = {', '.join(allowed_ips)}
PersistentKeepalive = {wg.get('persistent_keepalive', 15)}
"""


def write_config(config_text: str) -> Path:
    ensure_dirs()
    WG_CONFIG_PATH.write_text(config_text, encoding="utf-8")
    return WG_CONFIG_PATH


def install_tunnel_service(config_path: Path = WG_CONFIG_PATH) -> None:
    _, wireguard_exe = require_wireguard()
    uninstall_tunnel_service(ignore_errors=True)
    run_capture([str(wireguard_exe), "/installtunnelservice", str(config_path)])


def uninstall_tunnel_service(ignore_errors: bool = False) -> None:
    _, wireguard_exe = require_wireguard()
    proc = subprocess.run([str(wireguard_exe), "/uninstalltunnelservice", TUNNEL_NAME], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 and not ignore_errors:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False
