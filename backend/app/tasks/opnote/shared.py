"""
OpNote 模組 - 共用 Tasks

提供 IVI 和 OpNote 共用的下游流程：
- OpNoteBaseTask: 共用基礎類
- OpNotePreviewTask: 預覽任務
- OpNoteSubmitTask: 送出任務
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask
from vghsdk.utils import to_roc_date
from .models import (
    IviPayloadFields,
    SurgeryPayloadFields,
    OpTemplate,
    IcdCode,
    transform_side,
)
from .builder import PayloadBuilder
from .config import get_opnote_config_service
from app.core.registry import TaskRegistry
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Initialize shared services
_payload_builder = PayloadBuilder()
_config_service = get_opnote_config_service()


# =============================================================================
# Enums & Models
# =============================================================================

class SourceType(str, Enum):
    """資料來源類型"""
    IVI = "ivi"          # CKS 排程
    SURGERY = "surgery"  # 內網手術排程


class PreviewItem(BaseModel):
    """預覽項目"""
    hisno: str
    name: str = ""
    payload: Dict[str, Any] = {}
    missing_fields: List[str] = []
    editable_fields: List[str] = []
    source_map: Dict[str, str] = {}  # 欄位 -> 來源 (internal/gsheet/manual)
    status: str = "pending"
    

class PreviewParams(BaseModel):
    """預覽參數"""
    source_type: SourceType
    doc_code: str
    r_code: str
    date: str  # ISO or ROC
    items: List[Dict[str, Any]]  # 從上游 Fetch 取得的資料
    eip_id: str = ""  # 登入者的 EIP 帳號 (用於查詢 display_name)


class PreviewResult(BaseModel):
    """預覽結果"""
    total: int
    previews: List[PreviewItem]


class SubmitParams(BaseModel):
    """送出參數"""
    items: List[Dict[str, Any]]  # [{ hisno, payload }]


class SubmitResult(BaseModel):
    """送出結果"""
    total: int
    success: int
    failed: int
    details: List[str]


# =============================================================================
# Base Task (共用基礎類)
# =============================================================================

class OpNoteBaseTask(BaseTask):
    """
    手術紀錄共用基礎任務
    
    提供 IVI 和 OpNote 共用的功能：
    - _get_web9_form_data: 取得 Web9 病人基本資料
    - _post_note: 送出到 Web9
    
    使用 client.safe_request() 自動處理 retry/backoff/session 過期。
    """
    
    async def _get_web9_form_data(self, hisno: str, client: VghClient, date: str) -> Dict:
        """
        取得 Web9 病人基本資料
        
        Args:
            hisno: 病歷號
            client: VghClient (使用 safe_request 自動 retry)
            date: 日期 (ROC 格式)
            
        Returns:
            Web9 表單資料 dict
        """
        url = "https://web9.vghtpe.gov.tw/emr/OPAController?action=NewOpnForm01Action"
        payload = {"hisno": hisno, "pidno": "", "drid": "", "b1": "新增"}
        
        try:
            # 使用 safe_request 自動 retry/backoff/relogin
            res = await client.safe_request('POST', url, data=payload)
            soup = BeautifulSoup(res.text, "lxml")
            
            def get_val(name):
                el = soup.find(attrs={"name": name})
                return el.get('value') if el else ""
            
            sel_opck_el = soup.select_one("select#sel_opck > option")
            sel_opck = sel_opck_el.get('value') if sel_opck_el else ""
            
            bgntm = endtm = ""
            if sel_opck and "|" in sel_opck:
                parts = sel_opck.split('|')
                bgntm = parts[0][-4:]
                endtm = parts[1][-4:]
            
            return {
                "sect1": get_val("sect1"),
                "name": get_val("name"),
                "sex": get_val("sex"),
                "hisno": get_val("hisno"),
                "age": get_val("age"),
                "idno": get_val("idno"),
                "birth": get_val("birth"),
                "_antyp": get_val("_antyp"),
                "opbbgndt": get_val("opbbgndt"),
                "opbbgntm": get_val("opbbgntm"),
                "diagn": get_val("diagn"),
                "sel_opck": sel_opck,
                "bgntm": bgntm,
                "endtm": endtm,
            }
        except Exception as e:
            logger.error(f"Failed to get Web9 form for {hisno}: {e}")
            return {}
    
    async def _post_note(self, payload: Dict, client: VghClient) -> bool:
        """
        送出單筆記錄到 Web9
        
        Args:
            payload: 完整的 POST payload
            client: VghClient (使用 safe_request 自動 retry)
            
        Returns:
            成功/失敗
        """
        url = "https://web9.vghtpe.gov.tw/emr/OPAController"
        try:
            # 使用 safe_request 自動 retry/backoff/relogin
            res = await client.safe_request('POST', url, data=payload)
            
            # 檢查成功標記 (基於 HAR 分析的實際 Web9 回應)
            # Web9 成功時會顯示 <FONT COLOR="RED">系統訊息:新增成功!!</FONT>
            success_marker = '新增成功!!'
            error_markers = ['SQLCODE', 'SQLSTATE', 'DB2 SQL error']
            
            response_text = res.text
            has_success = success_marker in response_text
            has_error = any(marker in response_text for marker in error_markers)
            
            return has_success and not has_error
        except Exception as e:
            logger.error(f"Post failed: {e}")
            return False



# =============================================================================
# Preview Task (共用)
# =============================================================================

class OpNotePreviewTask(OpNoteBaseTask):
    """
    手術紀錄預覽任務
    
    負責：
    1. 根據來源類型 (IVI/Surgery) 建構 Payload
    2. 識別缺失欄位
    3. 標記可編輯欄位
    4. 不實際送出
    """
    id = "opnote_preview"
    name = "OpNote Preview"
    description = "預覽手術紀錄填充結果 (不送出)"
    params_model = PreviewParams
    
    async def _build_ivi_preview(
        self, 
        item: Dict, 
        web9: Dict, 
        roc_date: str,
        eip_id: str = "",
    ) -> Tuple[Dict, List[str]]:
        """建構 IVI 預覽 Payload"""
        ivi_fields = IviPayloadFields(
            diagnosis=item.get("diagnosis", ""),
            side=item.get("side", "OD"),
            drug=item.get("drug", ""),
            charge_type=item.get("charge_type", ""),
            op_start=item.get("op_start", "0830"),
            op_end=item.get("op_end", "0840"),
            doc_code=item.get("doc_code", ""),
            r_code=item.get("r_code", ""),
        )
        
        # 取得 IVI 模板
        ivi_template = await _config_service.get_template("IVI")
        template_content = None
        if ivi_template and ivi_template.template:
            template_content = ivi_template.template
            transformed_side = transform_side(item.get("side", "OD"))
            template_content = template_content.replace("$TRANSFORMED_SIDE", transformed_side)
            template_content = template_content.replace("$TRANSFORMED_DISTANCE", "3.5")
        
        # 取得助手姓名 (優先使用前端傳入的 r_name)
        r_display_name = item.get("r_name") or None
        if not r_display_name and eip_id:
            r_display_name = await _config_service.get_user_display_name(eip_id)
        
        payload = _payload_builder.build_ivi_payload(
            web9_data=web9,
            ivi_fields=ivi_fields,
            op_date=roc_date,
            vs_name=item.get("vs_name", "") or item.get("doc_code", ""),
            r_name=r_display_name or item.get("r_code", ""),
            template_content=template_content,
        )
        
        missing = []
        if not item.get("drug"):
            missing.append("drug")
        if not item.get("diagnosis"):
            missing.append("diagnosis")
            
        return payload, missing
    
    async def _build_surgery_preview(
        self,
        item: Dict,
        web9: Dict,
        params: PreviewParams,
        roc_date: str,
    ) -> Tuple[Dict, List[str]]:
        """建構 Surgery 預覽 Payload"""
        op_type = item.get("op_type", "PHACO")
        template = await _config_service.get_template(op_type, params.doc_code)
        
        if not template:
            template = await _config_service.get_template("PHACO")
        
        if not template:
            template = OpTemplate(
                op_type="PHACO",
                op_name="PHACOEMULSIFICATION + PC-IOL IMPLANTATION",
                op_code="OPH 1342",
                icd_codes={
                    "OD": IcdCode(code="08RJ3JZ", name="Replacement of Right Lens"),
                    "OS": IcdCode(code="08RK3JZ", name="Replacement of Left Lens"),
                },
                required_fields=["IOL", "FINAL"],
                optional_fields=[],
            )
        
        surgery_fields = SurgeryPayloadFields(
            op_sect=item.get("op_sect", "OPH"),
            op_bed=item.get("op_bed", ""),
            op_anesthesia=item.get("op_anesthesia", "LA"),
            op_side=item.get("op_side", "OD"),
            op_type=op_type,
            doc_code=params.doc_code,
            vs_name=params.doc_code,
            r_code=params.r_code,
            r_name=params.r_code,
        )
        
        placeholder_values = {
            "IOL": item.get("iol", ""),
            "FINAL": item.get("final", ""),
            "TARGET": item.get("target", ""),
            "SN": item.get("sn", ""),
            "CDE": item.get("cde", ""),
            "COMPLICATIONS": item.get("complications", ""),
            "COL_OP": item.get("op_type", op_type),
        }
        
        payload, missing = _payload_builder.build_surgery_payload(
            web9_data=web9,
            surgery_fields=surgery_fields,
            op_template=template,
            op_date=roc_date,
            placeholder_values=placeholder_values,
        )
        
        return payload, missing

    async def run(
        self, 
        params: PreviewParams, 
        client: VghClient,
        progress_callback=None
    ) -> PreviewResult:
        """執行預覽"""
        if not await client.ensure_eip():
            return PreviewResult(total=0, previews=[])
        
        session = client.session
        roc_date = to_roc_date(params.date)
        
        if not roc_date:
            return PreviewResult(total=0, previews=[])
        
        previews = []
        total_items = len(params.items)
        
        for idx, item in enumerate(params.items):
            hisno = str(item.get("hisno", ""))
            if not hisno:
                continue
            
            try:
                await client.rate_limit()
                
                web9 = await self._get_web9_form_data(hisno, client, roc_date)
                
                if params.source_type == SourceType.IVI:
                    payload, missing = await self._build_ivi_preview(
                        item, web9, roc_date, params.eip_id
                    )
                    editable = ["diagnosis", "side", "drug", "op_start", "op_end"]
                else:
                    payload, missing = await self._build_surgery_preview(
                        item, web9, params, roc_date
                    )
                    editable = ["op_side", "op_type", "iol", "final", "target", "sn"]
                
                previews.append(PreviewItem(
                    hisno=hisno,
                    name=web9.get("name", item.get("name", "")),
                    payload=payload,
                    missing_fields=missing,
                    editable_fields=editable,
                    status="ready" if not missing else "incomplete",
                ))
                
            except Exception as e:
                logger.error(f"Preview failed for {hisno}: {e}")
                previews.append(PreviewItem(
                    hisno=hisno,
                    name=item.get("name", ""),
                    status="error",
                ))
        
        return PreviewResult(total=len(previews), previews=previews)


# =============================================================================
# Submit Task (共用)
# =============================================================================

class OpNoteSubmitTask(OpNoteBaseTask):
    """
    手術紀錄送出任務
    
    負責：
    1. 送出已確認的 Payloads
    2. 回傳成功/失敗統計
    """
    id = "opnote_submit"
    name = "OpNote Submit"
    description = "送出手術紀錄 (需先透過 Preview 確認)"
    params_model = SubmitParams
    
    async def run(
        self, 
        params: SubmitParams, 
        client: VghClient,
        progress_callback=None
    ) -> SubmitResult:
        """執行送出"""
        if progress_callback:
            await progress_callback(5, "初始化送出任務")
            
        if not await client.ensure_eip():
            return SubmitResult(
                total=len(params.items),
                success=0,
                failed=len(params.items),
                details=["Login failed"]
            )
        
        session = client.session
        success_count = 0
        details = []
        total_items = len(params.items)
        
        # 載入設定
        from app.config import get_settings
        settings = get_settings()
        
        for idx, item in enumerate(params.items):
            hisno = item.get("hisno", "unknown")
            payload = item.get("payload", {})
            
            # 回報進度
            if progress_callback and total_items > 0:
                progress = 10 + int((idx / total_items) * 80)
                await progress_callback(progress, f"送出中 ({idx + 1}/{total_items})")
            
            try:
                await session.rate_limit()
                
                if settings.DEV_MODE:
                    logger.info(f"[DEV_MODE] OpNote Submit for {hisno}:")
                    logger.info(f"[DEV_MODE] Payload: {payload}")
                    ok = True
                    details.append(f"{hisno}: [DEV] Printed payload")
                else:
                    ok = await self._post_note(payload, client)
                    if ok:
                        details.append(f"{hisno}: Success")
                    else:
                        details.append(f"{hisno}: Failed")
                
                if ok:
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Submit error for {hisno}: {e}")
                details.append(f"{hisno}: Error - {e}")
        
        if progress_callback:
            await progress_callback(95, f"送出完成 ({success_count}/{total_items})")
        
        return SubmitResult(
            total=len(params.items),
            success=success_count,
            failed=len(params.items) - success_count,
            details=details,
        )


# =============================================================================
# Register Tasks
# =============================================================================

TaskRegistry.register(OpNotePreviewTask())
TaskRegistry.register(OpNoteSubmitTask())
