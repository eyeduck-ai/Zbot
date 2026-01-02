"""
快取管理服務 (CacheManager)

用於暫存已爬取但尚未成功上傳到 Google Sheets 的資料。
- 48 小時自動過期
- 每個任務只保留最新一筆快取
- JSON 檔案儲存於 backend/cache/{task_id}/
"""

import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 快取目錄 (相對於 backend/)
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_TTL_HOURS = 48  # 2 天


class CacheManager:
    """本地 JSON 快取管理器"""
    
    @classmethod
    def _ensure_dir(cls, task_id: str) -> Path:
        """確保快取目錄存在"""
        cache_path = CACHE_DIR / task_id
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path
    
    @classmethod
    def _cleanup_old_caches(cls, task_id: str) -> int:
        """
        清理該任務的舊快取，只保留最新一筆
        
        Args:
            task_id: 任務 ID
            
        Returns:
            刪除的快取數量
        """
        cache_path = CACHE_DIR / task_id
        if not cache_path.exists():
            return 0
        
        # 讀取所有快取並按時間排序
        caches = []
        for file_path in cache_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                caches.append({
                    "path": file_path,
                    "created_at": content.get("created_at", "")
                })
            except:
                pass
        
        # 刪除所有舊的快取 (只在有多個時)
        deleted = 0
        if len(caches) > 0:
            # 按建立時間排序，刪除全部 (因為待會會新增一筆)
            for cache in caches:
                try:
                    cache["path"].unlink()
                    deleted += 1
                except:
                    pass
        
        return deleted
    
    @classmethod
    def save_cache(
        cls,
        task_id: str,
        params: Dict[str, Any],
        data: Any,
        target_info: Dict[str, Any]
    ) -> str:
        """
        儲存快取 (會先刪除該任務的舊快取)
        
        Args:
            task_id: 任務 ID (如 'stats_fee_update')
            params: 任務參數 (用於顯示)
            data: 爬取的資料
            target_info: 目標資訊 (sheet_id, worksheet 等)
            
        Returns:
            cache_id: 快取識別碼
        """
        # 先清理該任務的舊快取
        deleted = cls._cleanup_old_caches(task_id)
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old cache(s) for {task_id}")
        
        cache_id = uuid.uuid4().hex[:12]
        cache_path = cls._ensure_dir(task_id)
        
        now = datetime.now()
        cache_content = {
            "id": cache_id,
            "task_id": task_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=CACHE_TTL_HOURS)).isoformat(),
            "params": params,
            "target_info": target_info,
            "data": data,
        }
        
        file_path = cache_path / f"{cache_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cache_content, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Cache saved: {task_id}/{cache_id}")
        return cache_id
    
    @classmethod
    def get_cache(cls, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        讀取特定快取
        
        Args:
            cache_id: 快取 ID
            
        Returns:
            快取內容，若不存在或已過期則返回 None
        """
        # 搜尋所有任務目錄
        if not CACHE_DIR.exists():
            return None
            
        for task_dir in CACHE_DIR.iterdir():
            if not task_dir.is_dir():
                continue
            file_path = task_dir / f"{cache_id}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    
                    # 檢查是否過期
                    expires_at = datetime.fromisoformat(content["expires_at"])
                    if datetime.now() > expires_at:
                        cls.delete_cache(cache_id)
                        return None
                    
                    return content
                except Exception as e:
                    logger.error(f"Failed to read cache {cache_id}: {e}")
                    return None
        return None
    
    @classmethod
    def list_caches(cls, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出快取 (不含資料內容，僅元資料)
        
        Args:
            task_id: 若指定則只列出該任務的快取
            
        Returns:
            快取列表 (不含 data 欄位)
        """
        cls.cleanup_expired()  # 先清理過期的
        
        result = []
        if not CACHE_DIR.exists():
            return result
        
        dirs_to_scan = [CACHE_DIR / task_id] if task_id else CACHE_DIR.iterdir()
        
        for task_dir in dirs_to_scan:
            if not isinstance(task_dir, Path):
                task_dir = Path(task_dir)
            if not task_dir.exists() or not task_dir.is_dir():
                continue
                
            for file_path in task_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    
                    # 檢查是否過期
                    expires_at = datetime.fromisoformat(content["expires_at"])
                    if datetime.now() > expires_at:
                        continue
                    
                    # 只返回元資料
                    result.append({
                        "id": content["id"],
                        "task_id": content["task_id"],
                        "created_at": content["created_at"],
                        "expires_at": content["expires_at"],
                        "params": content.get("params", {}),
                        "size_bytes": file_path.stat().st_size,
                    })
                except Exception as e:
                    logger.warning(f"Failed to read cache file {file_path}: {e}")
        
        # 按建立時間排序 (最新在前)
        result.sort(key=lambda x: x["created_at"], reverse=True)
        return result
    
    @classmethod
    def delete_cache(cls, cache_id: str) -> bool:
        """
        刪除快取
        
        Args:
            cache_id: 快取 ID
            
        Returns:
            是否成功刪除
        """
        if not CACHE_DIR.exists():
            return False
            
        for task_dir in CACHE_DIR.iterdir():
            if not task_dir.is_dir():
                continue
            file_path = task_dir / f"{cache_id}.json"
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"Cache deleted: {cache_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete cache {cache_id}: {e}")
                    return False
        return False
    
    @classmethod
    def cleanup_expired(cls) -> int:
        """
        清理過期快取
        
        Returns:
            刪除的快取數量
        """
        deleted_count = 0
        if not CACHE_DIR.exists():
            return 0
            
        for task_dir in CACHE_DIR.iterdir():
            if not task_dir.is_dir():
                continue
            for file_path in task_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                    expires_at = datetime.fromisoformat(content["expires_at"])
                    if datetime.now() > expires_at:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Expired cache deleted: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Error during cleanup {file_path}: {e}")
        
        return deleted_count
    
    @classmethod
    def check_existing(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        檢查特定任務是否有待上傳的快取
        
        Args:
            task_id: 任務 ID
            
        Returns:
            若有則返回最新的快取元資料，否則返回 None
        """
        caches = cls.list_caches(task_id)
        return caches[0] if caches else None
