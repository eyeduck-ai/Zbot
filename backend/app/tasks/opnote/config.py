"""
OpNote 模組 - Supabase 設定服務

提供手術組套模板與醫師刀表設定的載入功能。
資料結構：
- op_templates: 手術組套模板 (GLOBAL / DOCTOR 繼承)
- doctor_sheets: 醫師刀表設定與欄位對應
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.db.client import get_supabase_client
from .models import OpTemplate, DoctorSheet, IcdCode

logger = logging.getLogger(__name__)

# =============================================================================
# 快取設定
# =============================================================================

CACHE_TTL_MINUTES = 30  # 快取有效期限

_template_cache: Dict[str, OpTemplate] = {}
_template_cache_expiry: Dict[str, datetime] = {}

_sheet_cache: Dict[str, DoctorSheet] = {}
_sheet_cache_expiry: Dict[str, datetime] = {}

# Surkeycode cache (loaded once per session)
_surkeycode_cache: Dict[str, str] = {}  # surkeycode → op_type
_surkeycode_loaded: bool = False


# =============================================================================
# Config Service
# =============================================================================

class OpNoteConfigService:
    """
    手術紀錄設定服務
    
    負責從 Supabase 載入：
    - 手術組套模板 (op_templates)
    - 醫師刀表設定 (doctor_sheets)
    """
    
    async def get_template(
        self, 
        op_type: str, 
        doc_code: Optional[str] = None
    ) -> Optional[OpTemplate]:
        """
        取得手術組套模板
        
        查詢優先順序：
        1. DOCTOR 模板 (doc_code + op_type)
        2. GLOBAL 模板 (op_type)
        
        Args:
            op_type: 手術類型 (PHACO, VT, IVI, 等)
            doc_code: 主治醫師代碼 (選填，用於查詢客製化模板)
            
        Returns:
            OpTemplate 或 None
        """
        cache_key = f"{op_type}:{doc_code or 'GLOBAL'}"
        
        # 檢查快取
        if cache_key in _template_cache and cache_key in _template_cache_expiry:
            if datetime.now() < _template_cache_expiry[cache_key]:
                logger.debug(f"Cache hit for template: {cache_key}")
                return _template_cache[cache_key]
        
        client = get_supabase_client()
        
        try:
            # 查詢優先順序: DOCTOR > GLOBAL
            query = client.table("op_templates").select("*").eq("op_type", op_type.upper())
            
            if doc_code:
                # 查詢 DOCTOR 或 GLOBAL
                query = query.or_(f"scope.eq.GLOBAL,and(scope.eq.DOCTOR,doc_code.eq.{doc_code})")
            else:
                query = query.eq("scope", "GLOBAL")
            
            response = query.order("scope", desc=True).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                row = response.data[0]
                
                # 解析 ICD Codes
                icd_codes = {}
                raw_icd = row.get("icd_codes") or {}
                for side, icd_data in raw_icd.items():
                    if isinstance(icd_data, dict):
                        icd_codes[side] = IcdCode(
                            code=icd_data.get("code", ""),
                            name=icd_data.get("name", "")
                        )
                
                template = OpTemplate(
                    op_type=row.get("op_type"),
                    scope=row.get("scope", "GLOBAL"),
                    doc_code=row.get("doc_code"),
                    op_name=row.get("op_name", ""),
                    op_code=row.get("op_code", ""),
                    icd_codes=icd_codes,
                    template=row.get("template"),
                    required_fields=row.get("required_fields") or [],
                    optional_fields=row.get("optional_fields") or [],
                )
                
                # 更新快取
                _template_cache[cache_key] = template
                _template_cache_expiry[cache_key] = datetime.now() + timedelta(minutes=CACHE_TTL_MINUTES)
                
                logger.info(f"Loaded template: {op_type} (scope={template.scope})")
                return template
                
            logger.warning(f"No template found for op_type: {op_type}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch template '{op_type}': {e}")
            return None
    
    def _parse_template_row(self, row: Dict[str, Any]) -> OpTemplate:
        """Helper: 解析單筆模板資料"""
        icd_codes = {}
        raw_icd = row.get("icd_codes") or {}
        for side, icd_data in raw_icd.items():
            if isinstance(icd_data, dict):
                icd_codes[side] = IcdCode(
                    code=icd_data.get("code", ""),
                    name=icd_data.get("name", "")
                )
        
        return OpTemplate(
            op_type=row.get("op_type"),
            scope=row.get("scope", "GLOBAL"),
            doc_code=row.get("doc_code"),
            op_name=row.get("op_name", ""),
            op_code=row.get("op_code", ""),
            icd_codes=icd_codes,
            template=row.get("template"),
            required_fields=row.get("required_fields") or [],
            optional_fields=row.get("optional_fields") or [],
        )
    
    async def get_templates_batch(
        self, 
        op_types: List[str], 
        doc_code: Optional[str] = None
    ) -> Dict[str, OpTemplate]:
        """
        批次載入多個 op_type 的模板 (單次查詢)
        
        優先順序: DOCTOR > GLOBAL (保留現有邏輯)
        
        Args:
            op_types: 手術類型清單
            doc_code: 醫師代碼 (用於查詢 DOCTOR scope)
            
        Returns:
            {op_type: OpTemplate} dict
        """
        if not op_types:
            return {}
        
        client = get_supabase_client()
        
        try:
            # 單次查詢所有 op_types
            unique_types = list(set(t.upper() for t in op_types))
            query = client.table("op_templates").select("*").in_("op_type", unique_types)
            
            if doc_code:
                query = query.or_(f"scope.eq.GLOBAL,and(scope.eq.DOCTOR,doc_code.eq.{doc_code})")
            else:
                query = query.eq("scope", "GLOBAL")
            
            response = query.execute()
            
            # 建構結果 (先處理 GLOBAL，再用 DOCTOR 覆蓋)
            result: Dict[str, OpTemplate] = {}
            for row in sorted(response.data, key=lambda r: 0 if r.get("scope") == "GLOBAL" else 1):
                op_type = row["op_type"]
                result[op_type] = self._parse_template_row(row)
            
            logger.info(f"Batch-loaded {len(result)}/{len(unique_types)} templates")
            return result
            
        except Exception as e:
            logger.error(f"Failed to batch-load templates: {e}")
            return {}
    
    async def get_doctor_sheet(self, doc_code: str) -> Optional[DoctorSheet]:
        """
        取得醫師刀表設定
        
        Args:
            doc_code: 主治醫師代碼
            
        Returns:
            DoctorSheet 或 None
        """
        # 檢查快取
        if doc_code in _sheet_cache and doc_code in _sheet_cache_expiry:
            if datetime.now() < _sheet_cache_expiry[doc_code]:
                logger.debug(f"Cache hit for doctor_sheet: {doc_code}")
                return _sheet_cache[doc_code]
        
        client = get_supabase_client()
        
        try:
            response = client.table("doctor_sheets").select("*").eq("doc_code", doc_code).execute()
            
            if response.data and len(response.data) > 0:
                row = response.data[0]
                sheet = DoctorSheet(
                    doc_code=row.get("doc_code"),
                    sheet_id=row.get("sheet_id", ""),
                    worksheet=row.get("worksheet", ""),
                    column_map=row.get("column_map") or {},
                    header_row=row.get("header_row") or 1,  # 預設為第 1 列
                )
                
                # 更新快取
                _sheet_cache[doc_code] = sheet
                _sheet_cache_expiry[doc_code] = datetime.now() + timedelta(minutes=CACHE_TTL_MINUTES)
                
                logger.info(f"Loaded doctor_sheet for: {doc_code}")
                return sheet
                
            logger.warning(f"No doctor_sheet found for doc_code: {doc_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch doctor_sheet '{doc_code}': {e}")
            return None
    
    async def list_op_types(self) -> List[str]:
        """
        列出所有可用的手術類型
        
        Returns:
            手術類型清單 (用於前端選擇器)
        """
        client = get_supabase_client()
        
        try:
            response = client.table("op_templates").select("op_type").eq("scope", "GLOBAL").execute()
            
            if response.data:
                return sorted(set(row.get("op_type") for row in response.data if row.get("op_type")))
            return []
            
        except Exception as e:
            logger.error(f"Failed to list op_types: {e}")
            return []
    
    def clear_cache(self):
        """清除所有快取"""
        global _template_cache, _template_cache_expiry, _sheet_cache, _sheet_cache_expiry
        _template_cache.clear()
        _template_cache_expiry.clear()
        _sheet_cache.clear()
        _sheet_cache_expiry.clear()
        logger.info("OpNoteConfigService cache cleared")
    
    async def get_user_display_name(self, eip_id: str) -> Optional[str]:
        """
        從 Supabase users 表取得使用者的 display_name
        
        Args:
            eip_id: EIP 帳號 (如 DOC4050H)
            
        Returns:
            使用者的 display_name，若無則回傳 None
        """
        client = get_supabase_client()
        try:
            res = client.table("users").select("display_name").eq("eip_id", eip_id).execute()
            if res.data and res.data[0].get("display_name"):
                return res.data[0]["display_name"]
            return None
        except Exception as e:
            logger.error(f"Failed to get display_name for {eip_id}: {e}")
            return None


# =============================================================================
# Singleton Instance
# =============================================================================

_service_instance: Optional[OpNoteConfigService] = None


def get_opnote_config_service() -> OpNoteConfigService:
    """取得 OpNoteConfigService 單例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = OpNoteConfigService()
    return _service_instance


