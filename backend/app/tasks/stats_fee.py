
import time
import re
import json
import random
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from pydantic import BaseModel, Field

from app.core.registry import TaskRegistry
from app.core.alert import get_setting_from_db
from app.core.jobs import JobManager  # 用於檢查取消狀態
from app.core.cache import CacheManager  # 快取管理
from app.db.gsheet import get_gsheet_service
from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask

# --- 常數設定 ---
# 費用碼查詢 API 端點
FEE_API_URL = "https://rkeprd.vghtpe.gov.tw/CSTA/CostCenter/exportCstaDetail/exportDetail12"

logger = logging.getLogger("stats_fee")

# --- 預設聚合規則 (Default Aggregation Rules) ---
# 定義特殊識別符 (如 sum_cata)，對應一組子代碼。
# 若 DB 中未設定 sum_groups，將使用此預設值。
DEFAULT_SUM_GROUPS = {
    "sum_cata": ["P086007C", "P086008C", "P086009C", "P086010B", "P086012C"],
    "sum_plasty": [
        "P085001C", "P085002C", "P086802B", "P086803B", "P086804B", 
        "P086805B", "P086806B", "P086807B", "P086808B", "P086809B", 
        "P086810B", "P086811B", "P087003C", "P087004C", "P087005C", 
        "P087006C", "P087017C", "P087405B", "P087406B", "P087415B", 
        "P087416B"
    ],
    "sum_glaucoma": ["P085805C", "P085806C", "P085823B"],
    "sum_cornea": ["P085004C", "P085212B", "P085213B", "P085214C", "P085215B", "P085216B", "P085217B"],
    "sum_neuro": ["P086601C", "P086602C", "P086603C", "P086604C", "P086605C"],
    "sum_retina": [
        "P086206B", "P086207B", "P086208C", "P086209B", "P086410B", 
        "P086411B", "P086412B", "P086413B", "P086414B", "P086415B", 
        "P085608B"
    ],
    "sum_ivi": ["P086216C", "P086201C", "84584S04", "84584S05"]
}

class StatsFeeParams(BaseModel):
    sheet_id: Optional[str] = Field(None, description="Google Sheet ID (預設由 DB 讀取)")
    sheet_name: Optional[str] = Field(None, description="目標工作表名稱 (預設由 DB 讀取)")
    year: Optional[int] = Field(None, description="開始年份 (預設: 上個月)")
    month: Optional[int] = Field(None, description="開始月份 (預設: 上個月)")
    end_year: Optional[int] = Field(None, description="結束年份 (選填，用於範圍查詢)")
    end_month: Optional[int] = Field(None, description="結束月份 (選填，用於範圍查詢)")
    cost_id: str = Field("01400", description="成本中心代碼")
    password: str = Field("L9177", description="API 密碼")
    use_petition: str = Field("CCMACC31", description="API Petition Code")

class StatsFeeResult(BaseModel):
    status: str
    updated_cells: int
    details: List[str]
    message: Optional[str] = None  # 用於前端顯示
    sheet_url: Optional[str] = None  # Google Sheets 連結
    cache_id: Optional[str] = None  # 快取 ID (寫入失敗時提供)

