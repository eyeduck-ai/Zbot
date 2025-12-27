# Zbot 開發手冊

## 目錄

1. [快速啟動](#快速啟動)
2. [專案架構](#專案架構)
3. [建立新 Task](#建立新-task)
4. [建立新前端頁面](#建立新前端頁面)
5. [API 使用指南](#api-使用指南)
6. [環境設定](#環境設定-configjson)
7. [測試指南](#測試指南)
8. [常見問題](#常見問題)

> 📖 **相關文檔**：[README](README.md) | [BACKEND_GUIDE](backend/BACKEND_GUIDE.md) | [FRONTEND_GUIDE](frontend/FRONTEND_GUIDE.md) | [RELEASE_GUIDE](RELEASE_GUIDE.md)

---

## 快速啟動

### 啟動 Backend

```bash
cd backend
uv run uvicorn app.main:app --reload --port 5487
```

### 啟動 Frontend

```bash
cd frontend
npm run dev
```

> **Note**: Frontend 預設會在 http://localhost:5173 啟動，並透過 Vite proxy 連接 Backend

---

## 專案架構

```
Zbot/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── tasks.py      # Task 執行 API
│   │   │   └── auth.py       # 認證 API
│   │   ├── tasks/            # 📌 應用層 Task (繼承 BaseTask)
│   │   │   ├── base.py       # BaseTask 定義
│   │   │   ├── dashboard_bed.py
│   │   │   ├── stats_op.py
│   │   │   ├── stats_fee.py
│   │   │   ├── note_ivi.py
│   │   │   ├── note_surgery.py
│   │   │   └── opnote/       # 手術記錄相關
│   │   └── core/
│   │       └── registry.py   # Task 註冊中心
│   ├── vghsdk/               # 📌 底層爬蟲庫 (繼承 CrawlerTask)
│   │   ├── core.py           # VghClient, CrawlerTask
│   │   └── modules/          # 原始爬蟲函數
│   │       ├── patient.py
│   │       ├── surgery.py
│   │       └── ivi.py
│   └── BACKEND_GUIDE.md      # 👈 後端開發指南
├── frontend/
│   ├── src/
│   │   ├── pages/            # 📌 頁面元件
│   │   ├── components/       # 共用元件
│   │   ├── mocks/            # Demo 模擬資料
│   │   ├── context/          # React Context (Auth)
│   │   ├── config.ts         # 📌 前端設定 (含 DEMO_MODE)
│   │   └── api/client.ts     # API Client
│   ├── vite.config.ts        # Proxy 設定
│   └── FRONTEND_GUIDE.md     # 👈 前端開發指南
├── scripts/                  # 📌 專案腳本
│   └── build_release.py      # 發布腳本
└── DEVELOPMENT_GUIDE.md      # 👈 本文檔 (快速上手)
```

### Task 分層架構

| 層級 | 位置 | 基類 | 職責 |
|------|------|------|------|
| **應用層** | `app/tasks/` | `BaseTask` | 組合多個爬蟲 + 業務邏輯 (Google Sheets, Web9) |
| **底層庫** | `vghsdk/modules/` | `CrawlerTask` | 單一資料來源抓取 (可獨立發布) |

> 📖 詳細說明請參考：[backend/BACKEND_GUIDE.md](backend/BACKEND_GUIDE.md)

---

## 建立新 Task

### Step 1: 定義參數與結果 Model

```python
# backend/app/tasks/my_new_task.py
from pydantic import BaseModel, Field
from typing import Optional, List

class MyTaskParams(BaseModel):
    """任務參數"""
    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    option: Optional[str] = Field(None, description="可選參數")

class MyTaskResult(BaseModel):
    """任務結果"""
    status: str
    count: int
    details: List[str] = []
```

### Step 2: 實作 Task 類別

```python
from vghsdk.core import VghClient
from app.tasks.base import BaseTask  # 📌 使用 BaseTask
from app.core.registry import TaskRegistry

class MyNewTask(BaseTask):
    id: str = "my_new_task"          # 📌 API 路徑會用到
    name: str = "My New Task"
    description: str = "描述"
    params_model = MyTaskParams       # 📌 參數 Model

    async def run(self, params: MyTaskParams, client: VghClient, progress_callback=None):
        """
        執行任務
        
        Args:
            params: MyTaskParams (由 router 驗證並轉換，直接使用)
            client: VghClient (已登入的 session)
            progress_callback: async def(int, str) 用於回報進度
        """
        # ⚠️ 注意：params 已是 Pydantic model，不要再解構！
        # ❌ 錯誤: p = MyTaskParams(**params)
        # ✅ 正確: 直接使用 params
        
        # 回報進度 (可選)
        if progress_callback:
            await progress_callback(10, "開始執行...")
        
        # 使用 vghsdk 模組
        from vghsdk.modules.patient import PatientSearchTask
        patient_task = PatientSearchTask()
        data = await patient_task.run({"hisno": "12345678"}, client)
        
        if progress_callback:
            await progress_callback(100, "完成")
        
        return MyTaskResult(status="success", count=10)

# 📌 註冊任務 (很重要！)
TaskRegistry.register(MyNewTask())
```

### Step 3: Import 到 main.py

```python
# backend/app/main.py
# 在最上方加入 import，確保任務被註冊
import app.tasks.my_new_task  # noqa
```

### 呼叫方式

```bash
POST /api/tasks/my_new_task/run
Authorization: Bearer <token>
Content-Type: application/json

{
  "params": { "date": "2025-12-12", "option": "test" },
  "eip_id": "xxxxx",
  "eip_psw": "xxxxx"
}
```

---

## 建立新前端頁面

### 基本結構

```tsx
// frontend/src/pages/MyNewPage.tsx
import React, { useState, useCallback } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { tasksApi } from '../api/tasks';

export const MyNewPage: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [statusMsg, setStatusMsg] = useState<string | null>(null);
    
    // 執行任務
    const handleRun = useCallback(async () => {
        setLoading(true);
        setStatusMsg('任務執行中...');
        
        const eipId = localStorage.getItem('eip_id');
        const eipPsw = localStorage.getItem('eip_psw');
        
        try {
            // 📌 使用 tasksApi 執行任務
            const { job_id } = await tasksApi.run('my_new_task', {
                params: { date: '2025-12-12' },
                eip_id: eipId || undefined,
                eip_psw: eipPsw || undefined
            });
            
            // 📌 輪詢 job 狀態
            for (let i = 0; i < 60; i++) {
                await new Promise(r => setTimeout(r, 1000));
                const job = await tasksApi.getJob(job_id);
                
                if (job.status === 'success') {
                    setStatusMsg(job.result?.message || '執行成功');
                    break;
                }
                if (job.status === 'failed') {
                    throw new Error(job.error || '執行失敗');
                }
                // ⚠️ 重要：處理取消狀態
                if (job.status === 'cancelled') {
                    throw new Error('任務已取消');
                }
            }
            
        } catch (e: any) {
            setStatusMsg(`錯誤: ${e.message}`);
        } finally {
            setLoading(false);
        }
    }, []);
    
    return (
        <div style={{ padding: '24px' }}>
            <Card style={{ padding: '24px' }}>
                <Button onClick={handleRun} disabled={loading}>
                    {loading ? '執行中...' : '執行任務'}
                </Button>
                {statusMsg && <p>{statusMsg}</p>}
            </Card>
        </div>
    );
};
```

### 加入路由

```tsx
// frontend/src/App.tsx
import { MyNewPage } from './pages/MyNewPage';

// 在 Routes 中加入
<Route path="/my-new-page" element={<MyNewPage />} />
```

### 加入 Sidebar

```tsx
// frontend/src/components/Sidebar.tsx
// 在 NAV_ITEMS 中加入
{ icon: YourIcon, label: '新功能', path: '/my-new-page', prefix: 'my_new' }
```

---

## API 使用指南

### ✅ 推薦方式：使用封裝的 API Client

```tsx
import { apiClient } from '../api/client';
import { tasksApi } from '../api/tasks';
import { authApi } from '../api/auth';

// 執行任務
const { job_id } = await tasksApi.run('task_id', {
    params: { ... },
    eip_id: localStorage.getItem('eip_id') || undefined,
    eip_psw: localStorage.getItem('eip_psw') || undefined
});

// 查詢任務狀態
const job = await tasksApi.getJob(job_id);

// 列出最近任務
const jobs = await tasksApi.listJobs(10);

// 取消任務
await tasksApi.cancelJob(job_id);

// 一般 GET/POST 請求
const data = await apiClient.get<MyType>('/api/endpoint');
const result = await apiClient.post<Result>('/api/endpoint', { key: 'value' });
```

### ❌ 避免：直接使用 fetch

```tsx
// 不推薦 - 需要手動處理 token 和錯誤
const res = await fetch('/api/tasks/xxx/run', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`  // 容易忘記
    },
    body: JSON.stringify({ ... })
});
```

### 常見錯誤

| 錯誤 | 原因 | 解法 |
|------|------|------|
| `401 Unauthorized` | 缺少 Authorization header | 使用 `apiClient` 或 `tasksApi` (自動處理) |
| `422 Unprocessable Entity` | 參數格式錯誤 | 檢查 Pydantic model 定義 |
| `Invalid parameters` | 前端傳入的 params 無法驗證 | 檢查 params 結構是否符合 model |

---

## COL_* 動態欄位命名準則

手術記錄的動態填充欄位 (IOL, Final, Target 等) 統一使用 `COL_*` 命名。

**新增欄位流程** (無需程式碼改動)：

1. **op_templates 表**: `required_fields` 加入 `"COL_NEW_FIELD"`
2. **doctor_sheets 表**: `column_map` 加入 `{"COL_NEW_FIELD": "GSheet欄位名"}`
3. **op_templates.template**: 使用 `$COL_NEW_FIELD` 佔位符

> 📖 詳細架構說明請參考 [backend/BACKEND_GUIDE.md](backend/BACKEND_GUIDE.md#col-動態欄位命名準則)

---

## 環境設定 (config.json)

### 設定檔位置

| 環境 | 路徑 |
|------|------|
| **開發模式** | `backend/config.json` 或 `backend/.env` (向下相容) |
| **打包後** | `%LOCALAPPDATA%\Zbot\config.json` |

> **首次啟動**：若無設定檔，前端會顯示設定頁面讓使用者建立。

### 設定項目

```json
{
  "supabase_url": "https://xxx.supabase.co",
  "supabase_key": "eyJ...",
  "dev_mode": false,
  "log_level": "INFO",
  "test_eip_id": "",
  "test_eip_psw": ""
}
```

| 欄位 | 說明 | 必填 |
|------|------|------|
| `supabase_url` | Supabase 專案 URL | ✅ |
| `supabase_key` | Supabase API Key (anon 或 service_role) | ✅ |
| `dev_mode` | 開發模式 (不實際送出資料) | ❌ 預設 false |
| `log_level` | 日誌等級 (DEBUG/INFO/WARNING/ERROR) | ❌ 預設 INFO |
| `test_eip_id` | 測試用 EIP 帳號 | ❌ |
| `test_eip_psw` | 測試用 EIP 密碼 | ❌ |

### 程式碼使用

```python
from app.config import get_settings

settings = get_settings()
print(settings.SUPABASE_URL)
print(settings.DEV_MODE)
```

---

## 測試指南

### 目錄結構

```
backend/tests/
├── conftest.py              # 帳號管理 + 共用 fixtures
├── unit/                    # 🟢 單元測試 (不需帳號，秒級完成)
│   ├── test_api.py          # API 健康檢查
│   ├── test_registry.py     # TaskRegistry 機制
│   ├── test_opnote.py       # OpNote Payload 建構
│   └── test_models.py       # Pydantic Models 驗證
└── integration/             # 🟡 整合測試 (需 EIP 帳號)
    ├── test_login.py        # EIP 登入驗證
    └── test_tasks.py        # Task 執行測試
```

### 執行測試

```bash
cd backend

# 🟢 單元測試 (每次改動後快速驗證)
uv run pytest tests/unit -v

# 🟡 整合測試 (需要內網帳號)
# 在 config.json 中設定 test_eip_id 和 test_eip_psw
uv run pytest tests/integration -v -m integration

# 執行全部測試
uv run pytest tests/ -v
```

### 撰寫新測試

#### 單元測試 (Unit Test)

不需要真實帳號，使用 mock 模擬外部依賴：

```python
# tests/unit/test_my_feature.py
import pytest
from app.tasks.my_task import MyTaskParams

class TestMyTaskModels:
    def test_params_defaults(self):
        """驗證參數預設值"""
        params = MyTaskParams()
        assert params.option is None
        
    def test_params_validation(self):
        """驗證參數驗證"""
        params = MyTaskParams(date="2025-12-12")
        assert params.date == "2025-12-12"
```

#### 整合測試 (Integration Test)

需要真實 EIP 帳號，標記為 `@pytest.mark.integration`：

```python
# tests/integration/test_my_crawler.py
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_crawler(vgh_client):
    """測試爬蟲流程"""
    from app.tasks.my_task import MyTask
    
    task = MyTask()
    result = await task.run({"date": "2025-12-12"}, vgh_client)
    
    assert result.status == "success"
```

### conftest.py Fixtures

| Fixture | 說明 | 使用場景 |
|---------|------|----------|
| `eip_credentials` | 從環境變數讀取帳號 | 整合測試 |
| `vgh_client` | 已登入的 VghClient | 整合測試 |
| `mock_vgh_client` | Mock VghClient | 單元測試 |
| `mock_supabase` | Mock Supabase | 單元測試 |

---

## 常見問題

### Q: 如何取得 EIP Session?

```python
async def run(self, params: dict, client: VghClient, ...):
    session = client.session  # VghSession 物件
    
    # 發送請求
    resp = await session.get("https://...")
    resp = await session.post("https://...", data={...})
```

### Q: 如何讀取/寫入 Google Sheets?

```python
from app.db.supabase import get_setting_from_db
from google.oauth2.service_account import Credentials
import gspread

# 從 DB 讀取設定
settings = await get_setting_from_db("my_task_settings")
sheet_id = settings.get("sheet_id")

# 使用 gspread
creds = Credentials.from_service_account_file("path/to/creds.json", ...)
gc = gspread.authorize(creds)
sh = gc.open_by_key(sheet_id)
worksheet = sh.worksheet("Sheet1")
```

### Q: 如何從 Supabase 讀取設定?

```python
from app.db.supabase import get_setting_from_db

settings = await get_setting_from_db("my_setting_key")
# 回傳 dict 或 None
```

---

## 前端開發

> 📖 前端詳細規範請參考 [frontend/FRONTEND_GUIDE.md](frontend/FRONTEND_GUIDE.md)

前端使用 React 19 + TypeScript + Vite + TailwindCSS，主要包含：
- **API Client** (`src/api/`): 封裝的 HTTP 請求工具
- **共用元件** (`src/components/ui/`): Button, Card, Badge 等
- **頁面元件** (`src/pages/`): 各功能頁面

### 開發資訊

| 項目 | 說明 |
|------|------|
| 前端 Port | `5173` |
| 後端 Port | `5487` |
| API Proxy | `vite.config.ts` 自動轉發 `/api/*` |
| 框架版本 | React 19, TypeScript 5.9, Vite 7 |
