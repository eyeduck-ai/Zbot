
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# =============================================================================
# Log Directory Detection
# =============================================================================

def get_log_dir() -> str:
    """
    取得日誌目錄路徑
    
    - 開發模式: backend/logs/
    - 打包模式 (PyInstaller): 
        - Windows: %LOCALAPPDATA%/Zbot/logs/
        - macOS: ~/Library/Application Support/Zbot/logs/
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包環境
        if sys.platform == 'win32':
            base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            log_dir = os.path.join(base, 'Zbot', 'logs')
        else:  # macOS / Linux
            log_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'Zbot', 'logs')
    else:
        # 開發環境: backend/logs/
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
    
    # 確保目錄存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    return log_dir


# =============================================================================
# Log Level Configuration
# =============================================================================

# 預設值: 打包版用 WARNING，開發版用 INFO
DEFAULT_LOG_LEVEL = "WARNING" if getattr(sys, 'frozen', False) else "INFO"

_configured_log_level = None

def get_configured_log_level() -> str:
    """
    取得設定的 log level（延遲載入以避免循環依賴）
    
    優先順序:
    1. config.json 的 log_level
    2. 環境變數 LOG_LEVEL  
    3. 預設值 (打包版 WARNING, 開發版 INFO)
    """
    global _configured_log_level
    
    if _configured_log_level is not None:
        return _configured_log_level
    
    # 嘗試從 config.json 讀取
    try:
        from app.config import get_settings
        settings = get_settings()
        if settings.LOG_LEVEL:
            _configured_log_level = settings.LOG_LEVEL.upper()
            return _configured_log_level
    except Exception:
        pass  # config.json 可能還沒載入或不存在
    
    # 回退到環境變數
    env_level = os.environ.get("LOG_LEVEL")
    if env_level:
        _configured_log_level = env_level.upper()
        return _configured_log_level
    
    # 使用預設值
    _configured_log_level = DEFAULT_LOG_LEVEL
    return _configured_log_level


def reconfigure_log_level(level: str = None):
    """
    重新設定 log level（可在 config 載入後調用）
    
    Args:
        level: 新的 log level，若為 None 則從 config.json 讀取
    """
    global _configured_log_level
    
    if level:
        new_level = level.upper()
    else:
        _configured_log_level = None  # 清除快取，重新讀取
        new_level = get_configured_log_level()
    
    _configured_log_level = new_level
    log_level = getattr(logging, new_level, logging.INFO)
    
    # 更新 root logger 和所有 handler (包含 httpx 等第三方)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)
    
    logging.getLogger("app").info(f"Log level set to: {new_level}")


# =============================================================================
# Logger Setup
# =============================================================================

LOG_DIR = get_log_dir()
LOG_FILE_PATH = os.path.join(LOG_DIR, "app.log")

def setup_logger(name: str = "app"):
    """
    設定 logger
    
    - 檔案日誌: 10MB 單檔，保留 5 個備份
    - Console 輸出: 同步顯示
    - Log Level: 從 config.json > 環境變數 > 預設值
    - 所有 logger (包含 httpx 等第三方) 統一使用同一設定
    """
    log_level_str = get_configured_log_level()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure Root Logger (所有 logger 統一繼承此設定)
    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    return logging.getLogger(name)


# Create default logger instance
logger = setup_logger()

# Log the log file location for debugging
logger.info(f"Log file: {LOG_FILE_PATH}")
