"""
Zbot Server - Pure uvicorn backend (no systray)
Runs as independent process, managed by Zbot.exe (Launcher + Systray)
"""
import os
import sys
import logging
import webbrowser
import threading

# --- Path Setup ---
def get_base_path():
    """Get the base path for the application."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def get_exe_dir():
    """Get the directory where the executable is located."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
EXE_DIR = get_exe_dir()

# Add backend to path for imports
if BASE_PATH not in sys.path:
    sys.path.insert(0, BASE_PATH)

# --- Logging Setup ---
def setup_logging():
    """Setup logging to file and console."""
    log_dir = os.path.join(os.environ.get('LOCALAPPDATA', EXE_DIR), 'Zbot', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'server.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) if sys.stdout else logging.NullHandler()
        ]
    )
    return log_file

# --- NullWriter for noconsole mode ---
class NullWriter:
    """Dummy writer for when stdout/stderr is None."""
    def write(self, s): pass
    def flush(self): pass
    def isatty(self): return False

def fix_stdio():
    """Fix stdout/stderr for noconsole mode."""
    if sys.stdout is None:
        sys.stdout = NullWriter()
    if sys.stderr is None:
        sys.stderr = NullWriter()

# --- Browser ---
HOST = "127.0.0.1"
PORT = 5487
URL = f"http://{HOST}:{PORT}"

def open_browser():
    """Open browser after a short delay."""
    import time
    time.sleep(1.5)
    webbrowser.open(URL)

# --- Main ---
def main():
    """Main entry point for Zbot Server."""
    fix_stdio()
    log_file = setup_logging()
    
    logger = logging.getLogger("zbot_server")
    logger.info(f"Zbot Server starting...")
    logger.info(f"BASE_PATH: {BASE_PATH}")
    logger.info(f"EXE_DIR: {EXE_DIR}")
    logger.info(f"Log file: {log_file}")
    
    try:
        # Import app (this triggers all heavy imports like supabase, pyiceberg)
        # Since we're in main thread (not daemon), this is safe
        logger.info("Importing FastAPI app...")
        from app.main import app
        import uvicorn
        
        logger.info("FastAPI app imported successfully")
        
        # Open browser in background
        threading.Thread(target=open_browser, daemon=True).start()
        
        # Run uvicorn in main thread (blocking)
        logger.info(f"Starting uvicorn on {URL}")
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
