import ctypes
import ctypes.wintypes
import threading
import time

# --- Constants & Types ---
COMMCTRL_DLL = ctypes.windll.comctl32
USER32_DLL = ctypes.windll.user32

# TaskDialog Flags
TDF_USE_COMMAND_LINKS = 0x0010
TDF_EXPAND_FOOTER_AREA = 0x0040
TDF_EXPANDED_BY_DEFAULT = 0x0080
TDF_VERIFICATION_FLAG_CHECKED = 0x0100
TDF_SHOW_PROGRESS_BAR = 0x0200
TDF_SHOW_MARQUEE_PROGRESS_BAR = 0x0400
TDF_CALLBACK_TIMER = 0x0800
TDF_POSITION_RELATIVE_TO_WINDOW = 0x1000
TDF_RTL_LAYOUT = 0x2000
TDF_NO_DEFAULT_RADIO_BUTTON = 0x4000
TDF_CAN_BE_MINIMIZED = 0x8000

# Messages (Processor -> Dialog)
WM_USER = 0x0400
TDM_NAVIGATE_PAGE = WM_USER + 101
TDM_CLICK_BUTTON = WM_USER + 102
TDM_SET_MARQUEE_PROGRESS_BAR = WM_USER + 103
TDM_SET_PROGRESS_BAR_STATE = WM_USER + 104
TDM_SET_PROGRESS_BAR_RANGE = WM_USER + 105
TDM_SET_PROGRESS_BAR_POS = WM_USER + 106
TDM_SET_PROGRESS_BAR_MARQUEE = WM_USER + 107
TDM_SET_ELEMENT_TEXT = WM_USER + 108

# Element IDs for SetText
TDE_CONTENT = 0
TDE_EXPANDED_INFORMATION = 1
TDE_FOOTER = 2
TDE_MAIN_INSTRUCTION = 3

# Notifications (Dialog -> Callback)
TDN_CREATED = 0
TDN_NAVIGATED = 1
TDN_BUTTON_CLICKED = 2
TDN_HYPERLINK_CLICKED = 3
TDN_TIMER = 4
TDN_DESTROYED = 5
TDN_RADIO_BUTTON_CLICKED = 6
TDN_DIALOG_CONSTRUCTED = 7
TDN_VERIFICATION_CLICKED = 8
TDN_HELP = 9
TDN_EXPANDO_BUTTON_CLICKED = 10

# Common Button IDs
IDCANCEL = 2
IDRETRY = 4
IDCLOSE = 8

# Layout
LPVOID = ctypes.c_void_p
HANDLE = ctypes.c_void_p
HWND = ctypes.wintypes.HWND
HRESULT = ctypes.c_long
UINT = ctypes.c_uint
WPARAM = ctypes.wintypes.WPARAM
LPARAM = ctypes.wintypes.LPARAM
PCWSTR = ctypes.c_wchar_p

# Callback signature
# HRESULT Callback(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam, LONG_PTR lpRefData)
PFTASKDIALOGCALLBACK = ctypes.WINFUNCTYPE(HRESULT, HWND, UINT, WPARAM, LPARAM, LPVOID)

class TASKDIALOGCONFIG(ctypes.Structure):
    _pack_ = 4 # Important for 32/64 bit alignment compat usually, but on 64bit python alignment might differ. 
               # However, standard packing usually matches SDK.
               # Let's use strict definition.
    _fields_ = [
        ("cbSize", UINT),
        ("hwndParent", HWND),
        ("hInstance", HANDLE),
        ("dwFlags", UINT),
        ("dwCommonButtons", UINT),
        ("pszWindowTitle", PCWSTR),
        ("pszMainIcon", LPVOID), # HICON or LPCWSTR
        ("pszMainInstruction", PCWSTR),
        ("pszContent", PCWSTR),
        ("cButtons", UINT),
        ("pButtons", LPVOID),
        ("nDefaultButton", ctypes.c_int),
        ("cRadioButtons", UINT),
        ("pRadioButtons", LPVOID),
        ("nDefaultRadioButton", ctypes.c_int),
        ("pszVerificationText", PCWSTR),
        ("pszExpandedInformation", PCWSTR),
        ("pszExpandedControlText", PCWSTR),
        ("pszCollapsedControlText", PCWSTR),
        ("pszFooterIcon", LPVOID),
        ("pszFooter", PCWSTR),
        ("pfCallback", PFTASKDIALOGCALLBACK),
        ("lpCallbackData", LPVOID),
        ("cxWidth", UINT),
    ]

# Global state to share between thread and callback
class DialogContext:
    def __init__(self):
        self.hwnd = None
        self.download_url = ""
        self.dest_path = ""
        self.success = False
        self.worker_thread = None
        self.download_func = None
        self.apply_func = None
        self.worker_func = None
        self.logs = [] # Initialize logs

