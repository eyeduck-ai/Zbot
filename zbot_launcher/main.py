#!/usr/bin/env python3
"""
Zbot Launcher + Systray
======================
1. Check for updates and download new version of Zbot_Server
2. Launch Zbot_Server as subprocess
3. Display system tray icon with menu
4. Manage server lifecycle

Usage: Double-click Zbot.exe
"""
import os
import sys
import time
import subprocess
import webbrowser
import threading
import shutil

from config import (
    LAUNCHER_VERSION, 
    SERVER_EXE, 
    SERVER_DIR,
    DOWNLOAD_DIR,
    ASSETS_DIR,
    ICON_PATH,
    SERVER_URL,
    ZBOT_DIR,
    LEGACY_APP_DIR,
)
from updater import (
    ensure_directories,
    get_local_version,
    save_local_version,
    check_github_release,
    compare_versions,
    download_with_progress,
    apply_update,
    terminate_main_app,
)


def hide_console():
    """Hide the console window using Win32 API.
    
    This is called after the update process completes to allow
    the launcher to run silently in the system tray.
    """
    try:
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
            return True
    except Exception:
        pass
    return False


class ZbotManager:
    """Manages Zbot Server lifecycle and system tray."""
    
    def __init__(self):
        self.server_process = None
        self.systray = None
        self.running = True
    
    def start_server(self) -> bool:
        """Start Zbot Server as subprocess."""
        if not os.path.exists(SERVER_EXE):
            print(f"[✗] 找不到伺服器: {SERVER_EXE}")
            return False
        
        try:
            # Start server with hidden window
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            self.server_process = subprocess.Popen(
                [SERVER_EXE],
                cwd=SERVER_DIR,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[✓] 伺服器已啟動 (PID: {self.server_process.pid})")
            return True
        except Exception as e:
            print(f"[✗] 啟動失敗: {e}")
            return False
    
    def stop_server(self):
        """Stop Zbot Server."""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("[.] 伺服器已停止")
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                print("[!] 伺服器強制終止")
            except Exception as e:
                print(f"[!] 停止伺服器時發生錯誤: {e}")
            finally:
                self.server_process = None
    
    def restart_server(self):
        """Restart Zbot Server."""
        print("[.] 正在重啟伺服器...")
        self.stop_server()
        time.sleep(1)
        self.start_server()
    
    def open_browser(self):
        """Open browser to Zbot."""
        webbrowser.open(SERVER_URL)
    
    def on_quit(self, systray=None):
        """Quit handler for system tray."""
        print("[.] 正在關閉...")
        self.running = False
        self.stop_server()
        os._exit(0)
    
    def run_with_systray(self):
        """Run with system tray icon."""
        try:
            from infi.systray import SysTrayIcon
        except ImportError:
            print("[!] 無法載入 systray，改用無圖示模式")
            self.run_without_systray()
            return
        
        # Find icon - prioritize bundled icon
        icon_path = None
        
        # First try bundled assets (from PyInstaller bundle)
        if getattr(sys, 'frozen', False):
            bundled_icon = os.path.join(sys._MEIPASS, "assets", "icon.ico")
        else:
            bundled_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        
        if os.path.exists(bundled_icon):
            icon_path = bundled_icon
        elif os.path.exists(ICON_PATH):
            # Fallback to config ICON_PATH
            icon_path = ICON_PATH
        
        # If no icon found, systray will use default
        
        # Menu handlers
        def on_open_browser(systray):
            self.open_browser()
        
        def on_restart(systray):
            self.restart_server()
        
        menu_options = (
            ("開啟 Zbot", None, on_open_browser),
            ("重啟服務", None, on_restart),
        )
        
        try:
            self.systray = SysTrayIcon(
                icon_path,
                "Zbot",
                menu_options,
                on_quit=self.on_quit
            )
            
            # Start systray (blocking)
            self.systray.start()
            
        except Exception as e:
            print(f"[!] Systray 錯誤: {e}")
            self.run_without_systray()
    
    def run_without_systray(self):
        """Run without system tray (keep server running)."""
        print(f"[✓] Zbot 運行中: {SERVER_URL}")
        print("    按 Ctrl+C 結束")
        
        try:
            while self.running and self.server_process and self.server_process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.on_quit()


def print_header():
    """Print launcher header."""
    print(f"Zbot v{LAUNCHER_VERSION}")
    print("-" * 40)


def check_and_update():
    """Check for updates and apply if available. Returns True if ready to run."""
    # Ensure directories exist
    ensure_directories()
    
    # Check current version
    print("[.] 正在檢查版本...")
    local_version = get_local_version()
    
    # Check GitHub for updates
    remote_version, download_url = check_github_release()
    
    if remote_version is None:
        if local_version and os.path.exists(SERVER_EXE):
            print(f"[!] 無法連線至更新伺服器，使用本地版本 {local_version}")
            return True
        else:
            print("[✗] 無法連線至更新伺服器，且無本地版本")
            print("    請確認網路連線後重試")
            return False
    
    # Compare versions
    if compare_versions(local_version, remote_version):
        print(f"[!] 發現新版本: {remote_version}")
        
        if download_url:
            # Terminate existing server
            terminate_main_app()
            
            # Download update
            zip_path = os.path.join(DOWNLOAD_DIR, "update.zip")
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            
            if download_with_progress(download_url, zip_path):
                if apply_update(zip_path):
                    save_local_version(remote_version)
                    return True
                else:
                    print("[!] 更新失敗")
                    return os.path.exists(SERVER_EXE)
        else:
            print("[!] 找不到下載連結，跳過更新")
    else:
        ver_display = local_version or remote_version
        print(f"[✓] 目前版本: {ver_display} (最新)")
    
    return os.path.exists(SERVER_EXE)


def main():
    print_header()
    
    # Phase 1: Console visible - Check for updates
    if not check_and_update():
        input("按 Enter 鍵結束...")
        return
    
    # Phase 2: Hide console after update completes
    hide_console()
    
    # Phase 3: Run silently with systray
    manager = ZbotManager()
    
    # Start server
    print("[.] 正在啟動伺服器...")
    if not manager.start_server():
        print("[✗] 無法啟動伺服器")
        input("按 Enter 鍵結束...")
        return
    
    # Open browser
    print("[.] 正在開啟瀏覽器...")
    time.sleep(1.5)  # Wait for server to start
    manager.open_browser()
    
    # Run with systray (console now hidden)
    print("[✓] 已開啟瀏覽器，最小化至系統匣")
    manager.run_with_systray()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消")
    except Exception as e:
        import traceback
        print(f"\n[✗] 發生錯誤: {e}")
        print("\n詳細錯誤:")
        traceback.print_exc()
        input("\n按 Enter 鍵結束...")
