# Zbot Frontend 開發指南

> 🤖 **AI 開發者注意**：本文檔設計用於讓 AI 模型快速理解專案規範，產生一致品質的程式碼。

> 📖 **相關文檔**：[README](../README.md) | [BACKEND_GUIDE](../backend/BACKEND_GUIDE.md) | [LAUNCHER_GUIDE](../zbot_launcher/LAUNCHER_GUIDE.md) | [RELEASE_GUIDE](../RELEASE_GUIDE.md)

---

## 架構概覽

```
frontend/
├── src/
│   ├── api/           # API 客戶端與端點定義
│   ├── components/    # 共用元件
│   │   └── ui/        # 基礎 UI 元件 (Button, Card, Input...)
│   ├── constants/     # 共用常數
│   │   └── taskNames.ts  # 任務 ID 對應中文名稱
│   ├── context/       # React Context (AuthContext)
│   ├── hooks/         # 自訂 Hooks
│   ├── pages/         # 頁面元件
│   ├── services/      # 服務層
│   ├── styles/        # 共用樣式與主題常數
│   │   └── theme.ts   # THEME 常數定義
│   ├── config.ts      # 全域設定
│   └── App.tsx        # 路由與佈局
├── FRONTEND_GUIDE.md  # 本文檔
└── package.json
```

---

## 技術棧

| 類別 | 技術 | 版本 |
|------|------|------|
| **框架** | React | 19.x |
| **建置工具** | Vite | 7.x |
| **語言** | TypeScript | 5.9.x |
| **樣式** | Tailwind CSS | 3.4.x |
| **程式碼編輯器** | CodeMirror 6 | 6.x |
| **Icons** | Lucide React | 0.556.x |

---

## 開發與部署

### 本地開發

```bash
# 安裝依賴
cd frontend
npm install

# 啟動開發伺服器 (需要後端運行)
npm run dev
```

### 環境需求

- **後端**：需同時運行 `uv run uvicorn app.main:app --reload --port 5487`
- **API Proxy**：Vite 自動代理 `/api/*` 到 `localhost:5487`

### 建置

```bash
npm run build      # 產生 dist/ 資料夾
npm run preview    # 預覽建置結果
```

---

## Quick Reference

```typescript
// 📌 標準 imports
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { StepIndicator } from '../components/StepIndicator';
import { CodeMirrorEditor } from '../components/ui/CodeMirrorEditor';
import { JsonEditor } from '../components/ui/JsonEditor';
import { tasksApi } from '../api/tasks';
import type { Job, JobResult } from '../api/tasks';
import { THEME } from '../styles/theme';
import { TASK_NAMES, getTaskName } from '../constants/taskNames';

// 📌 THEME 常數 (從 styles/theme.ts 匯入，勿自行定義)
// THEME.primary      = '#137fec'
// THEME.primaryLight = '#eef4fd'
// THEME.success      = '#22c55e'
// THEME.successLight = '#dcfce7'
// THEME.disabled     = '#f3f4f6'

// 📌 任務名稱 (從 constants/taskNames.ts 匯入)
// getTaskName('note_surgery_submit') => '手術紀錄'

// 📌 API 類型 (從 api/tasks.ts 匯入，勿自行定義)
// Job: { id, status, progress, result, error, task_id, ... }
// JobResult: { status, message, details, sheet_url, ... }
```

---

## 全域設定檔 (config.ts)

所有可調整的前端設定參數集中在 `frontend/src/config.ts`：

```typescript
import { 
    DEMO_MODE,               // Demo 模式開關
    IDLE_TIMEOUT_MS,         // 閒置警告觸發時間
    IDLE_COUNTDOWN_SECONDS,  // 登出倒數秒數
    TASK_POLL_INTERVAL_MS,   // 任務輪詢間隔
} from '../config';
```

