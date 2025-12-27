
from typing import Any, Optional, List, Dict, Union
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from vghsdk.core import CrawlerTask, VghClient
from datetime import datetime, timedelta
from urllib.parse import unquote
import logging
import base64
import asyncio

logger = logging.getLogger(__name__)

# --- params ---

class ConsentParams(BaseModel):
    hisno: str = Field(..., description="Hospital Number")

class ConsentListParams(BaseModel):
    hisno: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ConsentSearchParams(BaseModel):
    hisno: str
    target_keyword: str = Field(default="手術")
    return_id: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ConsentPdfParams(BaseModel):
    jid: str = Field(..., description="Job ID of the consent form")

# --- Tasks ---

class ConsentOpScheduleTask(CrawlerTask):
    id = "consent_opschedule"
    name = "Consent Surgery Schedule"
    description = "Get recent surgery schedule from Consent System. (Ported from vghbot_crawler.consent_opschedule)\n" \
                  "Original Comment: 透過同意書系統查詢最近的手術排程，回傳多次手術排程組成的list"
    params_model = ConsentParams

    async def run(self, params: ConsentParams, client: VghClient) -> List[Dict[str, Any]]:
        if not await client.ensure_eip(): return []
        session = client.session
        # 1. Select Patient
        await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetSearchPatient.jsp',
            data={'histNum': params.hisno}
        )
        
        # 2. Get OP List
        resp = await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetOPBListJSON.jsp',
            data={'pNO': params.hisno}
        )
        data = resp.json()
        return data.get('OPSLIST', [])

class ConsentListTask(CrawlerTask):
    id = "consent_list"
    name = "Consent List"
    description = "Get consent form history. (Ported from vghbot_crawler.consent_list)\n" \
                  "Original Comment: start_date: 搜尋時間開始(格式2024-08-31)"
    params_model = ConsentListParams

    async def run(self, params: ConsentListParams, client: VghClient) -> Dict[str, Any]:
        if not await client.ensure_eip(): return {}
        session = client.session
        # Dates
        s_date = params.start_date
        e_date = params.end_date
        if not s_date:
            s_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        if not e_date:
            e_date = datetime.now().strftime('%Y-%m-%d')
            
        # 1. Select Patient
        await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetSearchPatient.jsp',
            data={'histNum': params.hisno}
        )
        
        # 2. Get List
        resp = await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/form.do',
            data={
                'action': 'svsQueryJob',
                'sD': s_date,
                'eD': e_date,
                'pNo': params.hisno
            }
        )
        return resp.json()

class ConsentSearchTask(CrawlerTask):
    id = "consent_search"
    name = "Search Consent"
    description = "Search consent forms with filtering. (Ported from vghbot_crawler.consent_search)\n" \
                  "Original Comment: target_keyword: 搜尋包含此字串的同意書; 預設設定匹配條件 (target_ATTR1 = \"OPH\") AND (target_status = \"COMPLETE\")"
    params_model = ConsentSearchParams

    async def run(self, params: ConsentSearchParams, client: VghClient) -> List[Union[Dict[str, Any], str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        # Reuse logic from ConsentListTask? 
        # Ideally we call the logic directly or instantiate the task.
        # But CrawlerTask doesn't easily allow calling other tasks unless we separate logic.
        # Duplicating the fetch logic for now to keep tasks independent.
        
        # Dates
        s_date = params.start_date
        e_date = params.end_date
        if not s_date:
            s_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        if not e_date:
            e_date = datetime.now().strftime('%Y-%m-%d')

        # 1. Select Patient
        await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/Forms/ajax/ajaxGetSearchPatient.jsp',
            data={'histNum': params.hisno}
        )
        
        # 2. Fetch
        resp = await session.post(
            url='https://web9.vghtpe.gov.tw/DICF/form.do',
            data={
                'action': 'svsQueryJob',
                'sD': s_date,
                'eD': e_date,
                'pNo': params.hisno
            }
        )
        json_data = resp.json()
        
        # 3. Filter
        results = []
        target_ATTR1 = "OPH"
        target_status = "COMPLETE"
        
        jobs = json_data.get("jobs", [])
        for job in jobs:
            job_info = job.get("jobinfo", {})
            temp_name = job_info.get("TEMP_NAME", "")
            decoded_name = unquote(temp_name)
            
            if (job_info.get("JOB_ATTR1") == target_ATTR1 and
                params.target_keyword in decoded_name and
                job_info.get("JOB_STATUS") == target_status):
                
                if params.return_id:
                    results.append(job_info.get('JOB_DOC_ID'))
                else:
                    results.append(job)
                    
        return results

class ConsentPdfBytesTask(CrawlerTask):
    id = "consent_pdf_bytes"
    name = "Get Consent PDF"
    description = "Download consent PDF (returns Base64 string). (Ported from vghbot_crawler.consent_pdf_bytes)\n" \
                  "Original Comment: 回傳bytes型態的consent pdf文件 (New: Returned as Base64 in JSON)"
    params_model = ConsentPdfParams

    async def run(self, params: ConsentPdfParams, client: VghClient) -> Dict[str, str]:
        if not await client.ensure_eip(): return {}
        session = client.session
        # Legacy code returns bytes via BytesIO. 
        # Since this API is JSON-based, we should return the Base64 string directly
        # or info about it. User asked for "pdf_bytes".
        # We will return {"pdf_base64": "..."}
        
        resp = await session.get(
            url='https://web9.vghtpe.gov.tw/DICF/form.do',
            params={
                "action": "getPDFFile",
                "jId": params.jid,
                "isD": "Y",
                "isP": "Y"
            }
        )
        data = resp.json()
        pdf_base64_encoded = data.get('pdfFile', '')
        # It seems the server returns URL-encoded Base64?
        # Legacy: unquote(response.json()['pdfFile']) -> base64.b64decode(...)
        
        pdf_base64 = unquote(pdf_base64_encoded)
        
        # The Task result must be JSON serializable. 
        # We can just return the clean base64 string.
        # Front end can decode it to blob.
        
        return {"pdf_base64": pdf_base64}

# Register

