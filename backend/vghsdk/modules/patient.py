"""Patient 模組 - 病人相關查詢 (Function-based)。

以 MCP 版本 (已驗證) 為主要邏輯來源。
"""
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from vghsdk.core import VghClient, TaskResult, crawler_task
from vghsdk.utils import normalize_date, to_roc_date_8, to_iso_string, to_yyyymmdd
from vghsdk.helpers import parse_table

logger = logging.getLogger(__name__)


# --- Params ---

class PatientSearchParams(BaseModel):
    hisno: Optional[str] = Field(None, description="病歷號")
    pidno: Optional[str] = Field(None, description="身分證號")
    name: Optional[str] = Field(None, description="姓名")
    ward: str = Field(default="0", description="病房號")

class PatientHisnoParams(BaseModel):
    hisno: str = Field(..., description="病歷號")

class PatientOpdListParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    old_than_four_years: bool = Field(default=True, description="包含 4 年前紀錄")

class PatientOpdNoteParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    dt: str = Field(..., description="門診日期")
    dept: str = Field(..., description="科別代碼")
    doc: Optional[str] = Field(None, description="醫師")
    deptnm: Optional[str] = Field(None, description="科別名稱")

class PatientOpNoteParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    dt: str = Field(..., description="手術日期 (YYYY-MM-DD)")

class PatientAdNoteParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    caseno: str = Field(..., description="住院案件號")
    adidate: str = Field(..., description="入院日期")

class PatientDrugContentParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    caseno: str = Field(..., description="案件號")
    dt: str = Field(..., description="日期")
    type: str = Field(..., description="類別 (O/I/E)")
    dept: str = Field(..., description="科別代碼")
    dt1: Optional[str] = Field(None, description="結束日期")

class PatientConsultNoteParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    caseno: str = Field(..., description="會診案件號")
    oseq: str = Field(..., description="會診序號")

class PatientOpdListSearchParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    doc_regex: Optional[str] = Field(None, description="醫師過濾 regex")
    dept_regex: Optional[str] = Field(None, description="科別過濾 regex")
    old_than_four_years: bool = Field(default=True)

class PatientScanedNoteParams(BaseModel):
    tdept: str = Field(default="OPH", description="科別代碼")


# --- Helpers ---

async def _select_patient(session, hisno: str) -> bool:
    """選擇病人 session。"""
    url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm"
    resp = await session.get(url, params={'action': 'findEmr', 'histno': str(hisno)})
    return '電子病歷查詢系統操作發生異常' not in resp.text


# --- Tasks ---

