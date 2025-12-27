"""
Op Templates Router

提供手術模板相關的 API 端點
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from app.auth.deps import get_current_user, User
from app.db.client import get_supabase_client
import logging
import re

router = APIRouter(prefix="/api/templates", tags=["templates"])
logger = logging.getLogger(__name__)


class TemplateRequest(BaseModel):
    """範本設定請求"""
    op_type: str                                    # 手術類型 (PHACO, VT, LENSX...)
    doc_code: Optional[str] = None                  # 醫師代碼 (None = GLOBAL)
    op_name: str                                    # 手術名稱
    op_code: Optional[str] = None                   # 手術代碼
    template: Optional[str] = None                  # 手術記錄模板 (含佔位符)
    icd_codes: Optional[Dict[str, Any]] = None      # ICD 編碼 JSON
    required_fields: Optional[List[str]] = None     # 必填欄位
    optional_fields: Optional[List[str]] = None     # 選填欄位


def _check_edit_permission(current_user: User, doc_code: Optional[str]) -> bool:
    """
    檢查編輯權限
    - GLOBAL (doc_code=None): 僅 admin
    - 個人範本: 本人 + vs + admin
    """
    # admin 可以編輯所有
    if current_user.role == "admin":
        return True
    
    # GLOBAL 範本只有 admin 可以編輯
    if doc_code is None:
        return False
    
    # vs 可以編輯任何個人範本
    if current_user.role == "vs":
        return True
    
    # 其他人只能編輯自己的
    match = re.search(r'DOC(\d{4})', current_user.username.upper())
    user_doc_code = match.group(1) if match else None
    return user_doc_code == doc_code


@router.get("/op-types")
async def get_op_types(current_user: User = Depends(get_current_user)):
    """
    取得所有可用的手術類型 (從 op_templates 表取得不重複的 op_type)
    """
    try:
        supabase = get_supabase_client()
        result = supabase.table("op_templates").select("op_type").execute()
        
        if result.data:
            op_types = sorted(set(item["op_type"] for item in result.data if item.get("op_type")))
            return {"op_types": op_types}
        
        return {"op_types": []}
        
    except Exception as e:
        logger.error(f"Failed to fetch op_types: {e}")
        return {"op_types": ["PHACO", "LENSX"]}


@router.get("")
async def list_templates(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """列出所有範本"""
    client = get_supabase_client()
    result = client.table("op_templates").select("*").order("op_type").execute()
    return result.data


@router.get("/field-keys")
async def get_all_field_keys(
    current_user: User = Depends(get_current_user)
) -> List[str]:
    """
    取得所有範本中使用過的 COL_* 欄位
    從 required_fields + optional_fields 聯集取得
    """
    client = get_supabase_client()
    result = client.table("op_templates").select("required_fields, optional_fields").execute()
    
    all_keys = set()
    for row in result.data:
        if row.get("required_fields"):
            all_keys.update(row["required_fields"])
        if row.get("optional_fields"):
            all_keys.update(row["optional_fields"])
    
    return sorted(list(all_keys))


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """取得特定範本"""
    client = get_supabase_client()
    result = client.table("op_templates").select("*").eq("id", template_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="範本不存在")
    
    return result.data[0]


@router.post("")
async def create_template(
    request: TemplateRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """新增範本"""
    if not _check_edit_permission(current_user, request.doc_code):
        if request.doc_code is None:
            raise HTTPException(status_code=403, detail="僅管理員可建立 GLOBAL 範本")
        raise HTTPException(status_code=403, detail="無權建立此範本")
    
    client = get_supabase_client()
    
    # 檢查是否已存在
    query = client.table("op_templates").select("id").eq("op_type", request.op_type)
    if request.doc_code:
        query = query.eq("doc_code", request.doc_code)
    else:
        query = query.is_("doc_code", "null")
    existing = query.execute()
    
    if existing.data:
        raise HTTPException(status_code=409, detail="此手術類型的範本已存在，請使用更新功能")
    
    data = {
        "op_type": request.op_type.strip(),
        "doc_code": request.doc_code.strip() if request.doc_code else None,
        "op_name": request.op_name.strip(),
        "op_code": request.op_code.strip() if request.op_code else None,
        "template": request.template,
        "icd_codes": request.icd_codes,
        "required_fields": request.required_fields or [],
        "optional_fields": request.optional_fields or [],
    }
    
    try:
        result = client.table("op_templates").insert(data).execute()
        return {"status": "success", "message": "範本已新增", "data": result.data[0] if result.data else data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增失敗: {str(e)}")


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    request: TemplateRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """更新範本"""
    client = get_supabase_client()
    
    existing = client.table("op_templates").select("*").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="範本不存在")
    
    template = existing.data[0]
    
    if not _check_edit_permission(current_user, template.get("doc_code")):
        if template.get("doc_code") is None:
            raise HTTPException(status_code=403, detail="僅管理員可編輯 GLOBAL 範本")
        raise HTTPException(status_code=403, detail="無權編輯此範本")
    
    data = {
        "op_type": request.op_type.strip(),
        "doc_code": request.doc_code.strip() if request.doc_code else None,
        "op_name": request.op_name.strip(),
        "op_code": request.op_code.strip() if request.op_code else None,
        "template": request.template,
        "icd_codes": request.icd_codes,
        "required_fields": request.required_fields or [],
        "optional_fields": request.optional_fields or [],
    }
    
    try:
        result = client.table("op_templates").update(data).eq("id", template_id).execute()
        return {"status": "success", "message": "範本已更新", "data": result.data[0] if result.data else data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """刪除範本"""
    client = get_supabase_client()
    
    existing = client.table("op_templates").select("*").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="範本不存在")
    
    template = existing.data[0]
    
    if not _check_edit_permission(current_user, template.get("doc_code")):
        if template.get("doc_code") is None:
            raise HTTPException(status_code=403, detail="僅管理員可刪除 GLOBAL 範本")
        raise HTTPException(status_code=403, detail="無權刪除此範本")
    
    try:
        client.table("op_templates").delete().eq("id", template_id).execute()
        return {"status": "success", "message": "範本已刪除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")
