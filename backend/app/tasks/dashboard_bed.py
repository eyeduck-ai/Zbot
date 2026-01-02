
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
import pandas as pd
import logging
import asyncio
import random
import time
import pygsheets

from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask
from vghsdk.utils import to_western_date, to_roc_date
from vghsdk.modules.surgery import surgery_dept_schedule, SurgeryScheduleParams, surgery_detail, SurgeryDetailParams
from app.db.gsheet import get_gsheet_service
from app.core.alert import get_setting_from_db
from app.core.registry import TaskRegistry
from app.core.jobs import JobManager  # 用於檢查取消狀態
from app.core.cache import CacheManager  # 快取管理

logger = logging.getLogger(__name__)

# --- Models ---

class DashboardBedParams(BaseModel):
    sheet_id: Optional[str] = Field(None, description="Google Sheet ID (預設: 從資料庫讀取)")
    worksheet_name: Optional[str] = Field(None, description="工作表名稱 (預設: 從資料庫讀取 或 'BED')")
    query: str = Field("OPH", description="部門查詢代碼 (預設: OPH)")
    date: Optional[str] = Field(None, description="Date (ISO or ROC). Default: Today")
    crawl_detail_days: int = Field(7, description="往後爬取詳細資料的天數 (從今天開始算)")

class DashboardBedResult(BaseModel):
    status: str
    updated_rows: int
    details: List[str]
    message: Optional[str] = None  # 用於前端顯示的訊息
    sheet_url: Optional[str] = None  # Google Sheets 連結
    cache_id: Optional[str] = None  # 快取 ID (寫入失敗時提供)

# --- Task ---