| 常數 | 預設值 | 說明 |
|------|--------|------|
| `DEMO_MODE` | `false` | Demo 模式開關 (錄影時設為 `true`) |
| `IDLE_TIMEOUT_MS` | 1.5 分鐘 | 閒置多久後顯示警告 |
| `IDLE_COUNTDOWN_SECONDS` | 30 秒 | 警告顯示後倒數多久自動登出 |
| `TASK_POLL_INTERVAL_MS` | 1.5 秒 | 輪詢任務狀態的間隔 |
| `BG_TASKS_POLL_RUNNING_MS` | 3 秒 | 有任務時背景輪詢間隔 |
| `BG_TASKS_POLL_IDLE_MS` | 30 秒 | 無任務時背景輪詢間隔 |

---

## Demo 模式 (錄影用)

Demo 模式使用模擬資料，避免真實病患隱私問題。影響範圍僅限 `SurgeryPage` 和 `IviPage`。

### 啟用方式

編輯 `frontend/src/config.ts`：

```typescript
export const DEMO_MODE = true;  // ← 改這裡
```

### Mock 資料位置

```
frontend/src/mocks/
├── surgeryMocks.ts   # Surgery 頁面 Mock 資料
└── iviMocks.ts       # IVI 頁面 Mock 資料
```

修改 Mock 資料後，Demo 模式會直接載入這些資料，不會呼叫後端 API。

### 注意事項

- Demo 模式下送出按鈕只會模擬成功，不會實際寫入資料
- 其他頁面（登入、設定等）正常運作
- **Production build 前記得將 `DEMO_MODE` 改回 `false`**

---

## 專案設定檔說明

以下檔案是 Vite + React + TypeScript + Tailwind 標準架構的一部分：

| 檔案 | 用途 |
|------|------|
| `vite.config.ts` | Vite 核心設定 (proxy、build 分割) |
| `tailwind.config.js` | Tailwind CSS 自訂色彩、字型 |
| `postcss.config.js` | PostCSS 設定 (Tailwind/autoprefixer) |
| `tsconfig.json` | TypeScript 根設定 (IDE 需要) |
| `tsconfig.app.json` | 前端程式碼的 TS 設定 |
| `tsconfig.node.json` | vite.config.ts 的 TS 設定 |
| `eslint.config.js` | ESLint 程式碼檢查設定 |

> 這些都是標準設定，一般不需修改。

---

## 閒置自動登出

當使用者閒置超過設定時間且無背景任務執行中，會顯示警告並倒數自動登出。

### Hook 用法

```typescript
import { useIdleTimer } from './hooks/useIdleTimer';

const { resetTimer } = useIdleTimer({
    onIdle: () => setShowWarning(true), // 閒置時觸發
    enabled: isAuthenticated,           // 只在登入時啟用
    // idleTimeoutMs 使用 config.ts 預設值
});
```

### 相關元件

- **`useIdleTimer`**: 偵測閒置並檢查背景任務
- **`IdleWarningModal`**: 顯示倒數警告對話框

---

## Design System

### 色彩系統 (CSS Variables)

| 變數名稱 | 值 | 用途 |
|----------|-----|------|
| `--bg-app` | `#F5F5F7` | 頁面背景 |
| `--bg-card` | `#FFFFFF` | 卡片背景 |
| `--text-primary` | `#1D1D1F` | 主要文字 |
| `--text-secondary` | `#86868B` | 次要文字 |
| `--accent-blue` | `#007AFF` | 主要操作按鈕 |
| `--accent-red` | `#FF3B30` | 錯誤/危險 |
| `--accent-green` | `#34C759` | 成功狀態 |
| `--accent-orange` | `#FF9500` | 警告狀態 |

### 間距規範

- 頁面 padding: `32px` (p-8)
- 卡片內 padding: `20px`
- 元素間距: `16px`
- 小元素間距: `8px`

### 圓角規範

| 元素類型 | 圓角大小 |
|----------|----------|
| 大容器/卡片 | `16px` (--radius-lg) |
| 按鈕/輸入框 | `8-10px` (--radius-md) |
| Badge/標籤 | `20px` (pill) |
| Icon 容器 | `14px` |

### 陰影規範

```css
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
```

---

## Component Catalog

### Button