class StatsFeeTask(BaseTask):
    """
    費用碼績效統計任務 (StatsFeeTask)
    
    負責從院內系統 (API) 爬取特定費用碼的執行數量，統計後填入 Google Sheet。
    系統會依據 Google Sheet 上的「手術碼」欄位決定要爬取的項目。
    
    功能特色:
    1. 支援「聚合代碼 (Aggregation)」:
       - 若 Sheet 上出現以 `sum_` 開頭的代碼 (如 sum_cata)，
       - 系統會自動依據設定 (DB: sum_groups 或 Default) 展開其對應的子代碼。
       - 分別爬取子代碼數據後，加總回填至該欄位。
    2. 支援「範圍查詢 (Range Query)」:
       - 可一次查詢多個月份 (Start ~ End)。
       - 自動在 Sheet 上尋找對應月份的欄位 (如 11407)。
       - 若月份欄位不存在，會自動在最右側新增。
       
    Attributes:
        id (str): 任務識別碼 ('stats_fee_update')
        name (str): 任務顯示名稱
        description (str): 任務功能描述
        params_model (Type[BaseModel]): 參數驗證模型 (StatsFeeParams)
    """
    id: str = "stats_fee_update"
    name: str = "費用碼績效統計 (Fee Stats)"
    description = "費用碼績效統計 (支援範圍查詢與聚合計算)"
    params_model = StatsFeeParams

    async def run(self, params: StatsFeeParams, client: VghClient, progress_callback: Callable[[int, str], Awaitable[None]] = None) -> StatsFeeResult:
        """
        執行費用碼統計任務。

        流程:
        1. 初始化與預設值設定 (若無指定時間則預設上個月)。
        2. 載入設定:
           - 從 DB (stats_fee_settings) 取得 Sheet ID 與 Worksheet Name。
           - 從 DB 取得聚合規則 (sum_groups)。
        3. 讀取 Sheet 上的目標手術碼清單。
        4. 準備查詢清單 (展開聚合代碼)。
        5. 執行爬蟲 (Fetch Phase):
           - 針對每個代碼呼叫院內 API。
           - 支援批次範圍查詢 (一次取得多個月份數據)。
        6. 寫入 Google Sheet (Write Phase):
           - 自動對應月份欄位 (如 11411)。
           - 若欄位不存在則自動建立。
           - 將統計結果填入對應儲存格。

        Args:
            params (StatsFeeParams): 任務參數
            client (VghClient): 已登入的 EIP 連線 Client
            progress_callback (Callable): 進度回報 callback

        Returns:
            StatsFeeResult: 執行結果 (Status, Stats, Details)
        """
        # params 已由 router 驗證並轉換為 StatsFeeParams
        p = params
        # 從 client 取得 session
        session = client.session
        
        # 1. 初始化預設值 (Defaults)
        # 若未指定時間，預設為上個月
        if p.year is None or p.month is None:
            now = datetime.now()
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            if p.year is None: p.year = prev_month_date.year
            if p.month is None: p.month = prev_month_date.month
            
        # 2. 載入設定 (Configuration)
        # 優先順序: 參數 > DB (stats_fee_settings dict) > DB (stats_fee_sheet_id fallback)
        # 同時載入 sum_groups (若 DB 有設定)
        
        sum_groups = DEFAULT_SUM_GROUPS
        db_settings = await get_setting_from_db("stats_fee_settings")
        
        if db_settings and isinstance(db_settings, dict):
            # A. 載入 Sheet 設定
            if not p.sheet_id: p.sheet_id = db_settings.get("sheet_id")
            if not p.sheet_name: p.sheet_name = db_settings.get("worksheet_name")
            
            # B. 載入聚合規則 (支援動態覆蓋)
            if "sum_groups" in db_settings:
                sum_groups = db_settings["sum_groups"]
        
        # 向後相容: 嘗試讀取舊設定 key (僅 ID)
        if not p.sheet_id:
            old_val = await get_setting_from_db("stats_fee_sheet_id")
            if old_val: p.sheet_id = str(old_val)
        
        # 驗證必要參數
        if not p.sheet_id:
             return StatsFeeResult(status="error", updated_cells=0, details=["缺少 Google Sheet ID (請檢查參數或 DB 設定)"])
        if not p.sheet_name:
             return StatsFeeResult(status="error", updated_cells=0, details=["缺少工作表名稱 (請檢查參數或 DB 設定)"])

        # 3. 初始化 Google Sheet 服務 (使用 pygsheets)
        gs = get_gsheet_service()
        try:
            gc = gs.get_pygsheets_client()
            sh = gc.open_by_key(p.sheet_id)
            wks = sh.worksheet_by_title(p.sheet_name)
        except Exception as e:
             return StatsFeeResult(status="error", updated_cells=0, details=[f"Google Sheet 連線失敗: {e}"])
        
        # 取得 worksheet GID (用於產生直接連結)
        worksheet_gid = wks.id
        
        # 4. 讀取目標手術碼 (Read Codes)
        # 從 Sheet 中讀取所有列出的手術碼，以決定要查詢哪些資料
        sheet_codes = self._get_surgery_codes(wks)
        if not sheet_codes:
            return StatsFeeResult(status="no_codes", updated_cells=0, details=["未發現任何手術碼 (請確認欄位名稱是否為 '手術碼')"])

        # 5. 計算查詢範圍 (Calculate Range)
        start_year, start_month = p.year, p.month
        end_year = p.end_year if p.end_year else start_year
        end_month = p.end_month if p.end_month else start_month
        
        # ⚠️ 重要：自動限制結束月份不超過上個月
        # API 特性：若查詢範圍包含未完成月份，整個回傳會是空的
        now = datetime.now()
        last_complete_year = now.year if now.month > 1 else now.year - 1
        last_complete_month = now.month - 1 if now.month > 1 else 12
        
        if (end_year > last_complete_year) or \
           (end_year == last_complete_year and end_month > last_complete_month):
            logger.warning(f"結束月份 {end_year}/{end_month} 超過上個完整月份，自動調整為 {last_complete_year}/{last_complete_month}")
            end_year = last_complete_year
            end_month = last_complete_month
        
        # 轉換為民國年 (ROC Year)
        start_roc = start_year - 1911
        end_roc = end_year - 1911
        
        start_ym_str = f"{start_roc:03d}{start_month:02d}"
        end_ym_str = f"{end_roc:03d}{end_month:02d}"
        
        # 資料容器: master_data[年月][手術碼] = 數量
        master_data = defaultdict(lambda: defaultdict(int))
        total_fetches = 0
        all_details = []

        # 6. 準備查詢清單 (Prepare Fetch List)
        # 邏輯: 
        # - 需要查詢 Sheet 上列出的所有代碼。
        # - 若遇到聚合代碼 (以 sum_ 開頭)，則不直接查詢，而是展開其對應的子代碼進行查詢。
        
        codes_to_fetch = set()
        
        for item in sheet_codes:
            code = item['code']
            if code.startswith('sum_'):
                # 展開子代碼 (Expand children from resolved sum_groups)
                children = sum_groups.get(code, [])
                if children:
                    for child in children:
                        codes_to_fetch.add(child.strip())
                else:
                    all_details.append(f"警告: {code} 未定義於聚合規則 (Config/Defaults)，無法聚合")
            else:
                codes_to_fetch.add(code)
                
        fetch_list = sorted(list(codes_to_fetch))
        total_codes = len(fetch_list)
        
        # 7. 執行爬蟲 (Fetch Phase)
        # 針對每個獨立手術碼，一次性查詢整個時間區間 (Range)
        logger.info(f"StatsFee: 準備查詢範圍 {start_ym_str} ~ {end_ym_str}，共 {total_codes} 個獨立代碼")
        
        # 取得 job_id 用於 Checkpoint 和取消檢查
        job_id = getattr(progress_callback, 'job_id', None) if progress_callback else None
        
        # 設定總項目數 (Checkpoint 支援)
        if job_id:
            JobManager.set_total_items(job_id, total_codes)
        
        for i, code in enumerate(fetch_list):
            # 檢查是否已被取消
            if job_id and JobManager.is_cancelled(job_id):
                logger.info(f"StatsFee: 任務已被取消 (job_id={job_id})")
                return StatsFeeResult(status="cancelled", updated_cells=0, details=[])
            
            # 斷點續跑: 跳過已完成項目
            if job_id and JobManager.is_item_completed(job_id, code):
                continue
            
            try:
                # 呼叫 API 取得區間資料 (使用 safe_request 自動重試 + backoff)
                data_map, is_valid = await self._fetch_fee_range_data(
                    client,  # 改傳 client 而非 session
                    p.cost_id, p.password, p.use_petition,
                    code, start_ym_str, end_ym_str
                )
                
                # ⚠️ 偵測到無效資料結構 (月份區間可能包含未結帳月份)
                if not is_valid:
                    # 計算建議的結束月份 (往前一個月)
                    if end_month > 1:
                        suggested_end = f"{end_roc:03d}{(end_month - 1):02d}"
                    else:
                        suggested_end = f"{(end_roc - 1):03d}12"
                    
                    return StatsFeeResult(
                        status="data_unavailable",
                        updated_cells=0,
                        details=[f"查詢 {code} 時偵測到無效資料結構"],
                        message=f"資料期間 {start_ym_str}~{end_ym_str} 可能橫跨到未結帳月份，建議將結束月份調整為 {suggested_end}"
                    )
                
                # 將結果寫入主資料結構
                for ym, qty in data_map.items():
                    master_data[ym][code] += qty
                
                # 標記完成 (Checkpoint)
                if job_id:
                    JobManager.mark_item_completed(job_id, code, f"查詢 {code} ({i+1}/{total_codes})")
                
            except Exception as e:
                logger.error(f"查詢 {code} 時發生錯誤: {e}")
                all_details.append(f"Fetch Error {code}: {e}")

        # 8. 寫入階段 (Write Phase) - 批次更新版本
        # 先收集所有需要更新的資料，最後一次性批次寫入以減少 API 請求
        if progress_callback: await progress_callback(90, "正在準備 Google Sheet 更新資料")
        
        # ⭐ 儲存快取 (在寫入前先保存，避免資料遺失)
        cache_data = {
            "master_data": dict(master_data),  # 轉換 defaultdict
            "sheet_codes": sheet_codes,
            "sum_groups": sum_groups,
            "start_year": start_year,
            "start_month": start_month,
            "end_year": end_year,
            "end_month": end_month,
        }
        cache_id = CacheManager.save_cache(
            task_id="stats_fee_update",
            params={"year": p.year, "month": p.month, "end_year": end_year, "end_month": end_month},
            data=cache_data,
            target_info={"sheet_id": p.sheet_id, "worksheet_name": p.sheet_name}
        )
        logger.info(f"StatsFee: 資料已快取 (cache_id={cache_id})")
        
        # 收集所有需要批次更新的儲存格
        # pygsheets.Worksheet.update_values_batch(ranges, values) 需要兩個陣列
        batch_ranges = []  # ['A1', 'B2', ...]
        batch_values = []  # [[[val1]], [[val2]], ...]
        total_updated = 0
        
        current_y, current_m = start_year, start_month
        
        while (current_y < end_year) or (current_y == end_year and current_m <= end_month):
            
            roc_year = current_y - 1911
            roc_month_str = f"{current_m:02d}"
            header_val = f"{roc_year:03d}{roc_month_str}" # 欄位標題範例: 11411
            
            # 取得或創建對應月份的欄位索引 (1-based column index)
            target_col_idx = self._get_or_create_column(wks, header_val)
            if target_col_idx is None:
                 all_details.append(f"無法存取欄位: {header_val}")
                 # 推進到下個月
                 if current_m == 12: current_y += 1; current_m = 1
                 else: current_m += 1
                 continue

            # 準備該月份的更新資料
            month_data = master_data[header_val]
            updates_count = 0
            
            for info in sheet_codes:
                code = info['code']
                val = 0
                
                if code.startswith('sum_'):
                    # 聚合計算 (Aggregation Logic - using resolved sum_groups)
                    children = sum_groups.get(code, [])
                    for child in children:
                        val += month_data.get(child.strip(), 0)
                else:
                    # 一般代碼
                    val = month_data.get(code, 0)
                
                # 將 1-based row/col 轉換為 A1 表示法
                col_letter = self._col_index_to_letter(target_col_idx)
                cell_range = f"{col_letter}{info['row_idx']}"
                batch_ranges.append(cell_range)
                batch_values.append([[val]])  # 每個 values 是 2D 陣列
                updates_count += 1
            
            total_updated += updates_count
            all_details.append(f"已準備 {header_val}: {updates_count} 筆")
            
            # 推進到下個月
            if current_m == 12:
                current_y += 1
                current_m = 1
            else:
                current_m += 1
        
        # 執行批次更新 (一次性寫入所有資料)
        write_failed = False
        if batch_ranges:
            try:
                if progress_callback: await progress_callback(95, f"正在批次寫入 {len(batch_ranges)} 筆資料")
                
                # pygsheets.Worksheet.update_values_batch(ranges, values, majordim='ROWS', parse=None)
                # ranges: 陣列 ['A1', 'B2', ...]
                # values: 陣列 [[[1]], [[2]], ...] (每個元素是 2D array)
                wks.update_values_batch(batch_ranges, batch_values, parse=True)
                
                all_details.append(f"批次更新完成: 共 {len(batch_ranges)} 個儲存格")
                logger.info(f"StatsFee: 批次更新完成，共 {len(batch_ranges)} 個儲存格")
                
                # ⭐ 寫入成功，刪除快取
                CacheManager.delete_cache(cache_id)
                cache_id = None  # 清除 cache_id 以免返回
                
            except Exception as e:
                all_details.append(f"批次寫入失敗: {e}")
                logger.error(f"StatsFee: 批次寫入失敗: {e}")
                write_failed = True
                # ⭐ 寫入失敗，保留快取供重試
                all_details.append(f"資料已快取，可重試上傳 (cache_id={cache_id})")
                
        # 產生月份顯示文字
        if end_year != start_year or end_month != start_month:
            month_str = f"{start_month}-{end_month} 月"
        else:
            month_str = f"{start_month} 月"
        
        # 產生 Sheet URL (包含 worksheet GID 直接開啟該工作表)
        if worksheet_gid is not None:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{p.sheet_id}/edit#gid={worksheet_gid}"
        else:
            sheet_url = f"https://docs.google.com/spreadsheets/d/{p.sheet_id}"
        
        # 根據寫入結果決定最終狀態
        final_status = "partial_success" if write_failed else "success"
        final_message = f"更新 {month_str} 統計表" if not write_failed else f"資料已爬取但上傳失敗，可重試"
        
        return StatsFeeResult(
            status=final_status, 
            updated_cells=total_updated if not write_failed else 0, 
            details=all_details,
            message=final_message,
            sheet_url=sheet_url,
            cache_id=cache_id  # ⭐ 失敗時返回 cache_id
        )

    async def _fetch_fee_range_data(self, client: VghClient, cost_id: str, password: str, use_petition: str, code: str, start_ym: str, end_ym: str) -> Tuple[Dict[str, int], bool]:
        """
        呼叫費用統計 API 取得指定區間的資料。
        會同時查詢門診 (O) 與 住院 (A) 並合併結果。
        使用 client.safe_request() 自動處理重試/backoff/session過期。
        
        Returns:
            Tuple[Dict[str, int], bool]: (資料字典, 是否為有效資料)
            若 is_valid=False，表示月份區間可能包含未結帳月份
        """
        combined = defaultdict(int)
        is_valid = True  # 預設有效
        
        for choose in ('O', 'A'):  # O=OPD, A=Admission
            payload = {
                'costid': cost_id,
                'startDate': start_ym,  # 格式: YYYYMM (ROC)
                'endDate': end_ym,
                'pfcod': code,
                'choose': choose,
                'password': password,
                'usePetition': use_petition
            }
            try:
                # 使用 safe_request 自動包含 retry/backoff/relogin
                r = await client.safe_request('POST', FEE_API_URL, data=payload)
                r.raise_for_status()
                
                data, valid = self._parse_range_count(r.text)
                if not valid:
                    is_valid = False  # 標記為無效
                else:
                    for ym, qty in data.items():
                        combined[ym] += qty
            except Exception as e:
                # 記錄錯誤但不中斷任務 (Allow partial failure)
                logging.warning(f"StatsFee API 錯誤 ({code}/{choose}): {e}")
                
        return dict(combined), is_valid

    def _parse_range_count(self, text: str) -> Tuple[Dict[str, int], bool]:
        """
        解析 API 回傳的 HTML/JS 內容，提取 JSON 資料。
        
        Returns:
            Tuple[Dict[str, int], bool]: (資料字典, 是否為有效資料結構)
            回傳結構: ({ '11407': 10, '11408': 5 }, True) 或 ({}, False)
        """
        # 1. 嘗試直接提取 JSON
        data_list = None
        try:
            data_list = json.loads(text)
        except:
            # 2. 若為 HTML，使用 Regex 提取 JS 變數 (var data = [...])
            m = re.search(r'var\s+data\s*=\s*(\[[\s\S]*?\]);', text)
            if m:
                try:
                    data_list = json.loads(m.group(1))
                except:
                    pass
        
        # 若無法解析 JSON 陣列，檢查是否為「未結帳」錯誤頁面
        if data_list is None or not isinstance(data_list, list):
            # 檢查 HTML 中是否含有「XXXXX還未結帳」錯誤訊息
            if re.search(r'\d{5}還未結帳', text):
                return {}, False  # 確認是未結帳錯誤，標記為無效
            else:
                return {}, True   # 只是該收費碼無資料，視為有效 (空資料)
        
        # 3. 遍歷資料陣列並加總
        result = defaultdict(int)
        for row in data_list:
            ym = str(row.get('acicym', '')).strip()  # acicym: 年月
            if ym == '總計': 
                continue
            
            try:
                qty = int(float(row.get('aciqnty', 0)))  # aciqnty: 數量
                result[ym] += qty
            except:
                pass
        
        return dict(result), True

    def _get_surgery_codes(self, wks) -> List[Dict]:
        """
        從 Google Sheet 讀取手術碼清單。
        假設標題列包含 "手術碼"。
        回傳: [{'code': 'P08...', 'row_idx': 5}, ...]
        
        Args:
            wks: pygsheets Worksheet 對象
        """
        vals = wks.get_all_values(include_tailing_empty=False, include_tailing_empty_rows=False)
        if not vals: return []
        
        headers = vals[0]
        try:
            col_idx = headers.index("手術碼")
        except ValueError:
            return []
            
        codes = []
        for i, row in enumerate(vals[1:], 2):  # Row index starts from 2 (Header is 1)
            # 確保該列有資料且不為空
            if len(row) > col_idx and row[col_idx].strip():
                codes.append({'code': row[col_idx].strip(), 'row_idx': i})
        return codes

    def _get_or_create_column(self, wks, header_val: str) -> int:
        """
        尋找標題列中名為 header_val (如 '11407') 的欄位。
        若不存在，則自動在最右側新增該欄位。
        回傳: 該欄位的 1-based 欄位索引 (如 1=A, 2=B...)。
        
        Args:
            wks: pygsheets Worksheet 對象
            header_val: 欄位標題 (如 '11407')
        """
        try:
            # 1. 讀取標題列 (Row 1)
            headers = wks.get_row(1, include_tailing_empty=False)
            
            # 2. 檢查是否已存在
            if header_val in headers:
                return headers.index(header_val) + 1  # 轉換為 1-based index
            
            # 3. 不存在 -> 在最右側新增
            new_col_idx = len(headers) + 1  # 1-based index
            
            # 立即寫入標題以佔用該欄位
            wks.update_value((1, new_col_idx), header_val)
            
            return new_col_idx
        except Exception as e:
            logger.error(f"取得/建立欄位失敗 {header_val}: {e}")
            return None

    def _col_index_to_letter(self, col_idx: int) -> str:
        """
        將 1-based 欄位索引轉換為 Excel 欄位字母。
        例如: 1 -> 'A', 2 -> 'B', 26 -> 'Z', 27 -> 'AA', 28 -> 'AB'
        
        Args:
            col_idx: 1-based 欄位索引
            
        Returns:
            欄位字母表示法 (如 'A', 'Z', 'AA')
        """
        result = ""
        while col_idx > 0:
            col_idx -= 1
            result = chr(65 + col_idx % 26) + result
            col_idx //= 26
        return result


