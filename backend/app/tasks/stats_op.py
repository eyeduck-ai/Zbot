
import logging
import asyncio
import pandas as pd
from typing import List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.core.registry import TaskRegistry
from app.core.alert import get_setting_from_db
from app.db.gsheet import get_gsheet_service
from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask
from vghsdk.utils import to_western_date
from vghsdk.modules.surgery import SurgeryDeptScheduleTask, SurgeryScheduleParams

logger = logging.getLogger("stats_op")

# --- 預設醫生群組定義 (Default Doctor Groups) ---
# 若 Supabase 設定中未指定 `stats_op_doctor_groups`，將使用此預設值。
# 用於將特定醫生的手術量聚合到一個群組欄位 (如 Sum_Retina)。
DEFAULT_DOCTOR_GROUPS = {
    "Sum_Retina": ["周昱百", "季聖筑", "林泰祺", "翁章旂", "陳世真", "黃德光", "黃怡銘"],
    "Sum_Cornea": ["陳克華", "張晉瑜", "林佩玉", "范乃文", "許志堅", "郭懿萱"],
    "Sum_Glaucoma": ["陳美如", "柯玉潔", "郭哲源", "張毓帆"],
    "Sum_Neuro": ["鄭惠禎", "洪偉哲", "王安國"],
    "Sum_Plasty": ["游偉光", "蔡傑智"]
}

class StatsOpParams(BaseModel):
    sheet_id: Optional[str] = Field(None, description="Google Sheet ID (若未提供則使用 DB 設定)")
    year: Optional[int] = Field(None, description="開始年份 (預設: 上個月)")
    month: Optional[int] = Field(None, description="開始月份 (預設: 上個月)")
    end_year: Optional[int] = Field(None, description="結束年份 (選填，用於範圍查詢)")
    end_month: Optional[int] = Field(None, description="結束月份 (選填，用於範圍查詢)")

class StatsOpResult(BaseModel):
    status: str
    message: str
    sheet_url: Optional[str] = None  # Google Sheets 連結

