
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
