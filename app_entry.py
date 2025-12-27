#!/usr/bin/env python3
"""
Zbot Main Entry Point - Server + System Tray (Windows)

Usage: 
  - Windows (packaged): Double-click Zbot_Main.exe
  - Dev mode: python app_entry.py
"""
import os
import sys
import time
import socket
import threading
import webbrowser
import multiprocessing

# PyInstaller fix for multiprocessing
if sys.platform.startswith('win'):
    multiprocessing.freeze_support()

import uvicorn

# Make sure backend/ is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Server configuration
HOST = "127.0.0.1"
PORT = 5487

# Icon path (relative to app_entry.py or packaged exe)
ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")


def is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def open_browser():
    """Open browser to the app URL."""
    url = f"http://{HOST}:{PORT}"
    print(f"Opening browser: {url}")
    webbrowser.open(url)


def run_server():
    """Run the uvicorn server (blocking)."""
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False, workers=1, log_level="warning")


def on_quit(systray):
    """Callback when user clicks 'Quit' in tray menu."""
    print("Shutting down...")
    # Note: This will exit the process, stopping the server
    os._exit(0)


def on_open_browser(systray):
    """Callback when user clicks 'Open Browser' in tray menu."""
    open_browser()


def start_with_tray():
    """Start server with Windows system tray icon."""
    try:
        from infi.systray import SysTrayIcon
    except ImportError:
        print("[!] infi.systray not installed, running in console mode")
        start_console_mode()
        return
    
    # Check if icon file exists
    icon_file = ICON_PATH if os.path.exists(ICON_PATH) else None
    
    # Define menu items
    menu_options = (
        ("開啟瀏覽器", None, on_open_browser),
    )
    
    # Create system tray icon
    systray = SysTrayIcon(
        icon_file,  # None = default Windows icon
        "Zbot - 執行中",
        menu_options,
        on_quit=on_quit
    )
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait a bit for server to start, then open browser
    time.sleep(2)
    open_browser()
    
    # Start tray icon (blocking - keeps the app running)
    systray.start()


def start_console_mode():
    """Start server in console mode (for development/non-Windows)."""
    print(f"Server running at http://{HOST}:{PORT}")
    
    # Open browser after delay
    browser_thread = threading.Thread(target=lambda: (time.sleep(2), open_browser()), daemon=True)
    browser_thread.start()
    
    # Run server (blocking)
    run_server()


if __name__ == "__main__":
    print("Starting Zbot Main...")
    
    # Single instance check
    if is_port_in_use(HOST, PORT):
        print(f"Server already running at http://{HOST}:{PORT}")
        print("Opening browser to existing instance...")
        open_browser()
        time.sleep(1)
        sys.exit(0)
    
    # Choose mode based on platform
    if sys.platform == "win32":
        # Windows: Use system tray
        start_with_tray()
    else:
        # macOS/Linux: Console mode
        start_console_mode()
