#!/usr/bin/env python3
"""
Zbot Launcher + Systray
======================
1. Check for updates and download new version of Zbot_Server
2. Launch Zbot_Server as subprocess
3. Display system tray icon with menu
4. Manage server lifecycle
5. Monitor server health and auto-restart on crash

Usage: Double-click Zbot.exe
"""
import os
import sys
import time
import subprocess
import webbrowser
import threading
import ctypes

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
    SERVER_HOST,
    SERVER_PORT,
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


# --- Single Instance Lock ---
def acquire_single_instance_lock():
    """Prevent multiple launcher instances using Windows Mutex.
    
    Returns True if lock acquired, False if another instance is running.
    """
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    # Create a named mutex
    mutex = kernel32.CreateMutexW(None, False, "Global\\ZbotLauncherMutex")
    last_error = ctypes.get_last_error()
    
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        return False
    
    return True


def show_error_messagebox(title: str, message: str):
    """Show a Windows MessageBox with an error icon."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR


def show_info_messagebox(title: str, message: str):
    """Show a Windows MessageBox with an info icon."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)  # MB_ICONINFORMATION


class ZbotManager:
    """Manages Zbot Server lifecycle and system tray."""
    
    MAX_RESTART_ATTEMPTS = 3
    
    def __init__(self):
        self.server_process = None
        self.systray = None
        self.running = True
        self.restart_count = 0
    
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
        self.restart_count = 0  # Reset restart count on manual restart
        self.start_server()
    
    def open_browser(self):
        """Open browser to Zbot main page."""
        webbrowser.open(SERVER_URL)
    
    def open_config_page(self):
        """Open browser to Zbot config page."""
        webbrowser.open(f"{SERVER_URL}/?openConfig=true")
    
    def on_quit(self, systray=None):
        """Quit handler for system tray."""
        print("[.] 正在關閉...")
        self.running = False
        self.stop_server()
        os._exit(0)
    
    def start_server_monitor(self):
        """Start background thread to monitor server health.
        
        If server crashes (exit code != 0), automatically restart up to 3 times.
        If server exits normally (exit code == 0), don't restart.
        """
        def monitor():
            while self.running:
                time.sleep(10)  # Check every 10 seconds
                
                if self.server_process:
                    exit_code = self.server_process.poll()
                    
                    if exit_code is not None:
                        # Server has exited
                        if exit_code == 0:
                            # Normal exit (idle timeout, API shutdown)
                            print("[.] Server 正常退出")
                            self.running = False
                            if self.systray:
                                try:
                                    self.systray.shutdown()
                                except:
                                    pass
                            os._exit(0)
                        else:
                            # Abnormal exit (crash)
                            self.restart_count += 1
                            if self.restart_count <= self.MAX_RESTART_ATTEMPTS:
                                print(f"[!] Server 異常退出 (code {exit_code}), 重啟中... ({self.restart_count}/{self.MAX_RESTART_ATTEMPTS})")
                                self.start_server()
                            else:
                                print(f"[✗] Server 連續 crash {self.MAX_RESTART_ATTEMPTS} 次，停止重啟")
                                log_path = os.path.join(ZBOT_DIR, "logs")
                                show_error_messagebox(
                                    "Zbot 錯誤",
                                    f"Zbot Server 無法啟動，請檢查 Log 檔案。\n\n路徑: {log_path}"
                                )
                                self.running = False
                                os._exit(1)
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
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
        
        # Menu handlers
        def on_open_browser(systray):
            self.open_browser()
        
        def on_open_config(systray):
            self.open_config_page()
        
        def on_restart(systray):
            self.restart_server()
        
        menu_options = (
            ("開啟 Zbot", None, on_open_browser),
            ("開啟設定頁", None, on_open_config),
            ("重啟伺服器", None, on_restart),
        )
        
        try:
            self.systray = SysTrayIcon(
                icon_path,
                f"Zbot v{LAUNCHER_VERSION}",  # Tooltip shows version
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
            # Terminate server first to release locks
            terminate_main_app()
            
            # Use Native TaskDialog for progress
            try:
                from ui_taskdialog import show_update_dialog
                zip_path = os.path.join(DOWNLOAD_DIR, "update.zip")
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                
                # Show dialog (blocking)
                # It will handle download and apply_update via callbacks
                if show_update_dialog(remote_version, download_url, download_with_progress, apply_update, zip_path):
                     save_local_version(remote_version)
                     return True
                else:
                    # Update failed or user cancelled
                    # show_error_messagebox handled inside show_update_dialog logic partly?
                    # The worker task sets success=False
                    # If failed, we fall back to existing version check
                    return os.path.exists(SERVER_EXE)
                    
            except ImportError:
                # Fallback to silent update if ui_taskdialog fails to load/import (e.g. non-Windows)
                 print("[!] UI 模組載入失敗，使用無介面更新")
                 zip_path = os.path.join(DOWNLOAD_DIR, "update.zip")
                 os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                 if download_with_progress(download_url, zip_path):
                    if apply_update(zip_path):
                        save_local_version(remote_version)
                        return True
                 return os.path.exists(SERVER_EXE)

        else:
            print("[!] 找不到下載連結，跳過更新")
    else:
        ver_display = local_version or remote_version
        print(f"[✓] 目前版本: {ver_display} (最新)")
    
    return os.path.exists(SERVER_EXE)


def startup_flow(ui):
    """The main startup logic running inside the TaskDialog thread."""
    
    # 1. Single Instance Check
    ui.set_instruction("正在檢查執行環境...")
    ui.log("正在檢查是否有重複執行...")
    time.sleep(0.5)
    
    # We need to re-implement lock check here properly?
    # Actually main() does it before showing dialog usually.
    # But user wants to see "Starting..." so we can move it here or keep it before.
    # If we keep it before, we might fail silently?
    # Let's keep acquire_lock in main() because if it fails we just want to exit.
    
    # 2. Update Check
    ui.set_instruction("正在檢查更新...")
    ui.log(f"目前版本: {LAUNCHER_VERSION}")
    
    ensure_directories()
    local_version = get_local_version()
    remote_version, download_url = check_github_release()
    
    time.sleep(0.5) # UX delay
    
    if remote_version and compare_versions(local_version, remote_version):
        ui.log(f"發現新版本: {remote_version}")
        if download_url:
            ui.set_instruction(f"正在下載更新 v{remote_version}")
            ui.set_content("Downloading update...")
            
            # Switch to progress bar
            ui.set_progress(0)
            
            # Define callback for downloader
            def dl_callback(pct, msg):
                ui.set_progress(pct)
                # Parse msg to extract more info? msg is "下載中: 50%..."
                # Log only important changes or always?
                # Let's just update content area
                ui.set_content(msg)
            
            terminate_main_app()
            zip_path = os.path.join(DOWNLOAD_DIR, "update.zip")
            
            success = download_with_progress(download_url, zip_path, progress_callback=dl_callback)
            
            if success:
                ui.set_instruction("正在安裝更新...")
                ui.set_marquee(True) # Back to marquee for unzip
                if apply_update(zip_path):
                   ui.log("更新成功")
                   save_local_version(remote_version)
                   ui.set_instruction("更新完成！")
                   ui.set_content("即將重啟...")
                   time.sleep(1.5)
                   # We should probably restart the process itself to load new code?
                   # But if we just update server, we are fine. Launcher is updated?
                   # Launcher updates itself. We CANNOT update running launcher easily.
                   # Usually launcher updates Zbot_Server.
                   # If we update Zbot_Server, we can just proceed.
                   pass
                else:
                   ui.log("安裝更新失敗")
                   ui.set_instruction("更新失敗")
                   time.sleep(2)
            else:
                ui.log("下載失敗")
                ui.set_instruction("下載失敗")
                time.sleep(2)
    else:
        ui.log("已是最新版本")
    
    # 3. Start Server
    ui.set_instruction("正在啟動系統...")
    ui.set_content("初始化伺服器核心...")
    ui.set_marquee(True) # Ensure marquee
    
    manager = ZbotManager()
    ui.log("啟動 Zbot Server...")
    
    if not manager.start_server():
        ui.log("伺服器啟動失敗！")
        ui.set_instruction("啟動失敗")
        ui.set_content("請檢查 Logs")
        time.sleep(3)
        return # Will close dialog
        
    # Store manager in a global/shared place so main thread can access it?
    # Or start monitoring here?
    # monitoring thread is inside manager.
    manager.start_server_monitor()
    
    # Pass manager back to main thread via a hack or refactor?
    # We can assign to global variable or return it?
    # But this function executes, then dialog closes.
    # main() waits for dialog to close.
    # So we need to pass manager out.
    global _manager_instance
    _manager_instance = manager
    
    # 4. Open Browser
    ui.set_content("正在開啟瀏覽器...")
    ui.log("開啟控制台頁面...")
    time.sleep(1.5) # Wait for server boot
    manager.open_browser()
    
    ui.set_instruction("啟動完成")
    ui.set_content("即將最小化至系統匣...")
    ui.log("系統就緒")
    time.sleep(1.5) # Show "Success" state briefly

_manager_instance = None

def main():
    # Check for single instance
    if not acquire_single_instance_lock():
        show_error_messagebox("Zbot", "程式已在執行中")
        return
        
    # Show Startup Dialog
    # This blocks until startup_flow finishes
    try:
        from ui_taskdialog import show_progress_dialog
        show_progress_dialog("Zbot 啟動中", "正在初始化...", startup_flow)
    except ImportError:
        # Fallback if no UI available (e.g. debugging)
        print("UI Import Failed - Running headless")
        ui = type('DummyUI', (), {
            'set_instruction': print, 'set_content': print, 'log': print, 
            'set_progress': lambda x: None, 'set_marquee': lambda x: None,
            'close': lambda: None
        })()
        startup_flow(ui)
        
    # Proceed to Systray loop if manager exists
    if _manager_instance and _manager_instance.running:
        _manager_instance.run_with_systray()
    else:
        # Startup failed or cancelled
        pass



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
