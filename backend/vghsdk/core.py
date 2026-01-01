
import httpx
import logging
import random
import asyncio
import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Type, Any, Callable, Awaitable
from abc import ABC, abstractmethod
from pydantic import BaseModel

logger = logging.getLogger("vghsdk.core")


# --- 0. Crawler Configuration (集中設定) ---

@dataclass
class CrawlerConfig:
    """
    爬蟲全域設定 - 統一管理所有參數
    
    使用方式: 直接修改 CRAWLER_CONFIG 實例的屬性，或建立新的 CrawlerConfig 實例。
    """
    # Rate Limit (正常請求延遲，模擬人類操作)
    rate_limit_min: float = 0.6        # 最小延遲秒數
    rate_limit_max: float = 1.2        # 最大延遲秒數
    
    # Retry Settings (重試設定)
    max_retries: int = 3               # 最大重試次數
    retry_base_delay: float = 1.0      # 重試基礎延遲秒數
    retry_max_delay: float = 30.0      # 重試最大延遲秒數
    retry_exponential_base: float = 2.0  # 指數退避基底
    retry_jitter: bool = True          # 隨機擾動 (避免同時重試)
    
    # Timeout
    request_timeout: float = 30.0      # 請求逾時秒數
    
    # Retryable HTTP Status Codes
    retryable_status_codes: tuple = (408, 429, 500, 502, 503, 504)


# 全域設定實例 (可被外部覆蓋)
CRAWLER_CONFIG = CrawlerConfig()


# --- 1. Models & Interfaces ---


class TaskResult(BaseModel):
    """統一的回傳格式。"""
    success: bool = True
    data: Any = None
    message: str = ""
    count: int = 0
    
    @classmethod
    def ok(cls, data: Any, message: str = "") -> "TaskResult":
        count = len(data) if isinstance(data, list) else (1 if data else 0)
        return cls(success=True, data=data, message=message, count=count)
    
    @classmethod
    def fail(cls, message: str) -> "TaskResult":
        return cls(success=False, data=None, message=message, count=0)


def crawler_task(id: str, name: str, description: str = "", params_model: Type[BaseModel] = None):
    """
    裝飾器：將 async function 註冊為 crawler task。
    
    使用方式:
        @crawler_task(id="consent_search", name="Search Consent")
        async def consent_search(params, client: VghClient) -> TaskResult:
            ...
    """
    def decorator(func: Callable[..., Awaitable[TaskResult]]) -> Callable:
        func.id = id
        func.name = name
        func.description = description
        func.params_model = params_model
        func.is_crawler_task = True
        return func
    return decorator


# Legacy: CrawlerTask ABC (保留向後相容，逐步淘汰)
class CrawlerTask(ABC):
    """
    Abstract Base Class for all crawler tasks in vghsdk.
    
    Used for primitive data fetching operations from VGH intranet.
    For composite business tasks, use app.tasks.base.BaseTask instead.
    """
    id: str
    name: str
    description: str
    params_model: Optional[Type[BaseModel]] = None
    search_keywords: List[str] = []

    @property
    def params_schema(self) -> Dict[str, Any]:
        if self.params_model:
            return self.params_model.model_json_schema()
        return {}

    @abstractmethod
    async def run(
        self,
        params: Any,  # Union[BaseModel, Dict] - accepts both for flexibility
        client: 'VghClient'
    ) -> Any:
        pass


# --- 2. Network Layer (Formerly session.py) ---

class VghSession:
    """
    Async wrapper for VGH EIP session management.
    Handles headers, cookies, and low-level HTTP requests.
    """
    def __init__(self):
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://eip.vghtpe.gov.tw/login.php'
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True)
        # Cookies are managed automatically by httpx.AsyncClient

    async def close(self):
        await self.client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.client.get(url, **kwargs)

    async def post(self, url: str, data: dict = None, **kwargs) -> httpx.Response:
        return await self.client.post(url, data=data, **kwargs)

    async def rate_limit(self):
        """
        Sleeps for random duration to prevent blocking.
        Uses CRAWLER_CONFIG for delay range.
        """
        delay = random.uniform(CRAWLER_CONFIG.rate_limit_min, CRAWLER_CONFIG.rate_limit_max)
        await asyncio.sleep(delay)
    
    def update_headers(self, headers: dict):
        self.client.headers.update(headers)


# --- 3. Logic Layer (Consolidated VghClient + Auth) ---

