"""
Stats API - 任務統計 API

提供任務使用統計資料的 API 端點。
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.auth.deps import get_current_user, User
from app.db.client import get_supabase_admin_client
from app.core.task_logger import TaskLogger

import logging

router = APIRouter(prefix="/api/stats", tags=["stats"])
logger = logging.getLogger(__name__)


# =============================================================================
# Response Models
# =============================================================================

class TaskStatsItem(BaseModel):
    task_id: str
    total_runs: int = 0
    total_success: int = 0
    total_items: int = 0
    last_run_at: Optional[str] = None


class TaskLogItem(BaseModel):
    id: str
    task_id: str
    job_id: Optional[str] = None
    operator_eip_id: str
    target_doc_code: Optional[str] = None
    status: str
    items_processed: int = 0
    error_message: Optional[str] = None
    started_at: str
    completed_at: str


# =============================================================================
# Admin-Only Endpoints
# =============================================================================

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """驗證使用者為 admin (開發者專用)"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此功能僅限管理員使用"
        )
    return current_user


@router.get("/tasks/summary", response_model=List[TaskStatsItem])
async def get_tasks_summary(current_user: User = Depends(require_admin)):
    """
    取得所有任務的統計摘要 (Admin Only)
    
    Returns:
        各任務的累計統計資料
    """
    try:
        stats = await TaskLogger.get_all_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get tasks summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/recent", response_model=List[TaskLogItem])
async def get_recent_logs(
    limit: int = Query(50, ge=1, le=200),
    task_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """
    取得最近的任務執行記錄 (Admin Only)
    
    Args:
        limit: 回傳筆數上限 (預設 50)
        task_id: 過濾特定任務
        status: 過濾狀態 (success/failed/cancelled)
    
    Returns:
        最近的執行記錄列表
    """
    try:
        supabase = get_supabase_admin_client()
        
        query = supabase.table("task_logs") \
            .select("*") \
            .order("completed_at", desc=True) \
            .limit(limit)
        
        if task_id:
            query = query.eq("task_id", task_id)
        if status:
            query = query.eq("status", status)
        
        result = query.execute()
        return result.data or []
        
    except Exception as e:
        logger.error(f"Failed to get recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/by-user")
async def get_stats_by_user(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin)
):
    """
    按使用者分群的統計 (Admin Only)
    
    Args:
        days: 統計天數範圍 (預設 30 天)
    
    Returns:
        各使用者的執行次數和處理筆數
    """
    try:
        supabase = get_supabase_admin_client()
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # 查詢指定期間的日誌
        result = supabase.table("task_logs") \
            .select("operator_eip_id, status, items_processed") \
            .gte("completed_at", since) \
            .execute()
        
        if not result.data:
            return {"users": [], "period_days": days}
        
        # 手動聚合
        user_stats = {}
        for log in result.data:
            user = log["operator_eip_id"]
            if user not in user_stats:
                user_stats[user] = {"operator_eip_id": user, "total_runs": 0, "total_success": 0, "total_items": 0}
            user_stats[user]["total_runs"] += 1
            if log["status"] == "success":
                user_stats[user]["total_success"] += 1
            user_stats[user]["total_items"] += log.get("items_processed", 0)
        
        # 按執行次數排序
        users = sorted(user_stats.values(), key=lambda x: x["total_runs"], reverse=True)
        
        return {"users": users, "period_days": days}
        
    except Exception as e:
        logger.error(f"Failed to get stats by user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Public Endpoints (用於各任務頁面顯示)
# =============================================================================

@router.get("/tasks/{task_id}/count")
async def get_task_count(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    取得單一任務的累計統計 (Public)
    
    用於各任務頁面顯示「累計完成 N 筆」
    
    Args:
        task_id: 任務識別碼
    
    Returns:
        任務統計資料
    """
    try:
        stats = await TaskLogger.get_task_stats(task_id)
        
        if stats:
            return {
                "task_id": task_id,
                "total_runs": stats.get("total_runs", 0),
                "total_success": stats.get("total_success", 0),
                "total_items": stats.get("total_items", 0),
                "last_run_at": stats.get("last_run_at")
            }
        else:
            return {
                "task_id": task_id,
                "total_runs": 0,
                "total_success": 0,
                "total_items": 0,
                "last_run_at": None
            }
            
    except Exception as e:
        logger.error(f"Failed to get task count: {e}")
        raise HTTPException(status_code=500, detail=str(e))
