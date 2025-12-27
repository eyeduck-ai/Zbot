from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.registry import TaskRegistry
from app.core.jobs import JobManager, JobStatus
from app.core.task_logger import TaskLogger
from vghsdk.core import SessionManager
from app.auth.service import check_task_permission
from app.core.loader import register_all_tasks

# Register tasks on startup (or import time if side-effects allowed)
register_all_tasks() 


import logging
import asyncio
from app.auth.deps import get_current_user, User

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

class JobCreate(BaseModel):
    params: Dict[str, Any] = {}
    eip_id: Optional[str] = None
    eip_psw: Optional[str] = None

class JobOut(BaseModel):
    job_id: str
    status: str

async def run_crawler_job(job_id: str, task_id: str, params: Dict[str, Any], eip_id: str, eip_psw: str):
    """
    Background logic to run the crawler.
    """
    logger.info(f"Starting job {job_id} for task {task_id}")
    JobManager.update_job(job_id, JobStatus.RUNNING)
    started_at = datetime.now()
    
    task = TaskRegistry.get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found during execution")
        JobManager.update_job(job_id, JobStatus.FAILED, error="Task not found")
        return

    # Initialize SDK components
    # NOTE: Here we need to decide how to handle authentication.
    # We can create a temporary BaseCrawler just to get the session/auth logic,
    # or pass a session to the task.
    # The CrawlerTask.run method signature expects (params, session).
    
    # Use SessionManager to get persistent crawler instance
    # from vghsdk.core import BaseCrawler # Removed direct import
    from vghsdk.core import SessionManager
    import os
    
    # Use provided creds or fallback to config (for easier testing)
    from app.config import get_settings
    settings = get_settings()
    actual_eip_id = eip_id or settings.TEST_EIP_ID
    actual_eip_psw = eip_psw or settings.TEST_EIP_PSW
    
    if not actual_eip_id or not actual_eip_psw:
         JobManager.update_job(job_id, JobStatus.FAILED, error="Missing credentials")
         return

    # Get Persistent Client from Pool
    client = SessionManager.get_client(actual_eip_id, actual_eip_psw)
    
    try:
        # Check login state (fast check inside ensure_eip if already logged in)
        login_success = await client.ensure_eip()
        if not login_success:
             JobManager.update_job(job_id, JobStatus.FAILED, error="Login failed")
             return
             
        # Parse params into the specific Pydantic model for the task
        # Router validates and converts dict -> Pydantic model
        # Task.run() receives the validated model directly
        if task.params_model:
            try:
                task_params = task.params_model(**params) if params else task.params_model()
            except Exception as e:
                JobManager.update_job(job_id, JobStatus.FAILED, error=f"Invalid parameters: {e}")
                return
        else:
            task_params = params if params else {}

        # Define Progress Callback with job_id closure
        # Tasks can call progress_callback.get_job_id() to check cancellation
        async def progress_callback(progress: int, message: str = None):
            JobManager.update_job(job_id, progress=progress)
            if message:
                logger.debug(f"Job {job_id} progress {progress}%: {message}")
        
        # Attach job_id to progress_callback for cancellation checking
        progress_callback.job_id = job_id

        # Execute task
        try:
             result = await task.run(task_params, client, progress_callback=progress_callback)
        except TypeError as te:
             logger.warning(f"Task {task.id} might not support progress_callback: {te}")
             result = await task.run(task_params, client)
        
        # 檢查 result 是否為取消狀態
        result_status = getattr(result, 'status', None) if hasattr(result, 'status') else (result.get('status') if isinstance(result, dict) else None)
        
        # 從 result 取得處理筆數
        # 任務類型決定計算方式：
        # - note_ivi_submit, note_surgery_submit: 按「筆」計算 (success 欄位)
        # - dashboard_bed, stats_fee, stats_op: 按「次」計算 (一次執行 = 1)
        items_processed = 0
        
        # 只有 IVI 和 Surgery 送出任務按筆計算
        per_item_tasks = ['note_ivi_submit', 'note_surgery_submit']
        
        if task_id in per_item_tasks:
            # 按筆計算：使用 success 欄位
            if hasattr(result, 'success'):
                val = getattr(result, 'success', 0)
                if val and val > 0:
                    items_processed = val
            elif isinstance(result, dict) and 'success' in result:
                val = result.get('success', 0)
                if val and val > 0:
                    items_processed = val
        
        # 成功完成的任務至少算 1 次執行
        if items_processed == 0 and result_status != 'cancelled' and result_status != 'error':
            items_processed = 1
        
        completed_at = datetime.now()
        target_doc_code = params.get('doc_code')
        
        if result_status == 'cancelled':
            JobManager.update_job(job_id, JobStatus.CANCELLED, result=result)
            await TaskLogger.log_task_completion(
                task_id=task_id, job_id=job_id, operator_eip_id=actual_eip_id,
                status="cancelled", items_processed=items_processed,
                started_at=started_at, completed_at=completed_at,
                target_doc_code=target_doc_code
            )
        else:
            # 檢查 result.status 是否為 error
            final_status = "failed" if result_status == "error" else "success"
            JobManager.update_job(job_id, JobStatus.SUCCESS, result=result)
            await TaskLogger.log_task_completion(
                task_id=task_id, job_id=job_id, operator_eip_id=actual_eip_id,
                status=final_status, items_processed=items_processed,
                started_at=started_at, completed_at=completed_at,
                target_doc_code=target_doc_code
            )
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed with exception")
        JobManager.update_job(job_id, JobStatus.FAILED, error=str(e))
        await TaskLogger.log_task_completion(
            task_id=task_id, job_id=job_id, operator_eip_id=actual_eip_id,
            status="failed", error_message=str(e),
            started_at=started_at, completed_at=datetime.now(),
            target_doc_code=params.get('doc_code')
        )
    # finally:
    #     await crawler_ctx.close() # REMOVED: Keep session alive for pool reuse


