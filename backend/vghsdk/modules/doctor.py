"""Doctor 模組 - 醫師相關查詢 (Function-based)。

以 MCP 版本 (已驗證) 為主要邏輯來源。
"""
import logging
import asyncio
import re
import random
from datetime import datetime, timedelta
from typing import Optional, List
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from vghsdk.core import VghClient, TaskResult, crawler_task
from vghsdk.utils import normalize_date, to_yyyymmdd
from vghsdk.helpers import parse_table

logger = logging.getLogger(__name__)


# --- Params ---

class DocOpdListPreviousParams(BaseModel):
    date: Optional[str] = Field(None, description="單一日期 (YYYY-MM-DD)")
    date_start: Optional[str] = Field(None, description="開始日期 (YYYY-MM-DD)")
    date_end: Optional[str] = Field(None, description="結束日期 (YYYY-MM-DD)")

class DocOpdAppointmentParams(BaseModel):
    date: str = Field(..., description="門診日期 (YYYY-MM-DD)")
    ect: str = Field(..., description="科代碼, 如 '010'")
    room: str = Field(..., description="診間代碼, 如 '08'")

class DocBatchOpdNoteParams(BaseModel):
    date_start: str = Field(..., description="開始日期 (YYYY-MM-DD)")
    date_end: Optional[str] = Field(None, description="結束日期 (YYYY-MM-DD)")
    limit: int = Field(default=50, description="最大處理數量")
    target_depts: Optional[List[str]] = Field(None, description="科別代碼清單")


# --- Tasks ---