# =============================================================================
# Surkeycode Service
# =============================================================================

class SurkeycodeService:
    """
    Surkeycode → op_type 查詢服務
    
    載入時機: FetchDetails 開始時呼叫 ensure_loaded()
    查詢方式: 本地快取 O(1)，無網路請求
    """
    
    async def ensure_loaded(self):
        """載入所有 surkeycode (單次查詢)"""
        global _surkeycode_cache, _surkeycode_loaded
        if _surkeycode_loaded:
            return
        
        client = get_supabase_client()
        try:
            res = client.table("surkeycode_map").select("surkeycode, op_type").execute()
            _surkeycode_cache = {r["surkeycode"]: r["op_type"] for r in res.data}
            _surkeycode_loaded = True
            logger.info(f"Loaded {len(_surkeycode_cache)} surkeycodes from database")
        except Exception as e:
            logger.warning(f"Failed to load surkeycode_map: {e} (will use fallback)")
            # Fallback: 使用空 cache，會走 check_op_type fallback
    
    def get_op_type(self, surkeycode: str) -> Optional[str]:
        """本地查表 O(1)"""
        return _surkeycode_cache.get(surkeycode)
    
    def is_loaded(self) -> bool:
        """檢查是否已載入"""
        return _surkeycode_loaded
    
    def get_cache_size(self) -> int:
        """取得快取大小"""
        return len(_surkeycode_cache)
    
    def clear_cache(self):
        """清除快取 (測試用)"""
        global _surkeycode_cache, _surkeycode_loaded
        _surkeycode_cache.clear()
        _surkeycode_loaded = False
        logger.info("SurkeycodeService cache cleared")


_surkeycode_service: Optional[SurkeycodeService] = None


def get_surkeycode_service() -> SurkeycodeService:
    """取得 SurkeycodeService 單例"""
    global _surkeycode_service
    if _surkeycode_service is None:
        _surkeycode_service = SurkeycodeService()
    return _surkeycode_service
