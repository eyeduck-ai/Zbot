
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from vghsdk.core import CrawlerTask, VghClient
from datetime import datetime
import logging
import re
import asyncio
import json
from urllib.parse import unquote

logger = logging.getLogger(__name__)

# --- Surgery Search Models ---

class SurgerySearchParams(BaseModel):
    """
    術式搜尋參數。
    
    Attributes:
        keyword: 搜尋關鍵字
            - 依術式名稱搜尋: e.g. "PHACO", "TRABE", "PPV", "IVI"
            - 依診斷搜尋: e.g. "CATA", "RD", "GLAUCOMA"
        dept_code: 科別代碼，預設 "OPH" (眼科)
            - 其他科別: "ENT", "GI", "CV", etc.
    """
    keyword: str = Field(..., description="搜尋關鍵字 (e.g. 'PHACO', 'CATA')")
    dept_code: str = Field(default="OPH", description="科別代碼 (預設 OPH)")


class SurgerySearchResult(BaseModel):
    """
    術式搜尋結果結構。
    
    API 原始 JSON 範例:
    ```json
    {
        "surkeycode": "OPH+++++13421",
        "surkeycode2": "",
        "surname": "PHACO-IOL OD",
        "surnamec": "右眼白內障摘除合併人工水晶體置入手術",
        "surnamew": "PHACO-IOL",
        "surmemo": "CATA OD",
        "surdurtime": 36,
        "surpriority": 700000
    }
    ```
    
    Attributes:
        surkeycode: 術式代碼 (前3碼為科別，後5碼為流水號)
        surkeycode2: 備用術式代碼 (通常為空)
        surname: 術式英文名稱 (用於手術記錄)
        surnamec: 術式中文名稱 (顯示用)
        surnamew: 術式簡稱/搜尋關鍵字
        surmemo: 備註 (常見診斷縮寫 + 部位)
        surdurtime: 預估手術時間 (分鐘)
        surpriority: 優先序 (數值越大越優先顯示)
    """
    surkeycode: str = Field(..., description="術式代碼 (e.g. 'OPH+++++13421')")
    surkeycode2: str = Field(default="", description="備用術式代碼")
    surname: str = Field(..., description="英文名稱 (e.g. 'PHACO-IOL OD')")
    surnamec: str = Field(..., description="中文名稱 (e.g. '右眼白內障摘除...')")
    surnamew: str = Field(default="", description="簡稱/關鍵字")
    surmemo: str = Field(default="", description="備註 (e.g. 'CATA OD')")
    surdurtime: int = Field(default=0, description="預估時間(分鐘)")
    surpriority: int = Field(default=0, description="優先序")


def _parse_surgery_search_response(response_json: dict) -> List[SurgerySearchResult]:
    """
    解析 rkeprd API 回傳的資料。
    API 回傳格式: {"isSuccess": true, "datas": "[URL-encoded JSON array]", ...}
    """
    if not response_json.get("isSuccess"):
        logger.warning(f"Surgery search API returned error: {response_json.get('errmsg')}")
        return []
    
    datas_str = response_json.get("datas", "")
    if not datas_str:
        return []
    
    try:
        # URL decode + JSON parse
        decoded = unquote(datas_str)
        items = json.loads(decoded)
        
        results = []
        for item in items:
            results.append(SurgerySearchResult(
                surkeycode=item.get("surkeycode", "").strip(),
                surkeycode2=item.get("surkeycode2", "").strip(),
                surname=item.get("surname", "").strip(),
                surnamec=item.get("surnamec", "").strip(),
                surnamew=item.get("surnamew", "").strip(),
                surmemo=item.get("surmemo", "").strip(),
                surdurtime=item.get("surdurtime", 0),
                surpriority=item.get("surpriority", 0),
            ))
        return results
    except Exception as e:
        logger.error(f"Failed to parse surgery search response: {e}")
        return []

# --- Helper Function (Replaces DataFrame Helper) ---

