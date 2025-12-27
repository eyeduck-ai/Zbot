# <img src="https://github.com/user-attachments/assets/68162a25-acfd-4a8d-984c-ad808f5691cb" width="40" valign="bottom"> Zbot

> 🏥 **眼科門診自動化助理** — 專為榮總眼科設計的智慧工作流程自動化工具

Zbot 整合內網系統（EIP、CKS、Web9）與 Google Sheets，自動化處理手術紀錄、IVI 注射紀錄、待床追蹤、績效統計等日常繁瑣工作，讓醫師專注於臨床照護。

[![Demo Video](https://img.youtube.com/vi/eenMQ8QS9fM/0.jpg)](https://www.youtube.com/watch?v=eenMQ8QS9fM)

---

## ✨ 主要功能

| 功能 | 說明 |
|------|------|
| 🩺 **手術紀錄** | 自動抓取排程、整合 GSheet 刀表、批次送出 Web9 |
| 💉 **IVI 注射** | 批次編輯診斷/側別/藥物，一鍵送出多筆紀錄 |
| 📊 **統計報表** | 手術量統計、費用碼績效，自動更新 GSheet |
| 🛏️ **待床追蹤** | 整合住院排程，自動更新待床清單 |

---

## 🚀 使用方式

### 安裝 (使用者)

1. 從 [GitHub Releases](https://github.com/your-org/Zbot/releases) 下載 `Zbot.exe`
2. 執行 `Zbot.exe`，程式會自動下載最新版本
3. 首次使用需設定 Supabase 連線資訊
4. 使用 EIP 帳號登入即可開始使用

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
git clone https://github.com/your-org/Zbot.git
cd Zbot

# 啟動後端
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 5487

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
| [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) | 開發手冊 — 專案架構、新增 Task、新增頁面 |
| [backend/BACKEND_GUIDE.md](backend/BACKEND_GUIDE.md) | 後端指南 — 核心模組、資料庫、API 設計 |
| [frontend/FRONTEND_GUIDE.md](frontend/FRONTEND_GUIDE.md) | 前端指南 — 元件庫、樣式規範、API 呼叫模式 |
| [RELEASE_GUIDE.md](RELEASE_GUIDE.md) | 發布指南 — Windows 打包與部署流程 |

---

## 🏗️ 專案架構

```
Zbot/
├── backend/                  # FastAPI 後端
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
├── scripts/                  # 發布腳本
│   └── build_release.py
└── zbot_launcher/            # Windows 啟動器
```

---

## 🛠️ 技術棧

| 類別 | 技術 |
|------|------|
| **後端** | FastAPI, Supabase, gspread, httpx |
| **前端** | React 19, TypeScript, Vite, TailwindCSS |
| **打包** | PyInstaller, infi.systray |

---

## 📦 發布 (開發者)

需在 Windows 環境執行：

```powershell
uv run python scripts/build_release.py release --patch
```

詳見 [RELEASE_GUIDE.md](RELEASE_GUIDE.md)

---

## 🔒 安全注意事項

- 所有憑證儲存於本地 `config.json`，不會上傳
- 建議使用 Supabase RLS 保護敏感資料

---

## 📄 授權

Private - 僅供內部使用
