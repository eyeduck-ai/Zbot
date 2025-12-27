import os
import pygsheets
import json
from google.oauth2 import service_account
from app.db.client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

# Path to service account file
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

class GSheetService:
    def __init__(self, key_path: str = None):
        self.key_path = key_path or SERVICE_ACCOUNT_FILE
        self._creds = None
        
    def _get_creds(self):
        if self._creds:
            return self._creds
            
        # 1. Try Local File
        if os.path.exists(self.key_path):
            logger.info(f"Loading Google Creds from file: {self.key_path}")
            self._creds = service_account.Credentials.from_service_account_file(
                self.key_path,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            return self._creds

        # 2. Try Supabase
        logger.info("Local credentials not found. Trying Supabase 'settings' table...")
        try:
            client = get_supabase_client()
            # Expecting table 'settings' with 'key'='google_service_account' and 'value'=JSON
            res = client.table("settings").select("value").eq("key", "google_service_account").execute()
            if res.data and len(res.data) > 0:
                info = res.data[0]['value']
                # If stored as string, parse it. If jsonb, it's dict.
                if isinstance(info, str):
                    info = json.loads(info)
                    
                self._creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive'
                    ]
                )
                logger.info("Successfully loaded Google Creds from Supabase.")
                return self._creds
            else:
                logger.warning("No Google Creds found in Supabase settings.")
        except Exception as e:
            logger.error(f"Failed to fetch Google Creds from Supabase: {e}")

        raise FileNotFoundError("Google Service Account credentials not found (File or DB).")

    def get_pygsheets_client(self):
        """Returns authorized pygsheets client"""
        creds = self._get_creds()
        return pygsheets.authorize(custom_credentials=creds)

# Singleton or factory
_service = None

def get_gsheet_service():
    global _service
    if _service is None:
        _service = GSheetService()
    return _service
