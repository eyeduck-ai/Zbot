# Zbot 發布指南

本文件說明如何在 Windows 上打包 Zbot 並發布到 GitHub Releases / Google Drive。

> 📖 **相關文檔**：[README](README.md) | [BACKEND_GUIDE](backend/BACKEND_GUIDE.md) | [FRONTEND_GUIDE](frontend/FRONTEND_GUIDE.md) | [LAUNCHER_GUIDE](zbot_launcher/LAUNCHER_GUIDE.md)

> ⚠️ **注意**：打包流程需在 **Windows** 環境下執行。開發可在 Mac/Windows 進行。

---

## 首次打包準備 (Windows)

首次在 Windows 上打包前，需完成以下設定。

### Step 1: 安裝必要工具

```powershell
# 1. 安裝 Python 套件管理器 (uv)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 安裝 Python 3.12 (uv 自動管理)
uv python install 3.12

# 3. 安裝 Node.js (前端編譯需要)
winget install OpenJS.NodeJS.LTS

# 4. 安裝 GitHub CLI (發布 Release 需要)
winget install GitHub.cli
gh auth login
# 選擇: GitHub.com → HTTPS → 瀏覽器登入
```

### Step 2: Clone 專案

```powershell
git clone https://github.com/eyeduck-ai/Zbot.git
cd Zbot
```

### Step 3: 安裝專案依賴

```powershell
# 安裝所有 Python 依賴 (使用 UV workspace)
uv sync

# Frontend 依賴
cd frontend
npm install
cd ..
```

> 💡 **說明**：`uv sync` 會自動安裝 backend、launcher 和打包工具（pyinstaller）的所有依賴。

### Step 4: 驗證環境

```powershell
# 確認工具都已安裝
uv --version        # 應顯示版本號
node --version      # 應顯示 v18+ 或 v20+
gh auth status      # 應顯示已登入
```

完成以上步驟後，即可執行打包。

---

## 發布流程

### 方式一：自動遞增版本號（推薦）

```powershell
# Patch 版本 (bug 修復): 1.2.0 → 1.2.1
uv run python scripts/build_release.py release --patch

# Minor 版本 (新功能): 1.2.0 → 1.3.0
uv run python scripts/build_release.py release --minor

# Major 版本 (破壞性變更): 1.2.0 → 2.0.0
uv run python scripts/build_release.py release --major
```

### 方式二：指定版本號

```powershell
uv run python scripts/build_release.py release 1.5.0
```

### 僅打包（不發布）

```powershell
uv run python scripts/build_release.py build
```

---

## 完整發布流程

執行 `release` 指令會自動完成以下步驟：

1. ✅ 清理舊的 build 資料夾
2. ✅ 建置 frontend (`npm run build`)
3. ✅ 打包 Zbot_Server (PyInstaller `--onedir`, 純後端服務)
4. ✅ 打包 Zbot 啟動器 + Systray (PyInstaller `--onefile`)
5. ✅ 複製 assets 到輸出目錄
6. ✅ 建立 `Zbot_Server_vX.X.X_win64.zip`
7. ✅ 建立 Git tag (`vX.X.X`) 並 push
8. ✅ 建立 GitHub Release 並上傳 ZIP
9. ✅ 上傳到 Google Drive (如果 rclone 已設定)

---

## 輸出結構

```
dist/
├── Zbot.exe                          # 啟動器 + Systray (分發給使用者)
├── Zbot_Server/                      # 後端服務器資料夾
│   ├── Zbot_Server.exe               # 後端服務 (無 console 視窗)
│   ├── assets/
│   │   └── icon.ico                  # 應用程式圖示
│   ├── _internal/
│   └── frontend/                     # 編譯好的前端
├── Zbot_Server_v1.2.0_win64.zip     # 上傳到 GitHub Release
└── version.json                      # 版本資訊
```

---

## 架構說明

| 元件 | 說明 |
|------|------|
| **Zbot.exe** | Launcher + Systray，負責更新、管理 Server 生命週期、顯示系統匣圖示 |
| **Zbot_Server.exe** | 純後端服務 (uvicorn + FastAPI)，作為獨立進程運行 |

---

## Launcher 啟動器架構

Launcher (`Zbot.exe`) 是一個輕量的自動更新工具，與主程式 (`Zbot_Server.exe`) 分離設計。

### 目錄結構

```
zbot_launcher/
├── main.py           # 啟動器入口 + Systray 邏輯
├── updater.py        # 自動更新邏輯
├── config.py         # 設定 (GitHub API URL, 路徑等)
├── pyproject.toml    # 依賴 (httpx, packaging, infi-systray)
├── zbot.spec         # PyInstaller 設定
└── assets/           # Launcher 專屬 assets
    └── icon.ico      # Systray 圖示
```

### 更新機制

Launcher 啟動時會執行以下流程：

