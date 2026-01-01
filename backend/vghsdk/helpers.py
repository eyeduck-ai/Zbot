"""VGHSDK 共用 Helper 函式 - HTML 解析與結果包裝"""
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup


def parse_table(html: str, table_id: str = None) -> List[Dict[str, str]]:
    """解析 HTML 表格為字典清單。
    
    Args:
        html: HTML 內容
        table_id: table 的 id (選填)
    
    Returns:
        每列資料作為一個 dict
    """
    def normalize_text(text: str) -> str:
        """清理多餘空格 (全形空格、多個空格合併為一個、括號前空格)"""
        cleaned = re.sub(r'[\s\u3000]+', ' ', text).strip()
        cleaned = re.sub(r'\s+([)\]）])', r'\1', cleaned)
        return cleaned
    
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', id=table_id) if table_id else soup.find('table')
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
        record = {}
        for i, col in enumerate(cols):
            if i < len(headers):
                record[headers[i]] = normalize_text(col.get_text(strip=True))
        results.append(record)
    return results


def parse_key_value_table(html: str) -> Dict[str, str]:
    """解析 key-value 形式的表格 (交替 td)。"""
    soup = BeautifulSoup(html, 'lxml')
    data = {}
    
    for row in soup.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        for i in range(0, len(cells) - 1, 2):
            key = cells[i].get_text(strip=True).replace('：', '')
            val = cells[i + 1].get_text(strip=True) if i + 1 < len(cells) else ''
            if key:
                data[key] = val
    
    return data
