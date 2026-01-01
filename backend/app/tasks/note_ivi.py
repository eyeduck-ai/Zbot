
import logging
from typing import List, Dict, Any, Optional, Type
import asyncio
from pydantic import BaseModel
from vghsdk.core import VghClient, VghSession
from app.tasks.base import BaseTask
from vghsdk.modules.ivi import ivi_fetch  # Function-based task
from vghsdk.utils import to_roc_date
from app.tasks.opnote import OpNoteBaseTask, PayloadBuilder, IviPayloadFields
from app.core.registry import TaskRegistry
from app.core.jobs import JobManager  # 用於檢查取消狀態
from app.config import get_settings

logger = logging.getLogger("ivi_plugin")

# Initialize shared PayloadBuilder
_payload_builder = PayloadBuilder()

# --- Models ---

class IviSubmitItem(BaseModel):
    hisno: str
    name: str  # 病患姓名 (informational)
    doc_code: str  # 醫師登號 → man
    vs_name: str = ""  # 醫師姓名 → mann
    r_code: str  # 助手登號 → ass1
    r_name: str = ""  # 助手姓名 → ass1n
    diagnosis: str
    side: str
    drug: str
    charge_type: str
    op_start: str  # HHMM
    op_end: str  # HHMM
    is_left_eye: bool 

class IviSubmitParams(BaseModel):
    items: List[IviSubmitItem]
    op_date: str # ISO or ROC

class IviSubmitResult(BaseModel):
    total: int
    success: int
    failed: int
    details: List[str]
    message: Optional[str] = None  # 用於前端顯示

# --- Plugin Task ---

class IviBatchSubmitTask(OpNoteBaseTask):
    """
    IVI 批次送出任務
    
    繼承 OpNoteBaseTask 共用 _get_web9_form_data, _post_note 方法。
    主要負責協調多筆 IVI 注射記錄的送出。
    """
    id: str = "note_ivi_submit"
    name: str = "IVI Batch Submit"
    description: str = "Submit multiple IVI notes to Web9 (Plugin)."
    params_model: Optional[Type[BaseModel]] = IviSubmitParams
    
    # _get_web9_form_data, _post_note 繼承自 OpNoteBaseTask

    async def run(self, params: IviSubmitParams, client: VghClient, progress_callback=None) -> IviSubmitResult:
        """執行 IVI 批次送出"""
        if not await client.ensure_eip():
            raise Exception("Login EIP Failed")
        
        session = client.session
        # params 已由 router 驗證並轉換為 IviSubmitParams
        p = params
        
        # Ensure OpDate is ROC for Web9
        roc_date = to_roc_date(p.op_date)
        if not roc_date:
            return IviSubmitResult(total=0, success=0, failed=0, details=["Invalid Date"])
        
        logger.info(f"Starting IVI Batch Submit for {len(p.items)} items on {roc_date}")
        
        success_count = 0
        details = []
        settings = get_settings()
        
        # 取得 job_id 用於 Checkpoint 和取消檢查
        job_id = getattr(progress_callback, 'job_id', None) if progress_callback else None
        total_items = len(p.items)
        
        # 設定總項目數 (Checkpoint 支援)
        if job_id:
            JobManager.set_total_items(job_id, total_items)
        
        for i, item in enumerate(p.items):
            # 檢查是否已被取消
            if job_id and JobManager.is_cancelled(job_id):
                logger.info(f"IVI: 任務已被取消 (job_id={job_id})")
                return IviSubmitResult(total=total_items, success=success_count, failed=i-success_count, details=["任務已被使用者取消"])
            
            # 斷點續跑: 跳過已完成項目
            if job_id and JobManager.is_item_completed(job_id, item.hisno):
                continue
            
            try:
                await client.rate_limit()
                
                # 1. 取得 Web9 資料 (使用繼承的共用方法, 自動 retry)
                web9_data = await self._get_web9_form_data(item.hisno, client, roc_date)
                
                if not web9_data:
                    logger.warning(f"Could not fetch Web9 form for {item.hisno}")
                    details.append(f"{item.name} ({item.hisno}): Failed to init form")
                    continue

                # 2. 建構 Payload
                post_data = self._construct_ivi_payload(web9_data, item, roc_date)
                
                # 3. 送出 (或開發模式印出, 自動 retry)
                if settings.DEV_MODE:
                    logger.info(f"[DEV_MODE] IVI Submit for {item.hisno}:")
                    logger.info(f"[DEV_MODE] Payload: {post_data}")
                    ok = True
                    details.append(f"{item.name} ({item.hisno}): [DEV] Printed payload")
                else:
                    ok = await self._post_note(post_data, client)
                    if ok:
                        details.append(f"{item.name} ({item.hisno}): Success")
                    else:
                        details.append(f"{item.name} ({item.hisno}): Failed (API Rejected)")
                     
                if ok:
                    success_count += 1
                    # 標記完成 (Checkpoint)
                    if job_id:
                        JobManager.mark_item_completed(job_id, item.hisno, f"送出 {item.name} ({i+1}/{total_items})")
                    
            except Exception as e:
                logger.error(f"Error submitting {item.hisno}: {e}")
                details.append(f"{item.name} ({item.hisno}): Error {e}")
                
        return IviSubmitResult(
            total=len(p.items),
            success=success_count,
            failed=len(p.items) - success_count,
            details=details,
            message=f"送出 {success_count} 筆紀錄"
        )

    def _construct_ivi_payload(self, web9: Dict, item: IviSubmitItem, op_date: str) -> Dict:
        """
        使用 PayloadBuilder 建構 IVI 注射的 Web9 Payload。
        
        Args:
            web9: Web9 病人基本資料與隱藏欄位
            item: IVI 項目資料
            op_date: 手術日期 (民國格式)
            
        Returns:
            完整的 Web9 POST payload
        """
        # 建立 IVI 專用欄位
        ivi_fields = IviPayloadFields(
            diagnosis=item.diagnosis,
            side=item.side,
            drug=item.drug,
            charge_type=item.charge_type,
            op_start=item.op_start,
            op_end=item.op_end,
            doc_code=item.doc_code,
            r_code=item.r_code,
        )
        
        # 使用 PayloadBuilder 建構 Payload
        payload = _payload_builder.build_ivi_payload(
            web9_data=web9,
            ivi_fields=ivi_fields,
            op_date=op_date,
            vs_name=item.doc_code,  # TODO: 未來可從 Supabase 查詢醫師姓名
            r_name=item.r_code,     # TODO: 未來可從 Supabase 查詢住院醫師姓名
        )
        
        return payload

# Auto Register
TaskRegistry.register(IviBatchSubmitTask())
# Note: IviFetchTask (now ivi_fetch) is registered in loader.py