```
┌─────────────────────────────────────────────────────────────┐
│                    Zbot.exe 啟動流程                         │
├─────────────────────────────────────────────────────────────┤
│  1. 檢查本地版本 (%LOCALAPPDATA%\Zbot\version.json)          │
│                          ↓                                   │
│  2. 查詢 GitHub API (/releases)                               │
│                          ↓                                   │
│  3. 比較版本號 (Semantic Versioning)                          │
│                          ↓                                   │
│  ┌──── 有新版 ────┐     ┌──── 已是最新 ────┐                │
│  │ 下載 ZIP       │     │                  │                 │
│  │ 解壓到 Zbot/   │     │                  │                 │
│  │ 更新 version   │     │                  │                 │
│  └───────────────┘     └─────────────────┘                  │
│                          ↓                                   │
│  4. 啟動 Zbot_Server.exe (子進程)                              │
│                          ↓                                   │
│  5. 開啟瀏覽器 + 顯示 Systray 圖示                               │
└─────────────────────────────────────────────────────────────┘
```

### 使用者端檔案位置

```
%LOCALAPPDATA%\Zbot\
├── Zbot_Server/         # 後端服務器 (自動下載)
│   ├── Zbot_Server.exe
│   ├── frontend/
│   └── ...
├── assets/              # 共用 assets
│   └── icon.ico
├── version.json         # 目前版本記錄
└── downloads/           # 暫存下載檔案
```

### 何時需要更新 Launcher？

Launcher 本身很少需要更新，因為它負責：
- 檢查版本、下載 ZIP
- 啟動和管理 Server 進程
- 顯示 Systray 圖示

**需要更新 Launcher 的情況**：
- 修改 GitHub API 或 Release 格式
- 修改下載/解壓邏輯
- 修改使用者端安裝路徑
- 修改 Systray 功能或圖示

**不需要更新 Launcher 的情況**：
- 新增功能到主程式
- 修改後端 API
- 修改前端 UI

### 上傳 Launcher 到 GitHub

> 💡 **自動上傳**：執行 `release` 命令時會自動上傳 Launcher 到專用 release，通常不需要手動執行此步驟。

Launcher 存放在一個專門的 GitHub Release (tag: `launcher`)，提供固定的下載連結。

```powershell
# 手動上傳已編譯的 launcher（通常不需要）
uv run python scripts/build_release.py upload-launcher

# 或手動編譯後直接上傳
uv run python scripts/build_release.py upload-launcher --build
```

執行後，使用者可從以下固定連結下載：
```
https://github.com/eyeduck-ai/Zbot/releases/download/launcher/Zbot.exe
```

> ⚠️ **注意**：更新 Launcher 後，使用者需重新下載 `Zbot.exe`。主程式可以自動更新，但 Launcher 本身無法自動更新。

---

## 發布選項

| 選項 | 說明 |
|------|------|
| `--no-tag` | 跳過 Git tag 建立 |
| `--no-github` | 跳過 GitHub Release |
| `--no-gdrive` | 跳過 Google Drive 上傳 |

範例：
```powershell
# 只建立 tag，不上傳
uv run python scripts/build_release.py release --patch --no-github --no-gdrive

# 只上傳 GitHub，不上傳 GDrive
uv run python scripts/build_release.py release 1.5.0 --no-gdrive
```

---

## 版本號規則 (Semantic Versioning)

| 類型 | 何時使用 | 範例 |
|------|----------|------|
| **MAJOR** | 破壞性變更、不向下相容 | `1.0.0` → `2.0.0` |
| **MINOR** | 新功能、向下相容 | `1.2.0` → `1.3.0` |
| **PATCH** | Bug 修復 | `1.2.0` → `1.2.1` |

---

## 使用者更新流程

打包發布後，使用者端會自動更新：

1. 使用者執行 `Zbot.exe`
2. 啟動器檢查 GitHub `/releases/latest`
3. 比較 `tag_name` 與本地 `version.json`
4. 若有新版，下載 ZIP 並解壓到 `%LOCALAPPDATA%/Zbot/`
5. 啟動 `Zbot_Server.exe` → 顯示托盤圖示 → 開啟瀏覽器

---

## 可選：設定 Google Drive 上傳

```powershell
# 安裝 rclone
winget install rclone

# 設定 remote
rclone config
# 選擇: n) New remote → 名稱: gdrive → Storage: Google Drive

# 驗證
rclone ls gdrive:
```

---

## 常見問題

### Q: GitHub CLI 顯示未授權？
```powershell
gh auth login
# 重新登入
```

### Q: rclone 上傳失敗？
```powershell
# 確認 remote 名稱是 "gdrive"
rclone listremotes

# 測試連線
rclone ls gdrive:
```

### Q: Tag 已存在？
腳本會自動跳過已存在的 tag。如需覆蓋：
```powershell
git tag -d v1.2.0
git push origin :refs/tags/v1.2.0
```

### Q: 為什麼 Mac 無法打包？
打包必須在 Windows 環境下執行，因為：
- PyInstaller 產生的 EXE 是平台特定的
- `infi.systray` 只支援 Windows

開發和測試可在 Mac 進行，最終打包請在 Windows 執行。

### Q: npm run build 失敗？
確認 Node.js 已安裝且 frontend 依賴已安裝：
```powershell
node --version
cd frontend
npm install
cd ..
```
