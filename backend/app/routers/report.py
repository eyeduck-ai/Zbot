
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional
from email.message import EmailMessage
import aiosmtplib
import logging
from datetime import datetime

from app.auth.deps import get_current_user, User
from app.core.alert import get_email_settings

router = APIRouter(prefix="/api/report", tags=["report"])
logger = logging.getLogger(__name__)

@router.post("")
async def submit_report(
    description: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    """
    提交問題回報或升等申請
    支援文字描述與單張圖片附件
    """
    settings = await get_email_settings()
    if not settings or not settings.SMTP_USER or not settings.DEVELOPER_EMAIL:
         raise HTTPException(status_code=500, detail="System email configuration is missing")

    # Construct email
    msg = EmailMessage()
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.DEVELOPER_EMAIL
    msg["Subject"] = f"[Zbot Report] {current_user.username} - Bug/升等申請"
    
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Body
    body = f"""使用者回報 (Bug/升等申請)
--------------------------
Time: {today}
User ID: {current_user.username}
Name: {current_user.full_name or "N/A"}
Role: {current_user.role}

內容描述:
{description}
"""
    msg.set_content(body)

    # Attachment
    if image:
        content = await image.read()
        file_name = image.filename or "screenshot.png"
        
        # Determine MIME type
        maintype, subtype = "application", "octet-stream"
        if image.content_type and "/" in image.content_type:
             maintype, subtype = image.content_type.split("/", 1)
        
        msg.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=file_name
        )

    # Send
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True
        )
        return {"status": "success", "message": "Report sent successfully"}
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        # Return 500 but log detailed error
        raise HTTPException(status_code=500, detail=f"發送郵件失敗: {str(e)}")