class DashboardBedTask(BaseTask):
    """
    儀表板待床追蹤任務 (DashboardBedTask)
    
    負責爬取手術排程，過濾出需要安排床位的病患資訊 (待床/簽床)，並更新至 Google Sheet。
    支援自動化爬取詳細病患資料 (如性別、病歷號、聯絡資訊等) 並整合顯示。
    
    功能特色:
    1. 「待床狀態過濾」: 
       - 自動識別「簽床」與「待床」狀態。
       - 排除 OPD (門診手術)。
       - 保留 GA (全身麻醉) 病患。
    2. 「智慧排序 (Sort)」:
       - 依據 手術日期 -> 麻醉方式 -> 簽床急迫性 進行排序。
    3. 「詳細資料整合 (Detail Crawl)」:
       - 自動深入爬取每一筆排程的詳細頁面 (支援設定天數範圍，如未來 7 天)。
       - 整合病歷號、性別、手術室等資訊。
    4. 「自動格式化 (Formatting)」:
       - 更新 Google Sheet 後，自動應用條件式格式 (Conditional Formatting)。
       - 未待床(紅)、GA(綠)、男性(藍) 等視覺化標示。
       
    Attributes:
        id (str): 任務識別碼 ('dashboard_bed')
        name (str): 任務顯示名稱
        description (str): 任務功能描述
        params_model (Type[BaseModel]): 參數驗證模型 (DashboardBedParams)
    """
    id: str = "dashboard_bed"
    name: str = "Dashboard: Waiting Bed (待床)"
    description: str = "爬取眼科手術排程，過濾待床資訊，並更新至 Google Sheet Dashboard。"
    params_model = DashboardBedParams

    # _convert_to_gregorian_date removed. Using vghsdk.utils instead.

    async def run(self, params: DashboardBedParams, client: VghClient, progress_callback=None) -> DashboardBedResult:
        """
        執行待床追蹤任務。

        流程:
        1. 設定載入:
           - 優先使用傳入參數，若無則從 DB (dashboard_bed_settings) 讀取設定。
           - 包含 Google Sheet ID、工作表名稱、詳細資料爬取天數。
        2. 讀取排程列表 (Fetch List):
           - 呼叫 Dept Schedule API 取得初步列表。
        3. 資料過濾與處理 (Filter & Process):
           - 排除 OPD，保留 GA。
           - 解析「簽床/待床」狀態。
           - 依權重排序 (日期 > 麻醉 > 狀態)。
        4. 詳細資料爬取 (Detail Crawl):
           - 針對未來 N 天內的資料，逐筆進入詳細頁面爬取。
           - 取得主刀醫師、病歷號、性別等完整資訊。
        5. 資料合併 (Merge):
           - 將詳細資料併回主表 (Left Join)。
        6. 更新 Google Sheet:
           - 寫入最終整理好的表格。
           - 調整儲存格對齊。
           - 應用條件式格式 (Conditional Formatting)。

        Args:
            params (DashboardBedParams): 任務參數
            client (VghClient): 已登入的 EIP 連線 Client
            progress_callback (Callable): 進度回報 callback

        Returns:
            DashboardBedResult: 執行結果 (Status, Rows, Details)
        """
        # params 已由 router 驗證並轉換為 DashboardBedParams
        p = params
        # 從 client 取得 session
        session = client.session
        
        # 0. 設定載入 (Configuration)
        # 優先順序: 參數 (Param) > 資料庫 (DB)
        
        # 若參數缺漏，嘗試從 DB 讀取設定
        if not p.sheet_id or not p.worksheet_name:
            db_settings = await get_setting_from_db("dashboard_bed_settings")
            # 預期格式 JSON: {"sheet_id": "...", "worksheet_name": "..."}
            
            extracted_days = None
            
            if db_settings:
                if isinstance(db_settings, dict):
                    if not p.sheet_id: p.sheet_id = db_settings.get("sheet_id")
                    if not p.worksheet_name: p.worksheet_name = db_settings.get("worksheet_name")
                    extracted_days = db_settings.get("crawl_detail_days")
                    
                elif isinstance(db_settings, list) and len(db_settings) > 0:
                     # 若為列表，取第一項作為預設值
                     first = db_settings[0]
                     if isinstance(first, dict):
                         if not p.sheet_id: p.sheet_id = first.get("sheet_id")
                         if not p.worksheet_name: p.worksheet_name = first.get("worksheet_name")
                         extracted_days = first.get("crawl_detail_days")

            if extracted_days is not None:
                p.crawl_detail_days = int(extracted_days)
        
        if not p.worksheet_name:
            p.worksheet_name = "BED" # 預設工作表名稱

        if progress_callback: await progress_callback(10, "正在讀取手術排程列表")

        # 1. 讀取排程列表 (Fetch List)
        list_params = SurgeryScheduleParams(
            query=p.query,
            date=to_roc_date(p.date) # Call Dept Schedule with ROC 
        )
        
        try:
            # 使用 function-based task (需傳入 params 和 client)
            result = await surgery_dept_schedule(list_params, client)
            if result.success:
                raw_data = result.data
            else:
                logger.error(f"Failed to fetch schedule: {result.message}")
                return DashboardBedResult(status="error", updated_rows=0, details=[f"Fetch Error: {result.message}"])
        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            return DashboardBedResult(status="error", updated_rows=0, details=[f"Fetch Error: {e}"])

        if not raw_data:
            return DashboardBedResult(status="success", updated_rows=0, details=["未找到排程資料"])
            
        df = pd.DataFrame(raw_data)
        
        if progress_callback: await progress_callback(30, "正在處理資料")
        
        # 確保必要欄位存在
        if '病房床號' not in df.columns: df['病房床號'] = ''
        if '麻醉' not in df.columns: df['麻醉'] = ''
        
        # 2. 初步過濾 (Filter)
        # 排除 OPD (門診手術) 或保留 GA (全身麻醉)
        mask = (~df['病房床號'].astype(str).str.contains("OPD", na=False)) | (df['麻醉'].astype(str).str.contains("GA", na=False))
        df_filtered = df[mask].copy()
        
        # 3. 處理欄位與排序 (Columns & Sort)
        def sign_status(bed):
            bed = str(bed)
            if '[簽]' in bed:
                return "待床"
            elif '-' in bed:
                 parts = bed.split('-')
                 if len(parts) > 1 and parts[1].strip().isdigit():
                     return "簽床"
            return "未待床"

        df_filtered['簽床狀態'] = df_filtered['病房床號'].apply(sign_status)
        
        sign_order = {"簽床": 1, "待床": 2, "未待床": 3}
        df_filtered['_sort_sign'] = df_filtered['簽床狀態'].map(sign_order).fillna(4)
        
        # 排序依據: 手術日期 -> 麻醉 -> 簽床狀態
        df_filtered.sort_values(by=['手術日期', '麻醉', '_sort_sign'], ascending=[True, True, True], inplace=True)
        
        if not await progress_callback(30, "正在爬取詳細資料"): pass

        # 4. 詳細資料爬取 (Detail Crawling - Optimized)
        # 轉換日期以進行過濾
        df_filtered['temp_date'] = df_filtered['手術日期'].apply(to_western_date)
        
        today = date.today()
        end_date = today + timedelta(days=p.crawl_detail_days)
        
        # 僅爬取指定天數範圍內的詳細資料 (today ~ today + crawl_detail_days)
        crawl_mask = (df_filtered['temp_date'] >= today) & (df_filtered['temp_date'] <= end_date)
        df_to_crawl = df_filtered[crawl_mask].copy()
        
        logger.info(f"詳細爬取: 在設定的 {p.crawl_detail_days} 天範圍內 ({today} 至 {end_date}) 找到 {len(df_to_crawl)} 筆資料 (總資料: {len(df_filtered)})")
        
        
        crawled_details = []
        
        total_crawl = len(df_to_crawl)
        
        # 取得 job_id 用於檢查取消狀態
        job_id = getattr(progress_callback, 'job_id', None) if progress_callback else None
        
        # 使用 enumerate 進行迴圈，以確保進度條顯示正確
        for i, (idx, row) in enumerate(df_to_crawl.iterrows()):
            # 檢查是否已被取消
            if job_id and JobManager.is_cancelled(job_id):
                logger.info(f"DashboardBed: 任務已被取消 (job_id={job_id})")
                return DashboardBedResult(status="cancelled", updated_rows=i, details=["任務已被使用者取消"])
            
            # 計算進度百分比 (30% -> 90%)
            pct = 30 + int(60 * ((i + 1) / max(1, total_crawl)))
            
            # 每 5 筆或最後一筆更新一次進度
            if i % 5 == 0 or i == total_crawl - 1:
                 if progress_callback: await progress_callback(pct, f"正在爬取詳細資料 {i+1}/{total_crawl}")
            
            link = row.get('link')
            if link:
                try:
                    # 使用集中設定的延遲 (模擬人類操作)
                    from vghsdk.core import CRAWLER_CONFIG
                    await asyncio.sleep(random.uniform(
                        CRAWLER_CONFIG.rate_limit_min * 0.5,  # 較短的延遲因為是批次操作
                        CRAWLER_CONFIG.rate_limit_max * 0.6
                    ))
                    
                    det_params = SurgeryDetailParams(link_url=link)
                    det_result = await surgery_detail(det_params, client)
                    if det_result.success and det_result.data:
                        det = det_result.data
                        det['_original_index'] = idx  # 保留原始 index 以便合併
                        crawled_details.append(det)
                except Exception as e:
                    logger.warning(f"詳細資料爬取失敗 {link}: {e}")
        
        # 5. 合併資料 (Merge)
        if crawled_details:
            df_details = pd.DataFrame(crawled_details)
            df_details.set_index('_original_index', inplace=True)
            
            # Left Join 將詳細資料併回主表
            df_combined = df_filtered.join(df_details, how='left', rsuffix='_detail')
            
            # 若有詳細資料的 '主刀'，優先使用，否則使用原始列表的 '主刀'
            if '主刀_detail' in df_combined.columns:
                df_combined['主刀_detail'] = df_combined['主刀_detail'].fillna(df_combined['主刀'])
            else:
                df_combined['主刀_detail'] = df_combined['主刀']
                
            # 確保 '術前診斷', '手術名稱', '手術室資訊' 等欄位存在並合併
            for col in ['術前診斷', '手術名稱', '手術室資訊']:
                 detail_col = f"{col}_detail"
                 if detail_col in df_combined.columns:
                     # 優先使用詳細資料欄位
                     df_combined[col] = df_combined[detail_col].fillna(df_combined.get(col, ''))
                 elif col not in df_combined.columns:
                     df_combined[col] = ""
        else:
            # 若無詳細資料，直接使用原始表
            df_combined = df_filtered.copy()
            df_combined['主刀_detail'] = df_combined['主刀']
            for col in ['術前診斷', '手術名稱', '手術室資訊']:
                if col not in df_combined.columns:
                    df_combined[col] = ""

        # 選取最終輸出欄位
        target_cols = ['手術日期', '手術時間', '簽床狀態', '病房床號', '病房資訊', '麻醉', '性別', '病歷號', '姓名', '主刀_detail', '術前診斷', '手術名稱', '手術室資訊']
        
        for c in target_cols:
            if c not in df_combined.columns:
                df_combined[c] = ""
                
        final_df = df_combined[target_cols].copy()
        
        if progress_callback: await progress_callback(95, "正在更新 Google Sheets")

        # 6. 準備輸出目標 (Prepare Targets)
        # 邏輯: 
        # 1. 若原始參數 (Params) 有指定 sheet_id，則僅輸出至該目標。
        # 2. 否則，讀取 DB 設定 (可能為 List 支援多目標)。
        
        targets = []
        original_sheet_id = p.sheet_id  # 使用已解析的 model 屬性
        
        if original_sheet_id:
             # 指定單一目標
             targets.append({"sheet_id": original_sheet_id, "worksheet_name": p.worksheet_name})
        else:
             # 使用 DB 設定
             db_settings = await get_setting_from_db("dashboard_bed_settings")
             if isinstance(db_settings, list):
                 for t in db_settings:
                     if isinstance(t, dict) and t.get("sheet_id"):
                         targets.append(t)
             elif isinstance(db_settings, dict) and db_settings.get("sheet_id"):
                 targets.append(db_settings)
        
        # 預防性 fallback (若 DB 未設定但有參數 defaults)
        if not targets and p.sheet_id:
             targets.append({"sheet_id": p.sheet_id, "worksheet_name": p.worksheet_name})
             
        if not targets:
             return DashboardBedResult(status="error", updated_rows=0, details=["未設定目標 Sheet (參數或 DB 皆無)"])

        # ⭐ 儲存快取 (在寫入前先保存，避免資料遺失)
        cache_data = {
            "final_df": final_df.to_dict(),
        }
        cache_id = CacheManager.save_cache(
            task_id="dashboard_bed",
            params={"date": p.date, "query": p.query},
            data=cache_data,
            target_info={"targets": targets}
        )
        logger.info(f"DashboardBed: 資料已快取 (cache_id={cache_id})")

        gs = get_gsheet_service()
        update_details = []
        success_count = 0
        first_ws_gid = None  # 用於儲存第一個成功目標的 worksheet GID
        
        for t in targets:
            ts_id = t.get('sheet_id')
            ts_name = t.get('worksheet_name', 'BED')
            
            try:
                gc = gs.get_pygsheets_client()
                sh = gc.open_by_key(ts_id)
                
                # 取得或建立工作表
                try:
                    wks = sh.worksheet_by_title(ts_name)
                except pygsheets.WorksheetNotFound:
                    wks = sh.add_worksheet(ts_name)
                    
                wks.clear()
                
                # 更新時間戳記
                update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                wks.update_value('A1', f"最後更新時間:{update_time}")
                
                # 寫入 DataFrame
                wks.set_dataframe(final_df, 'A2', copy_index=False, copy_head=True)
                
                # 格式調整: 靠左對齊與靠上對齊 (Batch Update)
                requests = [{
                    'repeatCell': {
                        'range': {'sheetId': wks.id},
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'TOP'
                            }
                        },
                        'fields': 'userEnteredFormat.horizontalAlignment, userEnteredFormat.verticalAlignment'
                    }
                }]
                sh.custom_request(requests, fields='replies')
                
                # 自動化條件格式 (Automated Conditional Formatting)
                try:
                    self._apply_conditional_formatting(sh, wks)
                    update_details.append(f"Updated {ts_id[:6]}/{ts_name} (+Fmt)")
                except Exception as e:
                    logger.error(f"Formatting failed for {ts_id}: {e}")
                    update_details.append(f"Updated {ts_id[:6]}/{ts_name} (Fmt Err)")
                
                # 取得 worksheet 的 GID (用於產生直接連結)
                if first_ws_gid is None:
                    first_ws_gid = wks.id
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to update target {ts_id}: {e}")
                update_details.append(f"Error {ts_id[:6]}: {e}")

        # 根據寫入結果決定狀態
        if success_count > 0:
            # ⭐ 至少部分成功，刪除快取
            CacheManager.delete_cache(cache_id)
            cache_id = None
            status = "success"
        else:
            # ⭐ 全部失敗，保留快取
            status = "partial_success"
            
        # 取得第一個成功的 sheet URL (包含 worksheet GID 直接開啟該工作表)
        first_sheet_id = targets[0].get('sheet_id') if targets else None
        if first_sheet_id:
            if first_ws_gid is not None:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{first_sheet_id}/edit#gid={first_ws_gid}"
            else:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{first_sheet_id}"
        else:
            sheet_url = None
        
        final_message = "更新待床統計表" if status == "success" else "資料已爬取但上傳失敗，可重試"
        
        return DashboardBedResult(
            status=status,
            updated_rows=len(final_df),
            details=update_details,
            message=final_message,
            sheet_url=sheet_url,
            cache_id=cache_id
        )

    def _apply_conditional_formatting(self, sh, wks):
        """
        Apply conditional formatting rules to the worksheet using batchUpdate.
        Rules:
        1. Col C (Sign): "未待床" -> Red (#F4CCCC)
        2. Col F (Anesthesia): "GA" -> Green (#D9EAD3)
        3. Col G (Gender): "M" -> Blue (#CFE2F3)
        """
        # 1. Fetch current rules to determine how many to delete
        # pygsheets doesn't natively expose rule count easily on the Worksheet object without a fetch.
        # We use the raw google client from the spreadsheet object.
        
        # sh.client is the pygsheets client. sh.client.sheet is the resource.
        # Structure: sh.client.sheet.get(spreadsheetId=..., fields=...)
        
        try:
            res = sh.client.sheet.get(
                spreadsheetId=sh.id,
                fields="sheets(properties(sheetId),conditionalFormats)"
            ).execute()
        except:
             # Fallback if raw access fails (e.g. auth scope issue?)
             # Assuming no rules or risky to delete? 
             # Let's hope it works. If not, we append (which duplicates).
             res = {}

        current_rules = []
        for s in res.get('sheets', []):
            if s['properties']['sheetId'] == wks.id:
                current_rules = s.get('conditionalFormats', [])
                break
        
        requests = []
        
        # 2. Delete Existing Rules (Reverse order logic not strictly needed if we delete by index 0 repeated?)
        # Actually API says: "Deletes a conditional format rule at the given index."
        # If we have N rules, deleting index 0 N times clears them all.
        for _ in range(len(current_rules)):
            requests.append({
                "deleteConditionalFormatRule": {
                    "index": 0,
                    "sheetId": wks.id
                }
            })
            
        # 3. Add New Rules
        # Colors (Approx RGB)
        # Red #F4CCCC: 0.957, 0.8, 0.8
        # Green #D9EAD3: 0.851, 0.918, 0.827
        # Blue #CFE2F3: 0.812, 0.886, 0.953
        
        # Rule 1: Col C (Index 2) - "未待床" -> Red
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": wks.id,
                        "startRowIndex": 1, # Skip Header
                        "startColumnIndex": 2, # C
                        "endColumnIndex": 3
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_CONTAINS",
                            "values": [{"userEnteredValue": "未待床"}]
                        },
                        "format": {
                            "backgroundColor": {
                                "red": 0.957, "green": 0.8, "blue": 0.8
                            }
                        }
                    }
                },
                "index": 0
            }
        })
        
        # Rule 2: Col F (Index 5) - "GA" -> Green
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": wks.id,
                        "startRowIndex": 1,
                        "startColumnIndex": 5, # F
                        "endColumnIndex": 6
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_CONTAINS",
                            "values": [{"userEnteredValue": "GA"}]
                        },
                        "format": {
                            "backgroundColor": {
                                "red": 0.851, "green": 0.918, "blue": 0.827
                            }
                        }
                    }
                },
                "index": 0
            }
        })
        
        # Rule 3: Col G (Index 6) - "M" -> Blue
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": wks.id,
                        "startRowIndex": 1,
                        "startColumnIndex": 6, # G
                        "endColumnIndex": 7
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_CONTAINS",
                            "values": [{"userEnteredValue": "M"}]
                        },
                        "format": {
                            "backgroundColor": {
                                "red": 0.812, "green": 0.886, "blue": 0.953
                            }
                        }
                    }
                },
                "index": 0
            }
        })
        
        # 4. Execute
        if requests:
            sh.custom_request(requests, fields='replies')


