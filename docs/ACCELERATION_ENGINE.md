# 加速引擎升級方向

目標不是讓所有流量盲目走 VPN，而是持續找出「玩家到遊戲伺服器」目前最穩的路徑。

## 核心判斷

每次連線都應該比較三段資料：

```text
玩家 -> 遊戲伺服器
玩家 -> GameBoost 節點
GameBoost 節點 -> 遊戲伺服器
```

目前版本已具備第一階段基礎：

- 桌面端測玩家到節點的 RTT / loss / jitter。
- 桌面端可對 profile 中的 TCP domain 做直連探測，並把結果交給後端保存。
- node-agent 回報 peer count、load、記憶體、介面流量。
- node-agent 提供 `/probe/tcp`，讓後端可要求節點測目標 endpoint。
- backend 提供 `/routes/evaluate`，同時比較玩家到節點、節點到遊戲 endpoint、玩家直連 endpoint。
- backend 會用 multi-hop weighted score 選節點。
- backend 會把選路、直連探測、節點探測結果寫入 `route_metrics`，方便之後分析改善率。
- backend 提供 probe matrix，可定期累積「節點 -> 遊戲 endpoint」資料。
- split profile 沒有可用目標時會 fallback 到 full tunnel，維持通用性。

## 下一階段

1. 建立真實遊戲 endpoint 資料庫。
2. 桌面端增加直連遊戲 endpoint 測試。
3. backend 定期要求各節點探測熱門遊戲 endpoint。
4. route score 納入 `player_to_node + node_to_game`。
5. 當加速路徑比直連差時，自動建議不要啟用。
6. 後台用 `route_metrics` 統計每個 ISP / 遊戲 / 區域的實際改善率。

## 分數模型

初期可使用：

```text
score = client_to_node + node_to_game + node_load_penalty + health_age_penalty
client_to_node = rtt + loss_percent * 40 + jitter * 1.5
node_to_game = rtt + loss_percent * 40 + jitter * 1.5
```

正式商用後應改成按遊戲與地區調整權重。例如 FPS 遊戲比下載/更新流量更重視 jitter 與 loss。

## API

桌面端應優先呼叫：

```text
POST /routes/evaluate
```

這個 API 會回傳：

- `selected_node_id`
- `candidates`
- `direct_score`
- `recommendation`
- `decision`

`recommendation.action` 可能是：

- `accelerate`
- `optional`
- `avoid`

維運端應定期呼叫：

```text
POST /admin/probes/run
GET /admin/probes/scoreboard?game_id=<profile-id>
```

也可以使用 CLI：

```bash
cd backend
python scripts/run_probe_matrix.py --base-url http://127.0.0.1:8080 --all-games
```

這會讓每個節點測每個遊戲 profile 的 endpoint，結果保存到 `node_probe_runs` 與 `node_probe_results`。桌面端呼叫 `/routes/evaluate` 時可使用這些快取資料，降低等待時間，也讓選路能依照不同節點到不同遊戲的實測狀態更新。

## 每日營運節奏

1. 尖峰前跑一次 `run_probe_matrix.py --all-games`。
2. 尖峰時每 15 到 30 分鐘跑一次 probe matrix。
3. 用 `/admin/probes/scoreboard` 看每款遊戲目前最佳節點。
4. 觀察 `route_metrics` 中 `recommendation` 與玩家回報，調整節點供應商與 profile。
5. 如果某節點 loss 或 jitter 長期偏高，下架或降低權重。

## 產品原則

- 不能承諾每次都降 ping。
- 要能證明「這次為什麼選這個節點」。
- 如果沒有改善，就不要硬連。
- 所有節點選擇都要可回放、可分析、可修正。
