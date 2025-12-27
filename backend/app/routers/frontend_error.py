"""
前端錯誤回報 API

接收前端 JavaScript 錯誤並記錄 + 通知開發者
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
import logging
from app.core.alert import AlertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/frontend-error", tags=["errors"])


class FrontendErrorReport(BaseModel):
    """前端錯誤回報結構"""
    message: str              # 錯誤訊息
    stack: Optional[str] = None  # 堆疊追蹤 (如果有)
    url: str                  # 發生錯誤的頁面 URL
    userAgent: Optional[str] = None  # 瀏覽器資訊
    timestamp: str            # 發生時間
    componentStack: Optional[str] = None  # React 元件堆疊
    user: Optional[str] = None  # 使用者 (eip_id)


@router.post("")
async def report_frontend_error(error: FrontendErrorReport, request: Request):
    """
    接收前端錯誤回報
    - 記錄到日誌
    - 發送 Email 給開發者
    """
    # 記錄到日誌
    logger.error(
        f"[Frontend Error] {error.message}\n"
        f"  URL: {error.url}\n"
        f"  User: {error.user or 'unknown'}\n"
        f"  Stack: {error.stack or 'N/A'}"
    )
    
    # 組裝郵件內容
    body = f"""
Frontend JavaScript Error

Message: {error.message}

Page URL: {error.url}
User: {error.user or 'Not logged in'}
Time: {error.timestamp}
Browser: {error.userAgent or 'Unknown'}

Stack Trace:
{error.stack or 'N/A'}

Component Stack:
{error.componentStack or 'N/A'}
    """.strip()
    
    # 發送通知 (非同步，不阻塞回應)
    try:
        await AlertService.send_alert("Frontend Error", body)
    except Exception as e:
        logger.warning(f"Failed to send frontend error alert: {e}")
    
    return {"status": "received"}
