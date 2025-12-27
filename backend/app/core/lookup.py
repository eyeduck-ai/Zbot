"""
查詢服務模組

提供各種資料查詢 API，如醫師姓名查詢等
"""

import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from app.auth.deps import get_current_user
from vghsdk.core import SessionManager
from vghsdk.modules.doctor import get_doctor_name

logger = logging.getLogger("lookup")

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


class DoctorNameResponse(BaseModel):
    code: str
    name: str


@router.get("/doctor-name/{code}", response_model=DoctorNameResponse)
async def lookup_doctor_name(
    code: str, 
    current_user=Depends(get_current_user),
    x_eip_id: Optional[str] = Header(None),
    x_eip_psw: Optional[str] = Header(None)
):
    """根據醫師登號查詢姓名
    
    Args:
        code: 4位數字的醫師登號 (例如 "4102")
        x_eip_id: EIP 帳號 (從 Header 傳入)
        x_eip_psw: EIP 密碼 (從 Header 傳入)
    
    Returns:
        醫師登號和對應的姓名
    """
    # 驗證輸入格式
    if not code.isdigit() or len(code) != 4:
        raise HTTPException(status_code=400, detail="醫師登號必須是4位數字")
    
    # 取得 EIP 憑證 (從 Header 或設定檔)
    from app.config import get_settings
    settings = get_settings()
    eip_id = x_eip_id or settings.TEST_EIP_ID
    eip_psw = x_eip_psw or settings.TEST_EIP_PSW
    
    if not eip_id or not eip_psw:
        raise HTTPException(status_code=400, detail="缺少 EIP 憑證")
    
    try:
        # 使用 SessionManager 取得已登入的 Client
        client = SessionManager.get_client(eip_id, eip_psw)
        
        # 確保已登入 EIP
        if not await client.ensure_eip():
            raise HTTPException(status_code=401, detail="EIP 登入失敗")
        
        name = await get_doctor_name(code, client.session)
        
        return DoctorNameResponse(code=code, name=name)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查詢醫師姓名失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))
