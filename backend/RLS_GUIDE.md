# Supabase RLS 遷移指南

> 本文件說明從 **service_role key** 遷移到 **anon key + RLS** 的完整計畫

---

## 目錄

1. [目前狀態](#1-目前狀態)
2. [Key 類型說明](#2-key-類型說明)
3. [遷移前置條件](#3-遷移前置條件)
4. [RLS Policy 設計](#4-rls-policy-設計)
5. [程式碼變更](#5-程式碼變更)
6. [遷移步驟](#6-遷移步驟)
7. [驗證與測試](#7-驗證與測試)
8. [回滾計畫](#8-回滾計畫)

---

## 1. 目前狀態

### 1.1 使用的 Key

| 項目 | 目前值 | 目標值 |
|------|--------|--------|
| `supabase_key` | `sb_secret_...` (service_role) | `eyJ...` (anon key) |
| RLS | ❌ 繞過 | ✅ 啟用 |

### 1.2 影響範圍

以下模組使用 Supabase：

| 檔案 | 使用的表 | 需要 RLS? |
|------|----------|-----------|
| `routers/auth.py` | `users`, `user_roles` | ⚠️ 需 service_role |
| `routers/sheets.py` | `doctor_sheets` | ✅ 可啟用 RLS |
| `routers/templates.py` | `op_templates` | ✅ 可啟用 RLS |
| `routers/stats.py` | `task_logs` | ✅ 可啟用 RLS |
| `auth/service.py` | `users`, `user_roles` | ⚠️ 需 service_role |
| `core/task_logger.py` | `task_logs` | ✅ 可啟用 RLS |
| `core/alert.py` | (Email settings) | ⚠️ 需 service_role |
| `tasks/opnote/config.py` | `doctor_sheets`, `op_templates` | ✅ 可啟用 RLS |

---

## 2. Key 類型說明

### 2.1 Supabase API Keys

| Key 類型 | 用途 | RLS 行為 | 安全性 |
|----------|------|----------|--------|
| **anon (publishable)** | 前端 / 公開 API | ✅ 受 RLS 限制 | 可暴露 |
| **service_role (secret)** | 後端管理操作 | ❌ 繞過 RLS | **絕對不可暴露** |

### 2.2 使用 anon key 的條件

使用 anon key 時，必須搭配：

1. **RLS Policies**：在 Supabase Console 設定每個表的存取規則
2. **JWT**：請求需帶 `Authorization: Bearer <JWT>` header
3. **JWT claims**：RLS policy 可讀取 `auth.jwt()` 中的 claims

### 2.3 JWT 結構

Zbot 自簽的 JWT 包含以下 claims：

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // 用戶 UUID (必須)
  "iss": "zbot",
  "aud": "authenticated",
  "role": "authenticated",
  "doc_code": "4050",                             // 醫師代碼
  "zbot_role": "user",                            // 系統角色: admin | vs | user
  "allowed_prefixes": ["note_", "surgery_"],      // 可執行的 task 前綴
  "exp": 1735600000,
  "iat": 1735500000
}
```

---

## 3. 遷移前置條件

### 3.1 必須完成的項目

- [ ] **JWT `sub` 必須是 UUID**
  - 目前狀態：✅ 已在 `auth/service.py` 中修復
  - Supabase RLS 的 `auth.uid()` 會讀取 JWT 的 `sub` claim

- [ ] **JWT 必須使用正確的 secret 簽名**
  - 目前狀態：✅ 使用 `SUPABASE_JWT_SECRET` 簽名
  - 位置：`app/config.py` 中的 `SUPABASE_JWT_SECRET`

- [ ] **Backend 需支援雙 Client 模式**
  - 目前狀態：✅ `get_supabase_client(use_user_jwt=True/False)`
  - 位置：`app/db/client.py`

- [ ] **RLS Policies 已在 Supabase Console 設定**
  - 目前狀態：❌ 尚未設定
  - 見 [第 4 節](#4-rls-policy-設計)

---

## 4. RLS Policy 設計

### 4.1 核心原則

```
┌─────────────────────────────────────────────────────────────┐
│  RLS 存取控制矩陣                                            │
├─────────────────────────────────────────────────────────────┤
│  角色          │  自己的資料  │  他人資料  │  所有資料       │
│  ──────────────│──────────────│────────────│────────────────│
│  user          │  ✅ R/W      │  ❌        │  ❌             │
│  vs            │  ✅ R/W      │  ✅ R      │  ❌             │
│  admin         │  ✅ R/W      │  ✅ R/W    │  ✅ R/W         │
│  service_role  │  ✅ R/W      │  ✅ R/W    │  ✅ R/W (繞過)  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 各表的 RLS Policy

#### `users` 表

> ⚠️ **特殊處理**：登入驗證必須用 service_role，不設 RLS

```sql
-- 不啟用 RLS，僅由 Backend (service_role) 存取
-- ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
```

#### `user_roles` 表

> ⚠️ **特殊處理**：權限查詢必須用 service_role

```sql
-- 不啟用 RLS
```

#### `doctor_sheets` 表

```sql
-- 啟用 RLS
ALTER TABLE public.doctor_sheets ENABLE ROW LEVEL SECURITY;

-- Policy 1: 所有已登入者可讀取 (用於顯示列表)
CREATE POLICY "Authenticated users can read all sheets"
ON public.doctor_sheets FOR SELECT
TO authenticated
USING (true);

-- Policy 2: 用戶只能更新自己的 (根據 JWT 中的 doc_code)
CREATE POLICY "Users can update own sheets"
ON public.doctor_sheets FOR UPDATE
TO authenticated
USING (doc_code = (auth.jwt()->>'doc_code'));

-- Policy 3: VS/Admin 可更新任何人的
CREATE POLICY "VS and Admin can update any sheets"
ON public.doctor_sheets FOR UPDATE
TO authenticated
USING (auth.jwt()->>'zbot_role' IN ('vs', 'admin'));

-- Policy 4: 任何已登入者可新增
CREATE POLICY "Authenticated users can insert"
ON public.doctor_sheets FOR INSERT
TO authenticated
WITH CHECK (true);
```

#### `op_templates` 表

```sql
-- 啟用 RLS
ALTER TABLE public.op_templates ENABLE ROW LEVEL SECURITY;

-- Policy 1: 所有已登入者可讀取
CREATE POLICY "Authenticated users can read all templates"
ON public.op_templates FOR SELECT
TO authenticated
USING (true);

-- Policy 2: 用戶只能更新自己的範本 (doc_code 匹配或是 GLOBAL)
CREATE POLICY "Users can update own templates"
ON public.op_templates FOR UPDATE
TO authenticated
USING (
  doc_code = (auth.jwt()->>'doc_code')
  OR doc_code IS NULL  -- GLOBAL 範本
);

-- Policy 3: 只有 admin 可以更新 GLOBAL 範本
CREATE POLICY "Only admin can update global templates"
ON public.op_templates FOR UPDATE
TO authenticated
USING (
  doc_code IS NULL 
  AND auth.jwt()->>'zbot_role' = 'admin'
);

-- Policy 4: 任何已登入者可新增個人範本
CREATE POLICY "Users can insert own templates"
ON public.op_templates FOR INSERT
TO authenticated
WITH CHECK (doc_code = (auth.jwt()->>'doc_code') OR doc_code IS NULL);

-- Policy 5: Admin 可刪除任何範本
CREATE POLICY "Admin can delete any template"
ON public.op_templates FOR DELETE
TO authenticated
USING (auth.jwt()->>'zbot_role' = 'admin');

-- Policy 6: 用戶可刪除自己的範本
CREATE POLICY "Users can delete own templates"
ON public.op_templates FOR DELETE
TO authenticated
USING (doc_code = (auth.jwt()->>'doc_code'));
```

#### `task_logs` 表

```sql
-- 啟用 RLS
ALTER TABLE public.task_logs ENABLE ROW LEVEL SECURITY;

-- Policy 1: 用戶只能讀取自己的 log
CREATE POLICY "Users can read own logs"
ON public.task_logs FOR SELECT
TO authenticated
USING (user_id = auth.uid());

-- Policy 2: VS/Admin 可讀取所有 log
CREATE POLICY "VS and Admin can read all logs"
ON public.task_logs FOR SELECT
TO authenticated
USING (auth.jwt()->>'zbot_role' IN ('vs', 'admin'));

-- Policy 3: 系統可寫入 (由 Backend 寫入)
CREATE POLICY "System can insert logs"
ON public.task_logs FOR INSERT
TO authenticated
WITH CHECK (true);
```

---

## 5. 程式碼變更

### 5.1 目前已完成 ✅

| 項目 | 狀態 | 位置 |
|------|------|------|
| JWT `sub` 改為 UUID | ✅ | `auth/service.py` |
| `get_supabase_client()` 支援雙模式 | ✅ | `db/client.py` |
| Authorization header 正確設定 | ✅ | `db/client.py` |
| JWT Middleware 設定 context | ✅ | `middleware/` |

### 5.2 遷移時需變更 ❌

| 項目 | 變更內容 | 位置 |
|------|----------|------|
| `config.json` | 改用 anon key | `backend/config.json` |
| Auth 相關呼叫 | 確保使用 `use_user_jwt=False` | `auth/service.py` |
| Alert 相關呼叫 | 確保使用 `use_user_jwt=False` | `core/alert.py` |

---

## 6. 遷移步驟

### Phase 1: 準備 (不影響現有功能)

- [ ] 1.1 在 Supabase Console 取得 **anon key**
- [ ] 1.2 保存現有 service_role key 作為 backup
- [ ] 1.3 在 Supabase Console 設定 RLS Policies (先不啟用)
- [ ] 1.4 建立測試腳本驗證 RLS 邏輯

### Phase 2: 程式碼調整

- [ ] 2.1 在 `config.json` 新增 `supabase_service_key` 欄位
- [ ] 2.2 修改 `app/config.py` 支援雙 key
- [ ] 2.3 修改 `auth/service.py` 明確使用 service_role key
- [ ] 2.4 修改 `core/alert.py` 明確使用 service_role key

### Phase 3: 切換與測試

- [ ] 3.1 在 Supabase Console 啟用 RLS
- [ ] 3.2 將 `supabase_key` 改為 anon key
- [ ] 3.3 完整測試所有功能
- [ ] 3.4 監控錯誤日誌

### Phase 4: 清理

- [ ] 4.1 移除舊的測試程式碼
- [ ] 4.2 更新文件

---

## 7. 驗證與測試

### 7.1 測試腳本

建立 `backend/tests/test_rls.py`：

```python
"""
RLS 驗證測試

執行前請確保：
1. 已在 Supabase Console 設定 RLS Policies
2. 已啟用 RLS
"""
import pytest
from supabase import create_client

SUPABASE_URL = "https://xxx.supabase.co"
ANON_KEY = "eyJ..."  # anon key
USER_JWT = "eyJ..."  # 測試用戶的 JWT

def test_can_read_sheets_with_jwt():
    """已登入用戶可讀取 doctor_sheets"""
    client = create_client(SUPABASE_URL, ANON_KEY)
    client.postgrest.session.headers['Authorization'] = f'Bearer {USER_JWT}'
    
    result = client.table('doctor_sheets').select('*').execute()
    assert result.data is not None

def test_cannot_read_users_with_jwt():
    """已登入用戶不可讀取 users 表 (如果 RLS 設定正確)"""
    client = create_client(SUPABASE_URL, ANON_KEY)
    client.postgrest.session.headers['Authorization'] = f'Bearer {USER_JWT}'
    
    # 應該拋出錯誤或返回空
    result = client.table('users').select('*').execute()
    assert len(result.data) == 0  # RLS 阻擋

def test_cannot_update_others_sheets():
    """用戶不可更新他人的 sheets"""
    client = create_client(SUPABASE_URL, ANON_KEY)
    client.postgrest.session.headers['Authorization'] = f'Bearer {USER_JWT}'
    
    # 嘗試更新他人資料，應該失敗
    with pytest.raises(Exception):
        client.table('doctor_sheets').update({
            'worksheet': 'hack'
        }).eq('doc_code', '9999').execute()
```

### 7.2 手動測試清單

| 測試項目 | 預期結果 |
|----------|----------|
| 登入功能 | ✅ 正常 (使用 service_role) |
| 讀取刀表列表 | ✅ 正常 (RLS 允許) |
| 更新自己的刀表 | ✅ 正常 (RLS 允許) |
| 更新他人的刀表 (user 角色) | ❌ 被拒 (RLS 阻擋) |
| 更新他人的刀表 (vs 角色) | ✅ 正常 (RLS 允許) |
| 讀取範本列表 | ✅ 正常 (RLS 允許) |
| 刪除 GLOBAL 範本 (user 角色) | ❌ 被拒 (RLS 阻擋) |
| 刪除 GLOBAL 範本 (admin 角色) | ✅ 正常 (RLS 允許) |

---

## 8. 回滾計畫

如果遷移後發生問題：

### 8.1 快速回滾

1. 將 `config.json` 的 `supabase_key` 改回 service_role key
2. 重啟 Backend

### 8.2 完整回滾

1. 執行上述快速回滾
2. 在 Supabase Console 停用 RLS：
   ```sql
   ALTER TABLE public.doctor_sheets DISABLE ROW LEVEL SECURITY;
   ALTER TABLE public.op_templates DISABLE ROW LEVEL SECURITY;
   ALTER TABLE public.task_logs DISABLE ROW LEVEL SECURITY;
   ```

---

## 附錄

### A. 雙 Key 配置範例

未來 `config.json` 格式：

```json
{
    "supabase_url": "https://xxx.supabase.co",
    "supabase_anon_key": "eyJ...",
    "supabase_service_key": "eyJ...",
    "dev_mode": false,
    "log_level": "INFO"
}
```

### B. 相關文件

- [Supabase RLS 官方文件](https://supabase.com/docs/guides/auth/row-level-security)
- [JWT Claims 參考](https://supabase.com/docs/guides/auth/jwts)
