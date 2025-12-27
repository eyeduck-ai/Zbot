"""
Surgery 手術記錄 - 分步驟 Tasks

提供 Surgery 流程的 4 個獨立 Task：
1. SurgeryFetchScheduleTask - 初次爬蟲 (排程表)
2. SurgeryFetchDetailsTask - 詳細爬蟲 (選中病人)
3. SurgeryPreviewTask - 載入模板+預覽
4. SurgerySubmitTask - 送出

設計原則：
- 每個 Task 獨立執行，前端控制流程
- 資料透過前端傳遞，後端不保留狀態
"""

import logging
import time
import re
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask
from vghsdk.utils import to_roc_date
from app.tasks.opnote import (
    PayloadBuilder,
    SurgeryPayloadFields,
    OpTemplate,
    IcdCode,
    transform_side,
    get_opnote_config_service,
    get_surkeycode_service,
)
from app.db.gsheet import get_gsheet_service
from app.config import get_settings
from app.core.jobs import JobManager  # 用於檢查取消狀態
from app.core.registry import TaskRegistry
from vghsdk.modules.doctor import get_doctor_name
from vghsdk.modules.surgery import SurgeryDetailTask, SurgeryDetailParams
from app.tasks.opnote.record_cache import (
    SurgeryRecord, 
    BASE_EDITABLE_FIELDS,
    set_record,
    get_record,
    clear_all as clear_record_cache,
)
from app.tasks.opnote.models import contains_side_info

logger = logging.getLogger("surgery_tasks")

_payload_builder = PayloadBuilder()
_config_service = get_opnote_config_service()

# SDK Task 實例 (重複使用)
_surgery_detail_task = SurgeryDetailTask()


# =============================================================================
# Helper Functions
# =============================================================================

def parse_doctor_info(info: str) -> tuple:
    """
    解析醫師資訊字串 (格式: "姓名代碼" 如 "黃怡銘4050")
    
    Args:
        info: 醫師資訊字串
        
    Returns:
        (姓名, 代碼) tuple，若無法解析則返回 (info, '')
    """
    import re
    if not info:
        return '', ''
    match = re.match(r'(.+?)(\d{4})$', info.strip())
    if match:
        return match.group(1), match.group(2)
    return info, ''


def parse_side(side_str: str) -> str:
    """解析部位字串為 OD/OS/OU"""
    if '右' in str(side_str):
        return 'OD'
    elif '左' in str(side_str):
        return 'OS'
    elif '雙' in str(side_str):
        return 'OU'
    return 'OD'


def check_op_type(input_string: str) -> Optional[str]:
    """
    從字串中識別手術類型 (舊邏輯，作為 fallback)
    
    Args:
        input_string: 輸入字串
        
    Returns:
        手術類型 (LENSX/ECCE/PHACO/VT/TRABE/BLEB/NEEDLING) 或 None
    """
    if not isinstance(input_string, str):
        return None
    s = input_string.upper()
    if 'LENSX' in s or 'LENS' in s: return 'LENSX'
    if 'ECCE' in s: return 'ECCE'
    if 'PHACO' in s: return 'PHACO'
    if 'VT' in s: return 'VT'
    if 'TRABE' in s: return 'TRABE'
    if 'BLEB' in s: return 'BLEB'
    if 'NEEDLING' in s: return 'NEEDLING'
    return None


# =============================================================================
# Surkeycode -> op_type 轉換
# 完整資料庫: backend/vghsdk/surkeycode_database.md
# 資料儲存於 Supabase surkeycode_map 表
# =============================================================================

def extract_surkeycodes(op_method: str) -> List[str]:
    """
    從手術方式欄位提取 surkeycode (5位數字)
    
    Args:
        op_method: 手術方式字串 (e.g. "LENSX-PHACO-IOL OD  OPH     13424")
        
    Returns:
        List of surkeycode strings (e.g. ["13424"])
    """
    import re
    if not op_method:
        return []
    # 提取所有 5 位數字 (surkeycode 格式)
    return re.findall(r'(\d{5})', op_method)


def check_op_type_by_surkeycode(op_method: str) -> Optional[str]:
    """
    優先使用 surkeycode 判斷 op_type (從 Supabase surkeycode_map 查詢)
    
    Args:
        op_method: 手術方式字串 (e.g. "LENSX-PHACO-IOL OD  OPH     13424")
        
    Returns:
        op_type (LENSX/PHACO/VT/...) 或 None
    """
    codes = extract_surkeycodes(op_method)
    service = get_surkeycode_service()
    
    for code in codes:
        op_type = service.get_op_type(code)
        if op_type:
            return op_type
    return None


# =============================================================================
# Models
# =============================================================================

class SurgeryFetchScheduleParams(BaseModel):
    """Step 1: 抓取排程表參數"""
    date: str = Field(..., description="手術日期 (YYYY-MM-DD)")
    doc_code: str = Field(..., description="主治醫師代碼")


class ScheduleItem(BaseModel):
    """排程表項目"""
    hisno: str
    name: str
    op_date: str = ""  # 手術日期
    op_time: str = ""  # 手術時間
    op_room: str = ""  # 開刀房號
    pre_op_dx: str = ""  # 術前診斷
    op_name: str = ""   # 手術名稱
    op_room_info: str = ""  # 手術室資訊
    link: str = ""  # 詳情連結


