
import uuid
import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Set
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(BaseModel):
    id: str
    task_id: str
    status: JobStatus
    params: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    progress: int = 0  # 0-100
    cancelled: bool = False  # 取消標記
    # Checkpoint 支援 (斷點續跑)
    total_items: int = 0  # 總項目數
    completed_keys: Set[str] = Field(default_factory=set)  # 已完成項目 keys
    progress_message: str = ""  # 進度訊息

class JobManager:
    _instance = None
    _jobs: Dict[str, Job] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def create_job(cls, task_id: str, params: Dict[str, Any]) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            task_id=task_id,
            status=JobStatus.PENDING,
            params=params,
            created_at=datetime.datetime.now(),
            progress=0,
            cancelled=False
        )
        cls._jobs[job_id] = job
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Job]:
        return cls._jobs.get(job_id)

    @classmethod
    def list_jobs(cls, status: str = None, limit: int = 20) -> List[Job]:
        """列出最近的 jobs，可依 status 過濾"""
        jobs = list(cls._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        """標記 job 為已取消"""
        if job_id in cls._jobs:
            cls._jobs[job_id].cancelled = True
            return True
        return False

    @classmethod
    def is_cancelled(cls, job_id: str) -> bool:
        """檢查 job 是否已被取消"""
        job = cls._jobs.get(job_id)
        return job.cancelled if job else False

    @classmethod
    def update_job(cls, job_id: str, status: JobStatus = None, result: Any = None, error: str = None, progress: int = None, message: str = None):
        if job_id in cls._jobs:
            job = cls._jobs[job_id]
            if status:
                job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            if progress is not None:
                job.progress = progress
            if message is not None:
                job.progress_message = message
                
            if status in [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.datetime.now()
                if status == JobStatus.SUCCESS:
                    job.progress = 100
    
    # --- Checkpoint Methods (斷點續跑支援) ---
    
    @classmethod
    def set_total_items(cls, job_id: str, total: int):
        """設定任務的總項目數"""
        job = cls._jobs.get(job_id)
        if job:
            job.total_items = total
    
    @classmethod
    def mark_item_completed(cls, job_id: str, key: str, message: str = ""):
        """
        標記單一項目完成，並自動計算進度百分比。
        
        Args:
            job_id: Job ID
            key: 項目的唯一識別 key (如手術碼)
            message: 進度訊息 (可選)
        """
        job = cls._jobs.get(job_id)
        if job:
            job.completed_keys.add(key)
            job.progress_message = message
            if job.total_items > 0:
                job.progress = int(len(job.completed_keys) / job.total_items * 100)
    
    @classmethod
    def is_item_completed(cls, job_id: str, key: str) -> bool:
        """檢查項目是否已完成"""
        job = cls._jobs.get(job_id)
        return key in job.completed_keys if job and job.completed_keys else False

