# 加速節點部署

## 節點地點建議

台灣玩家優先：

| 遊戲伺服器 | 節點城市 |
|---|---|
| 日服 | Tokyo |
| 韓服 | Seoul |
| 港服 | Hong Kong |
| 東南亞 | Singapore |
| 美西 | Los Angeles / San Jose / Seattle |

## 新增節點到後端

先登入取得 token：

```bash
TOKEN=$(curl -s http://127.0.0.1:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-this-admin-password"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
```

新增節點：

```bash
curl -X POST http://127.0.0.1:8080/admin/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "id":"tokyo-01",
    "name":"Tokyo 01",
    "region":"apac",
    "country":"JP",
    "city":"Tokyo",
    "public_endpoint":"YOUR_NODE_PUBLIC_IP",
    "wg_port":51820,
    "wg_public_key":"SERVER_PUBLIC_KEY_FROM_INSTALL_SCRIPT",
    "vpn_prefix":"10.66.1",
    "mtu":1280,
    "agent_url":"http://YOUR_NODE_PUBLIC_IP:8787",
    "agent_secret":"AGENT_SECRET_FROM_INSTALL_SCRIPT",
    "health_url":"http://YOUR_NODE_PUBLIC_IP:8787/health",
    "capacity":500,
    "enabled":true
  }'
```

同步節點健康資料：

```bash
curl -X POST http://127.0.0.1:8080/admin/nodes/refresh-health \
  -H "Authorization: Bearer $TOKEN"
```

node-agent 也提供受 `X-Agent-Secret` 保護的 TCP 探測 API，可讓後端或維運工具測「節點到遊戲 endpoint」：

```bash
curl -X POST http://YOUR_NODE_PUBLIC_IP:8787/probe/tcp \
  -H "X-Agent-Secret: AGENT_SECRET_FROM_INSTALL_SCRIPT" \
  -H 'Content-Type: application/json' \
  -d '{"targets":[{"host":"example.com","port":443}],"samples":3}'
```

部署多個節點後，建議從後端跑整體 probe matrix：

```bash
cd backend
python scripts/run_probe_matrix.py --all-games
```

查看某款遊戲的節點排行榜：

```bash
curl "http://127.0.0.1:8080/admin/probes/scoreboard?game_id=valorant-apac-sample" \
  -H "Authorization: Bearer $TOKEN"
```

## 節點供應商挑選標準

不要只看價格，要測：

- 台灣到節點 ping/loss/jitter
- 節點到遊戲伺服器 ping/loss/jitter
- 晚上 8–12 點尖峰品質
- 每 TB 流量成本
- 是否容易被遊戲平台風控
- 是否可快速擴容

## 正式商用監控

每台節點至少監控：

- CPU / RAM / Disk
- WireGuard peers
- 進出流量
- UFW / firewall 狀態
- agent health
- loss / jitter synthetic test
- 每區退款率與客服回報
