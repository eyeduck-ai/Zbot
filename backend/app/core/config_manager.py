"""
Config Manager - 多路徑設定檔管理

設定檔路徑優先順序：
1. 程式目錄/config.json (開發模式)
2. 程式目錄/.env (向下相容)
3. 使用者資料夾/Zbot/config.json (打包後)
   - Windows: %LOCALAPPDATA%\\Zbot\\config.json
   - macOS: ~/Library/Application Support/Zbot/config.json
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 設定檔 schema
CONFIG_DEFAULTS = {
    "supabase_url": "",
    "supabase_key": "",
    "dev_mode": False,
    "log_level": "INFO",
}

# 進階設定（不在 UI 顯示）
ADVANCED_KEYS = ["test_eip_id", "test_eip_psw"]

# 全域設定快取
_cached_config: Optional[dict] = None
_config_path: Optional[Path] = None


def get_user_data_dir() -> Path:
    """取得使用者資料目錄"""
    if sys.platform == "win32":
        # Windows: %LOCALAPPDATA%\Zbot
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(base) / "Zbot"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/Zbot
        return Path.home() / "Library" / "Application Support" / "Zbot"
    else:
        # Linux: ~/.config/Zbot
        return Path.home() / ".config" / "Zbot"


def get_app_dir() -> Path:
    """取得程式目錄（支援 PyInstaller）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後
        return Path(sys.executable).parent
    else:
        # 開發模式 - backend 目錄
        return Path(__file__).parent.parent.parent


def _find_config_path() -> Optional[Path]:
    """
    依優先順序尋找設定檔
    
    Returns:
        設定檔路徑，若不存在則回傳 None
    """
    app_dir = get_app_dir()
    user_dir = get_user_data_dir()
    
    # 優先順序
    candidates = [
        app_dir / "config.json",              # 1. 程式目錄 config.json
        app_dir / ".env",                     # 2. 程式目錄 .env (向下相容)
        user_dir / "config.json",             # 3. 使用者目錄
    ]
    
    for path in candidates:
        if path.exists():
            logger.info(f"Found config at: {path}")
            return path
    
    return None


def get_config_path() -> Path:
    """
    取得設定檔路徑
    
    若設定檔存在，回傳現有路徑
    若不存在，回傳預設寫入路徑：
      - 打包後：使用者資料目錄
      - 開發模式：程式目錄
    """
    existing = _find_config_path()
    if existing:
        return existing
    
    # 預設寫入路徑
    if getattr(sys, 'frozen', False):
        return get_user_data_dir() / "config.json"
    else:
        return get_app_dir() / "config.json"


def config_exists() -> bool:
    """檢查設定檔是否存在"""
    return _find_config_path() is not None


def _load_env_file(path: Path) -> dict:
    """載入 .env 格式的設定檔"""
    config = {}
    has_supabase_key = False  # 用於追蹤是否已有 SUPABASE_KEY
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                
                # 轉換布林值
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                
                # 將舊的 key 名稱轉換為新的
                # SUPABASE_KEY 優先於 SUPABASE_ANON_KEY
                if key == "supabase_key":
                    config["supabase_key"] = value
                    has_supabase_key = True
                elif key == "supabase_anon_key":
                    # 只在沒有 SUPABASE_KEY 時才使用 ANON_KEY
                    if not has_supabase_key:
                        config["supabase_key"] = value
                elif key in ("supabase_url", "dev_mode", "log_level", "test_eip_id", "test_eip_psw"):
                    config[key] = value
    
    return config


def _load_json_file(path: Path) -> dict:
    """載入 JSON 格式的設定檔"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(force_reload: bool = False) -> dict:
    """
    載入設定檔
    
    Args:
        force_reload: 強制重新載入（忽略快取）
    
    Returns:
        設定字典，包含預設值
    """
    global _cached_config, _config_path
    
    if _cached_config is not None and not force_reload:
        return _cached_config
    
    # 從預設值開始
    config = CONFIG_DEFAULTS.copy()
    
    path = _find_config_path()
    if path:
        _config_path = path
        try:
            if path.suffix == ".json":
                file_config = _load_json_file(path)
            else:
                file_config = _load_env_file(path)
            
            # 合併設定
            for key, value in file_config.items():
                if key in config or key in ADVANCED_KEYS:
                    config[key] = value
            
            logger.info(f"Loaded config from: {path}")
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
    
    _cached_config = config
    return config


def save_config(data: dict) -> Path:
    """
    儲存設定檔
    
    Args:
        data: 設定字典
    
    Returns:
        儲存的檔案路徑
    """
    global _cached_config
    
    path = get_config_path()
    
    # 確保目錄存在
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # 合併現有進階設定
    existing = load_config() if config_exists() else {}
    for key in ADVANCED_KEYS:
        if key in existing and key not in data:
            data[key] = existing[key]
    
    # 儲存為 JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved config to: {path}")
    
    # 清除快取
    _cached_config = None
    
    return path


def get_config_for_display() -> dict:
    """
    取得設定（用於顯示，敏感資料遮罩）
    
    Returns:
        設定字典，supabase_key 已遮罩
    """
    config = load_config()
    result = config.copy()
    
    # 遮罩敏感資料
    if result.get("supabase_key"):
        key = result["supabase_key"]
        if len(key) > 20:
            result["supabase_key"] = key[:10] + "..." + key[-10:]
        else:
            result["supabase_key"] = "***"
    
    return result