```tsx
import { Button } from '../components/ui/Button';

// Variants
<Button variant="primary">主要操作</Button>
<Button variant="secondary">次要操作</Button>
<Button variant="ghost">文字按鈕</Button>
<Button variant="danger">危險操作</Button>

// Sizes
<Button size="sm">小</Button>
<Button size="md">中 (預設)</Button>
<Button size="lg">大</Button>

// Loading 狀態
<Button isLoading>執行中...</Button>

// Disabled
<Button disabled>不可用</Button>
```

### Card

```tsx
import { Card } from '../components/ui/Card';

// 基本用法
<Card>內容</Card>

// 含標題
<Card title="設定">內容</Card>

// 含 footer
<Card footer={<Button>儲存</Button>}>內容</Card>

// 自訂 padding
<Card style={{ padding: '24px' }}>內容</Card>
```

### Badge

```tsx
import { Badge } from '../components/ui/Badge';

<Badge variant="success">成功</Badge>
<Badge variant="error">錯誤</Badge>
<Badge variant="warning">警告</Badge>
<Badge variant="info">資訊</Badge>
<Badge variant="neutral">一般</Badge>
```

### Input

```tsx
import { Input } from '../components/ui/Input';

<Input 
    label="欄位名稱"
    placeholder="請輸入..."
    value={value}
    onChange={e => setValue(e.target.value)}
/>

// 驗證錯誤
<Input 
    label="Email"
    error="格式不正確"
    value={email}
    onChange={...}
/>
```

### TrustBadge

信任徽章元件，在任務頁面初始步驟顯示累積完成筆數，建立使用者信任感。

```tsx
import { useTaskStats } from '../hooks/useTaskStats';
import { TrustBadge } from '../components/TrustBadge';

const { stats } = useTaskStats('note_surgery_submit');

// 在初始步驟、非 loading 狀態時顯示
{!loading && stats && stats.total_items > 0 && (
    <TrustBadge taskId="note_surgery_submit" totalItems={stats.total_items} />
)}
```

### CodeMirrorEditor

基於 CodeMirror 6 的文字編輯器，支援拖放插入、Undo/Redo、自訂游標樣式。

```tsx
import { CodeMirrorEditor } from '../components/ui/CodeMirrorEditor';

<CodeMirrorEditor
    value={content}
    onChange={(val) => setContent(val)}
    placeholder="輸入內容..."
    style={{ minHeight: '400px' }}
/>
```

**功能**：
- 原生 Undo/Redo (⌘Z / ⌘Shift+Z)
- 拖放精確定位 (紅色 dropCursor)
- 3px 粗游標

### JsonEditor

專門用於編輯 JSON 的編輯器，支援語法高亮和驗證。

```tsx
import { JsonEditor } from '../components/ui/JsonEditor';

<JsonEditor
    value={jsonString}
    onChange={(val) => setJsonString(val)}
    onValidChange={(isValid, error) => setError(error)}
    placeholder='{"key": "value"}'
    height="120px"
/>
```

**功能**：
- JSON 語法高亮 (Key 綠色、String 藍色、Number 橙色)
- 自動括號配對
- 即時驗證與錯誤標示

### Toast

```tsx
import { showToast } from '../components/ui/Toast';

showToast.success('操作成功');
showToast.error('發生錯誤');
showToast.info('提示訊息');
```

### Tooltip

```tsx
import { Tooltip } from '../components/ui/Tooltip';

<Tooltip content="提示文字">
    <Button>Hover Me</Button>
</Tooltip>
```

### StepIndicator

步驟進度條元件，用於多步驟流程頁面（如 Surgery、IVI）。

```tsx
import { StepIndicator } from '../components/StepIndicator';

// 定義步驟
type Step = 'fetch' | 'edit' | 'done';
const STEPS: { id: Step; label: string }[] = [
    { id: 'fetch', label: '抓取排程' },
    { id: 'edit', label: '確認編輯' },
    { id: 'done', label: '完成' },
];

// 使用元件
<StepIndicator
    steps={STEPS}
    currentStepId={currentStep}
    onStepClick={(stepId) => goToStep(stepId as Step)}
    disableNavigation={currentStep === 'done'}
/>
```

