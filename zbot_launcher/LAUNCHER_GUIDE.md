# Zbot Launcher 開發指南

> 📖 **相關文檔**：[README](../README.md) | [BACKEND_GUIDE](../backend/BACKEND_GUIDE.md) | [RELEASE_GUIDE](../RELEASE_GUIDE.md)

## 目錄

1. [概述](#概述)
2. [架構設計](#架構設計)
3. [核心功能](#核心功能)
4. [Exit Code 約定](#exit-code-約定)
5. [開發與測試](#開發與測試)
6. [打包發布](#打包發布)

---

## 概述

Zbot Launcher (`Zbot.exe`) 是一個輕量的管理程式，負責：

1. **自動更新**：檢查 GitHub Release，下載並安裝新版 Zbot_Server
2. **進程管理**：啟動、監控、重啟 Zbot_Server
3. **系統匣**：提供 Systray 圖示與選單
4. **防多開**：使用 Windows Mutex 確保只有一個實例

---

## 架構設計

```
┌─────────────────────────────────────────────────────────────┐
│                    Zbot.exe 啟動流程                          │
├─────────────────────────────────────────────────────────────┤
│  1. 檢查 Mutex 鎖 (防止多開)                                   │
│                          ↓                                   │
│  2. 顯示 TaskDialog 啟動視窗 (正在初始化...)                    │
│                          ↓                                   │
│  3. 檢查更新 → 下載新版 (如有) → 解壓到 %LOCALAPPDATA%\Zbot\    │
│                          ↓                                   │
│  4. 啟動 Zbot_Server.exe (子進程)                              │
│                          ↓                                   │
│  5. 啟動 Server 健康監控 (背景執行緒)                           │
│                          ↓                                   │
│  6. 開啟瀏覽器                                                 │
│                          ↓                                   │
│  7. TaskDialog 自動關閉，最小化至 Systray                       │
└─────────────────────────────────────────────────────────────┘
```

### 雙向健康監控

| 方向 | 機制 | 說明 |
|------|------|------|
| Launcher → Server | `poll()` + exit code | 每 10 秒檢查 Server 是否存活 |
| Server → Launcher | `os.getppid()` + `psutil` | 每 5 秒檢查 Launcher 是否存活 |

```
Launcher                              Server
   │                                    │
   │──── subprocess.Popen ────────────▶ │
   │                                    │
   │◀─── poll() 每 10s ────────────────│
   │     exit_code != 0 → 重啟          │
   │                                    │
   │                psutil.pid_exists() │◀── 每 5s
   │                Launcher 不見 → 自殺 │
   │                                    │
```

---

## 核心功能

### 1. 防多開 (Singleton Mutex)

```python
def acquire_single_instance_lock():
    kernel32 = ctypes.WinDLL('kernel32')
    mutex = kernel32.CreateMutexW(None, False, "Global\\ZbotLauncherMutex")
    
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return False  # 已有實例運行
    return True
```

### 2. 啟動進度 UI (TaskDialog)

使用 Windows 原生 `TaskDialogIndirect` API，提供：

- **進度條**：更新下載時顯示百分比；啟動時為 Marquee 模式
- **即時日誌**：Expanded Information 區域顯示詳細狀態
- **無 Console**：以 Windowed 模式編譯 (`console=False`)，無黑窗閃爍

```python
# ui_taskdialog.py
def show_progress_dialog(title, instruction, worker_func):
    """顯示 TaskDialog 並在背景執行 worker_func(ui)"""
    # worker_func 透過 ui 物件控制 dialog
    # ui.set_instruction(text), ui.set_progress(%), ui.log(msg), ui.close()
```

### 3. Systray 選單

```
[Tooltip: Zbot v2.0.0]
├── 開啟 Zbot        → 開啟瀏覽器 http://127.0.0.1:5487
├── 開啟設定頁       → 開啟瀏覽器 http://127.0.0.1:5487/config
├── 重啟伺服器       → stop_server() + start_server()
└── 退出            → 停止 Server + 退出 Launcher
```

### 4. Server 健康監控

```python
def start_server_monitor(self):
    def monitor():
        while self.running:
            time.sleep(10)
            
            exit_code = self.server_process.poll()
            if exit_code is not None:
                if exit_code == 0:
                    # 正常退出，不重啟
                    self.running = False
                else:
                    # 異常退出，自動重啟 (最多 3 次)
                    self.restart_count += 1
                    if self.restart_count <= 3:
                        self.start_server()
                    else:
                        show_error_messagebox("Zbot 錯誤", "...")
```

---

## Exit Code 約定

Server 與 Launcher 透過 Exit Code 溝通：

| Exit Code | 觸發場景 | Server 程式碼 | Launcher 行為 |
|-----------|----------|--------------|--------------|
| **0** | Idle Timeout (30分鐘) | `os._exit(0)` | 退出 Launcher |
| **0** | POST /api/shutdown | `os._exit(0)` | 退出 Launcher |
| **0** | PPID 偵測 Launcher 不見 | `os._exit(0)` | N/A |
| **1** | 程式錯誤 / 未處理異常 | `sys.exit(1)` | 自動重啟 |
| **非 0** | 工作管理員強制終止 | N/A | 自動重啟 |

---

## 開發與測試

### 環境需求

- Python 3.12+
- Windows (Systray 僅支援 Windows)

### 本地執行

```powershell
cd Zbot

# 確保 Server 已啟動 (或讓 Launcher 啟動它)
uv run --package zbot_launcher python -m main
```

### 測試項目

| 測試 | 步驟 | 預期結果 |
|------|------|---------|
| 防多開 | 執行兩次 Zbot.exe | 第二個顯示「已在運行中」MessageBox 後退出 |
| 啟動視窗 | 正常啟動 | 顯示「Zbot 啟動中」TaskDialog，完成後自動關閉 |
| Server 監控 | 工作管理員結束 Server | Launcher 自動重啟 Server |
| 正常退出 | 等待 Idle Timeout | Server + Launcher 都退出 |
| Systray 功能 | 右鍵選單 | 可正常開啟 Zbot、設定頁、重啟 |

---

## 打包發布

### 打包指令

```powershell
# 使用 build_release.py (會同時打包 Server 和 Launcher)
uv run python scripts/build_release.py release --patch

# 或只打包 Launcher
cd zbot_launcher
uv run pyinstaller zbot.spec
```

### 輸出檔案

```
dist/
├── Zbot.exe              ← Launcher (分發給使用者)
└── Zbot_Server/          ← Server (自動下載)
```

### 更新 Launcher 的時機

Launcher 本身很少需要更新，因為核心邏輯穩定。需要更新的情況：

| 需要更新 | 不需要更新 |
|----------|-----------|
| 修改 GitHub API 或 Release 格式 | 新增後端功能 |
| 修改下載/解壓邏輯 | 修改前端 UI |
| 修改 Systray 功能 | Bug 修復 (在 Server) |
| 修改安裝路徑 | 效能優化 (在 Server) |

---

## 檔案結構

```
zbot_launcher/
├── main.py           # 入口 + Systray + Server 監控
├── updater.py        # GitHub 檢查更新、下載、解壓
├── ui_taskdialog.py  # 原生 Windows TaskDialog 進度視窗
├── config.py         # 設定 (路徑、版本、URL)
├── pyproject.toml    # 依賴 (httpx, packaging, infi-systray)
├── zbot.spec         # PyInstaller 設定 (console=False)
├── LAUNCHER_GUIDE.md # 本文件
└── assets/
    └── icon.ico      # Systray 圖示
```

---

## 常見問題

### Q: Launcher 無法啟動 Server？

1. 確認 `%LOCALAPPDATA%\Zbot\Zbot_Server\Zbot_Server.exe` 存在
2. 檢查 `%LOCALAPPDATA%\Zbot\logs\server.log`

### Q: Systray 圖示沒出現？

可能是 `infi.systray` 載入失敗，Launcher 會改用無圖示模式。

### Q: Server 一直重啟？

檢查 Server 的 Exit Code。連續 3 次 crash 後會停止重啟並顯示 MessageBox。