@router.get("")
def list_tasks(current_user: User = Depends(get_current_user)):
    """
    List available crawler tasks for the current user.
    Returns all tasks with 'allowed' field indicating if user can run each task.
    """
    all_tasks = TaskRegistry.list_tasks()
    
    # Add 'allowed' field to each task based on user role
    result = []
    for task in all_tasks:
        task_with_permission = task.copy()
        task_with_permission["allowed"] = check_task_permission(current_user.role, task["id"])
        result.append(task_with_permission)
    
    return result

@router.post("/{task_id}/run", response_model=JobOut)
async def run_task(
    task_id: str, 
    request: JobCreate, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a crawler task.
    """
    task = TaskRegistry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Permission Check using prefix matching
    if not check_task_permission(current_user.role, task_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"無此權限: 角色 '{current_user.role}' 無法執行 '{task_id}'"
        )

    job = JobManager.create_job(task_id, request.params)
    
    # Inject job_id into params for progress tracking
    task_params = request.params.copy()
    task_params['_job_id'] = job.id
    
    background_tasks.add_task(
        run_crawler_job, 
        job.id, 
        task_id, 
        task_params, 
        request.eip_id, 
        request.eip_psw
    )
    
    return {"job_id": job.id, "status": "pending"}

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """
    Get the status of a specific job.
    """
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs")
def list_jobs(status: str = None, limit: int = 20):
    """
    列出所有 jobs (支援過濾)。
    
    Args:
        status: 過濾狀態 (pending, running, success, failed, cancelled)
        limit: 最多回傳數量 (預設 20)
    """
    jobs = JobManager.list_jobs(status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}

@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, current_user: User = Depends(get_current_user)):
    """
    取消指定的 job。
    """
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (already completed)")
    JobManager.cancel_job(job_id)
    JobManager.update_job(job_id, JobStatus.CANCELLED)
    return {"message": "Job cancelled", "job_id": job_id}
