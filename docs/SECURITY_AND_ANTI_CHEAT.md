# 資安與反作弊界線

## 絕對不要做

- 不要注入遊戲 process。
- 不要讀寫遊戲記憶體。
- 不要修改遊戲封包內容。
- 不要隱藏硬體 ID。
- 不要繞過封鎖或反作弊。
- 不要承諾「不會被偵測」或「繞過 ban」。

## 本專案採用的安全模式

- 僅建立 OS 層級 VPN tunnel。
- 僅變更路由目的地。
- 不碰遊戲檔案。
- 不收集遊戲帳號密碼。
- 節點只看到網路流量，正式營運需明確揭露日誌政策。

## 後端安全

MVP 使用 HMAC token 與 SQLite，正式商用建議：

- PostgreSQL
- Argon2id password hashing
- OAuth device/session 管理
- JWT refresh token rotation
- Rate limit
- WAF / reverse proxy
- audit log
- secrets manager

## 節點 Agent 安全

MVP 的 Agent 用 shared secret。正式商用必須升級：

- Agent 只允許後端 IP 連線。
- 使用 private network 或 WireGuard 管理網。
- 使用 mTLS。
- 每台節點獨立 secret，可撤銷。
- agent_url 不對玩家公開。
- 定期 prune stale peer。

## 玩家端安全

- 不把 private key 傳給後端。
- 每次 lease 可產生新 keypair。
- 停止時移除 tunnel service。
- 故障時提供 kill-switch 選項，但要避免把玩家網路鎖死。
