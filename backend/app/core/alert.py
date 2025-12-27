
import logging
import traceback
import aiosmtplib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from email.message import EmailMessage
from app.db.client import get_supabase_client

logger = logging.getLogger(__name__)

# --- Settings & Cache ---
# Simple in-memory cache
_cache: Dict[str, Any] = {}
_cache_expiry: Dict[str, datetime] = {}
CACHE_TTL_MINUTES = 5

class EmailSettings:
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_password, developer_email):
        self.SMTP_SERVER = smtp_server
        self.SMTP_PORT = smtp_port
        self.SMTP_USER = smtp_user
        self.SMTP_PASSWORD = smtp_password
        self.DEVELOPER_EMAIL = developer_email

async def get_setting_from_db(key: str) -> Optional[Any]:
    """
    Fetch a setting from 'settings' table by key.
    """
    # Check Cache
    if key in _cache and key in _cache_expiry:
        if datetime.now() < _cache_expiry[key]:
            return _cache[key]
            
    client = get_supabase_client()
    try:
        # Assuming table 'settings' has columns 'key' (text) and 'value' (jsonb)
        response = client.table("settings").select("value").eq("key", key).execute()
        if response.data and len(response.data) > 0:
            value = response.data[0].get("value")
            
            # Update Cache
            _cache[key] = value
            _cache_expiry[key] = datetime.now() + timedelta(minutes=CACHE_TTL_MINUTES)
            
            return value
        return None
    except Exception as e:
        logger.error(f"Failed to fetch setting '{key}': {e}")
        return None

async def get_email_settings() -> Optional[EmailSettings]:
    """
    Retrieve Email Configuration from DB.
    """
    config_data = await get_setting_from_db("smtp_config")
    
    if not config_data:
        return None
        
    return EmailSettings(
        smtp_server=config_data.get("server", "smtp.gmail.com"),
        smtp_port=config_data.get("port", 587),
        smtp_user=config_data.get("user", ""),
        smtp_password=config_data.get("password", ""),
        developer_email=config_data.get("dev_email", "")
    )

# --- Alert Service ---

class AlertService:
    @staticmethod
    async def send_alert(subject: str, body: str):
        """
        Sends an email to the developer.
        Fetches config dynamically from DB.
        """
        settings = await get_email_settings()
        
        # Check if settings exist
        if not settings:
            logger.warning(f"Alert Service: Config missing in DB. Subject: {subject}")
            return False
            
        # Check if critical fields exist
        if not settings.SMTP_USER or not settings.DEVELOPER_EMAIL:
            logger.warning(f"Alert Service: SMTP User or Developer Email not set. Subject: {subject}")
            return False

        msg = EmailMessage()
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.DEVELOPER_EMAIL
        msg["Subject"] = f"[VGH Bot Alert] {subject}"
        msg.set_content(body)

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True
            )
            logger.info(f"Alert email sent to {settings.DEVELOPER_EMAIL}. Subject: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
            return False

    @staticmethod
    async def send_exception_alert(exc: Exception, context: str = ""):
        """
        Helper to send exception traceback.
        """
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        body = f"Context: {context}\n\nException:\n{str(exc)}\n\nTraceback:\n{tb}"
        return await AlertService.send_alert("System Exception", body)
