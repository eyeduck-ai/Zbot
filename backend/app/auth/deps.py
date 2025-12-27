from typing import Optional, Union, Any
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.config import get_settings

# JWT 設定
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 Hours

# 取得 Supabase JWT Secret (用於 RLS)
_settings = get_settings()
SUPABASE_JWT_SECRET = _settings.SUPABASE_JWT_SECRET

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: str = ""
    allowed_prefixes: list[str] = []

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str = ""  # admin, basic, cr
    allowed_prefixes: list[str] = []

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    建立 Supabase RLS 相容的 JWT Token
    
    使用 Supabase JWT Secret 簽名，並包含 Supabase 所需的標準欄位
    
    注意: 
    - 'role' 欄位是 Supabase 資料庫角色 (authenticated/anon)，不是應用程式角色
    - 應用程式角色存在 'app_role' 欄位中，但 RLS 政策使用自訂欄位如 'eip_id', 'doc_code'
    """
    import time
    
    now_ts = int(time.time())
    
    if expires_delta:
        expire_ts = now_ts + int(expires_delta.total_seconds())
    else:
        expire_ts = now_ts + 15 * 60  # 15 minutes
    
    # 提取應用程式角色並設定 Supabase 資料庫角色
    zbot_role = data.pop("role", "")
    
    # Supabase RLS 所需的標準欄位
    to_encode = {
        "aud": "authenticated",       # Supabase 標準 audience
        "role": "authenticated",      # Supabase 資料庫角色 (重要!)
        "iss": "zbot",                # Issuer
        "iat": now_ts,
        "exp": expire_ts,
        "zbot_role": zbot_role,       # Zbot 應用程式角色 (admin, basic_0, basic_1, etc.)
        **data  # 包含 sub, doc_code, display_name, allowed_prefixes, eip_id
    }
    
    # 使用 Supabase JWT Secret 簽名 (讓 RLS 能識別)
    encoded_jwt = jwt.encode(to_encode, SUPABASE_JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 使用 Supabase JWT Secret 驗證
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=[ALGORITHM], options={"verify_aud": False})
        username: str = payload.get("sub")
        # 注意: 'role' 是 Supabase RLS 角色 (authenticated)，應用程式角色存在 'zbot_role'
        role: str = payload.get("zbot_role", "")
        allowed_prefixes: list = payload.get("allowed_prefixes", [])
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role, allowed_prefixes=allowed_prefixes)
    except jwt.JWTError:
        raise credentials_exception
    
    # In a full DB app, we would fetch user from DB here to verify active status.
    # For now, we trust the token (stateless).
    return User(username=token_data.username, role=token_data.role, allowed_prefixes=token_data.allowed_prefixes)

async def get_current_admin_user(current_user: User = Depends(get_current_user)):
    # Placeholder for role check
    if current_user.role != "admin":
        # Pass for now or implement DB check
        pass 
    return current_user