**Props**：

| Prop | Type | 說明 |
|------|------|------|
| `steps` | `{ id: string; label: string }[]` | 步驟定義陣列 |
| `currentStepId` | `string` | 目前步驟的 ID |
| `onStepClick` | `(stepId: string) => void` | 點擊已完成步驟時的回呼 |
| `disableNavigation` | `boolean` | 禁用導航（例如最終步驟時） |

---

## Page Patterns

### 標準頁面結構 (Dynamic Centering)
此結構確保：
1. **內容少時**：垂直水平置中 (透過 `my-auto` + `mx-auto`)
2. **內容多時**：自動長高並出現捲軸 (避免被切卡)

```tsx
// 外層：min-h-full 繼承 App.tsx 的高度，flex-col 用於佈局
// 移除 overflow-hidden，交由 App.tsx 的 main 區域處理捲動
<div className="bg-[#F5F5F7] min-h-full flex flex-col p-4 font-sans">
    
    // 內層：w-full + max-w-limit 限制寬度
    // mx-auto: 水平置中
    // my-auto: 垂直置中 (在 flex-col 中，當高度有餘裕時自動分配 margin)
    <div className="relative z-10 w-full max-w-5xl mx-auto my-auto">
        
        {/* Header */}
        <header className="mb-8">
            {/* ... */}
        </header>

        {/* Main Content */}
        <Card style={{ padding: '24px' }}>
            {/* 內容 */}
        </Card>

        {/* Status Message */}
        {statusMsg && (
            <div className="mt-4 ...">
                {statusMsg}
            </div>
        )}
        
    </div>
</div>
```

### 狀態訊息樣式

```tsx
// 成功
<div style={{
    padding: '12px 16px',
    backgroundColor: 'rgba(34, 197, 94, 0.1)',
    border: '1px solid rgba(34, 197, 94, 0.2)',
    borderRadius: '8px',
    color: '#15803d',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
}}>
    <Check size={16} />
    {message}
</div>

// 錯誤
<div style={{
    padding: '12px 16px',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    borderRadius: '8px',
    color: '#dc2626',
}}>
    {message}
</div>
```

---

## API 呼叫模式

### 執行背景任務

```tsx
import { tasksApi } from '../api/tasks';

const handleRun = async () => {
    setLoading(true);
    setStatusMsg('執行中...');
    
    try {
        // 1. 啟動任務
        const { job_id } = await tasksApi.run('task_id', {
            params: { date: '2025-01-01' },
            eip_id: localStorage.getItem('eip_id') || undefined,
            eip_psw: localStorage.getItem('eip_psw') || undefined,
        });

        // 2. 輪詢狀態
        for (let i = 0; i < 60; i++) {
            await new Promise(r => setTimeout(r, 1000));
            const job = await tasksApi.getJob(job_id);
            
            if (job.status === 'success') {
                // ⚠️ 重要：檢查 result.status 是否為 'error'
                if (job.result?.status === 'error') {
                    throw new Error(job.result?.details?.join(', ') || '執行失敗');
                }
                setStatusMsg(job.result?.message || '執行成功');
                setStatusType('success');
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
        setStatusType('error');
    } finally {
        setLoading(false);
    }
};
```

### 一般 API 請求

```tsx
import { apiClient } from '../api/client';

// GET
const data = await apiClient.get<ResponseType>('/api/endpoint');

// POST
const result = await apiClient.post<ResponseType>('/api/endpoint', { key: 'value' });

// PUT
await apiClient.put('/api/endpoint', { key: 'value' });

// DELETE
await apiClient.delete('/api/endpoint');
```

---

## 範例頁面

參考 `frontend/src/pages/_TemplatePage.tsx` 作為新頁面的起點。

---

## 建立新頁面

### Step 1: 建立頁面元件

