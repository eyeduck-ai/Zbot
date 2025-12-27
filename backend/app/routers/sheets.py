"""
Google 刀表設定 API

提供刀表設定的 CRUD 操作
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any

from app.auth.deps import get_current_user, User
from app.db.client import get_supabase_client

router = APIRouter(prefix="/api/sheets", tags=["sheets"])


class SheetSettingsRequest(BaseModel):
    """刀表設定請求"""
    doc_code: str  # 醫師代碼
    sheet_id: str  # Google Spreadsheet ID
    worksheet: str  # 工作表名稱
    column_map: Optional[Dict[str, Optional[str]]] = None  # 欄位對應
    header_row: int = 1  # 標題列行號 (1-indexed)，預設為第 1 列


class SheetSettingsResponse(BaseModel):
    """刀表設定回應"""
    doc_code: str
    sheet_id: str
    worksheet: str
    column_map: Optional[Dict[str, Optional[str]]] = None
    header_row: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("")
async def list_sheets(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    列出所有刀表設定
    
    任何已登入使用者都可以查看
    """
    client = get_supabase_client()
    result = client.table("doctor_sheets").select("*").order("doc_code").execute()
    return result.data


@router.get("/doc/{doc_code}")
async def get_sheet_by_doc_code(
    doc_code: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    取得特定醫師的刀表設定
    
    Returns:
        sheet_id, worksheet, column_map 等設定
    """
    client = get_supabase_client()
    result = client.table("doctor_sheets").select("*").eq("doc_code", doc_code).execute()
    
    if not result.data:
        return {"configured": False, "doc_code": doc_code}
    
    return {
        "configured": True,
        **result.data[0]
    }


@router.get("/column-keys")
async def get_all_column_keys(
    current_user: User = Depends(get_current_user)
) -> List[str]:
    """
    取得所有 doctor_sheets 中使用過的 column_map keys
    
    用於前端動態顯示欄位對應選項
    
    Returns:
        去重後的 key 清單，例如: ["COL_HISNO", "COL_OP", "COL_IOL", ...]
    """
    client = get_supabase_client()
    result = client.table("doctor_sheets").select("column_map").execute()
    
    # 收集所有 column_map 的 keys
    all_keys = set()
    for row in result.data:
        if row.get("column_map") and isinstance(row["column_map"], dict):
            all_keys.update(row["column_map"].keys())
    
    # 排序後返回
    return sorted(list(all_keys))


@router.post("")
async def create_sheet_settings(
    request: SheetSettingsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    新增刀表設定
    
    可以為任意醫師代碼新增設定
    """
    client = get_supabase_client()
    
    # 檢查是否已存在
    existing = client.table("doctor_sheets").select("doc_code").eq("doc_code", request.doc_code).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail=f"doc_code {request.doc_code} 的設定已存在，請使用更新功能")
    
    # 準備 column_map (空字串轉 null)
    column_map = {}
    if request.column_map:
        for key, value in request.column_map.items():
            column_map[key] = value if value and value.strip() else None
    
    data = {
        "doc_code": request.doc_code.strip(),
        "sheet_id": request.sheet_id.strip(),
        "worksheet": request.worksheet.strip(),
        "column_map": column_map,
        "header_row": request.header_row
    }
    
    try:
        result = client.table("doctor_sheets").insert(data).execute()
        return {
            "status": "success",
            "message": "設定已新增",
            "data": result.data[0] if result.data else data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增失敗: {str(e)}")


@router.put("/{doc_code}")
async def update_sheet_settings(
    doc_code: str,
    request: SheetSettingsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    更新刀表設定
    
    只能更新自己的設定 (由 RLS 控制)
    """
    import re
    
    # 從 EIP ID 提取當前使用者的 doc_code
    match = re.search(r'DOC(\d{4})', current_user.username.upper())
    user_doc_code = match.group(1) if match else None
    
    # 檢查權限：admin/vs 可以更新任何人的，其他人只能更新自己的
    is_privileged = current_user.role in ("admin", "vs")
    if not is_privileged and user_doc_code and doc_code != user_doc_code:
        raise HTTPException(status_code=403, detail="只能更新自己的刀表設定")
    
    client = get_supabase_client()
    
    # 檢查是否存在
    existing = client.table("doctor_sheets").select("doc_code").eq("doc_code", doc_code).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"doc_code {doc_code} 的設定不存在")
    
    # 準備 column_map (空字串轉 null)
    column_map = {}
    if request.column_map:
        for key, value in request.column_map.items():
            column_map[key] = value if value and value.strip() else None
    
    data = {
        "sheet_id": request.sheet_id.strip(),
        "worksheet": request.worksheet.strip(),
        "column_map": column_map,
        "header_row": request.header_row
    }
    
    try:
        result = client.table("doctor_sheets").update(data).eq("doc_code", doc_code).execute()
        
        # 清除快取
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
            "message": "設定已更新",
            "data": result.data[0] if result.data else data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")


@router.get("/worksheets/{sheet_id}")
async def get_worksheets(
    sheet_id: str,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    查詢 Google Spreadsheet 的工作表列表
    
    Returns:
        工作表列表，包含 title 和 index
    """
    try:
        from app.db.gsheet import get_gsheet_service
        
        # 使用 service account 連接
        gc = get_gsheet_service().get_pygsheets_client()
        
        # 開啟試算表
        spreadsheet = gc.open_by_key(sheet_id)
        
        # 取得所有工作表
        worksheets = []
        for ws in spreadsheet.worksheets():
            worksheets.append({
                "title": ws.title,
                "index": ws.index
            })
        
        return worksheets
        
    except Exception as e:
        error_msg = str(e)
        if "SpreadsheetNotFound" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail="找不到此試算表，請確認 ID 是否正確")
        elif "permission" in error_msg.lower() or "access" in error_msg.lower():
            raise HTTPException(status_code=403, detail="權限不足，請確認已分享給服務帳號")
        else:
            raise HTTPException(status_code=500, detail=f"查詢失敗: {error_msg}")

