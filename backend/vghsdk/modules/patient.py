
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from vghsdk.core import CrawlerTask, VghClient
import logging

logger = logging.getLogger(__name__)

class PatientSearchParams(BaseModel):
    hisno: Optional[str] = Field(default="", description="Hospital Number (病歷號)")
    pidno: Optional[str] = Field(default="", description="Patient ID (身分證號)")
    name: Optional[str] = Field(default="", description="Patient Name (姓名)")
    ward: Optional[str] = Field(default="0", description="Ward (病房號)")
    
class PatientSearchTask(CrawlerTask):
    """
    用病歷號/身分證號/姓名搜尋病人。
    
    Args:
        hisno: 病歷號
        pidno: 身分證號
        name: 姓名
        ward: 病房號；預設 "0"
    
    Returns:
        List[Dict] 包含欄位:
        - 功能: str
        - 病房床號: str
        - 病歷號: str
        - 姓名: str
        - 性別: str ("男"/"女")
        - 出生日: str (e.g. "19940216(31歲)")
    """
    id = "patient_search"
    name = "Patient Search"
    description = "搜尋病人 - 用病歷號/身分證號/姓名查詢"
    params_model = PatientSearchParams

    async def run(self, params: PatientSearchParams, client: VghClient) -> List[Dict[str, str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm?action=findPatient'
        
        # Mapped from old vghbot_crawler.py
        payload = {
            'wd': params.ward,
            'histno': params.hisno,
            'pidno': params.pidno,
            'namec': params.name,
            'drid': '', # Optional doc ID, left empty as per old code defaults
            'er': '0',
            'bilqrta': '0',
            'bilqrtdt': '',
            'bildurdt': '0',
            'other': '0',
            'nametype': ''
        }
        
        logger.info(f"Executing Patient Search with: {payload}")
        
        # We assume the session is already logged in by the runner
        resp = await session.post(url, data=payload)
        
        if '電子病歷查詢系統操作發生異常' in resp.text:
             logger.warning("VGH System specific error message detected.")
             return []

        # Parse HTML table
        # Old code used pd.read_html(..., attrs={'id':'patlist'})
        # We use BeautifulSoup for lightweight dependency
        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.find('table', id='patlist')
        
        results = []
        if not table:
            logger.info("No patient list table found.")
            return results
            
        # Parse headers
        headers = []
        thead = table.find('thead')
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all('th')]
        else:
            # Fallback if no thead, check first row
            rows = table.find_all('tr')
            if rows:
                 headers = [td.get_text(strip=True) for td in rows[0].find_all(['td', 'th'])]

        # Parse rows
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:] # Skip header if no tbody
        
        for row in rows:
            cols = row.find_all('td')
            if not cols: 
                continue
            
            # Map columns to headers
            record = {}
            for i, col in enumerate(cols):
                if i < len(headers):
                    record[headers[i]] = col.get_text(strip=True)
            results.append(record)
            
        return results

# Register
# Register

async def select_patient(session, hisno: str) -> bool:
    """
    Select a patient session-side before accessing their data.
    """
    check_url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
    check_payload = {
        'action': 'findEmr',
        'histno': str(hisno)
    }
    # We should use GET here as per old code
    resp = await session.get(check_url, params=check_payload)
    if '電子病歷查詢系統操作發生異常' in resp.text:
        return False
    return True

class PatientOpdListParams(BaseModel):
    hisno: str = Field(..., description="Hospital Number (病歷號)")
    old_than_four_years: bool = Field(default=True, description="Include records older than 4 years")

