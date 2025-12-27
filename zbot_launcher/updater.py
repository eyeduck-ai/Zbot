# Zbot Updater - Version check and update logic
import os
import json
import shutil
import zipfile
import requests
from packaging import version as pkg_version

from config import (
    GITHUB_API, ZBOT_DIR, VERSION_FILE, APP_DIR, 
    DOWNLOAD_DIR, REQUEST_TIMEOUT
)


def ensure_directories():
    """Create necessary directories if they don't exist."""
    os.makedirs(ZBOT_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_local_version() -> str | None:
    """Read current installed version from version.json."""
    if not os.path.exists(VERSION_FILE):
        return None
    
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("app_version")
    except (json.JSONDecodeError, IOError):
        return None


def save_local_version(ver: str):
    """Save version to version.json."""
    data = {
        "app_version": ver,
        "updated_at": __import__("datetime").datetime.now().isoformat()
    }
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check_github_release() -> tuple[str | None, str | None]:
    """
    Check GitHub for latest release.
    Returns (version, download_url) or (None, None) on failure.
    """
    try:
        resp = requests.get(GITHUB_API, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None, None
        
        data = resp.json()
        tag_name = data.get("tag_name", "")  # e.g., "v1.2.0"
        
        # Find ZIP asset
        assets = data.get("assets", [])
        download_url = None
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(".zip") and "Zbot_Main" in name:
                download_url = asset.get("browser_download_url")
                break
        
        return tag_name, download_url
    
    except requests.RequestException:
        return None, None


def compare_versions(local: str | None, remote: str | None) -> bool:
    """
    Check if remote version is newer than local.
    Returns True if update is needed.
    """
    if not remote:
        return False
    if not local:
        return True  # No local version = need to download
    
    # Remove 'v' prefix if present
    local_clean = local.lstrip("v")
    remote_clean = remote.lstrip("v")
    
    try:
        return pkg_version.parse(remote_clean) > pkg_version.parse(local_clean)
    except pkg_version.InvalidVersion:
        # Fallback to string comparison
        return remote_clean != local_clean


def download_with_progress(url: str, dest_path: str) -> bool:
    """
    Download file with progress display.
    Returns True on success.
    """
    try:
        resp = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        bar_len = 20
                        filled = int(bar_len * downloaded / total_size)
                        bar = "█" * filled + "░" * (bar_len - filled)
                        print(f"\r[↓] 正在下載... {percent:3d}% [{bar}]", end="", flush=True)
        
        print()  # Newline after progress
        return True
    
    except requests.RequestException as e:
        print(f"\n[✗] 下載失敗: {e}")
        return False


def apply_update(zip_path: str) -> bool:
    """
    Extract update ZIP and replace old version.
    Returns True on success.
    """
    try:
        # Backup old version (optional)
        backup_dir = os.path.join(ZBOT_DIR, "Zbot_Main_backup")
        if os.path.exists(APP_DIR):
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            shutil.move(APP_DIR, backup_dir)
        
        # Extract new version
        print("[↻] 正在安裝更新...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(ZBOT_DIR)
        
        # Clean up
        os.remove(zip_path)
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        
        print("[✓] 更新完成！")
        return True
    
    except Exception as e:
        print(f"[✗] 更新失敗: {e}")
        # Attempt rollback
        if os.path.exists(backup_dir) and not os.path.exists(APP_DIR):
            shutil.move(backup_dir, APP_DIR)
        return False