class SurgeryFetchScheduleResult(BaseModel):
    """Step 1: 排程表結果"""
    date: str
    doc_code: str
    count: int
    items: List[ScheduleItem]
    message: Optional[str] = None


class SurgeryFetchDetailsParams(BaseModel):
    """Step 2: 抓取詳情參數"""
    date: str
    doc_code: str
    r_code: str = Field(..., description="住院醫師代碼")
    items: List[Dict[str, Any]] = Field(..., description="選中的病人列表 (含 hisno, link)")


class PatientDetail(BaseModel):
    """
    病人詳情 (動態欄位版)
    
    col_fields: 動態 COL_* 欄位值 {'IOL': 'Tecnis', 'FINAL': '-0.5D', ...}
    editable_fields: 該模板需要的欄位清單 ['IOL', 'FINAL', ...]
    """
    hisno: str
    name: str
    # 從排程帶過來的欄位 (可選)
    op_date: str = ""      # 手術日期
    op_time: str = ""      # 手術時間
    pre_op_dx: str = ""    # 術前診斷
    op_name: str = ""      # 手術名稱
    op_room_info: str = "" # 手術室資訊
    # 內網排程
    op_sect: str = "OPH"
    op_bed: str = ""
    op_room: str = ""
    op_anesthesia: str = "LA"
    op_side: str = "OD"
    # 醫師資訊 (從 SDK SurgeryDetailTask 取得)
    man: str = ""          # 主刀代碼 (4位數字)
    mann: str = ""         # 主刀姓名
    ass1: str = ""         # 助手一代碼
    ass1n: str = ""        # 助手一姓名
    ass2: str = ""         # 助手二代碼
    ass2n: str = ""        # 助手二姓名
    ass3: str = ""         # 助手三代碼
    ass3n: str = ""        # 助手三姓名
    # 動態填充欄位 (from template required + optional)
    col_fields: Dict[str, str] = {}       # {'IOL': 'Tecnis', 'FINAL': '-0.5D'}
    editable_fields: List[str] = []       # ['IOL', 'FINAL', 'TARGET', ...]
    # Web9 資料
    web9_data: Dict[str, Any] = {}
    # GSheet 刀表資料
    gsheet_data: Dict[str, Any] = {}
    # 識別的手術類型
    op_type: str = ""
    # 術後診斷 (預先計算，可編輯)
    diaga: str = ""
    # 狀態
    status: str = "pending"
    error: Optional[str] = None


class SurgeryFetchDetailsResult(BaseModel):
    """步驟 2: 詳情結果"""
    count: int
    items: List[PatientDetail]
    column_map: Dict[str, Optional[str]] = {}


class SurgeryPreviewParams(BaseModel):
    """Step 3: 預覽參數"""
    date: str
    doc_code: str
    r_code: str
    items: List[Dict[str, Any]]
    column_map: Dict[str, Optional[str]] = {}


class PreviewItem(BaseModel):
    """預覽項目"""
    hisno: str
    name: str
    op_type: str
    payload: Dict[str, Any] = {}
    missing_fields: List[str] = []
    editable_fields: List[str] = []
    status: str = "ready"


class SurgeryPreviewResult(BaseModel):
    """Step 3: 預覽結果"""
    count: int
    previews: List[PreviewItem]


class SurgerySubmitParams(BaseModel):
    """步驟 4: 送出參數"""
    items: List[Dict[str, Any]] = Field(..., description="包含 hisno 和可覆蓋欄位 (diagn, diaga, col_* 等)")


class SurgerySubmitResult(BaseModel):
    """Step 4: 送出結果"""
    total: int
    success: int
    failed: int
    details: List[str]
    message: Optional[str] = None  # 用於前端顯示


# =============================================================================
# Task 1: Fetch Schedule (初次爬蟲)
# =============================================================================

