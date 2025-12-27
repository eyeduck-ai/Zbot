
import logging
import asyncio
import pandas as pd
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from vghsdk.core import CrawlerTask, VghClient
from vghsdk.utils import to_western_date, to_roc_date

logger = logging.getLogger("ivi_tasks")

# --- Models ---
class IviFetchParams(BaseModel):
    """IVI 排程抓取參數
    
    支援兩種模式:
    1. 單一日期: 只指定 date
    2. 日期區段: 指定 start_date 和 end_date
    """
    date: Optional[str] = Field(None, description="單一日期 (ISO YYYY-MM-DD 或 ROC YYY/MM/DD)")
    start_date: Optional[str] = Field(None, description="起始日期 (ISO YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="結束日期 (ISO YYYY-MM-DD)")
    username: Optional[str] = None
    password: Optional[str] = None

class IviFetchResult(BaseModel):
    date: str
    count: int
    data: List[Dict[str, Any]]
    message: Optional[str] = None  # 用於傳回驗證訊息或警告

# --- Logic Helpers (Moved from services/cks.py) ---
def _get_diagnosis(s: str) -> str:
    check_list = ["AMD","PCV","RAP","mCNV","CRVO", "BRVO", "DME", "VH", "PDR", "NVG", "CME"]
    found = [i for i in check_list if s.find(i) > -1]
    return "+".join(found)

def _get_side(s: str) -> str:
    if "OD" in s: return "OD"
    if "OS" in s: return "OS"
    if "OU" in s: return "OU"
    return ""

def _get_drug(s: str) -> str:
    drugs = []
    if "IVIE" in s: drugs.append("Eylea(8mg)")
    if "IVI-F" in s: drugs.append("Faricimab")
    if "IVI-B" in s: drugs.append("Beovu")
    if "IVI-A" in s: drugs.append("Avastin")
    if "IVI-L" in s: drugs.append("Lucentis")
    if "IVI-E" in s: drugs.append("Eylea")
    if "IVI-Ozu" in s: drugs.append("Ozurdex")
    if "STK" in s: drugs.append("STK")
    if "TPA" in s: drugs.append("TPA")
    return "+".join(drugs)

def _get_charge(s: str) -> str:
    if "NHI" in s: return "NHI"
    if "drug f" in s: return "Drug-Free"
    if "all f" in s: return "All-Free"
    if "SP-A" in s: return "SP-A"
    if "SP-1" in s: return "SP-1"
    if "SP-2" in s: return "SP-2"
    if "IVI-E" in s and "IVI-L" in s: return "L(E)"
    return ""


# --- Tasks ---

class IviFetchTask(CrawlerTask):
    id: str = "ivi_fetch_schedule"
    name: str = "IVI Schedule Fetch (CKS)"
    description: str = "Download IVI Schedule from CKS."
    params_model: Optional[Type[BaseModel]] = IviFetchParams

    async def run(self, params, client: VghClient, progress_callback=None) -> IviFetchResult:
        """抓取 CKS IVI 排程
        
        支援單一日期或日期區段查詢。
        注意: 不允許查詢未來日期 (無法填寫尚未發生的手術紀錄)
        """
        from datetime import date as date_type
        
        # 支援 dict 或 IviFetchParams 輸入
        if isinstance(params, dict):
            p = IviFetchParams(**params)
        else:
            p = params
        
        # 決定查詢的日期範圍
        if p.start_date and p.end_date:
            # 模式 2: 日期區段
            start_dt = to_western_date(p.start_date)
            end_dt = to_western_date(p.end_date)
            display_date = f"{p.start_date} ~ {p.end_date}"
        elif p.date:
            # 模式 1: 單一日期
            start_dt = to_western_date(p.date)
            end_dt = start_dt
            display_date = p.date
        else:
            logger.error("必須指定 date 或 (start_date, end_date)")
            return IviFetchResult(date="", count=0, data=[])
        
        if not start_dt or not end_dt:
            logger.error(f"日期格式錯誤: {display_date}")
            return IviFetchResult(date=display_date, count=0, data=[])
        
        # 未來日期驗證: 不能抓取未來的排程
        today = date_type.today()
        start_date_only = start_dt if isinstance(start_dt, date_type) else start_dt.date()
        end_date_only = end_dt if isinstance(end_dt, date_type) else end_dt.date()
        
        if end_date_only > today:
            logger.warning(f"不允許查詢未來日期: {end_date_only} > {today}")
            # 如果結束日期超過今天，限制到今天
            end_date_only = today
            if start_date_only > today:
                logger.warning(f"起始日期也是未來日期，無法查詢")
                return IviFetchResult(date=display_date, count=0, data=[], 
                                      message="不能查詢未來日期 (無法填寫尚未發生的手術)")
        
        # 1. Ensure CKS Login
        if not await client.ensure_cks():
             raise Exception("Failed to login to CKS via VghClient")
        
        # 2. Fetch Data
        READ_URL = "https://cks.vghtpe.gov.tw/Exm/ExmQ010/ExmQ010_Read"
        
        date_start_str = start_date_only.strftime("%Y%m%d")
        date_end_str = end_date_only.strftime("%Y%m%d")
            
        payload = {
            'sort': '',
            'group': '',
            'filter': '',
            'queryBeginDate': date_start_str,
            'queryEndDate': date_end_str,
            'scheduleID': 'CTOPHIVI',
            'cancelYN': 'N',
            'aheadScheduleYN': 'N',
            'caseFrom': 'O',
            'exmRoomID': '',
            'schShiftNo': '',
            'searchNRCode': '',
            'SearchCriticalYN': 'N',
            'SearchISOLYN': 'N'
        }
        
        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }

        # Use client.session directly
        res = await client.session.post(READ_URL, data=payload, headers=headers)
        
        if res.status_code != 200:
            logger.error(f"Fetch failed: {res.status_code}")
            return IviFetchResult(date=p.date, count=0, data=[])

        try:
            data_json = res.json()
        except Exception:
            logger.error(f"Failed to parse JSON")
            return IviFetchResult(date=p.date, count=0, data=[])

        if 'Data' not in data_json:
            return IviFetchResult(date=p.date, count=0, data=[])
            
        df = pd.DataFrame(data_json['Data'])
        if df.empty:
            return IviFetchResult(date=display_date, count=0, data=[], 
                                  message=f"查詢日期 {display_date} 無 IVI 排程資料")

        # Parse Logic
        results = []
        for _, row in df.iterrows():
            content = row.get('CombineSchExmItemName', '')
            
            # 從 CreateID 解析 doc_code (如 "DOC4106F" → "4106")
            create_id = str(row.get('CreateID', ''))
            doc_code = ""
            import re
            match = re.search(r'\d{4}', create_id)
            if match:
                doc_code = match.group()
            
            # 從 ScheduleTime 解析時間 (如 "13:30" → "1330")
            schedule_time = str(row.get('ScheduleTime', '')).replace(':', '')
            if len(schedule_time) < 4:
                schedule_time = schedule_time.zfill(4)
            
            # 計算結束時間 (+2 分鐘)
            end_time = schedule_time
            try:
                hour = int(schedule_time[:2])
                minute = int(schedule_time[2:]) + 2
                if minute >= 60:
                    hour += 1
                    minute -= 60
                end_time = f"{hour:02d}{minute:02d}"
            except:
                pass
            
            item = {
                "hisno": row.get('PatNo'),
                "name": row.get('PatNMC'),
                "schedule_name": row.get('ScheduleName'),
                "schedule_date": row.get('ScheduleDate'),
                # 主刀醫師
                "doc_code": doc_code,
                "vs_name": row.get('CreateName', ''),
                # 時間
                "op_start": schedule_time,
                "op_end": end_time,
                # 從 CombineSchExmItemName 解析
                "diagnosis": _get_diagnosis(content),
                "side": _get_side(content),
                "drug": _get_drug(content),
                "charge_type": _get_charge(content),
                "raw_content": content,
            }
            results.append(item)
            
        return IviFetchResult(date=display_date, count=len(results), data=results)
