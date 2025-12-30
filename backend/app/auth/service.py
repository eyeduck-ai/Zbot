
import logging
import re
from app.db.client import get_supabase_client

logger = logging.getLogger(__name__)


def extract_doc_code(eip_id: str) -> str:
    """
    從 EIP 帳號擷取醫師代碼 (doc_code)
    
    範例:
        DOC4106F -> 4106
        DOC4050H -> 4050
        
    Args:
        eip_id: EIP 帳號 (如 DOC4106F)
        
    Returns:
        4 碼醫師代碼，若無法解析則回傳空字串
    """
    if not eip_id:
        return ""
    
    # 匹配 DOC + 4碼數字 + 1字母 的格式
    match = re.match(r'^DOC(\d{4})[A-Z]$', eip_id.upper())
    if match:
        return match.group(1)
    
    # 嘗試直接提取中間的數字
    digits = re.findall(r'\d+', eip_id)
    if digits and len(digits[0]) == 4:
        return digits[0]
    
    return ""

async def authenticate_platform_user(username: str, password: str):
    """
    驗證非 EIP 平台使用者 (如 admin, viewer)
    
    查詢 Supabase users 表，比對 eip_id 和 eip_psw
    
    Args:
        username: 平台帳號
        password: 密碼 (明文)
        
    Returns:
        使用者資訊 dict 或 None (驗證失敗)
    """
    supabase = get_supabase_client()
    
    try:
        res = supabase.table("users").select("*").eq("eip_id", username).execute()
        
        if res.data and len(res.data) > 0:
            user = res.data[0]
            stored_password = user.get("eip_psw", "")
            
            # 明文密碼比對
            if stored_password == password:
                logger.info(f"Platform user {username} authenticated successfully")
                return user
            else:
                logger.warning(f"Platform user {username} password mismatch")
                return None
        else:
            logger.warning(f"Platform user {username} not found")
            return None
            
    except Exception as e:
        logger.error(f"Platform auth error: {e}")
        return None


async def authenticate_user(username: str, password: str):
    """
    使用者驗證主入口
    
    邏輯:
    1. 帳號以 DOC 開頭 => 使用 EIP 內網驗證
    2. 其他帳號 => 查詢 Supabase users 表驗證
    
    Returns:
        DOC: VghClient on success (caller must close), None on failure
        非 DOC: dict with user info, or None on failure
    """
    from vghsdk.core import VghClient
    
    # 非 DOC 帳號: 使用 Supabase 平台驗證
    if not username.upper().startswith("DOC"):
        return await authenticate_platform_user(username, password)

    # DOC 帳號: 使用 EIP 內網驗證
    client = VghClient(eip_id=username, eip_psw=password)
    try:
        success = await client.ensure_eip()
        if success:
            return client  # 成功，回傳 client (caller 負責 close)
        else:
            await client.close()
            return None
        
    except Exception as e:
        logger.error(f"EIP auth error: {e}")
        await client.close()
        return None
        
from datetime import datetime
import json

async def fetch_eip_display_name(client, eip_id: str) -> str:
    """
    從 EIP 通訊錄 API 取得使用者姓名
    
    Args:
        client: 已登入的 VghClient
        eip_id: EIP 帳號 (如 DOC4050H)
        
    Returns:
        使用者姓名，若無法取得則回傳空字串
    """
    url = "https://eip.vghtpe.gov.tw/company/vghtpe_dashboard/vghtpe_dashboard_action.php?action=get_contact"
    
    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        
        res = await client.session.post(url, data={"keyword": eip_id}, headers=headers)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("ERROR_CODE") == "0" and data.get("DOC_RECORD_LIST"):
                name = data["DOC_RECORD_LIST"][0].get("NAME", "")
                if name:
                    logger.info(f"Fetched display_name for {eip_id}: {name}")
                    return name
        
        logger.warning(f"Could not fetch display_name for {eip_id}")
        return ""
        
    except Exception as e:
        logger.error(f"Error fetching display_name for {eip_id}: {e}")
        return ""


