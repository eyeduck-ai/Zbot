"""
Task Logger - 任務使用追蹤服務

記錄所有任務執行情況到 Supabase，並維護統計快取。
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.db.client import get_supabase_admin_client

logger = logging.getLogger(__name__)


class TaskLogger:
    """
    任務日誌記錄服務
    
    負責：
    1. 記錄任務執行詳情到 task_logs 表
    2. 更新 task_stats 統計表
    """
    
    @classmethod
    async def log_task_completion(
        cls,
        task_id: str,
        job_id: str,
        operator_eip_id: str,
        status: str,
        items_processed: int = 0,
        target_doc_code: Optional[str] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        記錄任務完成並更新統計
        
        Args:
            task_id: 任務識別碼 (如 note_surgery_submit)
            job_id: Job UUID
            operator_eip_id: 操作者帳號
            status: 執行狀態 (success / failed / cancelled)
            items_processed: 處理筆數
            target_doc_code: 目標醫師代碼 (若適用)
            error_message: 錯誤訊息 (若失敗)
            started_at: 開始時間
            completed_at: 完成時間
            metadata: 額外資訊
        """
        try:
            supabase = get_supabase_admin_client()
            now = datetime.now()
            
            # 1. 插入 task_logs
            log_data = {
                "task_id": task_id,
                "job_id": job_id,
                "operator_eip_id": operator_eip_id,
                "status": status,
                "items_processed": items_processed,
                "target_doc_code": target_doc_code,
                "error_message": error_message,
                "started_at": (started_at or now).isoformat(),
                "completed_at": (completed_at or now).isoformat(),
                "metadata": metadata
            }
            
            supabase.table("task_logs").insert(log_data).execute()
            logger.info(f"Task log recorded: {task_id} ({status}, {items_processed} items)")
            
            # 2. 更新 task_stats (UPSERT)
            await cls._update_stats(task_id, status, items_processed, completed_at or now)
            
        except Exception as e:
            # 日誌記錄失敗不應影響主流程
            logger.error(f"Failed to log task completion: {e}")
    
    @classmethod
    async def _update_stats(
        cls, 
        task_id: str, 
        status: str, 
        items_processed: int,
        run_time: datetime
    ) -> None:
        """
        更新 task_stats 統計表
        
        使用 PostgreSQL RPC 函數實現原子操作，避免並發時的 race condition
        """
        try:
            supabase = get_supabase_admin_client()
            
            # 使用 RPC 呼叫 PostgreSQL 函數進行原子更新
            # 如果 RPC 不存在，則 fallback 到傳統方式
            try:
                supabase.rpc("increment_task_stats", {
                    "p_task_id": task_id,
                    "p_is_success": status == "success",
                    "p_items": items_processed,
                    "p_run_time": run_time.isoformat()
                }).execute()
                logger.debug(f"Task stats updated atomically for {task_id}")
                return
            except Exception as rpc_error:
                logger.warning(f"RPC increment_task_stats failed, fallback to traditional upsert: {rpc_error}")
            
            # Fallback: 使用 UPSERT (仍可能有 race condition，但較少見)
            result = supabase.table("task_stats") \
                .select("*") \
                .eq("task_id", task_id) \
                .execute()
            
            if result.data:
                # 更新現有記錄
                current = result.data[0]
                new_total_runs = current.get("total_runs", 0) + 1
                new_total_success = current.get("total_success", 0) + (1 if status == "success" else 0)
                new_total_items = current.get("total_items", 0) + items_processed
                
                supabase.table("task_stats") \
                    .update({
                        "total_runs": new_total_runs,
                        "total_success": new_total_success,
                        "total_items": new_total_items,
                        "last_run_at": run_time.isoformat()
                    }) \
                    .eq("task_id", task_id) \
                    .execute()
            else:
                # 插入新記錄
                supabase.table("task_stats") \
                    .insert({
                        "task_id": task_id,
                        "total_runs": 1,
                        "total_success": 1 if status == "success" else 0,
                        "total_items": items_processed,
                        "last_run_at": run_time.isoformat()
                    }) \
                    .execute()
            
            logger.debug(f"Task stats updated for {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to update task stats: {e}")
    
    @classmethod
    async def get_task_stats(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        取得單一任務的統計資料
        
        Args:
            task_id: 任務識別碼
            
        Returns:
            統計資料 dict 或 None
        """
        try:
            supabase = get_supabase_admin_client()
            result = supabase.table("task_stats") \
                .select("*") \
                .eq("task_id", task_id) \
                .execute()
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to get task stats: {e}")
            return None
    
    @classmethod
    async def get_all_stats(cls) -> list:
        """
        取得所有任務的統計資料
        
        Returns:
            統計資料列表
        """
        try:
            supabase = get_supabase_admin_client()
            result = supabase.table("task_stats") \
                .select("*") \
                .order("total_runs", desc=True) \
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to get all task stats: {e}")
            return []
