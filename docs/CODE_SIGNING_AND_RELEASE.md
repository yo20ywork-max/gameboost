# 簽章與正式發布

## 官網版

1. 用 `desktop/package/build_windows.ps1` 產生 EXE/安裝檔。
2. 使用 Windows SDK SignTool 簽章：

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a GameBoost.exe
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a GameBoostSetup-2.0.0.exe
```

3. 上傳到官網 HTTPS。
4. 提供 SHA256 checksum。
5. 做 VirusTotal/Defender 誤判申訴流程。

## Microsoft Store 版

- MSIX 上架：送 Store 後由 Microsoft 重新簽署。
- MSI/EXE 上架：通常仍要自行 Authenticode 簽章。
- 因本 App 需要 WireGuard service，送審備註要清楚寫明依賴與權限需求。