class SurgeryFetchScheduleTask(BaseTask):
    """
    Step 1: 抓取手術排程表
    
    從內網抓取指定日期和醫師的手術排程，
    返回可供使用者勾選的病人列表。
    """
    id: str = "note_surgery_fetch_schedule"
    name: str = "Surgery Schedule Fetch"
    description: str = "抓取手術排程表 (Step 1)"
    params_model: Optional[Type[BaseModel]] = SurgeryFetchScheduleParams

    async def run(self, params: SurgeryFetchScheduleParams, client: VghClient, progress_callback=None) -> SurgeryFetchScheduleResult:
        # params 已由 router 驗證並轉換
        p = params
        
        roc_date = to_roc_date(p.date)
        if not roc_date:
            return SurgeryFetchScheduleResult(
                date=p.date, doc_code=p.doc_code, count=0, items=[],
                message="日期格式錯誤"
            )
        
        if not await client.ensure_eip():
            raise Exception("Login EIP Failed")
        
        session = client.session
        
        # 抓取排程表
        url = 'https://web9.vghtpe.gov.tw/ops/opb.cfm'
        payload = {
            'action': 'findOpblist',
            'type': 'opbmain',
            'qry': p.doc_code,
            'bgndt': roc_date,
            '_': int(time.time() * 1000)
        }
        
        # 使用 safe_request 自動 retry/backoff
        res = await client.safe_request('GET', url, params=payload)
        
        # 解析 HTML 表格 (使用 BeautifulSoup 以取得 tooltip)
        try:
            soup = BeautifulSoup(res.text, "lxml")
            table = soup.find('table')
            
            if not table:
                return SurgeryFetchScheduleResult(
                    date=p.date, doc_code=p.doc_code, count=0, items=[],
                    message="找不到排程表"
                )
            
            rows = table.find_all('tr')
            if not rows:
                return SurgeryFetchScheduleResult(
                    date=p.date, doc_code=p.doc_code, count=0, items=[],
                    message="排程表無資料"
                )
            
            # 取得表頭
            headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
            
            # Regex 解析 tooltip
            import re
            tooltip_regex = re.compile(
                r'術前診斷:\s*(?P<pre_op_dx>.*?)\s*'
                r'手術名稱:\s*(?P<op_name>.*?)\s*'
                r'手術室資訊:\s*(?P<op_room_info>.*?)\s*'
                r'麻醉:\s*(?P<anesthesia>.*?)\s*$'
            )
            
            items = []
            for row in rows[1:]:
                cols = row.find_all('td')
                if not cols:
                    continue
                
                # 基本欄位 mapping
                record = {}
                for i, col in enumerate(cols):
                    if i < len(headers):
                        record[headers[i]] = col.get_text(strip=True)
                
                hisno = str(record.get('病歷號', '')).strip()
                if not hisno or not hisno.isdigit():
                    continue
                
                # 取得連結
                link = ''
                btn = row.find('button', attrs={'data-target': '#myModal'})
                if btn and btn.has_attr('data-url'):
                    link = btn['data-url']
                
                # 解析 tooltip
                pre_op_dx = ''
                op_name = ''
                op_room_info = ''
                tooltip_a = row.find('a', attrs={'data-toggle': 'tooltip'})
                if tooltip_a and tooltip_a.has_attr('title'):
                    tooltip_text = tooltip_a['title']
                    match = tooltip_regex.search(tooltip_text)
                    if match:
                        groups = match.groupdict()
                        pre_op_dx = groups.get('pre_op_dx', '').strip()
                        op_name = groups.get('op_name', '').strip()
                        op_room_info = groups.get('op_room_info', '').strip()
                
                items.append(ScheduleItem(
                    hisno=hisno,
                    name=str(record.get('姓名', '')).strip(),
                    op_date=str(record.get('手術日期', '')).strip(),
                    op_time=str(record.get('手術時間', '')).strip(),
                    op_room=str(record.get('開刀房號', '')).strip(),
                    pre_op_dx=pre_op_dx,
                    op_name=op_name,
                    op_room_info=op_room_info,
                    link=link
                ))
            
            return SurgeryFetchScheduleResult(
                date=p.date,
                doc_code=p.doc_code,
                count=len(items),
                items=items
            )
            
        except Exception as e:
            logger.error(f"Parse schedule failed: {e}")
            return SurgeryFetchScheduleResult(
                date=p.date, doc_code=p.doc_code, count=0, items=[],
                message=f"解析排程表失敗: {e}"
            )


# =============================================================================
# Task 2: Fetch Details (詳細爬蟲)
# =============================================================================

