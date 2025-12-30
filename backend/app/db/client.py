"""
Supabase Client

支援 RLS：
- 建立 client 時使用 publishable key (apikey header)
- 每個請求帶上用戶的 JWT (Authorization header) 以通過 RLS
"""

from contextvars import ContextVar
from supabase import create_client, Client
from app.config import get_settings

import logging

logger = logging.getLogger(__name__)

# Context variable for storing current user's JWT (for RLS)
_current_user_jwt: ContextVar[str] = ContextVar("current_user_jwt", default="")

# Cached base client (singleton, without user context)
_client: Client = None


def set_current_user_jwt(jwt: str):
    """
    設定當前請求的使用者 JWT (由 middleware 調用)
    
    此 JWT 用於 Supabase RLS 驗證
    """
    _current_user_jwt.set(jwt)


def get_current_user_jwt() -> str:
    """取得當前用戶的 JWT"""
    return _current_user_jwt.get()


def get_supabase_client(use_user_jwt: bool = True) -> Client:
    """
    取得 Supabase Client
    
    Args:
        use_user_jwt: 是否使用用戶 JWT（預設 True，用於 RLS）
                      設為 False 時只使用 API key
    
    Returns:
        Supabase Client
        
    RLS 注意事項：
    - apikey header: 始終使用 Supabase API key
    - Authorization header: 使用用戶 JWT（如果有的話），讓 RLS 能識別用戶
    """
    settings = get_settings()
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in config")
    
    # 如果需要使用用戶 JWT，每次都要建立新的 client 帶上 JWT
    if use_user_jwt:
        user_jwt = _current_user_jwt.get()
        if user_jwt:
            # 建立 client 時使用 API key（不是用戶 JWT！）
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            
            # 設定用戶 JWT 到 Authorization header（用於 RLS）
            if hasattr(client, 'postgrest') and hasattr(client.postgrest, 'session'):
                client.postgrest.session.headers['Authorization'] = f'Bearer {user_jwt}'
            
            return client
    
    # 無用戶 JWT 或不需要時，使用 cached client
    global _client
    if _client is None:
        logger.info(f"Initializing Supabase Client...")
        logger.info(f"URL: {settings.SUPABASE_URL}")
        # Log first 10 chars of key for debugging
        masked_key = settings.SUPABASE_KEY[:15] + "..." if settings.SUPABASE_KEY else "None"
        logger.info(f"KEY: {masked_key}")

        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info(f"Supabase client initialized.")
    
    return _client


def reset_client():
    """重設 client（設定變更後呼叫）"""
    global _client
    _client = None


# 相容舊程式碼的別名
def get_supabase_admin_client() -> Client:
    """
    [相容性別名] 取得 Supabase Client (不使用用戶 JWT)
    
    此函數繞過 RLS，用於管理操作
    """
    return get_supabase_client(use_user_jwt=False)
