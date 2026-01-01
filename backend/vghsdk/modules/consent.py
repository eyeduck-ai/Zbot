"""Consent 模組 - 4 個同意書相關任務 (Function-based)。

以 MCP 版本 (已驗證) 為主要邏輯來源。
"""
import logging
from datetime import datetime, timedelta
from urllib.parse import unquote
from typing import Optional
from pydantic import BaseModel, Field

from vghsdk.core import VghClient, TaskResult, crawler_task

logger = logging.getLogger(__name__)


# --- Params Models ---

class ConsentParams(BaseModel):
    hisno: str = Field(..., description="病歷號")

class ConsentListParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    start_date: Optional[str] = Field(None, description="開始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="結束日期 YYYY-MM-DD")

class ConsentSearchParams(BaseModel):
    hisno: str = Field(..., description="病歷號")
    target_keyword: str = Field(default="手術", description="搜尋關鍵字")
    return_id: bool = Field(default=False, description="只回傳 ID")
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ConsentPdfParams(BaseModel):
    jid: str = Field(..., description="Job ID")


# --- Helpers ---

async def _select_patient(session, hisno: str):
    """選擇病人 (同意書系統)。"""
    await session.post(
        'https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetSearchPatient.jsp',
        data={'histNum': hisno}
    )


# --- Tasks ---

@crawler_task(
    id="consent_opschedule",
    name="Consent Surgery Schedule",
    description="查詢病人手術排程 (同意書系統)",
    params_model=ConsentParams
)
async def consent_opschedule(params: ConsentParams, client: VghClient) -> TaskResult:
    """查詢病人手術排程 (同意書系統)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    await _select_patient(client.session, params.hisno)
    resp = await client.session.post(
        'https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetOPBListJSON.jsp',
        data={'pNO': params.hisno}
    )
    return TaskResult.ok(resp.json().get('OPSLIST', []))


@crawler_task(
    id="consent_list",
    name="Consent List",
    description="取得病人同意書清單",
    params_model=ConsentListParams
)
async def consent_list(params: ConsentListParams, client: VghClient) -> TaskResult:
    """取得病人同意書清單。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    s_date = params.start_date or (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
    e_date = params.end_date or datetime.now().strftime('%Y-%m-%d')
    
    await _select_patient(client.session, params.hisno)
    resp = await client.session.post(
        'https://web9.vghtpe.gov.tw/DICF/form.do',
        data={'action': 'svsQueryJob', 'sD': s_date, 'eD': e_date, 'pNo': params.hisno}
    )
    data = resp.json()
    jobs = data.get('jobs', [])
    return TaskResult(success=True, data=data, count=len(jobs))


@crawler_task(
    id="consent_search",
    name="Search Consent",
    description="搜尋同意書 (預設眼科+已完成)",
    params_model=ConsentSearchParams
)
async def consent_search(params: ConsentSearchParams, client: VghClient) -> TaskResult:
    """搜尋同意書 (預設眼科+已完成)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    s_date = params.start_date or (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
    e_date = params.end_date or datetime.now().strftime('%Y-%m-%d')
    
    await _select_patient(client.session, params.hisno)
    resp = await client.session.post(
        'https://web9.vghtpe.gov.tw/DICF/form.do',
        data={'action': 'svsQueryJob', 'sD': s_date, 'eD': e_date, 'pNo': params.hisno}
    )
    
    results = []
    for job in resp.json().get('jobs', []):
        info = job.get('jobinfo', {})
        name = unquote(info.get('TEMP_NAME', ''))
        
        if (info.get('JOB_ATTR1') == 'OPH' and 
            params.target_keyword in name and 
            info.get('JOB_STATUS') == 'COMPLETE'):
            results.append(info.get('JOB_DOC_ID') if params.return_id else job)
    
    return TaskResult.ok(results)


@crawler_task(
    id="consent_pdf_bytes",
    name="Get Consent PDF",
    description="下載同意書 PDF (Base64)",
    params_model=ConsentPdfParams
)
async def consent_pdf_bytes(params: ConsentPdfParams, client: VghClient) -> TaskResult:
    """下載同意書 PDF (Base64)。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    resp = await client.session.get(
        'https://web9.vghtpe.gov.tw/DICF/form.do',
        params={'action': 'getPDFFile', 'jId': params.jid, 'isD': 'Y', 'isP': 'Y'}
    )
    pdf_b64 = unquote(resp.json().get('pdfFile', ''))
    return TaskResult.ok({'pdf_base64': pdf_b64})


# --- Legacy Compatibility (可移除) ---
# 保留舊 class 名稱以供向後相容，指向新函式

ConsentOpScheduleTask = consent_opschedule
ConsentListTask = consent_list
ConsentSearchTask = consent_search
ConsentPdfBytesTask = consent_pdf_bytes
