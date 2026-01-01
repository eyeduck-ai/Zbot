
from datetime import datetime, date
from typing import Union, Optional

def to_roc_date(date_input: Union[str, datetime, date]) -> Optional[str]:
    """
    Convert date to ROC string (e.g. '1120703').
    Supports inputs:
    - datetime/date object
    - ISO string 'YYYY-MM-DD'
    - ROC string (passthrough, cleans non-digits)
    """
    if not date_input: return None
    
    dt = None
    
    # 1. Passthrough (Already ROC?)
    # Heuristic: If string is digits and len <= 8, assume ROC.
    if isinstance(date_input, str):
        cleaned = ''.join(filter(str.isdigit, date_input))
        # 7-digit ROC (e.g. 1120101, 1141223)
        if len(cleaned) == 7 and cleaned.startswith("1"):
             return cleaned
        # 8-digit ROC with leading 0 (e.g. 01120101, 01141223)
        # Convert to 7-digit by stripping leading 0
        if len(cleaned) == 8 and cleaned.startswith("0") and cleaned[1:].startswith("1"):
             return cleaned[1:]  # Strip leading 0
        # 6-digit ROC (e.g. 990101)
        if len(cleaned) == 6:
             return cleaned
             
        # Try parsing ISO
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d")
        except ValueError:
            pass # Not ISO
            
    if isinstance(date_input, (datetime, date)):
        dt = date_input
    
    if dt:
        roc_year = dt.year - 1911
        return f"{roc_year}{dt.month:02d}{dt.day:02d}"
        
    return str(date_input) # Fallback

def to_western_date(roc_str: str) -> Optional[date]:
    """
    Convert ROC string (e.g. '1120703') or ISO string to Python date object.
    """
    if not roc_str: return None
    
    # Check if already ISO
    if "-" in str(roc_str) and len(str(roc_str)) == 10:
        try:
            return datetime.strptime(roc_str, "%Y-%m-%d").date()
        except:
            pass
            
    # ROC Logic
    s = ''.join(filter(str.isdigit, str(roc_str)))
    if not s: return None
    
    try:
        if len(s) == 7: # 1120704
            year = int(s[:3]) + 1911
            month = int(s[3:5])
            day = int(s[5:])
        elif len(s) == 6: # 990101
            year = int(s[:2]) + 1911
            month = int(s[2:4])
            day = int(s[4:])
        elif len(s) == 8: # 01120704
             year = int(s[1:4]) + 1911
             month = int(s[4:6])
             day = int(s[6:])
        else:
            return None
            
        return date(year, month, day)
    except Exception:
        return None

def to_iso_string(roc_str: str) -> Optional[str]:
    """
    Convert ROC string to 'YYYY-MM-DD'.
    """
    d = to_western_date(roc_str)
    return d.strftime("%Y-%m-%d") if d else None


def normalize_date(date_input: Union[str, datetime, date]) -> Optional[date]:
    """
    統一日期格式轉換，輸出 date 物件。
    
    支援格式:
    - 'YYYY-MM-DD' (ISO, 推薦)
    - 'YYYYMMDD' (西元 8 位)
    - '1141220' (民國 7 位)
    - '01141220' (民國 8 位)
    - datetime/date 物件
    
    Returns:
        date 物件，無效則回傳 None
    """
    if not date_input:
        return None
    
    if isinstance(date_input, date) and not isinstance(date_input, datetime):
        return date_input
    
    if isinstance(date_input, datetime):
        return date_input.date()
    
    s = str(date_input).strip()
    
    # ISO 格式 YYYY-MM-DD
    if "-" in s and len(s) == 10:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    # 純數字處理
    digits = ''.join(filter(str.isdigit, s))
    
    # 西元 8 位 YYYYMMDD (年份 > 1911)
    if len(digits) == 8 and int(digits[:4]) > 1911:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
        except ValueError:
            pass
    
    # 民國格式 (6/7/8 位)
    return to_western_date(s)


def to_roc_date_8(date_input: Union[str, datetime, date]) -> Optional[str]:
    """
    轉換日期為 8 位民國格式 (如 '01141220')。
    
    與 to_roc_date 的差異: 前面補 0 成為 8 位數。
    """
    d = normalize_date(date_input)
    if not d:
        return None
    
    roc_year = d.year - 1911
    return f"0{roc_year}{d.month:02d}{d.day:02d}"


def to_yyyymmdd(date_input: Union[str, datetime, date]) -> Optional[str]:
    """轉換日期為西元 YYYYMMDD 格式。"""
    d = normalize_date(date_input)
    if not d:
        return None
    return d.strftime("%Y%m%d")

