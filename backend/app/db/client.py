"""
Supabase Client

簡化版本：統一使用 SUPABASE_KEY 建立 client
Key 類型（anon 或 service_role）由使用者填入的值決定權限
"""

from contextvars import ContextVar
from supabase import create_client, Client
from app.config import get_settings

import logging

logger = logging.getLogger(__name__)

# Context variable for storing current user's JWT (for compatibility)
_current_user_jwt: ContextVar[str] = ContextVar("current_user_jwt", default="")

# Cached client (singleton)
_client: Client = None


def set_current_user_jwt(jwt: str):
    """
    設定當前請求的使用者 JWT (由 middleware 調用)
    
    注意：此函數保留以維持向下相容，但目前簡化版 client 不使用此值
    """
    _current_user_jwt.set(jwt)


def get_supabase_client() -> Client:
    """
    取得 Supabase Client
    
    使用 settings 中的 SUPABASE_KEY，權限由 key 類型自動決定：
    - anon key: 受 RLS 限制
    - service_role key: 繞過 RLS
    
    Returns:
        Supabase Client (cached singleton)
    """
    global _client
    
    if _client is None:
        settings = get_settings()
        
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in config")
        
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info(f"Supabase client initialized for: {settings.SUPABASE_URL}")
    
    return _client


def reset_client():
    """重設 client（設定變更後呼叫）"""
    global _client
    _client = None


# 相容舊程式碼的別名
def get_supabase_admin_client() -> Client:
    """
    [相容性別名] 取得 Supabase Client
    
    此函數為向下相容保留，行為等同 get_supabase_client()
    """
    return get_supabase_client()
