-- =============================================================================
-- Zbot Supabase Database Schema
-- =============================================================================
-- 
-- 專案:    Zbot
-- 版本:    v3 (含任務追蹤)
-- 更新:    2025-12-15
-- 
-- 說明:
--   此檔案為 Supabase 資料庫結構的完整定義。
--   新部署時，在 Supabase SQL Editor 中執行此腳本即可建立所有表。
--   修改資料庫欄位時必須同步更新此檔案，並通知其他開發者執行 Migration。
--
-- 相關文件:
--   - backend/BACKEND_GUIDE.md: 後端開發指南（包含資料表使用說明）
--
-- =============================================================================
-- 資料表概覽
-- =============================================================================
-- 
-- 【用戶相關】
--   1. users         - 使用者帳號
--   2. user_roles    - 使用者權限角色
-- 
-- 【系統設定】
--   3. settings      - 系統設定 (Key-Value JSON)
-- 
-- 【任務模板】
--   4. op_templates  - 手術組套模板
--   5. doctor_sheets - 醫師 GSheet 刀表設定
-- 
-- 【任務追蹤】
--   6. task_logs     - 任務執行詳細日誌
--   7. task_stats    - 任務統計快取
-- 
-- =============================================================================
-- RLS (Row Level Security) 權限概覽
-- =============================================================================
-- 
-- | 資料表        | 讀取           | 寫入           |
-- |--------------|----------------|----------------|
-- | users        | 自己           | 自己           |
-- | user_roles   | 自己           | ❌ (Admin API) |
-- | settings     | 全表           | ❌ (Admin API) |
-- | op_templates | 全表           | ❌ (Admin API) |
-- | doctor_sheets| 全表           | 自己           |
-- | task_logs    | Admin Only     | 全部 (Insert)  |
-- | task_stats   | Admin Only     | 全部 (Admin)   |
-- 
-- =============================================================================


-- =============================================================================
-- [0] 共用函數: updated_at 自動更新觸發器
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- [1] 資料表: users (使用者帳號)
-- =============================================================================
-- 
-- 用途: 儲存應用程式使用者資訊
-- 
-- 驗證邏輯:
--   - DOC 開頭帳號: 透過 VGH EIP 內網驗證
--   - 其他帳號:     透過此表 eip_psw 欄位比對 (明文)
--