def _parse_schedule_table(html: str) -> List[Dict[str, str]]:
    """
    Parses surgery schedule table without Pandas.
    Extracts tooltips and links manualy.
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    if not table: return []
    
    # Headers
    headers = []
    rows = table.find_all('tr')
    if not rows: return []
    
    headers_row = rows[0]
    headers = [th.get_text(strip=True) for th in headers_row.find_all(['th', 'td'])]
    
    # Data
    results = []
    regex = re.compile(r'術前診斷:\s*(?P<pre_op_dx>.*?)\s*手術名稱:\s*(?P<op_name>.*?)\s*手術室資訊:\s*(?P<or_info>.*?)\s*麻醉:\s*(?P<anesthesia>.*?)\s*$')
    
    for row in rows[1:]:
        cols = row.find_all('td')
        if not cols: continue
        
        record = {}
        # Basic Columns
        for i, col in enumerate(cols):
            if i < len(headers):
                record[headers[i]] = col.get_text(strip=True)
                
        # Extra Extraction: Link
        # Legacy: l['data-url'] from button[data-target="#myModal"]
        btn = row.find('button', attrs={'data-target': '#myModal'})
        if btn and btn.has_attr('data-url'):
             record['link'] = btn['data-url']
        
        # Extra Extraction: Tooltip (Diagnosis, etc.)
        # Legacy: a[data-toggle="tooltip"]['title']
        tooltip_a = row.find('a', attrs={'data-toggle': 'tooltip'})
        if tooltip_a and tooltip_a.has_attr('title'):
            tooltip_text = tooltip_a['title']
            record['tooltip'] = tooltip_text
            
            # Regex Parsing
            match = regex.search(tooltip_text)
            if match:
                groups = match.groupdict()
                # Map to legacy Chinese keys
                record['術前診斷'] = groups.get('pre_op_dx', '')
                record['手術名稱'] = groups.get('op_name', '')
                record['手術室資訊'] = groups.get('or_info', '')
                record['麻醉'] = groups.get('anesthesia', '')
        
        results.append(record)
        
    return results

# --- Tasks ---

class SurgeryScheduleParams(BaseModel):
    query: str = Field(..., description="Doctor ID or Department Code")
    date: Optional[str] = Field(None, description="Date in ROC format (e.g. 1120703) or YYYYMMDD to be converted?")
    # Legacy code expects ROC format string e.g. '1120703'. 
    # If None, defaults to current date ROC.

class SurgeryDocScheduleTask(CrawlerTask):
    """
    透過醫師燈號取得手術排程清單。
    
    Args:
        query: 醫師燈號 (e.g. "4050")
        date: 民國格式日期 (e.g. "1141211")；預設今天
    
    Returns:
        List[Dict] 包含欄位:
        - 功能: str - 功能描述 (e.g. "內容修改")
        - 手術日期: str - 民國格式 (e.g. "01141211")
        - 手術時間: str - HHMM (e.g. "0800")
        - 病房床號: str
        - 科部: str - 科別代碼
        - 病歷號: str
        - 姓名: str
        - 開刀房號: str - 手術室編號 (e.g. "B07")
        - 主刀: str - 主刀醫師姓名
        - 狀態: str - 排程狀態 (已排程/修改過/已執行/已取消)
        - 急: str - 是否急刀 (Y/N)
        - link: str - 詳細資料 URL (供 surgery_schedule_detail 使用)
        - tooltip: str - 原始 tooltip 文字
        - 術前診斷: str (從 tooltip 解析)
        - 手術名稱: str (從 tooltip 解析)
        - 手術室資訊: str (從 tooltip 解析)
        - 麻醉: str (從 tooltip 解析)
    """
    id = "surgery_doc_schedule_list"
    name = "Doctor Surgery Schedule"
    description = "醫師手術排程清單 - 透過醫師燈號查詢"
    params_model = SurgeryScheduleParams

    async def run(self, params: SurgeryScheduleParams, client: VghClient) -> List[Dict[str, str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        url = 'https://web9.vghtpe.gov.tw/ops/opb.cfm'
        
        # Date Handling
        date_str = params.date
        if not date_str:
            # Default to today ROC
            now = datetime.now()
            roc_year = now.year - 1911
            date_str = f"{roc_year}{now.strftime('%m%d')}"
            
        payload = {
            'action': 'findOpblist',
            'type': 'opbmain',
            'qry': params.query,
            'bgndt': date_str,
            '_': 0
        }
        
        resp = await session.get(url, params=payload)
        return _parse_schedule_table(resp.text)

class SurgeryDeptScheduleTask(CrawlerTask):
    """
    透過科別代碼取得手術排程清單。
    回傳資料不含已取消的排程。
    
    Args:
        query: 科別代碼 (e.g. "OPH")
        date: 民國格式日期；預設今天
    
    Returns:
        List[Dict] - 欄位同 surgery_doc_schedule_list
    """
    id = "surgery_dept_schedule_list"
    name = "Dept Surgery Schedule"
    description = "科別手術排程清單 - 透過科別代碼查詢 (不含已取消)"
    params_model = SurgeryScheduleParams

    async def run(self, params: SurgeryScheduleParams, client: VghClient) -> List[Dict[str, str]]:
        if not await client.ensure_eip(): return []
        session = client.session
        url = 'https://web9.vghtpe.gov.tw/ops/opb.cfm'
        
        date_str = params.date
        if not date_str:
            now = datetime.now()
            roc_year = now.year - 1911
            date_str = f"{roc_year}{now.strftime('%m%d')}"
            
        payload = {
            'action': 'findOpblist',
            'type': 'opbsect',
            'qry': params.query, # e.g. 'oph'
            'bgndt': date_str,
            '_': 0
        }
        
        resp = await session.get(url, params=payload)
        return _parse_schedule_table(resp.text)

class SurgeryDetailParams(BaseModel):
    link_url: str = Field(..., description="Relative URL from schedule list")

class SurgeryDetailTask(CrawlerTask):
    """
    從排程清單的 link 取得單一手術的詳細資訊。
    
    Args:
        link_url: str - 來自手術排程清單的相對 URL
    
    Returns:
        Dict 包含欄位:
        - 病歷號, 手術科部, 病房床號, 姓名, 性別, 年齡
        - 是否急刀, 身份, 手術日期, 時間, 手術房號
        - 預估時間, 超過晚上8時, 輸入時間
        - 主刀, 助手一, 助手二, 助手三
        - 麻醉方式, 排程狀態, 術前診斷, 手術方式
        - 手術室資訊(器械植入物), 病房資訊, 部位
        - 術後麻醉床, 冰凍片否, ERAS, 癌症治療手術
        - 急刀最後進食, 麻醉評估, 最後修改, 已開同意書
    """
    id = "surgery_schedule_detail"
    name = "Surgery Detail"
    description = "手術詳細資料 - 從排程 link 取得"
    params_model = SurgeryDetailParams

    async def run(self, params: SurgeryDetailParams, client: VghClient) -> Dict[str, str]:
        if not await client.ensure_eip(): return {}
        session = client.session
        base_url = 'https://web9.vghtpe.gov.tw'
        full_url = base_url + params.link_url
        
        resp = await session.get(full_url)
        soup = BeautifulSoup(resp.text, 'lxml')
        
        data = {}
        tbody = soup.find('tbody')
        if not tbody: return {}
        
        for tr in tbody.find_all('tr'):
            text = tr.get_text()
            if '麻醉方式代碼說明' in text: continue
            
            cols = tr.find_all('td')
            # The layout is label: value, label: value (2 pairs per row sometimes?)
            # Legacy code: for i in range(0, len(cols), 2)
            for i in range(0, len(cols), 2):
                if i+1 < len(cols):
                    key = cols[i].get_text(strip=True).replace(':', '')
                    val = cols[i+1].get_text(strip=True)
                    data[key] = val
        return data

# Register
# TaskRegistry.register(SurgeryDocScheduleTask())
# TaskRegistry.register(SurgeryDeptScheduleTask())
# TaskRegistry.register(SurgeryDetailTask())


# --- Surgery Search Tasks ---

class SearchSurgeryByNameTask(CrawlerTask):
    """
    依術式英文名搜尋術式組套。
    
    API Endpoint:
        POST https://rkeprd.vghtpe.gov.tw/PPC/webapi/GetSurnameByNamekey
    
    Request (form-urlencoded):
        Surkeyname: 術式名稱關鍵字 (e.g. "PHACO")
        Surkeynamew: 同上 (重複參數)
        Surkeycode: 科別代碼 (e.g. "OPH")
    
    Response:
        {"isSuccess": true, "datas": "[URL-encoded JSON array]", "errmsg": ""}
    
    Args:
        keyword: 術式名稱關鍵字 (e.g. "PHACO", "TRABE", "PPV", "IVI")
        dept_code: 科別代碼 (預設 "OPH")
    
    Returns:
        List[SurgerySearchResult]: 術式搜尋結果列表
    
    Example:
        ```python
        task = SearchSurgeryByNameTask()
        params = SurgerySearchParams(keyword="PHACO", dept_code="OPH")
        results = await task.run(params, client)
        # results[0].surname -> "PHACO-IOL OD"
        # results[0].surnamec -> "右眼白內障摘除合併人工水晶體置入手術"
        ```
    """
    id = "search_surgery_by_name"
    name = "Search Surgery by Name"
    description = "依術式英文名搜尋 - 輸入術式名稱關鍵字"
    params_model = SurgerySearchParams

    async def run(self, params: SurgerySearchParams, client: VghClient) -> List[SurgerySearchResult]:
        """執行術式名稱搜尋，需先登入 EIP。"""
        if not await client.ensure_eip():
            logger.error("EIP login failed for surgery search")
            return []
        
        session = client.session
        url = "https://rkeprd.vghtpe.gov.tw/PPC/webapi/GetSurnameByNamekey"
        
        # Request payload: Surkeyname + Surkeynamew + Surkeycode
        payload = {
            "Surkeyname": params.keyword,
            "Surkeynamew": params.keyword,
            "Surkeycode": params.dept_code,
        }
        
        try:
            resp = await session.post(url, data=payload)
            response_json = resp.json()
            return _parse_surgery_search_response(response_json)
        except Exception as e:
            logger.error(f"Surgery search by name failed: {e}")
            return []


class SearchSurgeryByDiagnosisTask(CrawlerTask):
    """
    依診斷關鍵字搜尋術式組套。
    
    API Endpoint:
        POST https://rkeprd.vghtpe.gov.tw/PPC/webapi/GetSurnameBykey
    
    Request (form-urlencoded):
        Surkeyword: 診斷關鍵字 (e.g. "CATA")
        Surkeycode: 科別代碼 (e.g. "OPH")
    
    Response:
        {"isSuccess": true, "datas": "[URL-encoded JSON array]", "errmsg": ""}
    
    Args:
        keyword: 診斷關鍵字 (e.g. "CATA", "RD", "GLAUCOMA", "DME")
        dept_code: 科別代碼 (預設 "OPH")
    
    Returns:
        List[SurgerySearchResult]: 術式搜尋結果列表
    
    Example:
        ```python
        task = SearchSurgeryByDiagnosisTask()
        params = SurgerySearchParams(keyword="CATA")  # dept_code 預設 OPH
        results = await task.run(params, client)
        # results[0].surname -> "PHACO-IOL OD"
        # results[0].surmemo -> "CATA OD"
        ```
    """
    id = "search_surgery_by_diagnosis"
    name = "Search Surgery by Diagnosis"
    description = "依診斷關鍵字搜尋 - 輸入診斷關鍵字"
    params_model = SurgerySearchParams

    async def run(self, params: SurgerySearchParams, client: VghClient) -> List[SurgerySearchResult]:
        """執行診斷關鍵字搜尋，需先登入 EIP。"""
        if not await client.ensure_eip():
            logger.error("EIP login failed for surgery search")
            return []
        
        session = client.session
        url = "https://rkeprd.vghtpe.gov.tw/PPC/webapi/GetSurnameBykey"
        
        # Request payload: Surkeyword + Surkeycode
        payload = {
            "Surkeyword": params.keyword,
            "Surkeycode": params.dept_code,
        }
        
        try:
            resp = await session.post(url, data=payload)
            response_json = resp.json()
            return _parse_surgery_search_response(response_json)
        except Exception as e:
            logger.error(f"Surgery search by diagnosis failed: {e}")
            return []