async def sync_user_to_supabase(username: str, password: str = None, vgh_client = None) -> bool:
    """
    Upsert user to Supabase 'users' table.
    Schema: eip_id, eip_psw, doc_code, display_name, last_login
    
    會自動從 eip_id (如 DOC4106F) 擷取 doc_code (如 4106)
    若提供 vgh_client 且已登入，會從 EIP 通訊錄取得姓名存入 display_name
    """
    supabase = get_supabase_client()
    now_iso = datetime.now().isoformat()
    
    # 擷取 doc_code
    doc_code = extract_doc_code(username)
    
    # Map to Schema
    data = {
        "eip_id": username,
        "doc_code": doc_code,
        "last_login": now_iso
    }
    
    if password:
        data["eip_psw"] = password
    
    # 從 EIP 取得 display_name
    if vgh_client:
        display_name = await fetch_eip_display_name(vgh_client, username)
        if display_name:
            data["display_name"] = display_name
    
    try:
        # Upsert based on unique key 'eip_id'
        supabase.table("users").upsert(data, on_conflict="eip_id").execute()
        logger.info(f"Synced user {username} (doc_code={doc_code}, display_name={data.get('display_name', 'N/A')}) to Supabase.")
        return True
    except Exception as e:
        logger.error(f"Supabase sync failed: {e}")
        return False

# 預設角色權限 (fallback when DB not available)
# 需與 Supabase settings.role_definitions 保持同步
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["*"],  # 管理員: 全部權限
    "vs": ["*"],  # 主治醫師: 全部權限
    "cr": ["note_", "opnote_", "dashboard_", "stats_", "ivi_"],  # CR: 全功能
    "basic_2": ["note_", "opnote_", "ivi_"],  # 奴工: IVI + Surgery
    "basic_1": ["note_ivi_", "opnote_", "ivi_"],  # 初心者Lv.1: 僅 IVI
    "basic_0": [],  # 初心者Lv.0: 無權限
    "": [],  # 未設定角色: 無權限
}

# 快取從 DB 讀取的角色定義
_cached_role_permissions: dict[str, list[str]] | None = None

def get_allowed_prefixes(role: str) -> list[str]:
    """
    取得角色允許的 Task ID 前綴列表
    
    優先使用快取的 DB 定義，fallback 到預設值
    
    Args:
        role: 使用者角色 (admin, basic, cr)
        
    Returns:
        允許的前綴列表，admin 回傳 ["*"]
    """
    global _cached_role_permissions
    
    # 優先使用快取 (由 /api/status 設定)
    if _cached_role_permissions:
        role_def = _cached_role_permissions.get(role, {})
        if isinstance(role_def, dict):
            return role_def.get("allowed_prefixes", [])
        return []
    
    # Fallback 到預設值
    return DEFAULT_ROLE_PERMISSIONS.get(role, [])

def set_cached_role_permissions(roles: dict):
    """設定快取的角色權限 (由 /api/status 調用)"""
    global _cached_role_permissions
    _cached_role_permissions = roles


def check_task_permission(role: str, task_id: str) -> bool:
    """
    檢查角色是否有權限執行指定 Task
    
    Args:
        role: 使用者角色 (admin, basic, cr)
        task_id: Task ID (如 note_ivi_submit)
        
    Returns:
        True 表示有權限執行
    """
    prefixes = get_allowed_prefixes(role)
    
    # Admin 或有 * 前綴表示全部權限
    if "*" in prefixes:
        return True
    
    # 檢查 task_id 是否符合任一允許的前綴
    return any(task_id.startswith(prefix) for prefix in prefixes)


async def get_user_permissions(username: str) -> dict:
    """
    Fetch user role, display_name, doc_code and allowed prefixes from Supabase.
    
    Queries:
    - users table for display_name, doc_code, and role
    
    Returns:
        dict with 'role', 'display_name', 'doc_code' and 'allowed_prefixes' keys
    """
    # Admin bypass
    if username == "admin":
        return {"user_id": None, "role": "admin", "display_name": "管理者", "doc_code": "", "allowed_prefixes": ["*"]}

    client = get_supabase_client()
    try:
        # Query users table for user info (including role)
        user_res = client.table("users").select("id, display_name, doc_code, role").eq("eip_id", username).execute()
        
        if not user_res.data or len(user_res.data) == 0:
            # User not found
            return {"user_id": None, "role": "", "display_name": username, "doc_code": "", "allowed_prefixes": []}
        
        user = user_res.data[0]
        user_id = user.get("id")
        display_name = user.get("display_name", "") or username
        doc_code = user.get("doc_code", "")
        role = (user.get("role", "") or "").strip().lower()
        
        # Normalize legacy values
        if role in ["all", "*"]:
            role = "admin"
        
        allowed_prefixes = get_allowed_prefixes(role)
        return {
            "user_id": user_id,
            "role": role, 
            "display_name": display_name, 
            "doc_code": doc_code,
            "allowed_prefixes": allowed_prefixes
        }
        
    except Exception as e:
        logger.error(f"Permission fetch error: {e}")
        return {"user_id": None, "role": "", "display_name": username, "doc_code": "", "allowed_prefixes": []}

