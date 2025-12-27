#!/usr/bin/env python3
"""
Zbot Launcher - CLI version updater and app launcher

Usage: Double-click Zbot.exe or run `python main.py`
"""
import os
import sys
import time
import subprocess

from config import LAUNCHER_VERSION, APP_EXE, APP_DIR, DOWNLOAD_DIR
from updater import (
    ensure_directories,
    get_local_version,
    save_local_version,
    check_github_release,
    compare_versions,
    download_with_progress,
    apply_update,
)


def print_header():
    """Print launcher header."""
    print(f"Zbot v{LAUNCHER_VERSION}")
    print("-" * 40)


def launch_main_app() -> bool:
    """
    Launch Zbot_Main.exe and return True on success.
    """
    if not os.path.exists(APP_EXE):
        print(f"[✗] 找不到主程式: {APP_EXE}")
        return False
    
    try:
        # Start main app detached
        if sys.platform == "win32":
            # Windows: CREATE_NEW_CONSOLE for detached process
            subprocess.Popen(
                [APP_EXE],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=APP_DIR
            )
        else:
            # macOS/Linux
            subprocess.Popen([APP_EXE], cwd=APP_DIR)
        
        return True
    except Exception as e:
        print(f"[✗] 啟動失敗: {e}")
        return False


def main():
    print_header()
    
    # 1. Ensure directories exist
    ensure_directories()
    
    # 2. Check current version
    print("[.] 正在檢查版本...")
    local_version = get_local_version()
    
    # 3. Check GitHub for updates
    remote_version, download_url = check_github_release()
    
    if remote_version is None:
        if local_version:
            print(f"[!] 無法連線至更新伺服器，使用本地版本 {local_version}")
        else:
            print("[✗] 無法連線至更新伺服器，且無本地版本")
            print("    請確認網路連線後重試")
            input("按 Enter 鍵結束...")
            return
    else:
        # 4. Compare versions
        if compare_versions(local_version, remote_version):
            print(f"[!] 發現新版本: {remote_version}")
            
            if download_url:
                # Download update
                zip_path = os.path.join(DOWNLOAD_DIR, "update.zip")
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                
                if download_with_progress(download_url, zip_path):
                    if apply_update(zip_path):
                        save_local_version(remote_version)
                    else:
                        print("[!] 更新失敗，嘗試啟動舊版本...")
            else:
                print("[!] 找不到下載連結，跳過更新")
        else:
            ver_display = local_version or remote_version
            print(f"[✓] 目前版本: {ver_display} (最新)")
    
    # 5. Launch main app
    print("[.] 正在啟動主程式...")
    
    if launch_main_app():
        print("[✓] 已開啟瀏覽器，請稍候")
        time.sleep(2)
    else:
        print("[✗] 無法啟動主程式")
        input("按 Enter 鍵結束...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消")
    except Exception as e:
        print(f"\n[✗] 發生錯誤: {e}")
        input("按 Enter 鍵結束...")