class PatientOpdListTask(CrawlerTask):
    """
    取得病人門診就診紀錄清單。
    
    Args:
        hisno: 病歷號
        old_than_four_years: 是否包含 4 年前紀錄；預設 True
    
    Returns:
        List[Dict] 包含欄位:
        - 門診日期: str (e.g. "2025-06-05")
        - 門診時間: str (e.g. "08:26:42")
        - 門診醫師: str - 含醫師燈號 (e.g. "鄭明軒 (DOC4123J)")
        - 科別: str - 含科別名稱 (e.g. "0PH(眼科特別門診)")
        - 門診主診斷碼: str - ICD 碼以逗號分隔
    """
    id = "patient_opd_list"
    name = "Outpatient Visit List"
    description = "門診紀錄清單 - 取得病人就診歷史"
    params_model = PatientOpdListParams
    
    # ... (Run method unchanged) ...
    async def run(self, params: PatientOpdListParams, client: VghClient) -> List[Dict[str, str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        # 1. Select Patient
        if not await select_patient(session, params.hisno):
            logger.warning(f"Patient {params.hisno} not found or selection failed.")
            return []

        url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
        results = []

        # 2. Fetch Recent Records (findOpd)
        payload = {
            'action': 'findOpd',
            'histno': str(params.hisno),
            '_': 0 
        }
        await self._fetch_and_parse(session, url, payload, results)

        # 3. Fetch Older Records if requested (findOpd01)
        if params.old_than_four_years:
            payload_old = {
                'action': 'findOpd01',
                'histno': str(params.hisno),
                '_': 0
            }
            await self._fetch_and_parse(session, url, payload_old, results)
            
        return results

    async def _fetch_and_parse(self, session, url: str, payload: dict, results: list):
        try:
            resp = await session.get(url, params=payload)
            if '無門診' in resp.text:
                return

            soup = BeautifulSoup(resp.text, 'lxml')
            table_id = 'opdlist' if payload['action'] == 'findOpd' else 'opdlist01'
            table = soup.find('table', id=table_id)
            
            if not table: return

            headers = []
            rows = table.find_all('tr')
            if not rows: return
                
            headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
            
            for row in rows[1:]:
                cols = row.find_all('td')
                if not cols: continue
                record = {}
                for i, col in enumerate(cols):
                    if i < len(headers):
                        record[headers[i]] = col.get_text(strip=True)
                results.append(record)

        except Exception as e:
            logger.error(f"Failed to fetch OPD list part: {e}")

# --- Bulk Migration of Other Patient Tasks ---

class PatientInfoParams(BaseModel):
    hisno: str = Field(..., description="Hospital Number")

class PatientInfoTask(CrawlerTask):
    """
    取得病人詳細基本資料。
    
    Args:
        hisno: 病歷號
    
    Returns:
        Dict 包含欄位:
        - 病歷號, 病房床號, 姓名, 生日, 性別, 血型
        - 身份證號, 科別, 來院狀況, 身分, 病患狀態
        - 電話１, 電話２, 行動電話, 地址, ＥＭＡＩＬ
        - 目前診斷, 主治醫師, 住院醫師, 實習醫師, 醫五Clerk
        - 最近就診日, 傳染病註記, 吸菸習慣, 嚼檳榔習慣
        - 緊急聯絡人, 緊急聯絡人電話
    """
    id = "patient_info"
    name = "Patient Info"
    description = "病人基本資料 - 取得詳細個人資訊"
    params_model = PatientInfoParams

    async def run(self, params: PatientInfoParams, client: VghClient) -> Dict[str, str]:
        if not await client.ensure_eip(): return {}
        session = client.session
        if not await select_patient(session, params.hisno): return {}
        
        url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
        payload = {'action': 'findPba', 'histno': str(params.hisno), '_': 0}
        
        resp = await session.get(url, params=payload)
        soup = BeautifulSoup(resp.text, 'lxml')
        data = {}
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) == 2:
                label = cols[0].get_text(strip=True)
                # Clean label: remove "０１．" prefix etc.
                if '．' in label:
                     label = label.split('．')[-1]
                label = label.replace('：', '').replace('　', '')
                val = cols[1].get_text(strip=True)
                data[label] = val
        return data

class PatientOpdNoteParams(BaseModel):
    hisno: str
    dt: str
    dept: str
    doc: str = ""
    deptnm: str = ""

from urllib.parse import quote

class PatientOpdNoteTask(CrawlerTask):
    """
    取得特定門診的 SOAP 病歷內容。
    
    Args:
        hisno: 病歷號
        dt: 門診日期 (來自 opd_list)
        dept: 科別代碼
        doc: 門診醫師 (可選)
        deptnm: 科別名稱 (可選)
    
    Returns:
        Dict 包含欄位:
        - hisno, dt, dept, doc, deptnm: 輸入參數原樣回傳
        - S: str - Subjective (主觀資料)
        - O: str - Objective (客觀資料)
        - P: str - Plan (治療計畫)
        - soap: str - 完整 SOAP 內容
        - drugs: str - 用藥記錄
        - orders: str - 門診醫囑
    """
    id = "patient_opd_note"
    name = "OPD Note (SOAP)"
    description = "門診 SOAP 病歷 - 取得特定門診病歷內容"
    params_model = PatientOpdNoteParams

    async def run(self, params: PatientOpdNoteParams, client: VghClient) -> Dict[str, str]:
        if not await client.ensure_eip(): return {}
        session = client.session
        if not await select_patient(session, params.hisno): return {}
        
        url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
        # Need manual quoting for Big5 encoding if required by server?
        # Old code used: quote(doc, encoding='big5'). 
        # Requests/Httpx handles encoding but URL params might be tricky.
        # We will try standard dict first. If it fails, we handle encoding manually.
        # Actually httpx params are utf-8 by default. If server needs Big5, we might need manual string construction.
        # The old code EXPLICITLY quotes with big5. We should replicate that or let httpx handle it if we can set encoding.
        # Safest is to construct URL string or use encoded bytes.
        
        # NOTE: Httpx params accepts bytes.
        
        payload = {
            'action': 'findOpd',
            'histno': str(params.hisno),
            'dt': params.dt,
            'dept': params.dept,
            'doc': params.doc, # Might need Big5
            'deptnm': params.deptnm, # Might need Big5
            '_': 0
        }
        
        # TODO: Handle Big5 encoding for 'doc' and 'deptnm' if requests fail.
        # For now, implementing struct.
        
        resp = await session.get(url, params=payload)
        soup = BeautifulSoup(resp.text, 'lxml')
        
        data = params.model_dump()
        
        pre_tags = soup.find_all('pre')
        if len(pre_tags) >= 2:
            data['S'] = pre_tags[0].get_text()
            data['O'] = pre_tags[1].get_text()
            data['P'] = pre_tags[2].get_text() if len(pre_tags) > 2 else ""
        
        # Legend parsing
        def get_fieldset_text(legend_text):
            elem = soup.find('legend', string=lambda t: t and legend_text in t)
            if elem:
                return elem.find_parent('fieldset').get_text()
            return ""

        # S/O/A/P logic in old code:
        # soap = soup.find('legend').find_parent('fieldset').get_text()
        first_legend = soup.find('legend')
        if first_legend:
             data['soap'] = first_legend.find_parent('fieldset').get_text()
        
        data['drugs'] = get_fieldset_text('[用藥記錄]')
        data['orders'] = get_fieldset_text('[門診醫囑]')
        
        return data

class PatientOpListParams(BaseModel):
    hisno: str

class PatientOpListTask(CrawlerTask):
    id = "patient_op_list"
    name = "Operation List"
    description = "Get operation list. (Ported from vghbot_crawler.op_list)\n" \
                  "Original Comment: 病人:手術清單"
    params_model = PatientOpListParams

    async def run(self, params: PatientOpListParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         # Similar to opd_list parse logic
         if not await select_patient(session, params.hisno): return []
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findOpn', 'histno': str(params.hisno), '_': 0}
         resp = await session.get(url, params=payload)
         # Using generic table parser[內碼] 
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table', id='opnlist')
         if not table: return []
         
         # Reuse generic parser... (Copy-paste for now to keep independent)
         headers = []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i<len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res

class PatientOpNoteParams(BaseModel):
    hisno: str
    dt: str

class PatientOpNoteTask(CrawlerTask):
    id = "patient_op_note"
    name = "Operation Note"
    description = "Get operation note text. (Ported from vghbot_crawler.op_note)\n" \
                  "Original Comment: 病人:手術note"
    params_model = PatientOpNoteParams
    
    async def run(self, params: PatientOpNoteParams, client: VghClient) -> str:
         if not await client.ensure_eip(): return ""
         session = client.session
         if not await select_patient(session, params.hisno): return ""
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findOpn', 'histno': params.hisno, 'dt': params.dt, 'tm': 1, '_': 0}
         resp = await session.get(url, params=payload)
         return resp.text

class PatientAdListTask(CrawlerTask):
    id = "patient_ad_list"
    name = "Admission List"
    description = "Get admission list. (Ported from vghbot_crawler.ad_list)\n" \
                  "Original Comment: 病人:住院清單"
    params_model = PatientOpListParams # Shared params

    async def run(self, params: PatientOpListParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         if not await select_patient(session, params.hisno): return []
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findAdm', 'histno': str(params.hisno), '_': 0}
         resp = await session.get(url, params=payload)
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table', id='admlist')
         if not table: return []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i < len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res

class PatientAdNoteParams(BaseModel):
    hisno: str
    caseno: str
    adidate: str
    
class PatientAdNoteTask(CrawlerTask):
    id = "patient_ad_note"
    name = "Admission Note"
    description = "Get admission note text. (Ported from vghbot_crawler.ad_note)\n" \
                  "Original Comment: 病人:住院note"
    params_model = PatientAdNoteParams
    
    async def run(self, params: PatientAdNoteParams, client: VghClient) -> str:
         if not await client.ensure_eip(): return ""
         session = client.session
         if not await select_patient(session, params.hisno): return ""
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findAdm', 'histno': params.hisno, 'caseno': params.caseno, 'adidate': params.adidate, 'tm': 1, '_': 0}
         resp = await session.get(url, params=payload)
         return resp.text

# --- Drug Tasks ---

class PatientDrugListTask(CrawlerTask):
    id = "patient_drug_list"
    name = "Drug List"
    description = "Get patient drug/medication list history."
    params_model = PatientOpListParams 

    async def run(self, params: PatientOpListParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         if not await select_patient(session, params.hisno): return []
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findUd', 'histno': str(params.hisno), '_': 0}
         resp = await session.get(url, params=payload)
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table', id='caselist')
         if not table: return []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i < len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res

class PatientDrugContentParams(BaseModel):
    hisno: str
    caseno: str
    dt: str
    type: str
    dept: str
    dt1: str 
    
class PatientDrugContentTask(CrawlerTask):
    id = "patient_drug_content"
    name = "Drug Content"
    description = "Get details of a specific drug prescription."
    params_model = PatientDrugContentParams

    async def run(self, params: PatientDrugContentParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         if not await select_patient(session, params.hisno): return []
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {
             'action': 'findUd',
             'histno': str(params.hisno),
             'caseno': params.caseno,
             'dt': params.dt, 
             'type': params.type,
             'dept': params.dept,
             'dt1': params.dt1,
             '_': 0
         }
         resp = await session.get(url, params=payload)
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table', id='udorder')
         if not table: return []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i < len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res

# --- Consult Tasks ---

class PatientConsultListTask(CrawlerTask):
    id = "patient_consult_list"
    name = "Consultation List"
    description = "Get consultation list."
    params_model = PatientOpListParams 

    async def run(self, params: PatientOpListParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         if not await select_patient(session, params.hisno): return []
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findCps', 'histno': str(params.hisno), '_': 0}
         resp = await session.get(url, params=payload)
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table', id='cpslist')
         if not table: return []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i < len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res

class PatientConsultNoteParams(BaseModel):
    hisno: str
    caseno: str
    oseq: str

class PatientConsultNoteTask(CrawlerTask):
    id = "patient_consult_note"
    name = "Consultation Note"
    description = "Get consultation text."
    params_model = PatientConsultNoteParams

    async def run(self, params: PatientConsultNoteParams, client: VghClient) -> str:
         if not await client.ensure_eip(): return ""
         session = client.session
         if not await select_patient(session, params.hisno): return ""
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {
             'action': 'findCps', 
             'histno': str(params.hisno), 
             'caseno': params.caseno,
             'oseq': params.oseq,
             '_': 0
         }
         resp = await session.get(url, params=payload)
         return resp.text

# --- Scanned Note Task ---

class PatientScanNoteParams(BaseModel):
    tdept: str = Field(default="OPH", description="Department code")

class PatientScanedNoteTask(CrawlerTask):
    id = "patient_scaned_note"
    name = "Scanned Note List"
    description = "Get list of scanned notes."
    params_model = PatientScanNoteParams

    async def run(self, params: PatientScanNoteParams, client: VghClient) -> List[Dict[str,str]]:
         if not await client.ensure_eip(): return []
         session = client.session
         url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
         payload = {'action': 'findScan', 'tdept': params.tdept, '_': 0}
         resp = await session.get(url, params=payload)
         soup = BeautifulSoup(resp.text, 'lxml')
         table = soup.find('table') 
         if not table: return []
         rows = table.find_all('tr')
         if not rows: return []
         headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
         res = []
         for row in rows[1:]:
             cols = row.find_all('td')
             rec = {}
             for i,c in enumerate(cols):
                 if i < len(headers): rec[headers[i]] = c.get_text(strip=True)
             res.append(rec)
         return res



# --- Advanced Tasks ---
import re

class PatientOpdListSearchParams(BaseModel):
    hisno: str
    doc_regex: str = Field(default="", description="Regex for Doctor Name")
    dept_regex: str = Field(default="", description="Regex for Dept Name/Code")
    old_than_four_years: bool = True

class PatientOpdListSearchTask(CrawlerTask):
    id = "patient_opd_list_search"
    name = "Search OPD List"
    description = "Search OPD list with client-side filtering."
    params_model = PatientOpdListSearchParams

    async def run(self, params: PatientOpdListSearchParams, client: VghClient) -> List[Dict[str,str]]:
        base_task = PatientOpdListTask()
        base_params = PatientOpdListParams(
            hisno=params.hisno,
            old_than_four_years=params.old_than_four_years
        )
        
        raw_list = await base_task.run(base_params, client)
        
        if not raw_list:
            return []
            
        results = []
        doc_pattern = re.compile(params.doc_regex, re.IGNORECASE) if params.doc_regex else None
        dept_pattern = re.compile(params.dept_regex, re.IGNORECASE) if params.dept_regex else None
        
        for item in raw_list:
            doc_val = item.get('門診醫師', '')
            dept_val = item.get('科別', '')
            
            match_doc = (not doc_pattern) or bool(doc_pattern.search(doc_val))
            match_dept = (not dept_pattern) or bool(dept_pattern.search(dept_val))
            
            if match_doc and match_dept:
                results.append(item)
                
        return results

# Register all
# TaskRegistry.register(PatientOpdListSearchTask())