class DialogUI:
    """Controller for the TaskDialog UI, passed to the worker function."""
    def __init__(self, hwnd=None):
        self.hwnd = hwnd

    def set_hwnd(self, hwnd):
        self.hwnd = hwnd

    def set_instruction(self, text):
        if self.hwnd:
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_ELEMENT_TEXT, TDE_MAIN_INSTRUCTION, ctypes.c_wchar_p(text))

    def set_content(self, text):
        if self.hwnd:
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_ELEMENT_TEXT, TDE_CONTENT, ctypes.c_wchar_p(text))
            
    def set_progress(self, percent: int):
        """Set progress bar value (0-100). Automaticaly disables marquee."""
        if self.hwnd:
            # Disable marquee
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_PROGRESS_BAR_MARQUEE, 0, 0)
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_PROGRESS_BAR_POS, int(percent), 0)

    def set_marquee(self, enable: bool = True):
        """Enable or disable marquee (indeterminate) mode."""
        if self.hwnd:
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_PROGRESS_BAR_MARQUEE, 1 if enable else 0, 0)
            if enable:
                 USER32_DLL.SendMessageW(self.hwnd, TDM_SET_PROGRESS_BAR_STATE, 1, 0) # Normal state

    def log(self, text):
        """Append text to expanded information area."""
        if self.hwnd:
            _ctx.logs.append(text)
            if len(_ctx.logs) > 20: # Keep last 20 lines
                _ctx.logs = _ctx.logs[-20:]
            full_log = "\n".join(_ctx.logs)
            USER32_DLL.SendMessageW(self.hwnd, TDM_SET_ELEMENT_TEXT, TDE_EXPANDED_INFORMATION, ctypes.c_wchar_p(full_log))
            
    def close(self):
        """Close the dialog programmatically."""
        if self.hwnd:
             USER32_DLL.SendMessageW(self.hwnd, TDM_CLICK_BUTTON, IDCANCEL, 0)

# Global context
_ctx = DialogContext()
_ui = DialogUI()

def _worker_wrapper():
    """Wrapper to run the user-provided worker function."""
    try:
        time.sleep(0.5) # Allow dialog to paint
        if _ctx.worker_func:
            _ctx.worker_func(_ui)
    except Exception as e:
        _ui.log(f"Error: {e}")
        _ui.set_instruction("發生錯誤")
        _ui.set_content(str(e))
        time.sleep(2) # Let user see error?
    finally:
        _ui.close()

@PFTASKDIALOGCALLBACK
def _dialog_callback(hwnd, msg, wParam, lParam, lpRefData):
    if msg == TDN_CREATED:
        _ui.set_hwnd(hwnd)
        _ctx.hwnd = hwnd
        
        # Default to Marquee
        USER32_DLL.SendMessageW(hwnd, TDM_SET_PROGRESS_BAR_MARQUEE, 1, 0)
        USER32_DLL.SendMessageW(hwnd, TDM_SET_PROGRESS_BAR_POS, 0, 0)
        
        # Start worker
        _ctx.worker_thread = threading.Thread(target=_worker_wrapper)
        _ctx.worker_thread.start()
        
    elif msg == TDN_DESTROYED:
        pass
        
    return 0

def show_progress_dialog(title, instruction, worker_func):
    """
    Shows a TaskDialog with progress bar and runs worker_func(ui) in a thread.
    The dialog closes automatically when worker_func returns.
    """
    _ctx.worker_func = worker_func
    _ctx.logs = [] # Reset logs
    _ui.set_hwnd(None) 

    config = TASKDIALOGCONFIG()
    config.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    config.hwndParent = 0
    config.hInstance = 0
    # Enable Progress Bar + Marquee Support + Expanded Info
    config.dwFlags = TDF_SHOW_MARQUEE_PROGRESS_BAR | TDF_EXPANDED_BY_DEFAULT | TDF_CALLBACK_TIMER
    config.pszWindowTitle = title
    config.pszMainInstruction = instruction
    config.pszContent = "請稍候..."
    config.pszExpandedInformation = "初始化中..."
    config.pszExpandedControlText = "隱藏詳細資訊"
    config.pszCollapsedControlText = "顯示詳細資訊"
    config.pfCallback = _dialog_callback
    
    # Buttons - remove Cancel if we want to force wait? 
    # Or keep Cancel to allow aborting? 
    # Let's keep common buttons but maybe handle Cancel in callback?
    config.dwCommonButtons = 0 # No buttons? User can close via X.
    # Actually if no buttons, TaskDialog might fail or add OK.
    # Let's add Cancel.
    config.dwCommonButtons = 2 # IDCANCEL
    
    pnButton = ctypes.c_int()
    pnRadioButton = ctypes.c_int()
    pfVerificationFlagChecked = ctypes.c_bool()
    
    try:
        COMMCTRL_DLL.TaskDialogIndirect(
            ctypes.byref(config), 
            ctypes.byref(pnButton), 
            ctypes.byref(pnRadioButton), 
            ctypes.byref(pfVerificationFlagChecked)
        )
    except OSError as e:
        print(f"TaskDialog failed: {e}")
        # Fallback: run worker without UI
        worker_func(DialogUI(None))
        return


