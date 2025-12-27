"""
Surgery Record 暫存機制 (動態欄位版)

提供手術記錄的記憶體暫存，用於在多步驟流程中累積資料。
單一用戶情境，使用全域 dict，不需要 session_id。

欄位動態化設計:
- col_fields: Dict[str, str] 儲存所有 COL_* 欄位值
- editable_fields: List[str] 儲存該模板需要的欄位清單
- 欄位定義來自 op_templates 表的 required_fields + optional_fields
- 新增欄位只需修改資料庫，無需改程式碼
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 可編輯欄位定義 (前端可覆蓋)
# =============================================================================

# 基礎欄位 (非 COL_* 欄位)
BASE_EDITABLE_FIELDS = [
    "diagn",             # 術前診斷
    "op_name",           # 手術名稱 (用於構建 diaga)
    "op_side",           # 側別
    "op_type",           # 範本類型
]

# COL_* 欄位現在由 col_fields Dict 動態管理
# 前端傳來的 col_fields 會整個覆蓋


# =============================================================================
# SurgeryRecord 資料模型
# =============================================================================

@dataclass
class SurgeryRecord:
    """
    手術記錄完整資料結構 (動態欄位版)
    
    累積來自多個來源的資料：
    - 排程系統 (Schedule)
    - 內網詳情 (SDK Detail)
    - Web9
    - Google Sheets
    
    動態欄位設計:
    - col_fields: 儲存所有填充欄位值 {'IOL': 'Tecnis', 'FINAL': '-0.5D', ...}
    - editable_fields: 該模板需要的欄位清單 ['IOL', 'FINAL', 'TARGET', ...]
    - 欄位名稱對應 GSheet column_map 的 COL_* 鍵
    
    新增欄位流程:
    1. op_templates 表: 在 required_fields/optional_fields 加入欄位名
    2. doctor_sheets 表: 在 column_map 加入 COL_* 對應
    3. op_templates.template: 使用 $COL_* 佔位符
    無需修改此程式碼!
    """
    # 識別欄位
    hisno: str
    name: str = ""
    
    # 排程資料
    op_date: str = ""
    op_time: str = ""
    op_room: str = ""
    op_room_info: str = ""
    pre_op_dx: str = ""  # 術前診斷 (來自排程)
    op_name: str = ""    # 手術名稱 (來自排程或 GSheet COL_OP)
    
    # SDK 詳情 (自動填充)
    op_sect: str = "OPH"
    op_bed: str = ""
    op_anesthesia: str = "LA"
    op_side: str = ""
    
    # 醫師資訊 (自動填充)
    man: str = ""
    mann: str = ""
    ass1: str = ""
    ass1n: str = ""
    ass2: str = ""
    ass2n: str = ""
    ass3: str = ""
    ass3n: str = ""
    
    # Web9 資料 (含 sel_opck)
    web9_data: Dict[str, Any] = field(default_factory=dict)
    
    # GSheet 原始資料 (供參考)
    gsheet_data: Dict[str, Any] = field(default_factory=dict)
    
    # 手術類型
    op_type: str = ""
    
    # =========================================================================
    # 動態 COL_* 欄位 (核心改動)
    # =========================================================================
    # col_fields: 儲存填充欄位值
    # 例: {'IOL': 'Tecnis ZCB00', 'FINAL': '-0.5D', 'TARGET': '-0.25D'}
    col_fields: Dict[str, str] = field(default_factory=dict)
    
    # editable_fields: 該模板定義需要的欄位 (from template.required + optional)
    # 例: ['IOL', 'FINAL', 'TARGET', 'SN', 'CDE', 'COMPLICATIONS']
    editable_fields: List[str] = field(default_factory=list)
    
    # =========================================================================
    # 計算欄位 (可覆蓋)
    # =========================================================================
    diagn: str = ""   # 術前診斷 (預設=pre_op_dx, 可編輯)
    diaga: str = ""   # 術後診斷 (Submit 時從 op_name 構建)
    
    # 狀態
    status: str = "pending"
    error: str = ""
    
    def get_editable_dict(self) -> Dict[str, Any]:
        """取得可編輯欄位的值 (給前端顯示/編輯用)"""
        return {
            "hisno": self.hisno,
            "name": self.name,
            "op_date": self.op_date,
            "op_time": self.op_time,
            "op_room_info": self.op_room_info,
            "pre_op_dx": self.pre_op_dx,
            "op_name": self.op_name,
            "diagn": self.diagn,
            "op_side": self.op_side,
            "op_type": self.op_type,
            "col_fields": self.col_fields,           # 動態欄位
            "editable_fields": self.editable_fields, # 該模板需要的欄位
            "status": self.status,
            "error": self.error,
        }
    
    def apply_overrides(self, overrides: Dict[str, Any]) -> None:
        """
        套用前端覆蓋值
        
        Args:
            overrides: 前端傳來的覆蓋值，應包含:
                - diagn, op_name, op_side, op_type: 基礎欄位
                - col_fields: Dict[str, str] 動態欄位
        """
        # 套用基礎欄位
        for key in BASE_EDITABLE_FIELDS:
            if key in overrides and overrides[key] is not None:
                setattr(self, key, overrides[key])
        
        # 套用動態欄位 (整個 dict 覆蓋)
        if "col_fields" in overrides and isinstance(overrides["col_fields"], dict):
            # 只覆蓋有值的欄位，保留原有值
            for k, v in overrides["col_fields"].items():
                if v is not None:
                    self.col_fields[k] = v
    
    def get_placeholder_values(self) -> Dict[str, str]:
        """
        取得模板佔位符替換值
        
        Returns:
            Dict 形如 {'COL_IOL': 'Tecnis', 'COL_FINAL': '-0.5D', ...}
        """
        return {f"COL_{k}": v for k, v in self.col_fields.items()}


# =============================================================================
# 全域暫存 (簡化版，單一用戶)
# =============================================================================

# 全域記錄暫存：hisno -> SurgeryRecord
_records: Dict[str, SurgeryRecord] = {}


def set_record(record: SurgeryRecord) -> None:
    """存入記錄"""
    _records[record.hisno] = record
    logger.debug(f"[RecordCache] Set: hisno={record.hisno}, editable_fields={record.editable_fields}")


def get_record(hisno: str) -> Optional[SurgeryRecord]:
    """取出記錄"""
    return _records.get(hisno)


def get_all_records() -> List[SurgeryRecord]:
    """取得所有記錄"""
    return list(_records.values())


def clear_all() -> None:
    """清除所有暫存"""
    _records.clear()
    logger.info("[RecordCache] Cleared all records")


def record_count() -> int:
    """取得記錄數量"""
    return len(_records)

