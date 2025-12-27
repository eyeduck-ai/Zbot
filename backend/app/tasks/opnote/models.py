"""
OpNote 模組 - 資料模型

定義手術紀錄相關的資料結構：
- OpNotePayloadDefaults: Web9 Payload 固定預設值
- IviPayloadFields: IVI 注射專用欄位
- SurgeryPayloadFields: 一般手術專用欄位
- OpTemplate: 手術組套模板
- DoctorSheet: 醫師刀表設定
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# 固定預設值 - 所有手術紀錄共用
# =============================================================================

class OpNotePayloadDefaults(BaseModel):
    """
    Web9 手術紀錄 Payload 的固定預設值
    這些值在所有手術類型中保持不變
    """
    # 表單控制欄位
    opscode_num: int = 1
    film: str = "N"
    against: str = "N"
    action: str = "NewOpa01Action"
    signchk: str = "Y"
    source: str = "O"  # O = 門診
    
    # 手術記錄固定值
    again: str = "N"
    reason_aga: str = "0"
    mirr: str = "N"
    saw: str = "N"
    hurt: str = "1"
    posn1: str = "1"
    posn2: str = "0"
    cler1: str = "2"
    cler2: str = "0"
    item1: str = "3"
    item2: str = "2"
    
    # 空字串預設欄位 (助手、麻醉等)
    ass2n: str = ""
    ass3n: str = ""
    ant1n: str = ""
    ant2n: str = ""
    dirn: str = ""
    trtncti: str = ""
    babym: str = ""
    babyd: str = ""
    bed: str = ""
    final: str = ""
    ass2: str = ""
    ass3: str = ""
    ant1: str = ""
    ant2: str = ""
    dir: str = ""
    antyp1: str = ""
    antyp2: str = ""
    side: str = ""
    oper: str = ""
    rout: str = ""
    side01: str = ""
    oper01: str = ""
    rout01: str = ""
    
    # 備用手術碼欄位
    opanam2: str = ""
    opacod2: str = ""
    opanam3: str = ""
    opacod3: str = ""
    opanam4: str = ""
    opacod4: str = ""
    opanam5: str = ""
    opacod5: str = ""
    
    # 備用 ICD 欄位
    opaicd1: str = ""
    opaicdnm1: str = ""
    opaicd2: str = ""
    opaicdnm2: str = ""
    opaicd3: str = ""
    opaicdnm3: str = ""
    opaicd4: str = ""
    opaicdnm4: str = ""
    opaicd5: str = ""
    opaicdnm5: str = ""
    opaicd6: str = ""
    opaicdnm6: str = ""
    opaicd7: str = ""
    opaicdnm7: str = ""
    opaicd8: str = ""
    opaicdnm8: str = ""
    opaicd9: str = ""
    opaicdnm9: str = ""


# =============================================================================
# 資料來源優先順序
# =============================================================================

class DataSource(Enum):
    """資料來源標識"""
    WEB9 = "web9"          # Web9 病人基本資料
    SCHEDULE = "schedule"  # 內網手術排程
    GSHEET = "gsheet"      # 個人刀表 Google Sheet
    MANUAL = "manual"      # 前端手動輸入


# =============================================================================
# IVI 專用欄位
# =============================================================================

class IviPayloadFields(BaseModel):
    """
    IVI 注射專用的動態欄位
    資料主要來自 CKS 排程
    """
    diagnosis: str = Field(..., description="診斷")
    side: str = Field(..., description="側別 OD/OS/OU")
    drug: str = Field(..., description="藥物名稱")
    charge_type: str = Field(default="", description="收費類型")
    op_start: str = Field(..., description="手術開始時間 HHMM")
    op_end: str = Field(..., description="手術結束時間 HHMM")
    doc_code: str = Field(..., description="主治醫師代碼")
    r_code: str = Field(..., description="住院醫師代碼")
    
    # IVI 固定值
    sect: str = "OPH"
    ward: str = "OPD"
    antyp: str = "LA"
    opacod1: str = "OPH1476"
    opaicd0: str = "3E0C3GC"
    opaicdnm0: str = "Introduction of Other Therapeutic Substance into Eye, Percutaneous Approach"
    
    def get_opanam1(self) -> str:
        """產生手術名稱"""
        return f"INTRAVITREAL INJECTION OF {self.drug.upper()}"
    
    def get_diagn(self) -> str:
        """產生術前診斷"""
        return f"{self.diagnosis} {self.side}".strip()
    
    def get_diaga(self) -> str:
        """產生術後診斷"""
        return f"Ditto s/p IVI-{self.drug} {self.side}".strip()


# =============================================================================
# 手術專用欄位
# =============================================================================

class SurgeryPayloadFields(BaseModel):
    """
    一般手術的動態欄位
    資料來自內網排程 + Google Sheet
    """
    # 來自排程
    op_sect: str = Field(default="OPH", description="科別")
    op_bed: str = Field(default="", description="病床")
    op_anesthesia: str = Field(default="LA", description="麻醉方式")
    op_side: str = Field(default="", description="側別 OD/OS/OU")
    pre_op_dx: str = Field(default="", description="術前診斷 (來自 ScheduleItem)")
    op_name: str = Field(default="", description="手術名稱 (來自 ScheduleItem)")
    
    # 來自刀表或模板系統
    op_type: Optional[str] = Field(default=None, description="手術類型 PHACO/VT/etc")
    
    # 醫師資訊 (主刀)
    doc_code: str = Field(..., description="主治醫師代碼")
    vs_name: str = Field(default="", description="主治醫師姓名")
    
    # 助手資訊
    r_code: str = Field(default="", description="助手一代碼")
    r_name: str = Field(default="", description="助手一姓名")
    ass2: str = Field(default="", description="助手二代碼")
    ass2n: str = Field(default="", description="助手二姓名")
    ass3: str = Field(default="", description="助手三代碼")
    ass3n: str = Field(default="", description="助手三姓名")
    
    # Google Sheet 資料 (由 column_map 動態填充)
    gsheet_data: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# 手術模板 Schema
# =============================================================================

class IcdCode(BaseModel):
    """ICD 碼結構"""
    code: str
    name: str


class OpTemplate(BaseModel):
    """
    手術組套模板 (對應 Supabase op_templates 表)
    """
    op_type: str
    scope: str = "GLOBAL"  # GLOBAL | DOCTOR
    doc_code: Optional[str] = None
    
    op_name: str
    op_code: str
    icd_codes: Dict[str, IcdCode]  # {"OD": IcdCode, "OS": IcdCode, ...}
    
    template: Optional[str] = None
    required_fields: List[str] = []
    optional_fields: List[str] = []


class DoctorSheet(BaseModel):
    """
    醫師刀表設定 (對應 Supabase doctor_sheets 表)
    """
    doc_code: str
    sheet_id: str
    worksheet: str
    column_map: Dict[str, Optional[str]]  # placeholder -> column_name (None = 無此欄位)
    header_row: int = 1  # 標題列行號 (1-indexed)，預設為第 1 列


# =============================================================================
# 側別轉換
# =============================================================================

SIDE_TRANSFORM = {
    "OD": "Right",
    "OS": "Left", 
    "OU": "Both"
}


def transform_side(side: str) -> str:
    """將 OD/OS/OU 轉換為 Right/Left/Both"""
    return SIDE_TRANSFORM.get(side.upper(), side)


# =============================================================================
# Helper Functions
# =============================================================================

def check_op_side(input_string: str) -> Optional[str]:
    """
    從字串中識別手術側別
    
    Args:
        input_string: 輸入字串
        
    Returns:
        OD/OS/OU 或 None
    """
    if not isinstance(input_string, str):
        return None
    s = input_string.upper()
    if 'OD' in s: return 'OD'
    if 'OS' in s: return 'OS'
    if 'OU' in s: return 'OU'
    return None

def contains_side_info(input_string: str) -> bool:
    """
    檢查字串是否包含側別資訊 (OD/OS/OU)
    
    Args:
        input_string: 輸入字串
        
    Returns:
        True 如果包含 OD/OS/OU，否則 False
    """
    if not isinstance(input_string, str):
        return False
    s = input_string.upper()
    # 使用 word boundary 檢查以避免誤判 (e.g. "PHACO" 不含 "OD")
    import re
    return bool(re.search(r'\b(OD|OS|OU)\b', s))


def existandnotnone(d: dict, key: str) -> bool:
    """檢查 dict 中的 key 是否存在且有值"""
    val = d.get(key)
    if val is not None:
        if isinstance(val, str) and len(val.strip()) > 0:
            return True
        if isinstance(val, int):
            return True
    return False