CREATE TABLE IF NOT EXISTS public.users (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    
    -- 認證欄位
    eip_id text NOT NULL,                              -- 帳號 (EIP 帳號如 DOC4106F 或平台帳號如 admin)
    eip_psw text NULL,                                 -- 密碼 (EIP 自動同步，平台帳號手動設定)
    doc_code text NULL,                                -- 醫師代碼 (從 EIP 帳號解析，如 4106)
    
    -- 使用者資訊
    display_name text NULL,                            -- 顯示名稱 (從 EIP 通訊錄取得)
    
    -- 時間戳記
    created_at timestamptz NULL DEFAULT now(),
    last_login timestamptz NULL,                       -- 最後登入時間 (首次登入前為 NULL)
    
    -- 約束
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_eip_id_key UNIQUE (eip_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_doc_code ON public.users(doc_code);

-- 註解
COMMENT ON TABLE public.users IS 'Zbot 使用者帳號表';
COMMENT ON COLUMN public.users.eip_id IS '帳號。DOC 開頭為 EIP 帳號，其他為平台帳號';
COMMENT ON COLUMN public.users.eip_psw IS '密碼。EIP 帳號自動同步，平台帳號需手動設定';
COMMENT ON COLUMN public.users.doc_code IS '醫師代碼。從 EIP 帳號解析 (如 DOC4106F => 4106)';

-- RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_read_self ON public.users
FOR SELECT USING (eip_id = (auth.jwt()->>'eip_id'));

CREATE POLICY users_insert_self ON public.users
FOR INSERT WITH CHECK (eip_id = (auth.jwt()->>'eip_id'));

CREATE POLICY users_update_self ON public.users
FOR UPDATE USING (eip_id = (auth.jwt()->>'eip_id'))
WITH CHECK (eip_id = (auth.jwt()->>'eip_id'));


-- =============================================================================
-- [2] 資料表: user_roles (使用者權限)
-- =============================================================================
-- 
-- 用途: 儲存使用者權限 (獨立管理，使用者無法自行修改)
-- 
-- 權限角色:
--   - admin:    全部權限
--   - master:   全部權限
--   - cr:       note_*, opnote_*, dashboard_*, stats_* 權限
--   - basic_2:  note_*, opnote_*, ivi_* 權限
--   - basic_1:  note_ivi_*, opnote_*, ivi_* 權限
--   - basic_0:  無功能權限
--

CREATE TABLE IF NOT EXISTS public.user_roles (
    user_id uuid NOT NULL,
    role text NOT NULL DEFAULT 'basic_0',
    
    -- 時間戳記
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    
    -- 約束
    CONSTRAINT user_roles_pkey PRIMARY KEY (user_id),
    CONSTRAINT user_roles_user_fk FOREIGN KEY (user_id) 
        REFERENCES public.users(id) ON DELETE CASCADE
);

-- 觸發器
CREATE TRIGGER trigger_user_roles_updated_at
    BEFORE UPDATE ON public.user_roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 註解
COMMENT ON TABLE public.user_roles IS 'Zbot 使用者角色表 (獨立管理，使用者無法自行修改)';
COMMENT ON COLUMN public.user_roles.role IS '權限角色: admin, master, cr, basic_2, basic_1, basic_0';

-- RLS
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_roles_read_self ON public.user_roles
FOR SELECT USING (
    user_id IN (SELECT id FROM public.users WHERE eip_id = (auth.jwt()->>'eip_id'))
);


-- =============================================================================
-- [3] 資料表: settings (系統設定)
-- =============================================================================
-- 
-- 用途: 儲存系統與任務設定 (Key-Value JSON 形式)
-- 
-- 常用 Key 值:
--   - role_definitions:        動態角色權限定義
--   - stats_op_settings:       手術統計設定 {sheet_id, groups}
--   - stats_fee_settings:      費用碼統計設定 {sheet_id, sheet_name, sum_groups}
--   - dashboard_bed_settings:  待床追蹤設定 {sheet_id, worksheet_name}
--   - smtp_config:             Email 告警設定 {host, port, user, password, from, to}
--

CREATE TABLE IF NOT EXISTS public.settings (
    key text PRIMARY KEY,
    value jsonb NOT NULL,
    
    -- 時間戳記
    created_at timestamptz NULL DEFAULT now(),
    updated_at timestamptz NULL DEFAULT now()
);

CREATE TRIGGER trigger_settings_updated_at
    BEFORE UPDATE ON public.settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 註解
COMMENT ON TABLE public.settings IS 'Zbot 系統設定表 (Key-Value JSON)';
COMMENT ON COLUMN public.settings.key IS '設定鍵名 (如 stats_op_settings)';
COMMENT ON COLUMN public.settings.value IS '設定內容 (JSON 格式)';

-- RLS
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY settings_read_all ON public.settings
FOR SELECT USING (true);


-- =============================================================================
-- [4] 資料表: op_templates (手術組套模板)
-- =============================================================================
-- 
-- 用途: 手術組套模板 (用於生成手術紀錄)
-- 
-- 模板繼承:
--   - GLOBAL: 系統預設模板 (doc_code = NULL)
--   - DOCTOR: 醫師客製模板 (doc_code = 醫師代碼)
--   查詢時優先使用 DOCTOR 模板，找不到才使用 GLOBAL
--
-- 支援的手術類型 (op_type):
--   - PHACO:  白內障超音波乳化手術
--   - LENSX:  飛秒雷射白內障手術
--   - VT:     玻璃體切除術
--   - IVI:    玻璃體內注射
--   - TRABE:  小樑切除術
--   - BLEB:   濾過泡修整
--
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- COL_* 命名準則 (重要!)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--
-- 所有動態填充欄位都使用 COL_* 後綴 + 全大寫命名:
--
-- 1. op_templates.required_fields / optional_fields:
--    儲存: ["COL_IOL", "COL_FINAL", "COL_TARGET"] 或 ["$COL_IOL", ...]
--    後端會正規化為純欄位名 (IOL, FINAL, TARGET)
--
-- 2. op_templates.template 佔位符:
--    使用: $COL_IOL, $COL_FINAL, $COL_COMPLICATIONS 等
--
-- 3. doctor_sheets.column_map:
--    Key 使用: {"COL_IOL": "IOL", "COL_FINAL": "Final", ...}
--
-- 4. 前端顯示:
--    純欄位名 (IOL, Final, Target)，不顯示 COL_ 前綴
--
--

CREATE TABLE IF NOT EXISTS public.op_templates (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- 識別欄位
    op_type text NOT NULL,                             -- 手術類型 (PHACO, VT, IVI, LENSX 等)
    doc_code text NULL,                                -- 醫師代碼 (NULL = GLOBAL 模板)
    
    -- 模板內容
    op_name text NOT NULL,                             -- 手術名稱 (如 PHACOEMULSIFICATION...)
    op_code text NULL,                                 -- 手術代碼 (如 OPH 1342)
    template text NULL,                                -- 手術記錄模板 (含佔位符)
    compl_template text NULL,                          -- 併發症模板
    
    -- ICD 編碼 (JSON)
    icd_codes jsonb NULL,                              -- 側別對應 ICD {"OD": {code, name}, "OS": {code, name}}
    
    -- 欄位定義 (JSON)
    required_fields jsonb NULL,                        -- 必填欄位 ["COL_IOL", "COL_FINAL"]
    optional_fields jsonb NULL,                        -- 選填欄位 ["COL_TARGET", "COL_SN"]
    
    -- 時間戳記
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    
    -- 唯一約束: 同一醫師同一手術類型只能有一個模板
    CONSTRAINT op_templates_unique_type UNIQUE (op_type, doc_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_op_templates_op_type ON public.op_templates(op_type);
CREATE INDEX IF NOT EXISTS idx_op_templates_doc_code ON public.op_templates(doc_code);

-- 觸發器
CREATE TRIGGER trigger_op_templates_updated_at
    BEFORE UPDATE ON public.op_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 註解
COMMENT ON TABLE public.op_templates IS 'Zbot 手術組套模板表';
COMMENT ON COLUMN public.op_templates.doc_code IS '醫師代碼。NULL 表示 GLOBAL 系統模板';
COMMENT ON COLUMN public.op_templates.template IS '手術記錄模板，支援佔位符如 $COL_IOL, $COL_FINAL, $COL_COMPLICATIONS';

-- RLS
ALTER TABLE public.op_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY op_templates_read_all ON public.op_templates
FOR SELECT USING (true);


-- =============================================================================
-- [5] 資料表: doctor_sheets (醫師 GSheet 刀表設定)
-- =============================================================================
-- 
-- 用途: 醫師 Google Sheet 刀表設定
-- 
-- 欄位對應 (column_map): 
--   定義刀表欄位名稱與系統內部欄位的對應關係
--   
--   【實際使用的欄位】(用於從 GSheet 讀取補充資料):
--     - COL_HISNO:        病歷號欄位名 (用於比對病人)
--     - COL_SIDE_OR_DIAGNOSIS: 側別或診斷欄位名 (用於同病歷號多筆時區分 OD/OS)
--     - COL_OP:           術式欄位名 (決定使用哪個手術模板)
--     - COL_IOL:          IOL 人工水晶體型號
--     - COL_FINAL:        最終度數
--     - COL_TARGET:       目標度數
--     - COL_SN:           IOL 序號
--     - COL_CDE:          CDE (累積能量)
--     - COL_LENSX:        Lensx 飛秒雷射標記
--     - COL_COMPLICATIONS: 術中併發症 (預設 Nil)
--

CREATE TABLE IF NOT EXISTS public.doctor_sheets (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- 識別欄位
    doc_code text NOT NULL UNIQUE,                     -- 醫師代碼
    
    -- Google Sheet 設定
    sheet_id text NOT NULL,                            -- Google Sheet ID
    worksheet text NOT NULL DEFAULT 'Sheet1',          -- 工作表名稱
    header_row int NOT NULL DEFAULT 1,                 -- 標題列位置 (1-indexed)
    
    -- 欄位對應 (JSON)
    column_map jsonb NULL,                             -- {"COL_HISNO": "ID", "COL_OP": "術式", ...}
    
    -- 時間戳記
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 觸發器
CREATE TRIGGER trigger_doctor_sheets_updated_at
    BEFORE UPDATE ON public.doctor_sheets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 註解
COMMENT ON TABLE public.doctor_sheets IS 'Zbot 醫師刀表設定表';
COMMENT ON COLUMN public.doctor_sheets.column_map IS '刀表欄位對應。詳見表定義註解了解實際使用的欄位';

-- RLS
ALTER TABLE public.doctor_sheets ENABLE ROW LEVEL SECURITY;

CREATE POLICY doctor_sheets_read_all ON public.doctor_sheets
FOR SELECT USING (true);

CREATE POLICY doctor_sheets_insert_own ON public.doctor_sheets
FOR INSERT WITH CHECK (doc_code = (auth.jwt()->>'doc_code'));

CREATE POLICY doctor_sheets_update_own ON public.doctor_sheets
FOR UPDATE USING (doc_code = (auth.jwt()->>'doc_code'))
WITH CHECK (doc_code = (auth.jwt()->>'doc_code'));

CREATE POLICY doctor_sheets_delete_own ON public.doctor_sheets
FOR DELETE USING (doc_code = (auth.jwt()->>'doc_code'));


-- =============================================================================
-- [6] 資料表: task_logs (任務執行詳細日誌)
-- =============================================================================
-- 
-- 用途: 記錄所有任務執行情況，用於審計和故障排查
-- 
-- 任務識別碼範例:
--   - note_ivi_submit:      IVI 注射記錄送出
--   - note_surgery_submit:  手術記錄送出
--   - dashboard_bed:        待床追蹤
--   - stats_op_update:      手術統計更新
--   - stats_fee_update:     費用碼統計更新
--

CREATE TABLE IF NOT EXISTS public.task_logs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    
    -- 任務識別
    task_id text NOT NULL,                    -- 任務 ID (note_surgery_submit 等)
    job_id text NULL,                         -- Job ID (UUID from JobManager)
    
    -- 人員資訊
    operator_eip_id text NOT NULL,            -- 操作者帳號 (登入使用者)
    target_doc_code text NULL,                -- 目標醫師代碼 (若適用)
    
    -- 執行資訊
    status text NOT NULL,                     -- success / failed / cancelled
    items_processed int DEFAULT 0,            -- 處理筆數
    error_message text NULL,                  -- 錯誤訊息 (若失敗)
    
    -- 時間戳記
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    
    -- 額外資訊
    metadata jsonb NULL,                      -- 可擴展資料 (參數摘要等)
    
    created_at timestamptz DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON public.task_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_operator ON public.task_logs(operator_eip_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_completed ON public.task_logs(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_logs_status ON public.task_logs(status);

-- 註解
COMMENT ON TABLE public.task_logs IS 'Zbot 任務執行詳細日誌';
COMMENT ON COLUMN public.task_logs.task_id IS '任務識別碼 (如 note_surgery_submit)';
COMMENT ON COLUMN public.task_logs.operator_eip_id IS '操作者 EIP 帳號';
COMMENT ON COLUMN public.task_logs.target_doc_code IS '目標醫師代碼 (若適用)';
COMMENT ON COLUMN public.task_logs.items_processed IS '處理筆數';

-- RLS
ALTER TABLE public.task_logs ENABLE ROW LEVEL SECURITY;

-- 只有 Admin 可讀全部 (開發者專用)
CREATE POLICY task_logs_admin_read ON public.task_logs
FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.user_roles ur
        JOIN public.users u ON ur.user_id = u.id
        WHERE u.eip_id = (auth.jwt()->>'eip_id')
        AND ur.role = 'admin'
    )
);

-- 所有已登入使用者可寫入記錄 (由後端控制)
CREATE POLICY task_logs_insert ON public.task_logs
FOR INSERT WITH CHECK (true);


-- =============================================================================
-- [7] 資料表: task_stats (任務統計快取)
-- =============================================================================
-- 
-- 用途: 快速統計任務執行情況，用於前端顯示信任徽章
-- 
-- 計算邏輯:
--   - note_ivi_submit, note_surgery_submit: 按「筆」計算 (success 欄位)
--   - 其他任務 (dashboard_bed, stats_*): 按「次」計算 (一次執行 = 1)
--

CREATE TABLE IF NOT EXISTS public.task_stats (
    task_id text PRIMARY KEY,                 -- 任務 ID
    
    -- 累計統計
    total_runs int DEFAULT 0,                 -- 總執行次數
    total_success int DEFAULT 0,              -- 成功次數
    total_items int DEFAULT 0,                -- 累計處理筆數
    
    -- 最後更新
    last_run_at timestamptz NULL,
    updated_at timestamptz DEFAULT now()
);

-- 觸發器
CREATE TRIGGER trigger_task_stats_updated_at
    BEFORE UPDATE ON public.task_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 註解
COMMENT ON TABLE public.task_stats IS 'Zbot 任務統計快取表';
COMMENT ON COLUMN public.task_stats.total_runs IS '總執行次數';
COMMENT ON COLUMN public.task_stats.total_success IS '成功次數';
COMMENT ON COLUMN public.task_stats.total_items IS '累計處理筆數 (用於信任徽章顯示)';

-- RLS
ALTER TABLE public.task_stats ENABLE ROW LEVEL SECURITY;

-- 只有 Admin 可讀 (開發者專用)
CREATE POLICY task_stats_admin_read ON public.task_stats
FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.user_roles ur
        JOIN public.users u ON ur.user_id = u.id
        WHERE u.eip_id = (auth.jwt()->>'eip_id')
        AND ur.role = 'admin'
    )
);

-- 系統可更新 (backend 使用 service_role)
CREATE POLICY task_stats_upsert ON public.task_stats
FOR ALL USING (true) WITH CHECK (true);


-- =============================================================================
-- [8] RPC 函數: increment_task_stats (原子更新統計)
-- =============================================================================
-- 
-- 用途: 原子更新 task_stats 表，避免並發時的 Race Condition
-- 
-- 呼叫方式 (Python):
--   supabase.rpc("increment_task_stats", {
--       "p_task_id": "note_ivi_submit",
--       "p_is_success": True,
--       "p_items": 5,
--       "p_run_time": "2025-12-15T10:00:00Z"
--   }).execute()
--

CREATE OR REPLACE FUNCTION public.increment_task_stats(
    p_task_id TEXT,
    p_is_success BOOLEAN,
    p_items INTEGER,
    p_run_time TIMESTAMPTZ
) RETURNS VOID AS $$
BEGIN
    -- 使用 INSERT ON CONFLICT 實現原子 UPSERT
    -- PostgreSQL 會自動處理行級鎖定，確保並發安全
    INSERT INTO public.task_stats (task_id, total_runs, total_success, total_items, last_run_at)
    VALUES (
        p_task_id,
        1,
        CASE WHEN p_is_success THEN 1 ELSE 0 END,
        p_items,
        p_run_time
    )
    ON CONFLICT (task_id) DO UPDATE SET
        total_runs = public.task_stats.total_runs + 1,
        total_success = public.task_stats.total_success + CASE WHEN p_is_success THEN 1 ELSE 0 END,
        total_items = public.task_stats.total_items + p_items,
        last_run_at = p_run_time;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 授權
GRANT EXECUTE ON FUNCTION public.increment_task_stats TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_task_stats TO service_role;


-- =============================================================================
-- [9] 初始化資料: role_definitions (角色權限定義)
-- =============================================================================
-- 
-- 用途: 定義各角色可執行的 Task 前綴
-- 快取: 系統啟動時透過 /api/status 讀取
-- Fallback: backend/app/auth/service.py 的 DEFAULT_ROLE_PERMISSIONS
--

INSERT INTO settings (key, value) VALUES (
  'role_definitions',
  '{
    "roles": {
      "admin": {
        "display_name": "管理員",
        "allowed_prefixes": ["*"]
      },
      "vs": {
        "display_name": "醫界宗師",
        "allowed_prefixes": ["*"]
      },
      "cr": {
        "display_name": "奴工頭頭",
        "allowed_prefixes": ["note_", "opnote_", "dashboard_", "stats_", "ivi_"]
      },
      "basic_2": {
        "display_name": "奴工",
        "allowed_prefixes": ["note_", "opnote_", "ivi_"]
      },
      "basic_1": {
        "display_name": "初心者Lv.1",
        "allowed_prefixes": ["note_ivi_", "opnote_", "ivi_"]
      },
      "basic_0": {
        "display_name": "初心者Lv.0",
        "allowed_prefixes": []
      }
    },
    "default_role": "basic_0"
  }'::jsonb
) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;


-- =============================================================================
-- [10] 資料表: surkeycode_map (手術代碼對應表)
-- =============================================================================
-- 
-- 用途: 將醫院系統的 surkeycode 對應到手術類型 (op_type)
-- 
-- 設計說明:
--   - 無 Foreign Key 到 op_templates，允許定義尚未有模板的 op_type
--   - op_type 為邏輯分類，系統會從 op_templates 查找對應模板
--   - 若 op_templates 無對應模板，前端顯示 "無對應模板" 訊息
--
-- 資料來源:
--   - 初始資料由 scripts/db/init_surkeycode_map.py 匯入
--   - 共 246 筆 surkeycode 對應
--

CREATE TABLE IF NOT EXISTS public.surkeycode_map (
    surkeycode text PRIMARY KEY,              -- 手術代碼 (如 13421)
    op_type text NOT NULL,                    -- 對應手術類型 (如 PHACO, LENSX)
    surname text,                             -- 英文名稱 (用於 debug)
    surnamec text,                            -- 中文名稱 (用於 debug)
    surmemo text,                             -- 診斷備註 (區分同 surname 不同診斷)
    created_at timestamptz DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_surkeycode_map_op_type ON public.surkeycode_map(op_type);

-- RLS
ALTER TABLE public.surkeycode_map ENABLE ROW LEVEL SECURITY;

CREATE POLICY surkeycode_map_read_all ON public.surkeycode_map
FOR SELECT USING (true);

-- 註解
COMMENT ON TABLE public.surkeycode_map IS '手術代碼對應表，無 FK 設計允許彈性擴充';
COMMENT ON COLUMN public.surkeycode_map.surkeycode IS '醫院系統手術代碼 (如 13421)';
COMMENT ON COLUMN public.surkeycode_map.op_type IS '對應手術類型 (PHACO, LENSX, VT 等)';


-- =============================================================================
-- 驗證與說明
-- =============================================================================
-- 
-- 完成後執行以下查詢確認表已建立:
-- 
--   SELECT table_name FROM information_schema.tables 
--   WHERE table_schema = 'public' 
--   ORDER BY table_name;
-- 
-- 預期結果包含:
--   - users
--   - user_roles
--   - settings
--   - op_templates
--   - doctor_sheets
--   - task_logs
--   - task_stats
-- 
-- =============================================================================