class VghClient:
    """
    Unified VGH Client.
    Holds the session, credentials, and authentication state for various systems (EIP, CKS, DrWeb).
    """
    def __init__(self, eip_id: str, eip_psw: str):
        self.eip_id = eip_id
        self.eip_psw = eip_psw
        self.session = VghSession()
        
        # State Flags
        self.is_eip_logged_in = False
        self.is_drweb_initialized = False
        self.is_cks_logged_in = False

    async def close(self):
        await self.session.close()

    # --- Public Ensure Methods (Used by Modules) ---

    async def ensure_eip(self) -> bool:
        """
        EIP Login + DrWeb Initialization.
        Used by Patient, Doctor, Surgery, Consent modules.
        """
        if self.is_eip_logged_in and self.is_drweb_initialized:
            return True
        
        # 1. Login EIP
        if not self.is_eip_logged_in:
            logger.info(f"Logging into EIP as {self.eip_id}...")
            if not await self._login_eip():
                return False
            self.is_eip_logged_in = True

        # 2. Init DrWeb
        if not self.is_drweb_initialized:
            logger.info("Initializing DrWeb session...")
            if not await self._init_drweb():
                # Note: If DrWeb fails, we keep EIP as logged in, but return False for 'ensure_eip'
                # because the downstream task likely expects DrWeb.
                return False
            self.is_drweb_initialized = True
            
        return True

    async def ensure_cks(self) -> bool:
        """
        CKS Login.
        Used by IVI module.
        """
        if self.is_cks_logged_in:
            return True
            
        logger.info(f"Logging into CKS as {self.eip_id}...")
        if await self._login_cks():
            self.is_cks_logged_in = True
            return True
        return False

    # --- Private Auth Implementation ---

    async def _login_eip(self) -> bool:
        """EIP 登入，處理多重 JavaScript 重導向 (採用 MCP 版本邏輯)。"""
        if not self.eip_id or not self.eip_psw:
            logger.error("EIP ID or Password missing")
            return False

        base_url = 'https://eip.vghtpe.gov.tw'
        
        try:
            await self.session.get(f"{base_url}/login.php")
        except Exception as e:
            logger.error(f"Failed to access login page: {e}")
            return False

        data = {
            'loginCheck': '0',
            'login_name': self.eip_id,
            'password': self.eip_psw,
            'fromAjax': '0',
        }

        try:
            resp = await self.session.post(f"{base_url}/login_action.php", data=data)
        except Exception as e:
            logger.error(f"Failed to post login: {e}")
            return False

        content = resp.text
        
        if "帳號或密碼錯誤" in content:
            logger.warning("Login failed: Invalid credentials.")
            return False
        if "此帳戶已被停用" in content:
            logger.warning("Login failed: Account disabled.")
            return False

        # 追蹤 JavaScript 重導向鏈 (最多 5 次)
        for i in range(5):
            match = re.search(r'window\.location(\.href)?\s*=\s*["\']([^"\']+)["\']', content)
            if not match:
                break
                
            redirect_url = match.group(2)
            
            if "login.php" in redirect_url and "token" not in redirect_url:
                logger.warning(f"Login failed: Redirected to login page.")
                return False
            
            if redirect_url.startswith('/'):
                full_url = f"{base_url}{redirect_url}"
            elif redirect_url.startswith('http'):
                full_url = redirect_url
            else:
                full_url = f"{base_url}/{redirect_url}"
                
            logger.debug(f"Following redirect {i+1}: {full_url}")
            
            try:
                resp = await self.session.get(full_url)
                content = resp.text
            except Exception as e:
                logger.error(f"Failed to follow redirect: {e}")
                return False
        
        logger.info(f"EIP login successful for {self.eip_id}")
        return True

    async def _init_drweb(self) -> bool:
        url = "https://web9.vghtpe.gov.tw/emr/qemr/qemr.cfm?action=findPatient&srnId=DRWEBAPP&seqno=009"
        try:
            resp = await self.session.get(url)
            if "eip.vghtpe.gov.tw/login.php" in str(resp.url):
                logger.warning("DrWeb init failed: Redirected to login page.")
                return False
            return True
        except Exception as e:
            logger.error(f"DrWeb init error: {e}")
            return False

    async def _login_cks(self) -> bool:
        # Ported from services/cks.py
        login_url = "https://cks.vghtpe.gov.tw/Exm/HISLogin/CheckUserByID"
        
        data = {
            'signOnID': self.eip_id,
            'signOnPassword': self.eip_psw
        }
        
        try:
            res = await self.session.post(login_url, data=data)
            if res.status_code == 200:
                return True
            else:
                logger.error(f"CKS Login Failed: {res.status_code}")
                return False
        except Exception as e:
             logger.error(f"CKS Login Exception: {e}")
             return False

    # --- Proxy/Helper Methods ---
    
    async def rate_limit(self):
        await self.session.rate_limit()

    async def safe_request(self, method: str, url: str, **kwargs) -> Any:
        """
        Execute request with retry, exponential backoff, and auto-relogin logic.
        
        - 首次請求: rate_limit() 隨機延遲 (模擬人類操作)
        - 重試請求: 僅 Exponential Backoff (不重複 rate_limit)
        - Session 過期: 自動重新登入
        
        Args:
            method: HTTP method ('GET' or 'POST')
            url: Target URL
            **kwargs: Additional arguments passed to httpx
            
        Returns:
            httpx.Response object
            
        Raises:
            Exception: If all retries fail
        """
        config = CRAWLER_CONFIG
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                # 首次請求使用 rate_limit，重試時使用 backoff
                if attempt == 0:
                    await self.rate_limit()
                else:
                    # Exponential Backoff with optional Jitter
                    delay = min(
                        config.retry_base_delay * (config.retry_exponential_base ** (attempt - 1)),
                        config.retry_max_delay
                    )
                    if config.retry_jitter:
                        delay *= random.uniform(0.5, 1.5)
                    logger.info(f"Retry {attempt}/{config.max_retries}, waiting {delay:.1f}s...")
                    await asyncio.sleep(delay)
                
                # 執行請求
                if method.lower() == 'get':
                    response = await self.session.get(url, **kwargs)
                else:
                    response = await self.session.post(url, **kwargs)
                
                # 檢查 Session 過期 (HTTP 401/403)
                if response.status_code in [401, 403]:
                    logger.warning(f"Session expired ({response.status_code}), re-logging in...")
                    await self._handle_session_expired()
                    continue
                
                # 檢查 Session 過期 (Redirect to login page)
                if "sess_exceed.php" in str(response.url) or "login.php" in str(response.url):
                    logger.warning("Session redirect detected, re-logging in...")
                    await self._handle_session_expired()
                    continue
                
                # 檢查可重試的 HTTP 狀態碼
                if response.status_code in config.retryable_status_codes:
                    logger.warning(f"Retryable HTTP status {response.status_code}, will retry...")
                    continue
                
                return response
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"Network error (attempt {attempt + 1}): {e}")
                last_exception = e
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise
        
        raise Exception(f"Request failed after {config.max_retries + 1} attempts: {url}") from last_exception

    async def _handle_session_expired(self):
        """處理 Session 過期，重設狀態並重新登入"""
        self.is_eip_logged_in = False
        self.is_drweb_initialized = False
        self.is_cks_logged_in = False
        await self.ensure_eip()


