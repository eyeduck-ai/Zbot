"""IVI 模組 - 眼內注射排程查詢 (Function-based)。

以 MCP 版本 (已驗證) 為主要邏輯來源。
"""
import logging
import re
from datetime import date as date_type
from typing import Optional

import pandas as pd
from pydantic import BaseModel, Field

from vghsdk.core import VghClient, TaskResult, crawler_task
from vghsdk.utils import to_western_date

logger = logging.getLogger(__name__)


# --- Params ---

class IviFetchParams(BaseModel):
    date: Optional[str] = Field(None, description="單一日期 (YYYY-MM-DD)")
    start_date: Optional[str] = Field(None, description="開始日期")
    end_date: Optional[str] = Field(None, description="結束日期")


# --- Parsing Helpers ---

DIAGNOSIS_KEYWORDS = ["AMD", "PCV", "RAP", "mCNV", "CRVO", "BRVO", "DME", "VH", "PDR", "NVG", "CME"]
DRUG_MAP = [
    ("IVIE", "Eylea(8mg)"), ("IVI-F", "Faricimab"), ("IVI-B", "Beovu"),
    ("IVI-A", "Avastin"), ("IVI-L", "Lucentis"), ("IVI-E", "Eylea"),
    ("IVI-Ozu", "Ozurdex"), ("STK", "STK"), ("TPA", "TPA")
]
CHARGE_MAP = [
    ("NHI", "NHI"), ("drug f", "Drug-Free"), ("all f", "All-Free"),
    ("SP-A", "SP-A"), ("SP-1", "SP-1"), ("SP-2", "SP-2")
]


def _parse_content(content: str) -> dict:
    """解析 IVI 排程內容。"""
    diagnosis = "+".join(k for k in DIAGNOSIS_KEYWORDS if k in content)
    side = "OD" if "OD" in content else "OS" if "OS" in content else "OU" if "OU" in content else ""
    drugs = [d for k, d in DRUG_MAP if k in content]
    drug = "+".join(drugs)
    charge = next((v for k, v in CHARGE_MAP if k in content), "")
    if not charge and "IVI-E" in content and "IVI-L" in content:
        charge = "L(E)"
    return {"diagnosis": diagnosis, "side": side, "drug": drug, "charge_type": charge}


# --- Task ---

@crawler_task(
    id="ivi_fetch",
    name="IVI Schedule Fetch",
    description="從 CKS 下載 IVI 排程",
    params_model=IviFetchParams
)
async def ivi_fetch(params: IviFetchParams, client: VghClient) -> TaskResult:
    """從 CKS 下載 IVI 排程。不允許查詢未來日期。"""
    
    # Parse dates
    if params.start_date and params.end_date:
        start_dt = to_western_date(params.start_date)
        end_dt = to_western_date(params.end_date)
        display = f"{params.start_date} ~ {params.end_date}"
    elif params.date:
        start_dt = end_dt = to_western_date(params.date)
        display = params.date
    else:
        return TaskResult.fail("必須指定 date 或 (start_date, end_date)")
    
    if not start_dt or not end_dt:
        return TaskResult.fail(f"日期格式錯誤: {display}")
    
    today = date_type.today()
    start_d = start_dt if isinstance(start_dt, date_type) else start_dt.date()
    end_d = end_dt if isinstance(end_dt, date_type) else end_dt.date()
    
    if end_d > today:
        end_d = today
    if start_d > today:
        return TaskResult.fail("不能查詢未來日期")
    
    if not await client.ensure_cks():
        return TaskResult.fail("CKS 登入失敗")
    
    # Fetch data
    url = "https://cks.vghtpe.gov.tw/Exm/ExmQ010/ExmQ010_Read"
    payload = {
        'sort': '', 'group': '', 'filter': '',
        'queryBeginDate': start_d.strftime("%Y%m%d"),
        'queryEndDate': end_d.strftime("%Y%m%d"),
        'scheduleID': 'CTOPHIVI', 'cancelYN': 'N', 'aheadScheduleYN': 'N',
        'caseFrom': 'O', 'exmRoomID': '', 'schShiftNo': '', 'searchNRCode': '',
        'SearchCriticalYN': 'N', 'SearchISOLYN': 'N'
    }
    headers = {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest"
    }
    
    res = await client.session.post(url, data=payload, headers=headers)
    
    if res.status_code != 200:
        return TaskResult.fail(f"請求失敗: {res.status_code}")
    
    try:
        data_json = res.json()
    except Exception:
        return TaskResult.fail("JSON 解析失敗")
    
    if 'Data' not in data_json or not data_json['Data']:
        return TaskResult(success=True, data=[], message=f"查詢日期 {display} 無 IVI 排程", count=0)
    
    # Parse results
    df = pd.DataFrame(data_json['Data'])
    results = []
    
    for _, row in df.iterrows():
        content = row.get('CombineSchExmItemName', '')
        parsed = _parse_content(content)
        
        # Extract vs_code from CreateID
        create_id = str(row.get('CreateID', ''))
        match = re.search(r'\d{4}', create_id)
        vs_code = match.group() if match else ""
        
        # Time handling
        sched_time = str(row.get('ScheduleTime', '')).replace(':', '').zfill(4)
        try:
            h, m = int(sched_time[:2]), int(sched_time[2:]) + 2
            if m >= 60:
                h, m = h + 1, m - 60
            end_time = f"{h:02d}{m:02d}"
        except Exception:
            end_time = sched_time
        
        results.append({
            "hisno": row.get('PatNo'),
            "name": row.get('PatNMC'),
            "schedule_name": row.get('ScheduleName'),
            "schedule_date": row.get('ScheduleDate'),
            "doc_code": vs_code,  # 醫師登號
            "vs_name": row.get('CreateName', ''),
            "op_start": sched_time,
            "op_end": end_time,
            **parsed,
            "raw_content": content,
        })
    
    return TaskResult.ok(results)


# --- Legacy Compatibility ---
IviFetchTask = ivi_fetch