# --- 快取重試函數 ---

async def upload_from_cache(data: Dict[str, Any], target_info: Dict[str, Any], params: Dict[str, Any]) -> None:
    """
    從快取資料重新上傳到 Google Sheets
    
    Args:
        data: 快取的資料 (包含 final_df)
        target_info: 目標資訊 (targets)
        params: 原始參數
    """
    # 還原 DataFrame
    final_df = pd.DataFrame.from_dict(data.get("final_df", {}))
    
    targets = target_info.get("targets", [])
    
    if not targets:
        raise ValueError("快取資料中無目標 Sheet 資訊")
    
    # 連接 Google Sheets
    gs = get_gsheet_service()
    
    # 建立 Task 實例以使用其方法
    task = DashboardBedTask()
    
    success_count = 0
    for t in targets:
        ts_id = t.get('sheet_id')
        ts_name = t.get('worksheet_name', 'BED')
        
        try:
            gc = gs.get_pygsheets_client()
            sh = gc.open_by_key(ts_id)
            
            try:
                wks = sh.worksheet_by_title(ts_name)
            except pygsheets.WorksheetNotFound:
                wks = sh.add_worksheet(ts_name)
            
            wks.clear()
            
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            wks.update_value('A1', f"最後更新時間:{update_time}")
            
            wks.set_dataframe(final_df, 'A2', copy_index=False, copy_head=True)
            
            # 格式調整
            requests = [{
                'repeatCell': {
                    'range': {'sheetId': wks.id},
                    'cell': {
                        'userEnteredFormat': {
                            'horizontalAlignment': 'LEFT',
                            'verticalAlignment': 'TOP'
                        }
                    },
                    'fields': 'userEnteredFormat.horizontalAlignment, userEnteredFormat.verticalAlignment'
                }
            }]
            sh.custom_request(requests, fields='replies')
            
            # 條件格式
            task._apply_conditional_formatting(sh, wks)
            
            success_count += 1
        except Exception as e:
            logger.error(f"Cache retry failed for {ts_id}: {e}")
            raise
    
    logger.info(f"DashboardBed: 從快取重新上傳成功，共 {success_count} 個目標")


# 註冊 Task
TaskRegistry.register(DashboardBedTask())

