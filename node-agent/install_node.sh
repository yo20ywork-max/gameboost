#!/usr/bin/env bash
set -euo pipefail

WG_PORT="${WG_PORT:-51820}"
WG_INTERFACE="${WG_INTERFACE:-wg0}"
VPN_PREFIX="${VPN_PREFIX:-10.66.1}"
PUBLIC_ENDPOINT="${PUBLIC_ENDPOINT:-}"
AGENT_PORT="${AGENT_PORT:-8787}"
AGENT_SECRET="${AGENT_SECRET:-$(openssl rand -hex 32)}"

if [[ $EUID -ne 0 ]]; then
  echo "請用 sudo 執行"
  exit 1
fi

apt-get update
apt-get install -y wireguard wireguard-tools iptables-persistent python3 python3-venv python3-pip curl qrencode openssl

mkdir -p /etc/wireguard /opt/gameboost-node /var/lib/gameboost-node
chmod 700 /etc/wireguard

if [[ ! -f /etc/wireguard/server_private.key ]]; then
  wg genkey > /etc/wireguard/server_private.key
  chmod 600 /etc/wireguard/server_private.key
  wg pubkey < /etc/wireguard/server_private.key > /etc/wireguard/server_public.key
fi

SERVER_PRIVATE_KEY=$(cat /etc/wireguard/server_private.key)
SERVER_PUBLIC_KEY=$(cat /etc/wireguard/server_public.key)
WAN_IF=$(ip route list default | awk '{print $5; exit}')

cat > /etc/wireguard/${WG_INTERFACE}.conf <<EOF
[Interface]
Address = ${VPN_PREFIX}.1/24
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIVATE_KEY}
PostUp = iptables -t nat -A POSTROUTING -s ${VPN_PREFIX}.0/24 -o ${WAN_IF} -j MASQUERADE; iptables -A FORWARD -i ${WG_INTERFACE} -j ACCEPT; iptables -A FORWARD -o ${WG_INTERFACE} -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s ${VPN_PREFIX}.0/24 -o ${WAN_IF} -j MASQUERADE; iptables -D FORWARD -i ${WG_INTERFACE} -j ACCEPT; iptables -D FORWARD -o ${WG_INTERFACE} -j ACCEPT
EOF

sysctl -w net.ipv4.ip_forward=1
if ! grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf; then
  echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
fi

systemctl enable --now wg-quick@${WG_INTERFACE}

cp agent.py requirements.txt /opt/gameboost-node/
python3 -m venv /opt/gameboost-node/.venv
/opt/gameboost-node/.venv/bin/pip install -r /opt/gameboost-node/requirements.txt

cat > /etc/systemd/system/gameboost-node-agent.service <<EOF
[Unit]
Description=GameBoost Node Agent
After=network-online.target wg-quick@${WG_INTERFACE}.service
Wants=network-online.target

[Service]
Environment=WG_INTERFACE=${WG_INTERFACE}
Environment=AGENT_SECRET=${AGENT_SECRET}
Environment=GAMEBOOST_NODE_STATE=/var/lib/gameboost-node
WorkingDirectory=/opt/gameboost-node
ExecStart=/opt/gameboost-node/.venv/bin/uvicorn agent:app --host 0.0.0.0 --port ${AGENT_PORT}
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now gameboost-node-agent

if command -v ufw >/dev/null 2>&1; then
  ufw allow ${WG_PORT}/udp || true
  ufw allow ${AGENT_PORT}/tcp || true
fi

if [[ -z "${PUBLIC_ENDPOINT}" ]]; then
  PUBLIC_ENDPOINT=$(curl -fsS https://api.ipify.org || true)
fi

cat <<OUT

GameBoost node installed.

SERVER_PUBLIC_KEY=${SERVER_PUBLIC_KEY}
AGENT_SECRET=${AGENT_SECRET}
PUBLIC_ENDPOINT=${PUBLIC_ENDPOINT}
WG_PORT=${WG_PORT}
VPN_PREFIX=${VPN_PREFIX}
AGENT_URL=http://${PUBLIC_ENDPOINT}:${AGENT_PORT}
HEALTH_URL=http://${PUBLIC_ENDPOINT}:${AGENT_PORT}/health

請把這些資料加入 backend 的 /admin/nodes。
正式商用時不要讓 Agent 直接裸露公網，請至少限制來源 IP 或使用 private network / mTLS。
OUT
