
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.service import authenticate_user, sync_user_to_supabase, get_user_permissions
from app.auth.deps import create_access_token, Token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from datetime import timedelta

router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    使用者登入
    
    支援兩種帳號類型:
    - DOC 開頭: EIP 內網驗證
    - 其他: Supabase 平台驗證
    """
    # 1. 驗證帳密
    auth_result = await authenticate_user(form_data.username, form_data.password)
    if auth_result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. 根據帳號類型處理
    is_eip_user = form_data.username.upper().startswith("DOC")
    
    if is_eip_user:
        # EIP 用戶: auth_result 是 VghClient，需要 sync 和 close
        try:
            await sync_user_to_supabase(form_data.username, form_data.password, vgh_client=auth_result)
        finally:
            await auth_result.close()
    else:
        # 平台用戶: auth_result 是 dict，更新 last_login
        from app.db.client import get_supabase_client
        from datetime import datetime
        try:
            supabase = get_supabase_client()
            supabase.table("users").update({
                "last_login": datetime.now().isoformat()
            }).eq("eip_id", form_data.username).execute()
        except Exception:
            pass  # 更新失敗不阻止登入

    # 3. Fetch Permissions
    permission_data = await get_user_permissions(form_data.username)

    # 4. Issue Token (include doc_code and eip_id for Supabase RLS)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": form_data.username,
            "eip_id": form_data.username,  # RLS 政策使用 eip_id 驗證
            "role": permission_data["role"],
            "display_name": permission_data["display_name"],
            "doc_code": permission_data["doc_code"],
            "allowed_prefixes": permission_data["allowed_prefixes"]
        }, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me/gsheet-status")
async def get_my_gsheet_status(current_user = Depends(get_current_user)):
    """
    取得當前用戶的 Google 刀表連線狀態與設定
    
    Returns:
        configured: 是否已設定 (True/False)
        connected: 是否可連線讀取 (True/False/None if not configured)
        sheet_name: 試算表名稱 (if connected)
        worksheet: 工作表名稱 (if configured)
        doc_code: 醫師代碼
        sheet_id: 試算表 ID (if configured)
        column_map: 欄位對應 (if configured)
        error: 錯誤訊息 (if error)
    """
    import re
    eip_id = current_user.username
    
    # 從 EIP ID 提取 doc_code (DOC4050H -> 4050)
    match = re.search(r'DOC(\d{4})', eip_id.upper())
    if not match:
        return {"configured": False, "connected": None, "message": "非醫師帳號"}
    
    doc_code = match.group(1)
    
    # 查詢 doctor_sheets
    from app.db.client import get_supabase_client
    client = get_supabase_client()
    
    try:
        result = client.table("doctor_sheets").select("*").eq("doc_code", doc_code).execute()
    except Exception as e:
        return {"configured": False, "connected": None, "doc_code": doc_code, "error": f"資料庫查詢失敗: {str(e)}"}
    
    if not result.data:
        return {"configured": False, "connected": None, "doc_code": doc_code, "message": "尚未設定刀表"}
    
    row = result.data[0]
    sheet_id = row.get("sheet_id")
    worksheet = row.get("worksheet")
    column_map = row.get("column_map") or {}
    
    # 嘗試連線 Google Sheets
    try:
        from app.db.gsheet import get_gsheet_service
        gs = get_gsheet_service()
        gc = gs.get_pygsheets_client()
        sh = gc.open_by_key(sheet_id)
        return {
            "configured": True,
            "connected": True,
            "sheet_name": sh.title,
            "doc_code": doc_code,
            "sheet_id": sheet_id,
            "worksheet": worksheet,
            "column_map": column_map
        }
    except Exception as e:
        return {
            "configured": True,
            "connected": False,
            "doc_code": doc_code,
            "sheet_id": sheet_id,
            "worksheet": worksheet,
            "column_map": column_map,
            "error": str(e)
        }


from pydantic import BaseModel
from typing import Optional, Dict

class GSheetSettingsRequest(BaseModel):
    """Google 刀表設定請求"""
    sheet_id: str
    worksheet: str
    column_map: Optional[Dict[str, Optional[str]]] = None


@router.put("/me/gsheet-settings")
async def update_my_gsheet_settings(
    request: GSheetSettingsRequest,
    current_user = Depends(get_current_user)
):
    """
    更新當前用戶的 Google 刀表設定
    
    設定會儲存到 Supabase doctor_sheets 資料表
    """
    import re
    eip_id = current_user.username
    
    # 從 EIP ID 提取 doc_code
    match = re.search(r'DOC(\d{4})', eip_id.upper())
    if not match:
        raise HTTPException(status_code=400, detail="非醫師帳號，無法設定刀表")
    
    doc_code = match.group(1)
    
    # 準備 column_map (空字串轉 null)
    column_map = {}
    if request.column_map:
        for key, value in request.column_map.items():
            column_map[key] = value if value and value.strip() else None
    
    # Upsert 到 doctor_sheets
    from app.db.client import get_supabase_client
    client = get_supabase_client()
    
    try:
        data = {
            "doc_code": doc_code,
            "sheet_id": request.sheet_id.strip(),
            "worksheet": request.worksheet.strip(),
            "column_map": column_map
        }
        
        result = client.table("doctor_sheets").upsert(
            data, on_conflict="doc_code"
        ).execute()
        
        # 清除快取 (如果有)
        try:
            from app.tasks.opnote.config import _sheet_cache, _sheet_cache_expiry
            if doc_code in _sheet_cache:
                del _sheet_cache[doc_code]
            if doc_code in _sheet_cache_expiry:
                del _sheet_cache_expiry[doc_code]
        except ImportError:
            pass
        
        return {
            "status": "success",
            "message": "設定已儲存",
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存失敗: {str(e)}")
