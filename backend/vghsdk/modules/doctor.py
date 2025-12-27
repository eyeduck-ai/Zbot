
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from vghsdk.core import CrawlerTask, VghClient
from datetime import datetime, timedelta
import logging
import asyncio
from urllib.parse import unquote
from vghsdk.utils import to_western_date, to_roc_date

logger = logging.getLogger(__name__)

class DocOpdListPreviousParams(BaseModel):
    date: Optional[str] = Field(None, description="Specific date (YYYYMMDD)")
    date_start: Optional[str] = Field(None, description="Start date (YYYYMMDD)")
    date_end: Optional[str] = Field(None, description="End date (YYYYMMDD)")
    
class PatientOpdListPreviousTask(CrawlerTask):
    """
    取得登入醫師的過去看診病人名單。
    
    Args:
        date: 特定日期 (YYYYMMDD)
        date_start: 起始日期 (YYYYMMDD)
        date_end: 結束日期 (YYYYMMDD)
    
    Returns:
        List[Dict] 包含欄位:
        - date: str - 查詢日期
        - 病歷號: str
        - 姓名: str ()
        - 門診科別: str
        - 門診醫師: str
    """
    id = "doc_opd_patient_list_previous"
    name = "Doctor Previous OPD List"
    description = "醫師過去看診名單 - 取得指定日期或範圍的看診病人"
    params_model = DocOpdListPreviousParams

    async def run(self, params: DocOpdListPreviousParams, client: VghClient) -> List[Dict[str, str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        if params.date:
             return await self._fetch_date(session, params.date)
        elif params.date_start:
             return await self._fetch_range(session, params.date_start, params.date_end)
        return []

    async def _fetch_date(self, session, date_str: str) -> List[Dict[str, str]]:
        url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
        payload = {
            'action': 'findOpdRotQ8',
            'dtpdate': date_str,
            '_': 0
        }
        try:
            await session.rate_limit()
            resp = await session.get(url, params=payload)
            return self._parse_table(resp.text, date_str)
        except Exception as e:
            logger.error(f"Failed to fetch OPD previous list for {date_str}: {e}")
            return []

    async def _fetch_range(self, session, start_str: str, end_str: Optional[str]) -> List[Dict[str, str]]:
        results = []
        try:
            d_start = to_western_date(start_str)
            if not d_start: return []
            
            d_end = to_western_date(end_str) if end_str else datetime.now().date() - timedelta(days=1)
            
            if isinstance(d_start, datetime): d_start = d_start.date()
            if isinstance(d_end, datetime): d_end = d_end.date()

            curr = d_start
            while curr <= d_end:
                 date_s = to_roc_date(curr) # Fetch using ROC if logic demands it? 
                 # wait, _fetch_date takes?
                 # params.date in doctor.py line 29 calls _fetch_date(params.date)
                 # params.date description says YYYYMMDD?
                 # doctor.py line 14: "Specific date (YYYYMMDD)"
                 # But _fetch_date line 38 uses it as 'dtpdate'
                 # 'dtpdate' usually is ROC in VGH (e.g. 1120703).
                 # BUT the docstring said YYYYMMDD.
                 # Let's assume VGH standard ROC.
                 # I'll use to_roc_date(curr) just to be safe if 'dtpdate' expects ROC.
                 # BUT existing code was: curr.strftime("%Y%m%d") -> Western?
                 # If existing code used %Y%m%d, then it was Western. 
                 # Let's check _fetch_date logic again.
                 # It calls findOpdRotQ8.
                 # Usually these are ROC.
                 # IF existing code worked, maybe it expects Western?
                 # Wait, line 52: d_start = datetime.strptime(start_str, '%Y%m%d')
                 # line 57: date_s = curr.strftime("%Y%m%d")
                 # It seems strictly Western YYYYMMDD.
                 # I will preserve YYYYMMDD for now, but use utils for parsing input.
                 
                 date_s = curr.strftime("%Y%m%d")
                 day_res = await self._fetch_date(session, date_s)
                 if day_res:
                     results.extend(day_res)
                 curr += timedelta(days=1)
                 # Rate limit is handled by core.py safe_request which calls rate_limit() 
                 # BUT here we are calling session.get directly which DOES NOT rate limit?
                 # No, Task.run receives 'session' which is VghSession.
                 # The 'rate_limit' logic is on 'BaseCrawler'.
                 # The runner in router.py passes 'crawler_ctx.session'.
                 # If we want rate limiting here, we need to sleep manually
                 # OR we should have passed the 'crawler_ctx' instead of 'session' to 'run'.
                 # Refactoring Point: pass rate limiter or sleep manually here.
                 # Since user asked for safety, we MUST sleep manually here if valid method not available.
                 
                 await asyncio.sleep(2) # Manual safety sleep
                 
        except Exception as e:
            logger.error(f"Date range parse error: {e}")
        return results

    def _parse_table(self, html: str, date_str: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, 'lxml')
        # Check if "No Record"
        # Old code checks: table_list[0].iloc[0,0] == '看診清單'
        # If the table only has one cell saying "看診清單" usually means empty? 
        # Or actual data table. Needs strict check.
        # Let's parse generic table.
        
        table = soup.find('table')
        if not table: return []
        
        rows = table.find_all('tr')
        if not rows: return []
        
        # Check content indicating empty
        text_content = table.get_text()
        if "無紀錄" in text_content or len(rows) < 2:
            return []
            
        headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
        data = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if not cols: continue
            rec = {"date": date_str}
            for i, col in enumerate(cols):
                if i < len(headers):
                    rec[headers[i]] = col.get_text(strip=True)
            data.append(rec)
        return data


class DocOpdListAppointmentParams(BaseModel):
    date: Optional[str] = Field(None, description="Specific date (YYYYMMDD)")

class PatientOpdListAppointmentTask(CrawlerTask):
    """
    取得登入醫師的未來預約掙號病人名單。
    
    Args:
        date: 特定日期 (YYYYMMDD)，可選
    
    Returns:
        List[Dict] 包含欄位:
        - 掙號日期: str (YYYYMMDD)
        - 科代碼: str - 科別代碼
        - 診間代碼: str - 診間編號
        - 病歷號: str
        - 姓名: str
        - ...其他詳細欄位 (從 regdetail 取得)
    """
    id = "doc_opd_patient_list_appointment" 
    name = "Doctor Future Appointment List"
    description = "Get doctor's future appointment list. (Ported from vghbot_crawler.opd_patient_list_appointment)\n" \
                  "Original Comment: 醫師:未來掛號名單"
    params_model = DocOpdListAppointmentParams

    async def run(self, params: DocOpdListAppointmentParams, client: VghClient) -> List[Dict[str, Any]]:
        if not await client.ensure_eip(): return []
        session = client.session
        base_url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
        payload = {
            'action': 'findReg',
            '_': 0
        }
        
        # 1. Fetch Summary List
        resp = await session.get(base_url, params=payload)
        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.find('table', id='reglist')
        
        if not table: return []
        
        headers = []
        rows = table.find_all('tr')
        if rows:
            headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
        
        summary_list = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if not cols: continue
            rec = {}
            for i, col in enumerate(cols):
                if i < len(headers):
                    rec[headers[i]] = col.get_text(strip=True)
            summary_list.append(rec)
            
        # Filter by date if requested
        if params.date:
            summary_list = [x for x in summary_list if x.get('掛號日期') == params.date]
            
        # 2. Fetch Details for each entry
        detailed_list = []
        for item in summary_list:
            # item keys might depend on Chinese headers: '掛號日期','科代碼','診間代碼'
            dt = item.get('掛號日期')
            ect = item.get('科代碼')
            room = item.get('診間代碼')
            
            if dt and ect and room:
                payload2 = {
                    'action': 'findReg',
                    'dt': dt,
                    'ect': ect,
                    'room': room,
                    '_': 0
                }
                
                # Safety delay
                await asyncio.sleep(1.5)
                
                resp2 = await session.get(base_url, params=payload2)
                soup2 = BeautifulSoup(resp2.text, 'lxml')
                table2 = soup2.find('table', id='regdetail')
                
                if table2:
                    rows2 = table2.find_all('tr')
                    if rows2:
                        h2 = [th.get_text(strip=True) for th in rows2[0].find_all(['th', 'td'])]
                        for r2 in rows2[1:]:
                            c2 = r2.find_all('td')
                            sub_rec = item.copy() # Inherit summary info
                            for i, val in enumerate(c2):
                                if i < len(h2):
                                    sub_rec[h2[i]] = val.get_text(strip=True)
                            detailed_list.append(sub_rec)
        
        return detailed_list


# --- Advanced Batch Tasks ---
from vghsdk.modules.patient import PatientOpdNoteTask, PatientOpdNoteParams
import asyncio
import random

class DoctorBatchOpdNoteParams(BaseModel):
    date_start: str
    date_end: Optional[str] = None
    limit: Optional[int] = Field(None, description="Max patients to process")

class BatchOpdNoteTask(CrawlerTask):
    """
    批次取得醫師過去病人的門診 SOAP 病歷。
    會先取得醫師的過去看診名單，再逐一取得 SOAP。
    
    Args:
        date_start: 起始日期 (YYYYMMDD)
        date_end: 結束日期 (可選)
        limit: 最大處理病人數 (可選)
    
    Returns:
        List[Dict] 合併結果，包含:
        - 原始看診名單欄位 (病歷號, 門診日期, 科別...)
        - soap: str - SOAP 內容
        - S, O, P: str - 分開的 SOAP 內容
        - drugs: str - 用藥記錄
    
    Note:
        此功能耗時較長，建議設定 limit 限制處理數量。
    """
    id = "doc_batch_opd_note"
    name = "Batch OPD Notes"
    description = "批次門診病歷 - 取得醫師過去病人的 SOAP (耗時操作)"
    params_model = DoctorBatchOpdNoteParams

    async def run(self, params: DoctorBatchOpdNoteParams, client: VghClient) -> List[Dict[str, Any]]:
        if not await client.ensure_eip(): return []
        session = client.session
        # 1. Get Doctor's Schedule (Previous List)
        # Using DocOpdPatientListPreviousTask
        list_task = DocOpdPatientListPreviousTask()
        list_params = DocOpdListPreviousParams(
            date_start=params.date_start,
            date_end=params.date_end
        )
        patient_list = await list_task.run(list_params, client)
        
        logger.info(f"Batch Note: Found {len(patient_list)} records in schedule.")
        
        # Filter Logic (Eye Depts)
        # 010, 110, 0PH, 1PH
        target_depts = ['010', '110', '0PH', '1PH']
        
        # The list items (from DocOpdPatientListPreviousTask) have keys mapping from table headers.
        # We need to map them correctly.
        # Typically keys: '病歷號', '門診日期', '門診科別', '門診醫師'
        
        filtered_list = []
        for row in patient_list:
            # Check keys - assuming standard Chinese headers based on legacy usage
            dept = row.get('門診科別') or row.get('科別')
            if dept in target_depts:
                filtered_list.append(row)
        
        logger.info(f"Batch Note: {len(filtered_list)} records match target departments.")
        
        results = []
        count = 0
        limit = params.limit or 9999
        
        # 2. Iterate and Fetch Notes
        note_task = PatientOpdNoteTask()
        
        for i, row in enumerate(filtered_list):
            if count >= limit: break
            
            # Extract params
            hisno = row.get('病歷號')
            dt = row.get('門診日期') # Format? YYYYMMDD usually if from previous code
            dept = row.get('門診科別') or row.get('科別')
            doc = row.get('門診醫師') or row.get('醫師') # Might contain name+id
            
            if not hisno or not dt:
                continue
                
            # Legacy code passes 'deptnm' which is mapped from code.
            # dpt_to_dptnm = {'010': '眼科－上午', ...}
            # We can try empty or reuse dept code as placeholder if server allows.
            # Or define the map here.
            dpt_map = {
                '010': '眼科－上午',
                '110': '眼科－下午',
                '0PH': '眼科特別門診',
                '1PH': '眼科特別門診',
            }
            deptnm = dpt_map.get(dept, "")

            note_params = PatientOpdNoteParams(
                hisno=hisno,
                dt=dt,
                dept=dept,
                doc=doc,
                deptnm=deptnm
            )
            
            # Fetch Note
            try:
                note_data = await note_task.run(note_params, client)
                
                # Merge Info
                composite = row.copy()
                if note_data:
                    composite['soap'] = note_data.get('soap')
                    composite['S'] = note_data.get('S')
                    composite['O'] = note_data.get('O')
                    composite['P'] = note_data.get('P')
                    composite['drugs'] = note_data.get('drugs')
                    # ... other fields
                
                results.append(composite)
                count += 1
                
                # Safety Sleep
                # Every 50 records sleep 15s (Legacy) -> We can do smaller checks or just random sleep
                if (i + 1) % 50 == 0:
                    logger.info("Batch Note: Long pause (15s)...")
                    await asyncio.sleep(15)
                else:
                    await session.rate_limit() # Using the new random 1.5-4s logic
                    
            except Exception as e:
                logger.error(f"Failed to fetch note for {hisno} on {dt}: {e}")
                
        return results


# --- Helper Functions ---

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