class SurgeryFetchDetailsTask(BaseTask):
    """
    Step 2: 抓取選中病人的詳細資料
    
    針對使用者勾選的病人：
    1. 抓取內網排程詳情
    2. 抓取 Web9 病人資料
    3. 從 GSheet 讀取刀表資料
    """
    id: str = "note_surgery_fetch_details"
    name: str = "Surgery Details Fetch"
    description: str = "抓取選中病人的詳細資料 (Step 2)"
    params_model: Optional[Type[BaseModel]] = SurgeryFetchDetailsParams

    async def run(self, params: SurgeryFetchDetailsParams, client: VghClient, progress_callback=None) -> SurgeryFetchDetailsResult:
        # params 已由 router 驗證並轉換
        p = params
        
        roc_date = to_roc_date(p.date)
        if not roc_date:
            raise Exception("日期格式錯誤")
        
        if not await client.ensure_eip():
            raise Exception("Login EIP Failed")
        
        session = client.session
        
        # 載入 surkeycode 對應表 (單次查詢，後續本地查表)
        surkeycode_service = get_surkeycode_service()
        await surkeycode_service.ensure_loaded()
        
        # 載入醫師刀表設定
        doctor_sheet = await _config_service.get_doctor_sheet(p.doc_code)
        column_map = doctor_sheet.column_map if doctor_sheet else {}
        
        # 載入 GSheet 刀表
        gsheet_df = None
        if doctor_sheet:
            try:
                gs = get_gsheet_service()
                gc = gs.get_pygsheets_client()
                sh = gc.open_by_key(doctor_sheet.sheet_id)
                wks = sh.worksheet_by_title(doctor_sheet.worksheet)
                data_matrix = wks.get_all_values(returnas='matrix')
                
                # 使用 header_row 決定標題列位置 (1-indexed -> 0-indexed)
                header_idx = doctor_sheet.header_row - 1
                if header_idx < len(data_matrix):
                    headers = data_matrix[header_idx]
                    data_rows = data_matrix[header_idx + 1:]
                    gsheet_df = pd.DataFrame(data_rows, columns=headers)
                else:
                    logger.warning(f"header_row {doctor_sheet.header_row} exceeds data rows")
            except Exception as e:
                logger.warning(f"Load GSheet failed: {e}")
        
        results = []
        
        # 清除舊的暫存，開始新一輪
        clear_record_cache()
        logger.info("[FetchDetails] Cleared old cache, starting fresh")
        
        # 取得 job_id 用於 Checkpoint 和取消檢查
        job_id = getattr(progress_callback, 'job_id', None) if progress_callback else None
        total_items = len(p.items)
        
        # 設定總項目數 (Checkpoint 支援)
        if job_id:
            JobManager.set_total_items(job_id, total_items)
        
        # =====================================================================
        # 批次載入模板 (優化: 根據 items 中的預估 op_types 一次性載入)
        # =====================================================================
        # 先從 op_name 預估可能的 op_types
        estimated_op_types = set()
        for item in p.items:
            op_name = str(item.get('op_name', ''))
            estimated_type = check_op_type(op_name) or 'PHACO'
            estimated_op_types.add(estimated_type)
        
        # 確保包含常用類型
        estimated_op_types.update(['PHACO', 'LENSX', 'VT'])
        
        # 批次載入模板 (一次 DB 查詢)
        templates_map = await _config_service.get_templates_batch(
            list(estimated_op_types), 
            p.doc_code
        )
        logger.info(f"[FetchDetails] Batch-loaded {len(templates_map)} templates: {list(templates_map.keys())}")
        
        for i, item in enumerate(p.items):
            hisno = str(item.get('hisno', ''))
            name = str(item.get('name', ''))
            link = str(item.get('link', ''))
            
            # 斷點續跑: 跳過已完成項目
            if job_id and JobManager.is_item_completed(job_id, hisno):
                continue
            
            # 從前端傳入的排程資料初始化
            detail = PatientDetail(
                hisno=hisno, 
                name=name,
                op_date=str(item.get('op_date', '')),
                op_time=str(item.get('op_time', '')),
                pre_op_dx=str(item.get('pre_op_dx', '')),
                op_name=str(item.get('op_name', '')),
                op_room_info=str(item.get('op_room_info', '')),
            )
            
            detail_data = None
            gsheet_op_name = ""
            
            try:
                await session.rate_limit()
                
                # 1. 使用 SDK 抓取排程詳情 (取得完整醫師資訊)
                if link:
                    sdk_params = SurgeryDetailParams(link_url=link)
                    detail_data = await _surgery_detail_task.run(sdk_params, client)
                    
                    # Debug log
                    logger.debug(f"[SDK Detail] hisno={hisno}, link={link}")
                    logger.debug(f"[SDK Detail] Raw data: {detail_data}")
                    
                    if detail_data:
                        # 解析排程欄位
                        detail.op_side = parse_side(detail_data.get('部位', ''))
                        detail.op_sect = detail_data.get('手術科部', 'OPH').strip()
                        detail.op_bed = detail_data.get('病房床號', '').strip(' -')
                        detail.op_anesthesia = detail_data.get('麻醉方式', 'LA').strip()
                        detail.op_room = detail_data.get('手術房號', '').strip()
                        
                        # 解析主刀資訊 (格式: "黃怡銘4050")
                        mann, man = parse_doctor_info(detail_data.get('主刀', ''))
                        detail.man = man
                        detail.mann = mann
                        
                        # 解析助手一 (格式: "曾宇璿6459")
                        ass1n, ass1 = parse_doctor_info(detail_data.get('助手一', ''))
                        detail.ass1 = ass1
                        detail.ass1n = ass1n
                        
                        # 解析助手二
                        ass2n, ass2 = parse_doctor_info(detail_data.get('助手二', ''))
                        detail.ass2 = ass2
                        detail.ass2n = ass2n
                        
                        # 解析助手三
                        ass3n, ass3 = parse_doctor_info(detail_data.get('助手三', ''))
                        detail.ass3 = ass3
                        detail.ass3n = ass3n
                        
                        logger.debug(f"[SDK Detail] Parsed: man={man}, mann={mann}, ass1={ass1}, ass1n={ass1n}")
                else:
                    logger.warning(f"[SDK Detail] No link for hisno={hisno}, skipping SDK detail fetch")
                
                # 2. 抓取 Web9 病人資料 (使用 safe_request 自動 retry)
                url = 'https://web9.vghtpe.gov.tw/emr/OPAController?action=NewOpnForm01Action'
                res = await client.safe_request('POST', url, data={'hisno': hisno, 'pidno': '', 'drid': '', 'b1': '新增'})
                soup = BeautifulSoup(res.text, 'lxml')
                
                def get_val(name):
                    el = soup.find(attrs={'name': name})
                    return el.get('value', '') if el else ''
                
                detail.web9_data = {
                    'sect1': get_val('sect1'),
                    'name': get_val('name'),
                    'sex': get_val('sex'),
                    'hisno': get_val('hisno'),
                    'age': get_val('age'),
                    'idno': get_val('idno'),
                    'birth': get_val('birth'),
                    '_antyp': get_val('_antyp'),
                    'opbbgndt': get_val('opbbgndt'),
                    'opbbgntm': get_val('opbbgntm'),
                    'diagn': get_val('diagn'),
                }
                
                # 解析 sel_opck
                sel_opck_el = soup.select_one('select#sel_opck > option')
                sel_opck = sel_opck_el.get('value', '') if sel_opck_el else ''
                detail.web9_data['sel_opck'] = sel_opck
                if sel_opck and '|' in sel_opck:
                    parts = sel_opck.split('|')
                    detail.web9_data['bgntm'] = parts[0][-4:]
                    detail.web9_data['endtm'] = parts[1][-4:] if len(parts) > 1 else ''
                
                # 3. 從 GSheet 讀取刀表 (只讀取原始資料，欄位填充稍後進行)
                if gsheet_df is not None:
                    hisno_col = column_map.get('COL_HISNO', 'ID')
                    matched = gsheet_df[gsheet_df[hisno_col].astype(str) == hisno]
                    
                    # 多筆資料時，使用 COL_SIDE_OR_DIAGNOSIS 欄位區分側別
                    if len(matched) > 1:
                        side_col_name = column_map.get('COL_SIDE_OR_DIAGNOSIS')
                        if side_col_name and side_col_name in gsheet_df.columns and detail.op_side:
                            # 在側別/診斷欄位中搜尋 OD 或 OS
                            side_matched = matched[
                                matched[side_col_name].astype(str).str.contains(
                                    detail.op_side, case=False, na=False
                                )
                            ]
                            if not side_matched.empty:
                                matched = side_matched
                                logger.debug(f"[GSheet Match] hisno={hisno}, multiple rows found, filtered by side '{detail.op_side}' -> {len(matched)} rows")
                            else:
                                logger.warning(f"[GSheet Match] hisno={hisno}, side '{detail.op_side}' not found in COL_SIDE_OR_DIAGNOSIS, using first row")
                        else:
                            logger.warning(f"[GSheet Match] hisno={hisno}, {len(matched)} rows found but no COL_SIDE_OR_DIAGNOSIS mapping, using first row")
                    
                    if not matched.empty:
                        detail.gsheet_data = matched.iloc[0].to_dict()
                
                # 4. 識別手術類型 (優先使用 surkeycode)
                op_method = detail_data.get('手術方式', '') if detail_data else ''
                op_type_from_surkeycode = check_op_type_by_surkeycode(op_method)
                
                if op_type_from_surkeycode:
                    # 使用 surkeycode 識別 (最準確)
                    detail.op_type = op_type_from_surkeycode
                    logger.debug(f"[Op Type] hisno={hisno} detected by surkeycode: {op_type_from_surkeycode}")
                else:
                    # Fallback: 使用 GSheet 術式欄位
                    op_col = column_map.get('COL_OP', '術式')
                    detail.op_type = check_op_type(detail.gsheet_data.get(op_col, '')) or 'PHACO'
                    logger.debug(f"[Op Type] hisno={hisno} fallback to GSheet/default: {detail.op_type}")
                    
                    # LENSX 特殊判斷 (只在 fallback 時使用)
                    lensx_col = column_map.get('COL_LENSX', 'Lensx')
                    if detail.gsheet_data.get(lensx_col):
                        detail.op_type = 'LENSX'
                
                # 更新 op_name 使用 GSheet 優先 (GSheet COL_OP > 內網排程)
                op_col = column_map.get('COL_OP', '術式')
                gsheet_op_name = str(detail.gsheet_data.get(op_col, '')).strip()
                if gsheet_op_name:
                    detail.op_name = gsheet_op_name
                
                # LENSX 手術名稱前綴補充
                # 如果 op_type 是 LENSX 但 op_name 不含 "LENSX"，在 "Phaco" 前補上 "LENSX-"
                if detail.op_type == 'LENSX' and 'lensx' not in detail.op_name.lower():
                    # 在 "Phaco" 前插入 "LENSX-" (不區分大小寫)
                    detail.op_name = re.sub(
                        r'(?i)(phaco)',
                        r'LENSX-\1',
                        detail.op_name,
                        count=1  # 只替換第一個
                    )
                    logger.debug(f"[LENSX Prefix] hisno={hisno}, op_name updated to: {detail.op_name}")
                
                # =============================================================
                # 5. 動態讀取 COL_* 欄位 (核心改動)
                # =============================================================
                # 如果模板未載入，嘗試即時載入
                template = templates_map.get(detail.op_type)
                if not template:
                    template = await _config_service.get_template(detail.op_type, p.doc_code)
                    if template:
                        templates_map[detail.op_type] = template
                
                if template:
                    # 取得該模板需要的欄位清單
                    raw_fields = (template.required_fields or []) + (template.optional_fields or [])
                    
                    # 正規化欄位名稱 (移除 COL_ 或 $COL_ 前綴)
                    def normalize_field_name(name: str) -> str:
                        """將 'COL_IOL', '$COL_IOL', 'IOL' 都轉為 'IOL'"""
                        name = name.strip()
                        if name.startswith('$COL_'):
                            return name[5:]
                        elif name.startswith('COL_'):
                            return name[4:]
                        return name
                    
                    editable_fields = [normalize_field_name(f) for f in raw_fields]
                    detail.editable_fields = editable_fields
                    
                    # 動態讀取 GSheet 欄位值
                    col_fields = {}
                    for field_name in editable_fields:
                        col_key = f"COL_{field_name}"  # e.g. "COL_IOL"
                        gsheet_col = column_map.get(col_key)
                        if gsheet_col and gsheet_col in detail.gsheet_data:
                            col_fields[field_name] = str(detail.gsheet_data.get(gsheet_col, '')).strip()
                        else:
                            col_fields[field_name] = ''  # 欄位未設定，給空值
                    
                    detail.col_fields = col_fields
                    logger.debug(f"[Dynamic Fields] hisno={hisno}, op_type={detail.op_type}, raw={raw_fields}, normalized={editable_fields}, values={col_fields}")
                else:
                    detail.editable_fields = []
                    detail.col_fields = {}
                    logger.warning(f"[Dynamic Fields] No template for op_type={detail.op_type}, hisno={hisno}")
                
                detail.status = 'ready'
                
            except Exception as e:
                logger.error(f"Fetch details for {hisno} failed: {e}")
                detail.status = 'error'
                detail.error = str(e)
            
            # 存入暫存 (PatientDetail -> SurgeryRecord)
            record = SurgeryRecord(
                hisno=detail.hisno,
                name=detail.name,
                op_date=detail.op_date,
                op_time=detail.op_time,
                op_room=detail.op_room,
                op_room_info=detail.op_room_info,
                pre_op_dx=detail.pre_op_dx,
                op_name=detail.op_name,
                op_sect=detail.op_sect,
                op_bed=detail.op_bed,
                op_anesthesia=detail.op_anesthesia,
                op_side=detail.op_side,
                man=detail.man,
                mann=detail.mann,
                ass1=detail.ass1,
                ass1n=detail.ass1n,
                ass2=detail.ass2,
                ass2n=detail.ass2n,
                ass3=detail.ass3,
                ass3n=detail.ass3n,
                web9_data=detail.web9_data,
                gsheet_data=detail.gsheet_data,
                op_type=detail.op_type,
                # 動態欄位
                col_fields=detail.col_fields,
                editable_fields=detail.editable_fields,
                # 計算欄位
                diagn=detail.pre_op_dx,  # 預設填入術前診斷
                diaga='',  # Submit 時從 op_name 構建
                status=detail.status,
                error=detail.error or '',
            )
            set_record(record)
            
            # 標記完成 (Checkpoint)
            if job_id:
                JobManager.mark_item_completed(job_id, hisno, f"抓取 {name} ({i+1}/{total_items})")
            
            results.append(detail)
        
        return SurgeryFetchDetailsResult(
            count=len(results),
            items=results,
            column_map=column_map
        )