@crawler_task(
    id="patient_search",
    name="Patient Search",
    description="搜尋病人 - 用病歷號/身分證號/姓名查詢",
    params_model=PatientSearchParams
)
async def patient_search(params: PatientSearchParams, client: VghClient) -> TaskResult:
    """搜尋病人。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm?action=findPatient'
    payload = {
        'wd': params.ward, 'histno': params.hisno or '', 'pidno': params.pidno or '',
        'namec': params.name or '', 'drid': '', 'er': '0', 'bilqrta': '0',
        'bilqrtdt': '', 'bildurdt': '0', 'other': '0', 'nametype': ''
    }
    
    resp = await client.session.post(url, data=payload)
    if '電子病歷查詢系統操作發生異常' in resp.text:
        return TaskResult.fail("系統異常")
    
    return TaskResult.ok(parse_table(resp.text, 'patlist'))


@crawler_task(
    id="patient_info",
    name="Patient Info",
    description="取得病人完整基本資料",
    params_model=PatientHisnoParams
)
async def patient_info(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人完整基本資料。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findPba', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    data = {}
    
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if '．' in label:
                key = label.split('．')[1].replace('：', '').replace('　', '').strip()
                if key:
                    data[key] = value if value != '－' else ''
    
    return TaskResult.ok(data)


@crawler_task(
    id="patient_opd_list",
    name="Patient OPD List",
    description="取得病人門診清單",
    params_model=PatientOpdListParams
)
async def patient_opd_list(params: PatientOpdListParams, client: VghClient) -> TaskResult:
    """取得病人門診清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    results = []
    
    resp = await session.get(url, params={'action': 'findOpd', 'histno': str(params.hisno), '_': 0})
    if '無門診' not in resp.text:
        results.extend(parse_table(resp.text, 'opdlist'))
    
    if params.old_than_four_years:
        resp = await session.get(url, params={'action': 'findOpd01', 'histno': str(params.hisno), '_': 0})
        if '無門診' not in resp.text:
            results.extend(parse_table(resp.text, 'opdlist01'))
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_opd_note",
    name="Patient OPD Note",
    description="取得門診 SOAP 病歷",
    params_model=PatientOpdNoteParams
)
async def patient_opd_note(params: PatientOpdNoteParams, client: VghClient) -> TaskResult:
    """取得門診 SOAP 病歷。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    payload = {'action': 'findOpd', 'histno': params.hisno, 'dt': params.dt, 'dept': params.dept,
               'doc': params.doc or '', 'deptnm': params.deptnm or '', 'tm': 1, '_': 0}
    resp = await session.get(url, params=payload)
    
    soup = BeautifulSoup(resp.text, 'lxml')
    data = {'hisno': params.hisno, 'dt': params.dt, 'dept': params.dept,
            'S': '', 'O': '', 'P': '', 'soap': '', 'drugs': '', 'orders': ''}
    
    for sid, key in [('S', 'S'), ('O', 'O'), ('P', 'P'), ('SOAP', 'soap')]:
        el = soup.find(id=sid)
        if el:
            data[key] = el.get_text(strip=True)
    
    for div_id, key in [('drugs', 'drugs'), ('opdord', 'orders')]:
        el = soup.find(id=div_id)
        if el:
            data[key] = el.get_text(strip=True)
    
    return TaskResult.ok(data)


@crawler_task(
    id="patient_op_list",
    name="Patient Op List",
    description="取得病人已完成的手術紀錄清單",
    params_model=PatientHisnoParams
)
async def patient_op_list(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人已完成的手術紀錄清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findOpn', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='opnlist')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    if not rows:
        return TaskResult.ok([])
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        link = row.find('a')
        if link and link.has_attr('href'):
            match = re.search(r'dt=(\d{8})', link['href'])
            if match:
                record['手術日期_iso'] = to_iso_string(match.group(1))
        
        results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_op_schedule",
    name="Patient Op Schedule",
    description="取得病人預定的手術排程清單",
    params_model=PatientHisnoParams
)
async def patient_op_schedule(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人預定的手術排程清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findOpb', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    if not rows:
        return TaskResult.ok([])
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        if '排程日期' in record and record['排程日期']:
            record['排程日期_iso'] = to_iso_string(record['排程日期'])
        
        results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_op_note",
    name="Patient Op Note",
    description="取得手術病歷 (HTML)",
    params_model=PatientOpNoteParams
)
async def patient_op_note(params: PatientOpNoteParams, client: VghClient) -> TaskResult:
    """取得手術病歷 (HTML)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    api_date = to_roc_date_8(params.dt) or params.dt
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findOpn', 'histno': params.hisno, 'dt': api_date, 'tm': 1, '_': 0})
    return TaskResult.ok(resp.text)


@crawler_task(
    id="patient_ad_list",
    name="Patient Ad List",
    description="取得病人住院清單",
    params_model=PatientHisnoParams
)
async def patient_ad_list(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人住院清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findAdm', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='admlist')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    if not rows:
        return TaskResult.ok([])
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        link = row.find('a')
        if link and link.has_attr('href'):
            href = link['href']
            caseno_match = re.search(r'caseno=(\d+)', href)
            adidate_match = re.search(r'adidate=(\d+)', href)
            if caseno_match:
                record['caseno'] = caseno_match.group(1)
            if adidate_match:
                record['adidate'] = adidate_match.group(1)
        
        if '住院日期' in record and len(record['住院日期']) == 8:
            d = record['住院日期']
            record['住院日期_iso'] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        
        results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_ad_note",
    name="Patient Ad Note",
    description="取得住院病歷摘要 (HTML)",
    params_model=PatientAdNoteParams
)
async def patient_ad_note(params: PatientAdNoteParams, client: VghClient) -> TaskResult:
    """取得住院病歷摘要 (HTML)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    api_date = to_yyyymmdd(params.adidate) or params.adidate
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findAdm', 'histno': params.hisno, 'caseno': params.caseno, 'adidate': api_date, '_': 0})
    return TaskResult.ok(resp.text)


@crawler_task(
    id="patient_drug_list",
    name="Patient Drug List",
    description="取得病人用藥清單",
    params_model=PatientHisnoParams
)
async def patient_drug_list(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人用藥清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findUd', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='caselist')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    if not rows:
        return TaskResult.ok([])
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        link = row.find('a')
        if link and link.has_attr('href'):
            href = link['href']
            for name, pattern in [('caseno', r'caseno=([A-Z0-9]+)'), ('dt', r'dt=(\d+)'),
                                   ('type', r'type=([A-Z])'), ('dept', r'dept=([A-Z0-9]+)'), ('dt1', r'dt1=(\d+)')]:
                m = re.search(pattern, href)
                if m:
                    record[name] = m.group(1)
            if 'dt1' not in record:
                record['dt1'] = ''
        
        if '日期' in record and len(record['日期']) == 8:
            d = record['日期']
            record['日期_iso'] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        
        results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_drug_content",
    name="Patient Drug Content",
    description="取得用藥詳細內容",
    params_model=PatientDrugContentParams
)
async def patient_drug_content(params: PatientDrugContentParams, client: VghClient) -> TaskResult:
    """取得用藥詳細內容。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    api_dt = to_yyyymmdd(params.dt) or params.dt
    api_dt1 = to_yyyymmdd(params.dt1) if params.dt1 else ''
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={
        'action': 'findUd', 'histno': str(params.hisno), 'caseno': params.caseno,
        'dt': api_dt, 'type': params.type, 'dept': params.dept, 'dt1': api_dt1, '_': 0
    })
    return TaskResult.ok(parse_table(resp.text, 'udorder'))