class StatsOpTask(BaseTask):
    """
    手術統計任務 (StatsOpTask)
    
    負責從 EIP 系統爬取手術排程資料，進行統計分析後，將結果寫入 Google Sheet。
    支援單月查詢或多月範圍查詢，並可針對特定醫生群組 (如網膜科、角膜科等) 進行加總聚合。
    
    Attributes:
        id (str): 任務識別碼 ('stats_op_update')
        name (str): 任務顯示名稱
        description (str): 任務功能描述
        params_model (Type[BaseModel]): 參數驗證模型 (StatsOpParams)
    """
    id: str = "stats_op_update"
    name: str = "手術統計 (Stats Op)"
    description = "查詢月份手術排程 -> 統計 -> 更新 Google Sheet (支援範圍查詢與多目標更新)"
    params_model = StatsOpParams

    async def run(self, params: StatsOpParams, client: VghClient, progress_callback: Callable[[int, str], Awaitable[None]] = None) -> StatsOpResult:
        """
        執行手術統計任務。

        流程:
        1. 初始化參數與日期範圍 (若未指定則預設為上個月)。
        2. 從 Supabase 載入設定 (stats_op_settings)，包含目標 Google Sheet ID 與醫生群組定義。
        3. 從 EIP 系統爬取手術排程資料 (支援一次性讀取大範圍)。
        4. 本地端過濾資料 (Filter) 與資料清理 (Parse Dates)。
        5. 統計分析:
           - 計算手術總量。
           - 識別白內障手術 (關鍵字: CATA)。
           - 識別 FLACS 手術 (關鍵字: LENSX)。
           - 產生樞紐分析表 (Pivot Tables)。
           - 應用醫生群組聚合 (Aggregation)。
        6. 將結果寫入 Google Sheet (支援多目標更新)。

        Args:
            params (StatsOpParams): 任務參數
            client (VghClient): 已登入的 EIP 連線 Client
            progress_callback (Callable): 進度回報 callback

        Returns:
            StatsOpResult: 執行結果 (Status, Message)
        """
        # params 已由 router 驗證並轉換為 StatsOpParams
        p = params
        # 從 client 取得 session
        session = client.session
        
        if progress_callback: await progress_callback(5, "初始化統計任務")

        # 0. 應用預設值 (Defaults)
        # 若未指定時間，預設為上個月
        now = datetime.now()
        if p.year is None or p.month is None:
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            p.year = prev_month_date.year
            p.month = prev_month_date.month
            
        # 決定查詢範圍 (Range)
        if p.end_year is None: p.end_year = p.year
        if p.end_month is None: p.end_month = p.month
        
        # 驗證日期順序
        start_date_val = p.year * 100 + p.month
        end_date_val = p.end_year * 100 + p.end_month
        
        if end_date_val < start_date_val:
            return StatsOpResult(status="error", message="結束日期必須大於或等於開始日期")
            
        # 1. 載入設定 (Settings Loading)
        # 支援多種 Supabase 設定格式 (向下相容):
        # 格式 A (整合式): { "targets": [...], "doctor_groups": {...} }
        # 格式 B (舊版列表): [ {"sheet_id":...}, ... ]
        # 格式 C (舊版字典): {"sheet_id":...}
        
        db_settings = await get_setting_from_db("stats_op_settings")
        doctor_groups = DEFAULT_DOCTOR_GROUPS
        db_targets = []

        if db_settings:
            # 優先嘗試解析新版整合格式
            if isinstance(db_settings, dict) and "targets" in db_settings:
                db_targets = db_settings.get("targets", [])
                if "doctor_groups" in db_settings:
                    doctor_groups = db_settings["doctor_groups"]
            # 相容舊版陣列格式
            elif isinstance(db_settings, list):
                db_targets = db_settings
            # 相容舊版單一物件格式
            elif isinstance(db_settings, dict) and "sheet_id" in db_settings:
                db_targets = [db_settings]
        
        # 2. 爬取排程資料 (Fetching)
        if progress_callback: await progress_callback(10, "正在讀取手術排程")

        # 2. 爬取排程資料 (Fetching)
        if progress_callback: await progress_callback(10, "正在讀取手術排程")

        def parse_roc_ym(d_str):
            """解析 ROC (1120101) -> (2023, 1) using utils"""
            dt = to_western_date(d_str)
            if dt:
                return dt.year, dt.month
            return 0, 0

        # 一次性抓取優化 (Single Fetch)
        # 從開始月份的 1 號抓取，EIP 會回傳該日之後的所有排程
        roc_year = p.year - 1911
        roc_date_str = f"{roc_year:03d}{p.month:02d}01"
        
        logger.info(f"StatsOp Fetching from: {roc_date_str}")
        
        query_params = SurgeryScheduleParams(query="OPH", date=roc_date_str)
        fetcher = SurgeryDeptScheduleTask()
        
        # 使用 Exponential Backoff 重試
        from vghsdk.core import CRAWLER_CONFIG
        data = []
        for attempt in range(CRAWLER_CONFIG.max_retries + 1):
            try:
                data = await fetcher.run(query_params, client)
                if data:
                    break
                # Exponential backoff
                delay = min(
                    CRAWLER_CONFIG.retry_base_delay * (CRAWLER_CONFIG.retry_exponential_base ** attempt),
                    CRAWLER_CONFIG.retry_max_delay
                )
                logger.info(f"StatsOp retry {attempt + 1}, waiting {delay:.1f}s...")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.warning(f"Fetch failed attempt {attempt + 1}: {e}")
                delay = min(
                    CRAWLER_CONFIG.retry_base_delay * (CRAWLER_CONFIG.retry_exponential_base ** attempt),
                    CRAWLER_CONFIG.retry_max_delay
                )
                await asyncio.sleep(delay)
        
        if not data:
             return StatsOpResult(status="empty", message=f"無資料 ({p.year}/{p.month} 起)")

        if progress_callback: await progress_callback(50, "處理資料中")

        # 3. 資料處理與過濾 (Processing & Filtering)
        full_df = pd.DataFrame(data)
        
        if '手術日期' in full_df.columns:
             # 標準化日期格式
             full_df['手術日期'] = full_df['手術日期'].astype(str).str.strip()
             full_df['手術日期'] = full_df['手術日期'].apply(lambda x: x[1:] if len(x) == 8 and x.startswith('0') else x)
             
              
             # 解析年份與月份
             full_df['y_m'] = full_df['手術日期'].apply(lambda x: parse_roc_ym(str(x)))
             
             # 過濾出符合使用者指定範圍的資料
             def is_in_range(ym):
                 y, m = ym
                 val = y * 100 + m
                 return start_date_val <= val <= end_date_val
             
             mask = full_df['y_m'].apply(is_in_range)
             df = full_df[mask].copy()
             
             if df.empty:
                 return StatsOpResult(status="empty", message=f"指定範圍內無資料 ({p.year}/{p.month}-{p.end_year}/{p.end_month})")
        else:
             return StatsOpResult(status="error", message="資料來源缺少 '手術日期' 欄位")
             
        if progress_callback: await progress_callback(75, "正在寫入 Google Sheet")

        # 4. 目標解析 (Target Resolution)
        # 決定要更新哪些 Google Sheets
        targets = []
        
        if p.sheet_id:
             # Case 1: 參數指定了 Sheet ID (測試模式或單次執行)
             # 若此 ID 存在於 DB 設定中，則繼承 DB 中的詳細設定 (如中文 Worksheet 名稱)
             found_in_db = False
             for t in db_targets:
                 if isinstance(t, dict) and t.get("sheet_id") == p.sheet_id:
                     targets.append(t)
                     found_in_db = True
                     break
            
             if not found_in_db:
                 # 若 DB 無此 ID，使用基本設定 (預設英文 Worksheet 名稱)
                 targets.append({"sheet_id": p.sheet_id})
        else:
             # Case 2: 使用 DB 中的所有目標 (正式排程執行)
             for t in db_targets:
                 if isinstance(t, dict) and t.get("sheet_id"):
                     targets.append(t)
             
        if not targets:
             return StatsOpResult(status="error", message="未指定目標 Google Sheet ID (參數或 DB 設定)")

        logger.info(f"StatsOp 執行範圍: {p.year}/{p.month}-{p.end_year}/{p.end_month} -> 目標數: {len(targets)}")

        # 5. 統計分析 (Analysis)
        df['年月'] = df['手術日期'].apply(lambda x: f"{int(x[:3])+1911}{x[3:5]}") 
        
        CATARACT_KEYWORD = 'CATA'
        LENSX_KEYWORD = 'LENSX'
        
        # 補全欄位以防錯誤
        if '術前診斷' not in df.columns: df['術前診斷'] = ''
        if '手術名稱' not in df.columns: df['手術名稱'] = ''
        if '主刀' not in df.columns: df['主刀'] = 'Unknown'
        
        df = df.rename(columns={'主刀': '主刀醫師'})

        # 計算指標
        df['手術總量'] = 1
        df['白內障數量'] = df['術前診斷'].astype(str).str.contains(CATARACT_KEYWORD, case=False, na=False).astype(int)
        df['LENSX數量'] = df['手術名稱'].astype(str).str.contains(LENSX_KEYWORD, case=False, na=False).astype(int)

        # 樞紐分析 (Pivot Tables)
        # 基礎: 以 [年月, 主刀醫師] 分組
        overview = df.groupby(['年月', '主刀醫師'])[['手術總量', '白內障數量', 'LENSX數量']].sum().reset_index()
        
        # 轉置: 列=醫師, 欄=年月
        total_ops = pd.pivot_table(overview, values='手術總量', index='主刀醫師', columns='年月', fill_value=0)
        cataract_ops = pd.pivot_table(overview, values='白內障數量', index='主刀醫師', columns='年月', fill_value=0)
        lensx_ops = pd.pivot_table(overview, values='LENSX數量', index='主刀醫師', columns='年月', fill_value=0)
        
        # 應用聚合邏輯 (套用醫生群組設定)
        total_ops = self._apply_aggregation(total_ops, doctor_groups)
        cataract_ops = self._apply_aggregation(cataract_ops, doctor_groups)
        lensx_ops = self._apply_aggregation(lensx_ops, doctor_groups)

        # 6. 更新 Google Sheet (Update GSheet)
        gs = get_gsheet_service()
        
        success_count = 0
        details_msg = []
        first_total_ws_gid = None  # 用於儲存第一個 Total worksheet 的 GID
        
        for tgt in targets:
            sheet_id = tgt.get('sheet_id')
            
            # 取得 Worksheet 名稱 (支援從 DB 設定自訂，否則使用預設值)
            ws_total = tgt.get('worksheet_total', 'Total_Operations')
            ws_cataract = tgt.get('worksheet_cataract', 'Cataract_Operations')
            ws_lensx = tgt.get('worksheet_lensx', 'LENSX_Operations')
            
            try:
                gc = gs.get_pygsheets_client() 
                sh = gc.open_by_key(sheet_id)
                
                # 寫入各個分頁
                self._write_df(sh, ws_total, total_ops, include_index=True, merge_pivot=True)
                self._write_df(sh, ws_cataract, cataract_ops, include_index=True, merge_pivot=True)
                self._write_df(sh, ws_lensx, lensx_ops, include_index=True, merge_pivot=True)
                
                # 取得 Total worksheet 的 GID (用於產生直接連結)
                if first_total_ws_gid is None:
                    first_total_ws_gid = self._get_worksheet_gid(sh, ws_total)
                
                success_count += 1
                details_msg.append(f"Updated {sheet_id[:6]}")
            except Exception as e:
                logger.error(f"Failed to update target {sheet_id}: {e}")
                details_msg.append(f"Failed {sheet_id[:6]}: {e}")

        status = "success" if success_count > 0 else "error"
        # 產生月份顯示文字
        if p.end_year and p.end_month and (p.end_year != p.year or p.end_month != p.month):
            month_str = f"{p.month}-{p.end_month} 月"
        else:
            month_str = f"{p.month} 月"
        # 取得第一個成功的 sheet URL (targets[0] 是 dict，需提取 sheet_id)
        first_sheet_id = targets[0].get('sheet_id') if targets and isinstance(targets[0], dict) else targets[0] if targets else None
        # 產生 Sheet URL (包含 worksheet GID 直接開啟 Total 工作表)
        if first_sheet_id:
            if first_total_ws_gid is not None:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{first_sheet_id}/edit#gid={first_total_ws_gid}"
            else:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{first_sheet_id}"
        else:
            sheet_url = None
        return StatsOpResult(
            status=status, 
            message=f"更新 {month_str} 統計表",
            sheet_url=sheet_url
        )

    def _apply_aggregation(self, pivot_df: pd.DataFrame, groups: Dict[str, List[str]]) -> pd.DataFrame:
        """
        將 groups 定義的醫生群組 (如 Sum_Retina) 加總，並將結果列附加到表格下方。
        """
        df_out = pivot_df.copy()
        
        for group_name, doctors in groups.items():
            # 找出目前 Pivot Table 中存在的醫師
            valid_doctors = df_out.index.intersection(doctors)
            
            if not valid_doctors.empty:
                # 計算總和
                sum_row = df_out.loc[valid_doctors].sum()
                sum_row.name = group_name
                
                # 附加到 DataFrame (使用 concat)
                row_df = pd.DataFrame([sum_row])
                
                # 若該 Group row 已存在，先移除再加 (確保更新)
                if group_name in df_out.index:
                    df_out.drop(index=group_name, inplace=True)
                    
                df_out = pd.concat([df_out, row_df])
                
        return df_out

    def _get_worksheet_gid(self, spreadsheet, worksheet_name: str) -> int:
        """
        取得指定工作表的 GID (sheetId)。
        用於產生直接開啟該工作表的連結。
        
        Args:
            spreadsheet: pygsheets Spreadsheet 對象
            worksheet_name: 工作表名稱
            
        Returns:
            int: worksheet GID，若找不到則返回 None
        """
        try:
            wks = spreadsheet.worksheet_by_title(worksheet_name)
            return wks.id
        except Exception as e:
            logger.warning(f"無法取得 worksheet GID for '{worksheet_name}': {e}")
            return None

    def _write_df(self, sh, title, df, include_index=False, merge_overview=False, merge_pivot=False):
        """
        將 DataFrame 寫入指定的 Worksheet。
        支援 Pivot Merge 模式：保留舊有資料的欄位，並新增新月份的欄位。
        """
        try:
            try:
                wks = sh.worksheet_by_title(title)
            except:
                wks = sh.add_worksheet(title)
            
            final_df = df
            
            if merge_overview:
                # 總表合併邏輯 (Append raw rows)
                try:
                    existing_df = wks.get_as_df(start='A2', include_index=False)
                    if not existing_df.empty:
                        final_df = pd.concat([existing_df, df])
                        if '年月' in final_df.columns and '主刀醫師' in final_df.columns:
                            final_df = final_df.drop_duplicates(subset=['年月', '主刀醫師'], keep='last')
                            final_df = final_df.sort_values(['年月', '主刀醫師'])
                except Exception as e:
                    logger.warning(f"Overview Merge failed: {e}")
            
            elif merge_pivot:
                # 樞紐表合併邏輯 (Merge Columns)
                try:
                    existing_df = wks.get_as_df(start='A2', include_index=False, empty_value='', include_tailing_empty=False)
                    
                    if not existing_df.empty:
                        # 設定 Index
                        if '主刀醫師' in existing_df.columns:
                            existing_df.set_index('主刀醫師', inplace=True)
                        elif len(existing_df.columns) > 0:
                            # 假設第一欄是 Index
                            original_idx_name = existing_df.columns[0]
                            existing_df.set_index(original_idx_name, inplace=True)
                            existing_df.index.name = '主刀醫師'
                        
                        existing_df = existing_df.groupby(level=0).first()

                        # 合併新舊資料 (Concat Axis 1)
                        final_df = pd.concat([existing_df, df], axis=1)
                        
                        # 移除重複欄位 (保留最新的)
                        final_df.columns = final_df.columns.astype(str)
                        final_df = final_df.loc[:, ~final_df.columns.duplicated(keep='last')]
                        
                        # 填補空值並排序欄位 (年月)
                        final_df = final_df.fillna(0)
                        final_df = final_df.reindex(sorted(final_df.columns), axis=1)
                        
                except Exception as e:
                    logger.warning(f"Pivot Merge failed: {e}")

            # 清除舊內容並寫入新內容
            wks.clear()
            wks.update_value('A1', f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # 過濾空白欄位名稱以避免 pygsheets 警告
            if hasattr(final_df, 'columns'):
                final_df.columns = [str(c) if c else f"col_{i}" for i, c in enumerate(final_df.columns)]
            # 確保 index 有名稱
            if include_index and (not final_df.index.name or final_df.index.name == ''):
                final_df.index.name = '主刀醫師'
            wks.set_dataframe(final_df, 'A2', copy_index=include_index, nan='')
            
            # 版面調整 (Formatting)
            try:
                wks.frozen_rows = 2 
                wks.adjust_column_width(start=1, end=10) 
            except:
                pass
                
        except Exception as e:
            logger.error(f"Write error {title}: {e}")

# 註冊任務
TaskRegistry.register(StatsOpTask())