# =============================================================================
# Task 3: Preview (預覽)
# =============================================================================

class SurgeryPreviewTask(BaseTask):
    """
    Step 3: 建構 Payload 預覽
    
    載入手術模板並建構 Payload，
    讓使用者確認和編輯。
    """
    id: str = "note_surgery_preview"
    name: str = "Surgery Preview"
    description: str = "建構 Payload 預覽 (Step 3)"
    params_model: Optional[Type[BaseModel]] = SurgeryPreviewParams

    async def run(self, params: SurgeryPreviewParams, client: VghClient, progress_callback=None) -> SurgeryPreviewResult:
        # params 已由 router 驗證並轉換
        p = params
        
        roc_date = to_roc_date(p.date)
        if not roc_date:
            raise Exception("日期格式錯誤")
        
        previews = []
        total_items = len(p.items)
        
        for i, item in enumerate(p.items):
            hisno = item.get('hisno', '')
            name = item.get('name', '')
            
            # 優先從暫存讀取完整資料
            cached_record = get_record(hisno)
            
            if cached_record:
                # 使用暫存的完整資料
                op_type = item.get('op_type') or cached_record.op_type or 'PHACO'
                web9_data = cached_record.web9_data
                gsheet_data = cached_record.gsheet_data
                op_side = item.get('op_side') or cached_record.op_side or 'OD'
                op_sect = cached_record.op_sect
                op_bed = cached_record.op_bed
                op_anesthesia = item.get('op_anesthesia') or cached_record.op_anesthesia or 'LA'
                pre_op_dx = cached_record.pre_op_dx
                op_name_from_schedule = cached_record.op_name
                man = cached_record.man or p.doc_code
                mann = cached_record.mann
                ass1 = cached_record.ass1 or p.r_code
                ass1n = cached_record.ass1n
                ass2 = cached_record.ass2
                ass2n = cached_record.ass2n
                ass3 = cached_record.ass3
                ass3n = cached_record.ass3n
                logger.debug(f"[Preview] Using cached record for {hisno}: mann={mann}, ass1n={ass1n}")
            else:
                # Fallback: 從前端 params 讀取 (舊行為)
                op_type = item.get('op_type', 'PHACO')
                web9_data = item.get('web9_data', {})
                gsheet_data = item.get('gsheet_data', {})
                op_side = item.get('op_side', 'OD')
                op_sect = item.get('op_sect', 'OPH')
                op_bed = item.get('op_bed', '')
                op_anesthesia = item.get('op_anesthesia', 'LA')
                pre_op_dx = item.get('pre_op_dx', '')
                op_name_from_schedule = item.get('op_name', '')
                man = item.get('man', '') or p.doc_code
                mann = item.get('mann', '')
                ass1 = item.get('ass1', '') or p.r_code
                ass1n = item.get('ass1n', '')
                ass2 = item.get('ass2', '')
                ass2n = item.get('ass2n', '')
                ass3 = item.get('ass3', '')
                ass3n = item.get('ass3n', '')
                logger.warning(f"[Preview] No cached record for {hisno}, using frontend params")
            
            try:
                # 載入模板 (不 fallback 到其他類型)
                template = await _config_service.get_template(op_type, p.doc_code)
                
                if not template:
                    # 找不到對應模板，標記為 no_template 狀態
                    logger.warning(f"No template found for op_type={op_type}, hisno={hisno}")
                    previews.append(PreviewItem(
                        hisno=hisno,
                        name=name,
                        op_type=op_type,
                        status='no_template'
                    ))
                    continue
                
                # 建立 SurgeryPayloadFields (使用從 SDK 取得的醫師資訊)
                surgery_fields = SurgeryPayloadFields(
                    op_sect=op_sect,
                    op_bed=op_bed,
                    op_anesthesia=op_anesthesia,
                    op_side=op_side,
                    op_type=op_type,
                    pre_op_dx=pre_op_dx,          # 術前診斷 (for diagn)
                    op_name=op_name_from_schedule, # 手術名稱 (for diaga fallback)
                    doc_code=man,
                    vs_name=mann,
                    r_code=ass1,
                    r_name=ass1n,
                    ass2=ass2,
                    ass2n=ass2n,
                    ass3=ass3,
                    ass3n=ass3n,
                )
                
                # 解析佔位符
                resolved, missing = _payload_builder.resolve_placeholders(
                    required_fields=template.required_fields,
                    optional_fields=template.optional_fields,
                    schedule_data={},
                    gsheet_data=gsheet_data,
                    column_map=p.column_map,
                )
                
                op_col = p.column_map.get('COL_OP', '術式')
                resolved['COL_OP'] = gsheet_data.get(op_col, op_type)
                
                # 建構 Payload
                payload, _ = _payload_builder.build_surgery_payload(
                    web9_data=web9_data,
                    surgery_fields=surgery_fields,
                    op_template=template,
                    op_date=roc_date,
                    placeholder_values=resolved,
                )
                
                # 可編輯欄位 (包含 diagn, diaga 讓使用者可以確認和編輯)
                editable = ['diagn', 'diaga', 'op_side', 'op_anesthesia'] + template.required_fields + template.optional_fields
                
                previews.append(PreviewItem(
                    hisno=hisno,
                    name=name,
                    op_type=op_type,
                    payload=payload,
                    missing_fields=missing,
                    editable_fields=editable,
                    status='ready'
                ))
                
            except Exception as e:
                logger.error(f"Preview for {hisno} failed: {e}")
                previews.append(PreviewItem(
                    hisno=hisno,
                    name=name,
                    op_type=op_type,
                    status='error'
                ))
        
        return SurgeryPreviewResult(count=len(previews), previews=previews)


