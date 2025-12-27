# Zbot Launcher Configuration
import os

# GitHub Release Settings
GITHUB_REPO = "eyeduck-ai/Zbot"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Local Paths (%LOCALAPPDATA%/Zbot)
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
ZBOT_DIR = os.path.join(LOCAL_APPDATA, "Zbot")
VERSION_FILE = os.path.join(ZBOT_DIR, "version.json")
APP_DIR = os.path.join(ZBOT_DIR, "Zbot_Main")
DOWNLOAD_DIR = os.path.join(ZBOT_DIR, "downloads")

# Main App Executable
APP_EXE = os.path.join(APP_DIR, "Zbot_Main.exe")

# Launcher Version
LAUNCHER_VERSION = "1.0.0"

# Network Settings
REQUEST_TIMEOUT = 10  # seconds