```tsx
// frontend/src/pages/MyNewPage.tsx
import React, { useState, useCallback } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { tasksApi } from '../api/tasks';

export const MyNewPage: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [statusMsg, setStatusMsg] = useState<string | null>(null);
    
    const handleRun = useCallback(async () => {
        setLoading(true);
        // ... 任務邏輯
    }, []);
    
    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-4 font-sans">
            <div className="relative z-10 w-full max-w-5xl mx-auto my-auto">
                <Card style={{ padding: '24px' }}>
                    <Button onClick={handleRun} disabled={loading}>
                        {loading ? '執行中...' : '執行任務'}
                    </Button>
                    {statusMsg && <p>{statusMsg}</p>}
                </Card>
            </div>
        </div>
    );
};
```

### Step 2: 加入路由

```tsx
// frontend/src/App.tsx
import { MyNewPage } from './pages/MyNewPage';

// 在 Routes 中加入
<Route path="/my-new-page" element={<MyNewPage />} />
```

### Step 3: 加入 Sidebar

```tsx
// frontend/src/components/Sidebar.tsx
import { YourIcon } from 'lucide-react';

// 在 NAV_ITEMS 中加入
{ icon: YourIcon, label: '新功能', path: '/my-new-page', prefix: 'my_new' }
```

> **prefix** 用於任務統計徽章顯示，應對應到後端 task_id 的前綴

---

## ⚠️ 任務輪詢注意事項

### 必須處理的狀態

輪詢後端任務時，必須處理以下 **3 種終止狀態**：

| Job Status | 說明 | 處理方式 |
|------------|------|----------|
| `success` | 任務完成 | 還需檢查 `result.status` |
| `failed` | 任務失敗 | 顯示 `job.error` |
| `cancelled` | 使用者取消 | 顯示「任務已取消」 |

### ⚠️ 常見陷阱：result.status 檢查

**問題**：後端任務執行成功 (`job.status === 'success'`)，但任務結果可能是錯誤 (`result.status === 'error'`)。

```tsx
// ❌ 錯誤：只檢查 job.status
if (job.status === 'success') {
    setStatusMsg('執行成功');  // 可能顯示錯誤的成功訊息
}

// ✅ 正確：同時檢查 result.status
if (job.status === 'success') {
    if (job.result?.status === 'error') {
        setStatusType('error');
        setStatusMsg(job.result?.details?.join(', ') || '執行失敗');
    } else {
        setStatusType('success');
        setStatusMsg(job.result?.message || '執行成功');
    }
}
```

### ⚠️ 常見陷阱：忘記處理 cancelled

**問題**：使用者從背景任務面板取消任務，但頁面輪詢沒有處理，導致 UI 卡住。

```tsx
// ❌ 錯誤：缺少 cancelled 處理
if (job.status === 'success') { ... }
if (job.status === 'failed') { ... }
// 如果 cancelled，迴圈會跑到 timeout

// ✅ 正確：加入 cancelled 處理
if (job.status === 'success') { ... }
if (job.status === 'failed') { throw new Error(job.error); }
if (job.status === 'cancelled') { throw new Error('任務已取消'); }
```

---

## Anti-patterns ❌

請避免以下做法：

| ❌ 避免 | ✅ 正確做法 |
|--------|------------|
| `min-h-screen` 在子頁面 | 移除，由 App.tsx 處理 |
| 硬編碼 `localhost:5487` | 使用相對路徑 `/api/...` |
| 直接 `fetch()` | 使用 `apiClient` 或 `tasksApi` |
| `export default function` | `export const PageName: React.FC = () =>` |
| 內聯色彩值 `#007AFF` | 使用 CSS 變數 `var(--accent-blue)` |

---

## 檔案命名

| 類型 | 格式 | 範例 |
|------|------|------|
| 頁面元件 | PascalCase + Page | `DashboardBedPage.tsx` |
| UI 元件 | PascalCase | `Button.tsx`, `Card.tsx` |
| API 模組 | camelCase | `tasks.ts`, `auth.ts` |
| 範例/內部 | 底線前綴 | `_TemplatePage.tsx` |