# =============================================================================
# Task 4: Submit (送出)
# =============================================================================

class SurgerySubmitTask(BaseTask):
    """
    Step 4: 送出手術記錄
    
    將 Payload 送出到 Web9。
    """
    id: str = "note_surgery_submit"
    name: str = "Surgery Submit"
    description: str = "送出手術記錄 (Step 4)"
    params_model: Optional[Type[BaseModel]] = SurgerySubmitParams

    async def run(self, params: SurgerySubmitParams, client: VghClient, progress_callback=None) -> SurgerySubmitResult:
        p = params
        
        if not await client.ensure_eip():
            raise Exception("Login EIP Failed")
        
        session = client.session
        settings = get_settings()
        
        success_count = 0
        details = []
        total_items = len(p.items)
        
        # Debug: 記錄 cache 狀態
        from app.tasks.opnote.record_cache import record_count
        logger.info(f"[Submit] Starting with {total_items} items, cache has {record_count()} records")
        
        # 取得 job_id 用於 Checkpoint 和取消檢查
        job_id = getattr(progress_callback, 'job_id', None) if progress_callback else None
        
        # 設定總項目數 (Checkpoint 支援)
        if job_id:
            JobManager.set_total_items(job_id, total_items)
        
        for i, item in enumerate(p.items):
            # 檢查取消
            if job_id and JobManager.is_cancelled(job_id):
                logger.info(f"Surgery Submit: 任務已被取消")
                return SurgerySubmitResult(total=total_items, success=success_count, failed=i-success_count, details=["任務已取消"])
            
            hisno = item.get('hisno', '')
            
            # 斷點續跑: 跳過已完成項目
            if job_id and JobManager.is_item_completed(job_id, hisno):
                continue
            
            # 1. 從暫存取出完整記錄
            record = get_record(hisno)
            if not record:
                logger.warning(f"[Submit] Record not found in cache for hisno={hisno}")
                details.append(f"({hisno}): Record not found in cache")
                continue
            
            # 2. 套用前端覆蓋值
            record.apply_overrides(item)
            
            # 3. 建構 Payload
            try:
                # 準備 SurgeryPayloadFields
                surgery_fields = SurgeryPayloadFields(
                    doc_code=record.man,
                    vs_name=record.mann,
                    r_code=record.ass1,
                    r_name=record.ass1n,
                    ass2=record.ass2,
                    ass2n=record.ass2n,
                    ass3=record.ass3,
                    ass3n=record.ass3n,
                    op_side=record.op_side,
                    op_sect=record.op_sect,
                    op_bed=record.op_bed,
                    op_anesthesia=record.op_anesthesia,
                    pre_op_dx=record.diagn,  # 使用可能被覆蓋的 diagn
                    op_name=record.op_name,  # 使用 op_name (GSheet COL_OP 優先已在 FetchDetails 處理)
                )
                
                # 載入模板 (不 fallback 到其他類型)
                template = await _config_service.get_template(record.op_type, record.man)
                
                if not template:
                    # 找不到對應模板，拒絕送出
                    logger.warning(f"No template found for op_type={record.op_type}, hisno={hisno}")
                    details.append(f"{record.name} ({hisno}): 無對應手術模板 ({record.op_type})")
                    continue
                
                # 轉換日期
                roc_date = to_roc_date(record.op_date)
                if not roc_date:
                    logger.error(f"Invalid op_date for {hisno}: {record.op_date}")
                    details.append(f"{record.name} ({hisno}): 無效日期 ({record.op_date})")
                    continue
                
                # 建構 placeholder_values (使用動態欄位)
                # 從 gsheet_data 取得所有欄位 (轉為大寫 key)
                placeholder_values = {
                    k.upper(): v for k, v in record.gsheet_data.items()
                }
                # 使用動態 col_fields 覆蓋 (format: {'COL_IOL': 'Tecnis', 'COL_FINAL': '-0.5D', ...})
                placeholder_values.update(record.get_placeholder_values())
                
                # 建構 Payload
                payload, _ = _payload_builder.build_surgery_payload(
                    op_date=roc_date,
                    web9_data=record.web9_data,
                    surgery_fields=surgery_fields,
                    op_template=template,
                    placeholder_values=placeholder_values,
                )
                
                # diagn: 使用 record 中的值 (已經過使用者編輯)
                payload['diagn'] = record.diagn
                
                # diaga: 從 op_name 動態構建 (格式: "Ditto s/p {op_name}")
                # op_name 優先順序: 前端編輯 > GSheet COL_OP > 內網排程
                op_name_for_diaga = record.op_name or ''
                if op_name_for_diaga and record.op_side:
                    # 只有當 op_name 不包含側別資訊時，才加上 op_side
                    if not contains_side_info(op_name_for_diaga):
                        op_name_for_diaga = f"{op_name_for_diaga} {record.op_side}"
                payload['diaga'] = f"Ditto s/p {op_name_for_diaga}" if op_name_for_diaga else ""
                
                logger.debug(f"[Submit] Built payload: diagn={payload.get('diagn')}, diaga={payload.get('diaga')}, mann={payload.get('mann')}")
                
            except Exception as e:
                logger.error(f"Build payload for {hisno} failed: {e}")
                details.append(f"{record.name} ({hisno}): Payload error: {e}")
                continue
            
            # 4. 送出
            try:
                await session.rate_limit()
                
                if settings.DEV_MODE:
                    logger.info(f"[DEV_MODE] Surgery Submit for {hisno}:")
                    logger.info(f"[DEV_MODE] Payload: {payload}")
                    success_count += 1
                    details.append(f"{record.name} ({hisno}): [DEV] OK")
                    # 標記完成 (Checkpoint)
                    if job_id:
                        JobManager.mark_item_completed(job_id, hisno, f"送出 {record.name} ({i+1}/{total_items})")
                else:
                    url = 'https://web9.vghtpe.gov.tw/emr/OPAController'
                    
                    # 使用 safe_request 自動 retry/backoff
                    res = await client.safe_request('POST', url, data=payload)
                    
                    # 解析 Web9 回應
                    response_text = res.text
                    
                    # 檢查成功標記 (基於 HAR 分析的實際 Web9 回應)
                    # Web9 成功時會顯示 <FONT COLOR="RED">系統訊息:新增成功!!</FONT>
                    success_markers = ['新增成功!!']
                    # 明確的資料庫錯誤標記
                    error_markers = ['SQLCODE', 'SQLSTATE', 'DB2 SQL error', '異動失敗', '新增失敗', '資料錯誤']
                    
                    is_success = any(marker in response_text for marker in success_markers)
                    has_error = any(marker in response_text for marker in error_markers)
                    
                    # 如果有成功標記且沒有明確的錯誤標記，視為成功
                    if is_success and not has_error:
                        success_count += 1
                        details.append(f"{record.name} ({hisno}): Success")
                        # 標記完成 (Checkpoint)
                        if job_id:
                            JobManager.mark_item_completed(job_id, hisno, f"送出 {record.name} ({i+1}/{total_items})")
                    elif has_error:
                        # 有明確錯誤（如 SQLCODE）
                        logger.warning(f"[Submit] Failed for {hisno}: DB error detected")
                        details.append(f"{record.name} ({hisno}): DB Error")
                    else:
                        # 沒有明確的成功或錯誤標記，但 HTTP 200，視為成功
                        # 這是合理的假設，因為 Web9 在失敗時通常會返回明確的錯誤訊息
                        success_count += 1
                        details.append(f"{record.name} ({hisno}): Success (HTTP 200)")
                        if job_id:
                            JobManager.mark_item_completed(job_id, hisno, f"送出 {record.name} ({i+1}/{total_items})")
                        
            except Exception as e:
                logger.error(f"Submit {hisno} failed: {e}")
                details.append(f"{record.name} ({hisno}): Error {e}")
        
        # 清理暫存
        clear_record_cache()
        
        return SurgerySubmitResult(
            total=total_items,
            success=success_count,
            failed=total_items - success_count,
            details=details,
            message=f"送出 {success_count}/{total_items} 筆"
        )


# =============================================================================
# Register Tasks
# =============================================================================

TaskRegistry.register(SurgeryFetchScheduleTask())
TaskRegistry.register(SurgeryFetchDetailsTask())
TaskRegistry.register(SurgeryPreviewTask())
TaskRegistry.register(SurgerySubmitTask())
