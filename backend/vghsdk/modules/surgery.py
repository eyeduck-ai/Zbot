"""Surgery 模組 - 手術排程查詢 (Function-based)。

以 MCP 版本 (已驗證) 為主要邏輯來源。
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from vghsdk.core import VghClient, TaskResult, crawler_task
from vghsdk.utils import to_roc_date

logger = logging.getLogger(__name__)


# --- Params ---

class SurgeryScheduleParams(BaseModel):
    query: str = Field(..., description="醫師燈號 (如 4050) 或科別代碼 (如 OPH)")
    date: Optional[str] = Field(None, description="日期 YYYY-MM-DD，空白=今天")

class SurgeryDetailParams(BaseModel):
    link_url: str = Field(..., description="從排程表取得的 link URL")


# --- Helpers ---

TOOLTIP_REGEX = re.compile(
    r'術前診斷:\s*(?P<pre_op_dx>.*?)\s*'
    r'手術名稱:\s*(?P<op_name>.*?)\s*'
    r'手術室資訊:\s*(?P<or_info>.*?)\s*'
    r'麻醉:\s*(?P<anesthesia>.*?)\s*$'
)


def _parse_schedule_table(html: str) -> List[Dict[str, str]]:
    """解析手術排程表格 (含 tooltip)。"""
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    if not table:
        return []
    
    rows = table.find_all('tr')
    if not rows:
        return []
    
    headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    results = []
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols:
            continue
        
        record = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols) if i < len(headers)}
        
        btn = row.find('button', attrs={'data-target': '#myModal'})
        if btn and btn.has_attr('data-url'):
            record['link'] = btn['data-url']
        
        tooltip_a = row.find('a', attrs={'data-toggle': 'tooltip'})
        if tooltip_a and tooltip_a.has_attr('title'):
            tooltip = tooltip_a['title']
            record['tooltip'] = tooltip
            match = TOOLTIP_REGEX.search(tooltip)
            if match:
                record.update({
                    '術前診斷': match.group('pre_op_dx'),
                    '手術名稱': match.group('op_name'),
                    '手術室資訊': match.group('or_info'),
                    '麻醉': match.group('anesthesia')
                })
        
        results.append(record)
    
    return results


def _get_roc_today() -> str:
    """取得今天的民國日期。"""
    now = datetime.now()
    return f"{now.year - 1911}{now.strftime('%m%d')}"


# --- Tasks ---

@crawler_task(
    id="surgery_doc_schedule",
    name="Surgery Doc Schedule",
    description="查詢醫師的手術排程",
    params_model=SurgeryScheduleParams
)
async def surgery_doc_schedule(params: SurgeryScheduleParams, client: VghClient) -> TaskResult:
    """查詢醫師的手術排程。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    api_date = to_roc_date(params.date) if params.date else _get_roc_today()
    
    url = 'https://web9.vghtpe.gov.tw/ops/opb.cfm'
    payload = {'action': 'findOpblist', 'type': 'opbmain', 'qry': params.query, 'bgndt': api_date, '_': 0}
    resp = await client.session.get(url, params=payload)
    return TaskResult.ok(_parse_schedule_table(resp.text))


@crawler_task(
    id="surgery_dept_schedule",
    name="Surgery Dept Schedule",
    description="查詢科別的手術排程",
    params_model=SurgeryScheduleParams
)
async def surgery_dept_schedule(params: SurgeryScheduleParams, client: VghClient) -> TaskResult:
    """查詢科別的手術排程。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    api_date = to_roc_date(params.date) if params.date else _get_roc_today()
    
    url = 'https://web9.vghtpe.gov.tw/ops/opb.cfm'
    payload = {'action': 'findOpblist', 'type': 'opbsect', 'qry': params.query, 'bgndt': api_date, '_': 0}
    resp = await client.session.get(url, params=payload)
    return TaskResult.ok(_parse_schedule_table(resp.text))


@crawler_task(
    id="surgery_detail",
    name="Surgery Detail",
    description="取得手術詳細資訊",
    params_model=SurgeryDetailParams
)
async def surgery_detail(params: SurgeryDetailParams, client: VghClient) -> TaskResult:
    """取得手術詳細資訊。需先用 surgery_*_schedule 取得 link_url。"""
    if not await client.ensure_eip():
        return TaskResult.fail("EIP 登入失敗")
    
    full_url = 'https://web9.vghtpe.gov.tw' + params.link_url
    resp = await client.session.get(full_url)
    
    soup = BeautifulSoup(resp.text, 'lxml')
    tbody = soup.find('tbody')
    if not tbody:
        return TaskResult(success=True, data={}, message="無詳細資料", count=0)
    
    data = {}
    for tr in tbody.find_all('tr'):
        if '麻醉方式代碼說明' in tr.get_text():
            continue
        cols = tr.find_all('td')
        for i in range(0, len(cols), 2):
            if i + 1 < len(cols):
                key = cols[i].get_text(strip=True).replace(':', '')
                data[key] = cols[i + 1].get_text(strip=True)
    
    return TaskResult.ok(data)


# --- Legacy Compatibility ---
# 保留舊名稱供向後相容
SurgeryDocScheduleTask = surgery_doc_schedule
SurgeryDeptScheduleTask = surgery_dept_schedule
SurgeryDetailTask = surgery_detail
