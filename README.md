<div align="center">

# <img src="https://github.com/user-attachments/assets/68162a25-acfd-4a8d-984c-ad808f5691cb" width="40" valign="bottom"> Zbot

</div>

> 🏥 **眼科門診自動化助理** — 專為榮總眼科設計的智慧工作流程自動化工具

Zbot 整合內網系統（EIP、CKS、Web9）與 Google Sheets，自動化處理手術紀錄、IVI 注射紀錄、待床追蹤、績效統計等日常繁瑣工作，讓醫師專注於臨床照護。

[![Demo Video](https://img.youtube.com/vi/eenMQ8QS9fM/hqdefault.jpg)](https://www.youtube.com/watch?v=eenMQ8QS9fM)

---

## ✨ 主要功能

| 功能 | 說明 |
|------|------|
| 🩺 **手術紀錄** | 自動抓取排程、整合 GSheet 刀表、批次送出 Web9 |
| 💉 **IVI 注射** | 批次編輯診斷/側別/藥物，一鍵送出多筆紀錄 |
| 📊 **統計報表** | 手術量統計、費用碼績效，自動更新 GSheet |
| 🛏️ **待床追蹤** | 整合住院排程，自動更新待床清單 |

---

## 📥 下載

[![Download Zbot](https://img.shields.io/badge/Download-Zbot.exe-blue?style=for-the-badge&logo=windows)](https://github.com/eyeduck-ai/Zbot/releases/download/launcher/Zbot.exe)

> ⚠️ **系統需求**：僅支援 **Windows** 作業系統（建議 Windows 10 以上）

---

## 🚀 使用方式

### 安裝 (使用者)

1. 點擊上方按鈕下載 `Zbot.exe`
2. 執行 `Zbot.exe`，程式會自動下載最新版 `Zbot_Server`
3. 程式會顯示系統匣圖示，點擊可開啟瀏覽器或退出
4. 首次使用需設定 Supabase 連線資訊
5. 使用 EIP 帳號登入即可開始使用

### 更新

程式會自動檢查更新。執行 `Zbot.exe` 時若有新版本會自動下載安裝。

---

## 💻 開發者快速開始

### 環境需求

- **Python**: 3.12+
- **Node.js**: 18+
- **套件管理**: [uv](https://github.com/astral-sh/uv)

### 本地開發

```bash
# Clone 專案
git clone https://github.com/eyeduck-ai/Zbot.git
cd Zbot

# 安裝所有依賴 (使用 UV workspace)
uv sync

# 啟動後端
uv run uvicorn app.main:app --reload --port 5487 --app-dir backend

# 啟動前端 (另開終端)
cd frontend
npm install
npm run dev
```

開啟瀏覽器訪問 http://localhost:5173

### 首次設定

1. 開啟應用後會顯示設定頁面
2. 填入 Supabase URL 和 API Key
3. 使用 EIP 帳號登入

---

## 📖 開發文檔

| 文檔 | 說明 |
|------|------|
| [backend/BACKEND_GUIDE.md](backend/BACKEND_GUIDE.md) | 後端指南 — 核心模組、資料庫、API 設計、Task 開發 |
| [frontend/FRONTEND_GUIDE.md](frontend/FRONTEND_GUIDE.md) | 前端指南 — 元件庫、樣式規範、頁面開發 |
| [zbot_launcher/LAUNCHER_GUIDE.md](zbot_launcher/LAUNCHER_GUIDE.md) | Launcher 指南 — 自動更新、Systray、進程管理 |
| [RELEASE_GUIDE.md](RELEASE_GUIDE.md) | 發布指南 — Windows 打包與部署流程 |

---

## 🏗️ 專案架構

```
Zbot/
├── pyproject.toml            # UV Workspace 根設定
├── .venv/                    # 統一的虛擬環境
├── backend/                  # FastAPI 後端 (workspace member)
│   ├── pyproject.toml        # Backend 依賴
│   ├── run_server.py         # Server 入口點
│   ├── zbot_server.spec      # PyInstaller spec
│   ├── app/
│   │   ├── routers/         # API 端點
│   │   ├── tasks/           # 業務任務
│   │   ├── core/            # JobManager, TaskRegistry
│   │   └── db/              # Supabase 連接
│   └── vghsdk/              # 底層爬蟲庫
├── frontend/                 # React + Vite 前端
│   └── src/
│       ├── pages/           # 頁面元件
│       ├── components/      # 共用元件
│       └── api/             # API Client
├── zbot_launcher/            # Launcher + Systray (workspace member)
│   ├── pyproject.toml        # Launcher 依賴
│   ├── main.py               # 入口 + Systray 邏輯
│   ├── zbot.spec             # PyInstaller spec
│   └── assets/               # Launcher 專屬 assets (icon.ico)

└── scripts/                  # 發布腳本
    └── build_release.py
```

---

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| **後端** | FastAPI, Supabase, gspread, httpx |
| **前端** | React 19, TypeScript, Vite, TailwindCSS |
| **打包** | PyInstaller |
| **Systray** | infi.systray (Launcher) |

---



## 🔒 安全注意事項

- 所有憑證儲存於本地 `config.json`，不會上傳
- 建議使用 Supabase RLS 保護敏感資料

---

## 📄 授權

Private - 僅供內部使用
