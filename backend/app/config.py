
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


class Settings:
    """
    應用程式設定
    
    設定來源優先順序：
    1. config.json (程式目錄或使用者目錄)
    2. .env 檔案 (向下相容)
    """
    
    _instance: Optional["Settings"] = None
    
    def __init__(self):
        from app.core.config_manager import load_config
        
        config = load_config()
        
        # Supabase 設定
        self.SUPABASE_URL: str = config.get("supabase_url", "")
        self.SUPABASE_KEY: str = config.get("supabase_key", "")
        
        # 開發模式
        self.DEV_MODE: bool = config.get("dev_mode", False)
        
        # 日誌等級
        self.LOG_LEVEL: str = config.get("log_level", "INFO")
        
        # 進階設定（手動編輯）
        self.TEST_EIP_ID: str = config.get("test_eip_id", "")
        self.TEST_EIP_PSW: str = config.get("test_eip_psw", "")
        
        # JWT Secret (硬編碼，不需使用者設定)
        self.SUPABASE_JWT_SECRET: str = "aVffTIvzzmREbZNdfFotPKhY0cXdenWpgPKxz6JYarc7pbec2GDylW8OBiKThcNa+hc3jA5l2e0Chz7JVOY+/w=="
        
        logger.info(f"Settings loaded: SUPABASE_URL={self.SUPABASE_URL[:30] if self.SUPABASE_URL else 'not set'}...")


@lru_cache()
def get_settings() -> Settings:
    """取得設定單例"""
    return Settings()


def reload_settings():
    """重新載入設定（設定變更後呼叫）"""
    get_settings.cache_clear()
    from app.core.config_manager import load_config
    load_config(force_reload=True)
    return get_settings()