# --- 快取重試函數 ---

async def upload_from_cache(data: Dict[str, Any], target_info: Dict[str, Any], params: Dict[str, Any]) -> None:
    """
    從快取資料重新上傳到 Google Sheets
    
    Args:
        data: 快取的資料 (包含 master_data, sheet_codes, sum_groups 等)
        target_info: 目標資訊 (sheet_id, worksheet_name)
        params: 原始參數
    """
    from collections import defaultdict
    
    sheet_id = target_info.get("sheet_id")
    worksheet_name = target_info.get("worksheet_name")
    
    if not sheet_id or not worksheet_name:
        raise ValueError("缺少目標 Sheet 資訊")
    
    # 還原資料
    master_data = defaultdict(lambda: defaultdict(int))
    for ym, codes in data.get("master_data", {}).items():
        for code, val in codes.items():
            master_data[ym][code] = val
    
    sheet_codes = data.get("sheet_codes", [])
    sum_groups = data.get("sum_groups", DEFAULT_SUM_GROUPS)
    start_year = data.get("start_year")
    start_month = data.get("start_month")
    end_year = data.get("end_year")
    end_month = data.get("end_month")
    
    if not all([start_year, start_month, end_year, end_month]):
        raise ValueError("快取資料不完整")
    
    # 連接 Google Sheets
    gs = get_gsheet_service()
    gc = gs.get_pygsheets_client()
    sh = gc.open_by_key(sheet_id)
    wks = sh.worksheet_by_title(worksheet_name)
    
    # 建立 Task 實例以使用其方法
    task = StatsFeeTask()
    
    # 準備批次更新資料
    batch_ranges = []
    batch_values = []
    
    current_y, current_m = start_year, start_month
    
    while (current_y < end_year) or (current_y == end_year and current_m <= end_month):
        roc_year = current_y - 1911
        header_val = f"{roc_year:03d}{current_m:02d}"
        
        target_col_idx = task._get_or_create_column(wks, header_val)
        if target_col_idx is None:
            if current_m == 12: 
                current_y += 1
                current_m = 1
            else: 
                current_m += 1
            continue
        
        month_data = master_data.get(header_val, {})
        
        for info in sheet_codes:
            code = info['code']
            val = 0
            
            if code.startswith('sum_'):
                children = sum_groups.get(code, [])
                for child in children:
                    val += month_data.get(child.strip(), 0)
            else:
                val = month_data.get(code, 0)
            
            col_letter = task._col_index_to_letter(target_col_idx)
            cell_range = f"{col_letter}{info['row_idx']}"
            batch_ranges.append(cell_range)
            batch_values.append([[val]])
        
        if current_m == 12:
            current_y += 1
            current_m = 1
        else:
            current_m += 1
    
    # 執行批次寫入
    if batch_ranges:
        wks.update_values_batch(batch_ranges, batch_values, parse=True)
        logger.info(f"StatsFee: 從快取重新上傳成功，共 {len(batch_ranges)} 個儲存格")


# 註冊任務
TaskRegistry.register(StatsFeeTask())

