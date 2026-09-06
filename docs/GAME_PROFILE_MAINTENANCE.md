# 遊戲 Profile 維護

## 格式

```json
{
  "id": "minecraft-server-custom",
  "name": "Minecraft｜自訂伺服器範本",
  "publisher": "Mojang / Community",
  "recommended_mode": "split",
  "description": "描述",
  "cidrs": ["203.0.113.10/32"],
  "domains": ["example.com"],
  "ports": [{"proto": "tcp", "range": "25565"}],
  "dns": ["1.1.1.1"],
  "maintenance": "維護備註"
}
```

## recommended_mode

- `full`：遊戲 IP 常變，建議全流量。
- `split`：遊戲伺服器固定或玩家自訂伺服器，適合分流。

## 為什麼很多遊戲 profile 不能只靠 Google 一次解決

遊戲會使用：

- 登入伺服器
- 配對伺服器
- 聊天伺服器
- 對戰伺服器
- CDN / patch server
- 語音服務
- 不同平台 endpoint
- Geo-DNS

所以成熟產品通常要靠：

- 玩家回報
- 實測封包目的地
- 不同 ISP 監測
- 每週更新 profile
- 全流量 fallback

## 建議營運方式

初期不要追求上百款遊戲。先做：

- VALORANT
- League of Legends
- Apex Legends
- PUBG
- Minecraft 自訂伺服器
- Steam 遊戲通用全流量

每個遊戲建立「有效率」：

```text
有效率 = 加速後 loss 降低或 jitter 降低的測試樣本 / 總測試樣本
```

有效率低於 50% 的遊戲，不要主打。
