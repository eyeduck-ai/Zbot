# Zbot Updater - Version check and update logic
import os
import json
import shutil
import zipfile
import time
import subprocess
from typing import Optional, Tuple
import httpx
from packaging import version as pkg_version

from config import (
    GITHUB_API, ZBOT_DIR, VERSION_FILE, SERVER_DIR, 
    DOWNLOAD_DIR, REQUEST_TIMEOUT, ASSETS_DIR
)


def ensure_directories():
    """Create necessary directories if they don't exist."""
    os.makedirs(ZBOT_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)


def get_local_version() -> Optional[str]:
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


def check_github_release() -> Tuple[Optional[str], Optional[str]]:
    """
    Check GitHub for latest release.
    Returns (version, download_url) or (None, None) on failure.
    Only considers releases with version tags (vX.X.X format).
    Looks for Zbot_Server.zip asset (new architecture).
    Retries up to 3 times.
    """
    import re
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            resp = httpx.get(GITHUB_API, timeout=REQUEST_TIMEOUT, follow_redirects=True)
            if resp.status_code != 200:
                print(f"[!] 無法取得發布資訊 (HTTP {resp.status_code})，重試中 ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            
            releases = resp.json()
            if not isinstance(releases, list):
                return None, None
            
            # Find first release with version tag (vX.X.X format)
            version_pattern = re.compile(r'^v?\d+\.\d+\.\d+$')
            
            for release in releases:
                tag_name = release.get("tag_name", "")
                
                # Skip non-version tags like "launcher"
                if not version_pattern.match(tag_name):
                    continue
                
                # Find ZIP asset - prefer Zbot_Server, fallback to Zbot_Main for migration
                assets = release.get("assets", [])
                download_url = None
                for asset in assets:
                    name = asset.get("name", "")
                    # New architecture: look for Zbot_Server
                    if name.endswith(".zip") and "Zbot_Server" in name:
                        download_url = asset.get("browser_download_url")
                        break
                    # Fallback: old Zbot_Main for transition period
                    if name.endswith(".zip") and "Zbot_Main" in name:
                        download_url = asset.get("browser_download_url")
                
                if download_url:
                    return tag_name, download_url
            
            return None, None
        
        except httpx.RequestError as e:
            if attempt < max_retries - 1:
                print(f"[!] 連線失敗 ({e})，重試中 ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                return None, None
    
    return None, None


def compare_versions(local: Optional[str], remote: Optional[str]) -> bool:
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
    Retries up to 3 times for initial connection.
    """
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            with open(dest_path, "wb") as f:
                with httpx.stream("GET", url, timeout=REQUEST_TIMEOUT, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    
                    total_size = int(resp.headers.get("content-length", 0))
                    downloaded = 0
                    
                    for chunk in resp.iter_bytes(chunk_size=8192):
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
        
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < max_retries - 1:
                print(f"\n[!] 下載中斷 ({e})，重試中 ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                print(f"\n[✗] 下載失敗: {e}")
                return False
    return False


def terminate_main_app():
    """Terminate running Zbot_Server and legacy Zbot_Main processes."""
    print("[.] 正在關閉運作中的主程式...")
    try:
        # Kill Zbot_Server.exe (new architecture)
        subprocess.run(
            ["taskkill", "/F", "/IM", "Zbot_Server.exe"], 
            capture_output=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # Kill Zbot_Main.exe (legacy)
        subprocess.run(
            ["taskkill", "/F", "/IM", "Zbot_Main.exe"], 
            capture_output=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(2)  # Wait for release
    except Exception:
        pass


def apply_update(zip_path: str) -> bool:
    """
    Extract update ZIP and replace old version.
    Returns True on success.
    """
    try:
        # Kill existing process to release file locks
        terminate_main_app()

        # Backup old version
        backup_dir = os.path.join(ZBOT_DIR, "Zbot_Server_backup")
        if os.path.exists(SERVER_DIR):
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            shutil.move(SERVER_DIR, backup_dir)
        
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
        if os.path.exists(backup_dir) and not os.path.exists(SERVER_DIR):
            shutil.move(backup_dir, SERVER_DIR)
        return False