# --- 4. Management Layer (Formerly pool.py) ---

class SessionManager:
    """
    Singleton to manage persistent VGH EIP sessions.
    """
    _instance = None
    _clients: Dict[str, VghClient] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_client(cls, eip_id: str, eip_psw: str) -> VghClient:
        """
        Get an existing authenticated client or create a new one.
        
        安全性增強：如果密碼不同，會清除舊 session 並建立新 client。
        這可防止帳密變更後仍使用舊 session 的安全風險。
        """
        if eip_id in cls._clients:
            client = cls._clients[eip_id]
            
            # 密碼驗證：若密碼不同，清除舊 session
            if client.eip_psw != eip_psw:
                logger.warning(f"Password changed for {eip_id}, closing old session and creating new one")
                # 非同步關閉需要特別處理（同步方法中無法 await）
                # 我們只清除參照，讓 GC 處理 httpx client
                del cls._clients[eip_id]
            else:
                logger.info(f"Reusing existing client for {eip_id}")
                return client
            
        logger.info(f"Creating NEW client for {eip_id}")
        client = VghClient(eip_id, eip_psw)
        cls._clients[eip_id] = client
        return client

    @classmethod
    async def close_all(cls):
        for eip_id, client in cls._clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing client {eip_id}: {e}")
        cls._clients.clear()