@crawler_task(
    id="patient_consult_list",
    name="Patient Consult List",
    description="取得病人會診清單",
    params_model=PatientHisnoParams
)
async def patient_consult_list(params: PatientHisnoParams, client: VghClient) -> TaskResult:
    """取得病人會診清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findCps', 'histno': str(params.hisno), '_': 0})
    
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', id='cpslist')
    if not table:
        return TaskResult.ok([])
    
    rows = table.find_all('tr')
    if not rows:
        return TaskResult.ok([])
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        link = row.find('a')
        if link and link.has_attr('href'):
            href = link['href']
            caseno_match = re.search(r'caseno=([A-Z0-9]+)', href)
            oseq_match = re.search(r'oseq=(\d+)', href)
            if caseno_match:
                record['caseno'] = caseno_match.group(1)
            if oseq_match:
                record['oseq'] = oseq_match.group(1)
        
        if '會診日期' in record and len(record['會診日期']) == 8:
            d = record['會診日期']
            record['會診日期_iso'] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        
        results.append(record)
    
    return TaskResult.ok(results)


@crawler_task(
    id="patient_consult_note",
    name="Patient Consult Note",
    description="取得會診內容 (HTML)",
    params_model=PatientConsultNoteParams
)
async def patient_consult_note(params: PatientConsultNoteParams, client: VghClient) -> TaskResult:
    """取得會診內容 (HTML)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    session = client.session
    if not await _select_patient(session, params.hisno):
        return TaskResult.fail("病人選擇失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await session.get(url, params={'action': 'findCps', 'histno': str(params.hisno), 'caseno': params.caseno, 'oseq': params.oseq, '_': 0})
    return TaskResult.ok(resp.text)


@crawler_task(
    id="patient_scaned_note",
    name="Patient Scaned Note",
    description="取得科別掃描病歷清單",
    params_model=PatientScanedNoteParams
)
async def patient_scaned_note(params: PatientScanedNoteParams, client: VghClient) -> TaskResult:
    """取得科別掃描病歷清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    url = 'https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm'
    resp = await client.session.get(url, params={'action': 'findScan', 'tdept': params.tdept, '_': 0})
    return TaskResult.ok(parse_table(resp.text, None))


@crawler_task(
    id="patient_opd_list_search",
    name="Patient OPD List Search",
    description="搜尋門診清單 (支援 regex 過濾)",
    params_model=PatientOpdListSearchParams
)
async def patient_opd_list_search(params: PatientOpdListSearchParams, client: VghClient) -> TaskResult:
    """搜尋門診清單 (支援 regex 過濾)。"""
    result = await patient_opd_list(PatientOpdListParams(hisno=params.hisno, old_than_four_years=params.old_than_four_years), client)
    if not result.success or not result.data:
        return result
    
    doc_pat = re.compile(params.doc_regex, re.IGNORECASE) if params.doc_regex else None
    dept_pat = re.compile(params.dept_regex, re.IGNORECASE) if params.dept_regex else None
    
    filtered = [
        item for item in result.data
        if ((not doc_pat) or doc_pat.search(item.get('門診醫師', '')))
        and ((not dept_pat) or dept_pat.search(item.get('科別', '')))
    ]
    
    return TaskResult.ok(filtered)


# --- Legacy Compatibility ---
PatientSearchTask = patient_search
PatientInfoTask = patient_info
PatientOpdListTask = patient_opd_list
PatientOpdNoteTask = patient_opd_note
PatientOpListTask = patient_op_list
PatientOpNoteTask = patient_op_note
PatientAdListTask = patient_ad_list
PatientAdNoteTask = patient_ad_note
PatientDrugListTask = patient_drug_list
PatientDrugContentTask = patient_drug_content
PatientConsultListTask = patient_consult_list
PatientConsultNoteTask = patient_consult_note
PatientScanedNoteTask = patient_scaned_note
PatientOpdListSearchTask = patient_opd_list_search
