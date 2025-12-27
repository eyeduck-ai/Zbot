"""
RLS Context Middleware

自動從請求中提取 JWT 並設定到 context，
讓 Supabase client 在 RLS 模式下能自動使用正確的 JWT。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.db.client import set_current_user_jwt


class RLSContextMiddleware(BaseHTTPMiddleware):
    """
    RLS Context Middleware
    
    從 Authorization header 提取 JWT 並設定到 context variable，
    讓後續的 Supabase client 調用能自動帶入 JWT。
    """
    
    async def dispatch(self, request: Request, call_next):
        # 提取 Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if auth_header.startswith("Bearer "):
            jwt = auth_header[7:]  # 移除 "Bearer " 前綴
            set_current_user_jwt(jwt)
        else:
            set_current_user_jwt("")
        
        response = await call_next(request)
        return response
