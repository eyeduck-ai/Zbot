"""
Config API Router - 設定檔管理 API

提供前端檢查和建立設定檔的功能。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from typing import Optional

from app.core.config_manager import (
    config_exists,
    get_config_path,
    load_config,
    save_config,
    get_config_for_display,
)
from app.core.logger import logger

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigStatus(BaseModel):
    """設定檔狀態"""
    exists: bool
    path: str


class ConfigData(BaseModel):
    """設定資料"""
    supabase_url: str
    supabase_key: str
    dev_mode: bool = False
    log_level: str = "INFO"
    # 進階設定（可選）
    test_eip_id: Optional[str] = ""
    test_eip_psw: Optional[str] = ""
    
    @validator("supabase_url")
    def validate_url(cls, v):
        if not v.startswith("https://") or not v.endswith(".supabase.co"):
            raise ValueError("Invalid Supabase URL format")
        return v
    
    @validator("supabase_key")
    def validate_key(cls, v):
        if len(v) < 20:
            raise ValueError("Invalid Supabase Key")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class ConfigTestRequest(BaseModel):
    """連線測試請求"""
    supabase_url: str
    supabase_key: str


@router.get("/status", response_model=ConfigStatus)
def get_config_status():
    """
    檢查設定檔狀態
    
    Returns:
        exists: 設定檔是否存在
        path: 設定檔路徑（若不存在則為預設寫入路徑）
    """
    exists = config_exists()
    path = str(get_config_path())
    
    return ConfigStatus(exists=exists, path=path)


@router.get("")
def get_current_config():
    """
    取得目前設定（敏感資料遮罩）
    
    若設定檔不存在，回傳錯誤
    """
    if not config_exists():
        raise HTTPException(status_code=404, detail="Config not found")
    
    return get_config_for_display()


@router.post("")
def create_or_update_config(data: ConfigData):
    """
    儲存設定檔
    
    Args:
        data: 設定資料
    
    Returns:
        success: 是否成功
        path: 儲存的路徑
    """
    try:
        config_dict = data.dict()
        
        # Check for existing config to handle masked key
        if config_exists():
            existing = load_config()
            existing_key = existing.get("supabase_key", "")
            
            # Reconstruct the masked key to compare
            masked_key = "***"
            if len(existing_key) > 20:
                masked_key = existing_key[:10] + "..." + existing_key[-10:]
            
            # If the submitted key matches the masked version, keep the original key
            if data.supabase_key == masked_key:
                config_dict["supabase_key"] = existing_key
                logger.info("Preserved existing supabase_key (received masked value)")

        path = save_config(config_dict)
        
        logger.info(f"Config saved to: {path}")
        
        return {
            "success": True,
            "path": str(path),
            "message": "設定檔已儲存"
        }
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
def test_supabase_connection(data: ConfigTestRequest):
    """
    測試 Supabase 連線
    
    使用提供的 URL 和 Key 嘗試連線 Supabase
    透過實際發送請求驗證 key 有效性
    """
    import httpx
    
    try:
        # 基本格式驗證
        if not data.supabase_url.startswith("https://"):
            return {"success": False, "message": "URL 必須以 https:// 開頭"}
        
        if not data.supabase_url.endswith(".supabase.co"):
            return {"success": False, "message": "URL 格式錯誤，應為 https://xxx.supabase.co"}
        
        # 使用 REST API 直接驗證 key
        # 這會發送實際的網路請求，如果 key 無效會返回 401
        api_url = f"{data.supabase_url}/rest/v1/"
        
        headers = {
            "apikey": data.supabase_key,
            "Authorization": f"Bearer {data.supabase_key}",
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(api_url, headers=headers)
        
        # 200 = 連線成功，取得 schema 資訊
        # 401 = key 無效
        # 其他狀態碼也可能表示連線問題
        if response.status_code == 200:
            return {"success": True, "message": "連線成功！"}
        elif response.status_code == 401:
            return {"success": False, "message": "API Key 無效，請確認 Key 是否正確"}
        else:
            return {"success": False, "message": f"連線失敗 (HTTP {response.status_code})"}

    except httpx.ConnectError:
        return {"success": False, "message": "無法連線到 Supabase，請檢查 URL 或網路"}
    except httpx.TimeoutException:
        return {"success": False, "message": "連線逾時，請稍後再試"}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Supabase connection test failed: {error_msg}")
        return {"success": False, "message": f"連線失敗: {error_msg}"}
