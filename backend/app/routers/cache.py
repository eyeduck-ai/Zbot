"""
快取 API 路由

提供前端存取快取的 API:
- GET /api/cache - 列出待上傳快取
- GET /api/cache/check/{task_id} - 檢查特定任務是否有快取
- POST /api/cache/{cache_id}/retry - 重新上傳
- DELETE /api/cache/{cache_id} - 刪除快取
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.core.cache import CacheManager
from app.auth.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


# --- Response Models ---

class CacheItemResponse(BaseModel):
    id: str
    task_id: str
    created_at: str
    expires_at: str
    params: Dict[str, Any]
    size_bytes: int


class CacheListResponse(BaseModel):
    caches: List[CacheItemResponse]


class CacheCheckResponse(BaseModel):
    has_cache: bool
    cache: Optional[CacheItemResponse] = None


class RetryResponse(BaseModel):
    status: str
    message: str


# --- Routes ---

@router.get("", response_model=CacheListResponse)
async def list_caches(
    task_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """列出所有待上傳快取"""
    caches = CacheManager.list_caches(task_id)
    return CacheListResponse(caches=caches)


@router.get("/check/{task_id}", response_model=CacheCheckResponse)
async def check_cache(
    task_id: str,
    current_user=Depends(get_current_user)
):
    """檢查特定任務是否有待上傳快取"""
    cache = CacheManager.check_existing(task_id)
    if cache:
        return CacheCheckResponse(has_cache=True, cache=cache)
    return CacheCheckResponse(has_cache=False)


@router.post("/{cache_id}/retry", response_model=RetryResponse)
async def retry_cache_upload(
    cache_id: str,
    current_user=Depends(get_current_user)
):
    """
    重新上傳快取資料到 Google Sheets
    
    根據 task_id 呼叫對應的上傳邏輯
    """
    cache = CacheManager.get_cache(cache_id)
    if not cache:
        raise HTTPException(status_code=404, detail="快取不存在或已過期")
    
    task_id = cache["task_id"]
    data = cache["data"]
    target_info = cache["target_info"]
    params = cache.get("params", {})
    
    try:
        # 根據任務類型呼叫對應的上傳函數
        if task_id == "stats_fee_update":
            from app.tasks.stats_fee import upload_from_cache
            await upload_from_cache(data, target_info, params)
            
        elif task_id == "stats_op_update":
            from app.tasks.stats_op import upload_from_cache
            await upload_from_cache(data, target_info, params)
            
        elif task_id == "dashboard_bed":
            from app.tasks.dashboard_bed import upload_from_cache
            await upload_from_cache(data, target_info, params)
            
        else:
            raise HTTPException(status_code=400, detail=f"不支援的任務類型: {task_id}")
        
        # 上傳成功，刪除快取
        CacheManager.delete_cache(cache_id)
        return RetryResponse(status="success", message="上傳成功")
        
    except Exception as e:
        logger.error(f"Cache retry failed for {cache_id}: {e}")
        return RetryResponse(status="error", message=str(e))


@router.delete("/{cache_id}")
async def delete_cache(
    cache_id: str,
    current_user=Depends(get_current_user)
):
    """刪除快取"""
    success = CacheManager.delete_cache(cache_id)
    if not success:
        raise HTTPException(status_code=404, detail="快取不存在")
    return {"status": "success", "message": "快取已刪除"}
