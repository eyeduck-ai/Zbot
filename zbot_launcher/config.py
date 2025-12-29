# Zbot Launcher Configuration
import os

# GitHub Release Settings
GITHUB_REPO = "eyeduck-ai/Zbot"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

# Local Paths (%LOCALAPPDATA%/Zbot)
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
ZBOT_DIR = os.path.join(LOCAL_APPDATA, "Zbot")
VERSION_FILE = os.path.join(ZBOT_DIR, "version.json")

# Server directory and executable
SERVER_DIR = os.path.join(ZBOT_DIR, "Zbot_Server")
SERVER_EXE = os.path.join(SERVER_DIR, "Zbot_Server.exe")

# Legacy paths (for migration)
LEGACY_APP_DIR = os.path.join(ZBOT_DIR, "Zbot_Main")

# Download directory
DOWNLOAD_DIR = os.path.join(ZBOT_DIR, "downloads")

# Assets
ASSETS_DIR = os.path.join(ZBOT_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")

# Launcher Version
LAUNCHER_VERSION = "2.0.0"  # Major version bump for new architecture

# Server URL
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5487
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Network Settings
REQUEST_TIMEOUT = 10  # seconds