@crawler_task(
    id="doc_opd_list_previous",
    name="Doc OPD List Previous",
    description="取得醫師過去看診名單",
    params_model=DocOpdListPreviousParams
)
async def doc_opd_list_previous(params: DocOpdListPreviousParams, client: VghClient) -> TaskResult:
    """取得醫師過去看診名單。僅能查詢過去日期。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
    results = []
    
    if params.date:
        api_date = to_yyyymmdd(params.date) or params.date
        d = normalize_date(params.date)
        iso_date = d.strftime("%Y-%m-%d") if d else params.date
        
        resp = await client.session.get(url, params={'action': 'findOpdRotQ8', 'dtpdate': api_date, '_': 0})
        rows = parse_table(resp.text, None)
        for r in rows:
            r['date'] = api_date
            r['date_iso'] = iso_date
        results = rows
    
    elif params.date_start:
        d_start = normalize_date(params.date_start)
        if not d_start:
            return TaskResult.fail("日期格式錯誤")
        
        d_end = normalize_date(params.date_end) if params.date_end else datetime.now().date() - timedelta(days=1)
        
        curr = d_start
        while curr <= d_end:
            api_date = curr.strftime("%Y%m%d")
            iso_date = curr.strftime("%Y-%m-%d")
            resp = await client.session.get(url, params={'action': 'findOpdRotQ8', 'dtpdate': api_date, '_': 0})
            rows = parse_table(resp.text, None)
            for r in rows:
                r['date'] = api_date
                r['date_iso'] = iso_date
            results.extend(rows)
            curr += timedelta(days=1)
            await asyncio.sleep(2)
    
    return TaskResult.ok(results)


@crawler_task(
    id="doc_opd_schedule",
    name="Doc OPD Schedule",
    description="取得醫師未來門診掛號日期清單",
    params_model=None
)
async def doc_opd_schedule(params, client: VghClient) -> TaskResult:
    """取得醫師未來門診掛號日期清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
    resp = await client.session.get(url, params={'action': 'findReg', '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='reglist')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])] if rows else []
    
    results = []
    for row in rows[1:]:
        cols = row.find_all('td')
        if cols:
            record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
            
            if '掛號日期' in record and len(record['掛號日期']) == 8:
                d = record['掛號日期']
                record['掛號日期_iso'] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            
            results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="doc_opd_list_appointment",
    name="Doc OPD Appointment List",
    description="取得醫師特定門診時段的掛號名單",
    params_model=DocOpdAppointmentParams
)
async def doc_opd_list_appointment(params: DocOpdAppointmentParams, client: VghClient) -> TaskResult:
    """取得醫師特定門診時段的掛號名單。需先用 doc_opd_schedule 取得參數。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    api_date = to_yyyymmdd(params.date) or params.date
    
    url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
    resp = await client.session.get(url, params={'action': 'findReg', 'dt': api_date, 'ect': params.ect, 'room': params.room, '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='regdetail')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])] if rows else []
    
    results = []
    for row in rows[1:]:
        cols = row.find_all('td')
        if cols:
            record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
            results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="doc_batch_opd_note",
    name="Doc Batch OPD Note",
    description="批次取得門診 SOAP (耗時操作)",
    params_model=DocBatchOpdNoteParams
)
async def doc_batch_opd_note(params: DocBatchOpdNoteParams, client: VghClient) -> TaskResult:
    """批次取得門診 SOAP。防護機制：基本延遲+批次休息+錯誤退避。"""
    
    # 預設眼科科別
    target_depts = params.target_depts or ['010', '110', '0PH', '1PH']
    target_set = set(target_depts)
    
    # 取得病人清單
    list_params = DocOpdListPreviousParams(date_start=params.date_start, date_end=params.date_end)
    list_result = await doc_opd_list_previous(list_params, client)
    if not list_result.success:
        return list_result
    
    patient_list = list_result.data
    
    # 過濾科別
    filtered = []
    dpt_map = {}
    for r in patient_list:
        dept_field = r.get('科別', '') or r.get('門診科別', '')
        match = re.match(r'(\w+)\((.+)\)', dept_field)
        if match:
            dept_code = match.group(1)
            dept_name = match.group(2).strip()
            if dept_code in target_set:
                r['_dept_code'] = dept_code
                r['_dept_name'] = dept_name
                dpt_map[dept_code] = dept_name
                filtered.append(r)
        else:
            dept_code = r.get('門診科別') or dept_field
            if dept_code in target_set:
                r['_dept_code'] = dept_code
                r['_dept_name'] = dpt_map.get(dept_code, '')
                filtered.append(r)
    
    total = min(len(filtered), params.limit)
    logger.info(f"[Batch] 符合科別: {len(filtered)}/{len(patient_list)}, 處理: {total}")
    
    from vghsdk.modules.patient import patient_opd_note, PatientOpdNoteParams
    
    results = []
    consecutive_errors = 0
    base_delay = 1.0
    
    for i, row in enumerate(filtered[:params.limit]):
        hisno = row.get('病歷號')
        dt = row.get('門診日期') or row.get('date_iso')
        dept_code = row.get('_dept_code', '')
        dept_name = row.get('_dept_name', '')
        doc = row.get('門診醫師') or row.get('醫師', '')
        
        if not hisno or not dt:
            continue
        
        status = "OK"
        try:
            note_params = PatientOpdNoteParams(hisno=hisno, dt=dt, dept=dept_code, doc=doc, deptnm=dept_name)
            note = await patient_opd_note(note_params, client)
            rec = row.copy()
            rec.pop('_dept_code', None)
            rec.pop('_dept_name', None)
            
            if note.success and note.data:
                for k in ['soap', 'S', 'O', 'P', 'drugs']:
                    rec[k] = note.data.get(k, '')
                consecutive_errors = 0
            else:
                status = "EMPTY"
                consecutive_errors += 1
            
            results.append(rec)
            
        except Exception as e:
            status = f"ERROR: {e}"
            consecutive_errors += 1
            logger.error(f"Failed for {hisno}: {e}")
        
        logger.info(f"[{i+1}/{total}] {hisno} - {status}")
        
        delay = base_delay + random.uniform(0, 0.5)
        if (i + 1) % 50 == 0:
            delay += 10
        if consecutive_errors >= 3:
            logger.warning(f"連續 {consecutive_errors} 錯誤，暫停 30 秒")
            delay = 30
            consecutive_errors = 0
        elif consecutive_errors > 0:
            delay *= (1 + consecutive_errors * 0.5)
        
        await asyncio.sleep(delay)
    
    logger.info(f"[Batch] 完成: {len(results)}/{total}")
    return TaskResult.ok(results)


# --- Helper for external use ---

async def get_doctor_name(doc_code: str, session) -> str:
    """根據醫師登號查詢姓名
    
    Args:
        doc_code: 4位數字的醫師登號 (例如 "4102")
        session: VghSession 實例
    
    Returns:
        醫師姓名，若查詢失敗則返回空字串
    """
    url = "https://web9.vghtpe.gov.tw/emr/OPAController"
    params = {"doc": str(doc_code), "action": "CheckDocAction"}
    
    try:
        res = await session.get(url, params=params)
        name = res.text.strip()
        if name:
            logger.debug(f"查詢醫師登號 {doc_code} → {name}")
            return name
        else:
            logger.warning(f"醫師登號 {doc_code} 查無對應姓名")
            return ""
    except Exception as e:
        logger.error(f"查詢醫師登號失敗: {e}")
        return ""


# --- Legacy Compatibility ---
PatientOpdListPreviousTask = doc_opd_list_previous
PatientOpdListAppointmentTask = doc_opd_list_appointment
BatchOpdNoteTask = doc_batch_opd_note
