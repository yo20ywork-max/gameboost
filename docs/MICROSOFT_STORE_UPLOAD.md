# Windows 電腦 App 上架流程

## 先講結論

你可以走兩條路：

1. **官網下載簽章安裝檔**：最適合 VPN / 遊戲加速器，因為需要安裝 WireGuard tunnel service，通常需要系統管理員權限。
2. **Microsoft Store**：可以做，但 VPN/driver/service 依賴要特別小心，需在 Partner Center certification notes 說明。

## 為什麼不能直接幫你「送上架」

實際上架需要：

- 你的 Microsoft Partner Center 開發者帳號
- 公司/個人資料與驗證
- App 名稱保留
- 簽章憑證或 MSIX Store 簽署流程
- 隱私權政策網址
- 支援信箱/網站
- 截圖、年齡分級、價格與地區
- 若使用 MSI/EXE，安裝檔通常需 Authenticode 簽章

我可以把專案、安裝包腳本、文案、隱私權政策範本、送審 checklist 準備好；但不能代替你登入帳號與提交付費/身分驗證資料。

## 路線 A：官網下載安裝檔

建議商用初期先走這條。

流程：

1. 買網域，例如 `gameboost.tw`。
2. 後端與節點全部上 HTTPS。
3. 用 PyInstaller + Inno Setup 產生 `GameBoostSetup.exe`。
4. 購買 OV/EV Code Signing Certificate。
5. 使用 Windows SDK `signtool.exe` 簽章安裝檔與 EXE。
6. 官網提供下載。
7. App 內建自動更新或提示更新。

優點：

- 可以要求 admin 權限。
- 可以安裝/呼叫 WireGuard service。
- 不用等 Store 審核。

缺點：

- SmartScreen 初期可能警告。
- 需要累積簽章信譽。
- 使用者信任成本較高。

## 路線 B：Microsoft Store

### MSIX 方向

Microsoft Store 對 MSIX 包會在認證後由 Microsoft 重新簽署。若你用 MSIX 上架，簽章成本比較低，但包裝與權限限制較多。

### MSI/EXE 方向

Microsoft Store 也支援部分桌面安裝器情境，但 MSI/EXE 通常需要你自己做 Authenticode 簽章，並符合 Store 要求。

### VPN / service 注意事項

遊戲加速器需要依賴 WireGuard for Windows 或 tunnel service。這類依賴在 Store 審核中要主動揭露：

- App 需要 WireGuard for Windows。
- 第一次連線需要 admin 權限。
- App 不安裝自製 kernel driver。
- App 不注入遊戲程序、不修改遊戲。
- App 只建立 OS 層級 VPN/tunnel。

若 Store 審核不接受，保留官網下載版是最實際方案。

## 上架前 checklist

- [ ] App 名稱確定：GameBoost 或你的品牌名
- [ ] Logo：44x44、150x150、310x150、StoreLogo
- [ ] 至少 4 張截圖
- [ ] 隱私權政策 URL
- [ ] 支援 email
- [ ] 年齡分級
- [ ] 價格/地區
- [ ] 安裝包簽章
- [ ] 後端 API HTTPS
- [ ] 節點 Agent 不裸露公網
- [ ] 測試帳號提供給審核員
- [ ] certification notes 說明 WireGuard 依賴與 admin 權限

## 商店文案

可直接使用：

```text
desktop/package/store_listing_zh-TW.txt
```

## 隱私權政策範本

```text
desktop/package/privacy_policy_zh-TW.md
```
