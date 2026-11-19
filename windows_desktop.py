"""Windows notification icon, system banners, and a per-data-folder instance guard.

The message window is never shown. No desktop input is sent or captured.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import hashlib
import os
from pathlib import Path
import queue
import threading

APP_NAME = "To-do List"
APP_ID = "Stepan.ToDoList.Desktop"
WM_TRAY = 0x8000 + 42
WM_SHOW = 0x8000 + 43
WM_STOP = 0x8000 + 44


def instance_key(directory):
    return hashlib.sha256(str(Path(directory).resolve()).casefold().encode("utf-8")).hexdigest()[:24]


class InstanceGuard:
    def __init__(self, directory):
        self.key = instance_key(directory)
        self.window_title = "ToDoList.Tray." + self.key
        self.handle = None
        self.already_running = False
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
            self.kernel.CreateMutexW.restype = wt.HANDLE
            self.kernel.CloseHandle.argtypes = [wt.HANDLE]
            self.handle = self.kernel.CreateMutexW(None, False, "Local\\ToDoList." + self.key)
            if not self.handle:
                raise OSError(ctypes.get_last_error(), "Instance guard could not be created")
            self.already_running = ctypes.get_last_error() == 183

    def request_open(self):
        if os.name != "nt": return False
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
        user.FindWindowW.restype = wt.HWND
        user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        window = user.FindWindowW(None, self.window_title)
        return bool(window and user.PostMessageW(window, WM_SHOW, 0, 0))

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


if os.name == "nt":
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte*8)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                    ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR*128),
                    ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR*256),
                    ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR*64), ("dwInfoFlags", wt.DWORD),
                    ("guidItem", GUID), ("hBalloonIcon", wt.HICON)]


def clipped(text, capacity):
    return str(text).encode("utf-16-le")[:(capacity-1)*2].decode("utf-16-le", errors="ignore")


class DesktopBridge:
    def __init__(self, directory, icon_path=None):
        self.directory = Path(directory)
        self.window_title = "ToDoList.Tray." + instance_key(directory)
        self.icon_path = Path(icon_path) if icon_path else None
        self.events = queue.Queue()
        self.available = False
        self.error = ""
        self.hwnd = None
        self.icon = None
        self.enabled = True
        self._ready = threading.Event()
        self.thread = None

    def start(self):
        if os.name != "nt":
            self.error = "Systémová oznámení jsou dostupná ve Windows."
            return False
        self.thread = threading.Thread(target=self._run, name="todo-system-tray", daemon=True)
        self.thread.start()
        self._ready.wait(4)
        return self.available

    def _configure_api(self):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.shell = ctypes.WinDLL("shell32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetModuleHandleW.argtypes = [wt.LPCWSTR]
        self.kernel.GetModuleHandleW.restype = wt.HMODULE
        self.user.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        self.user.RegisterClassW.restype = wt.ATOM
        self.user.UnregisterClassW.argtypes = [wt.LPCWSTR, wt.HINSTANCE]
        self.user.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
        self.user.CreateWindowExW.restype = wt.HWND
        self.user.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        self.user.DefWindowProcW.restype = LRESULT
        self.user.DestroyWindow.argtypes = [wt.HWND]
        self.user.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
        self.user.GetMessageW.restype = wt.BOOL
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
        self.user.DispatchMessageW.restype = LRESULT
        self.user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        self.user.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
        self.user.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
        self.user.LoadImageW.restype = wt.HANDLE
        self.user.LoadIconW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
        self.user.LoadIconW.restype = wt.HICON
        self.user.DestroyIcon.argtypes = [wt.HICON]
        self.shell.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        self.shell.Shell_NotifyIconW.restype = wt.BOOL
        self.user.CreatePopupMenu.restype = wt.HMENU
        self.user.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
        self.user.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, ctypes.c_void_p]
        self.user.TrackPopupMenu.restype = wt.UINT
        self.user.DestroyMenu.argtypes = [wt.HMENU]
        self.user.SetForegroundWindow.argtypes = [wt.HWND]
        self.user.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]

    def _data(self, flags):
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = flags
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self.icon
        data.szTip = APP_NAME
        return data

    def _add_icon(self):
        data = self._data(1 | 2 | 4 | 128)
        success = bool(self.shell.Shell_NotifyIconW(0, ctypes.byref(data)))
        if success:
            data.uVersion = 4
            self.shell.Shell_NotifyIconW(4, ctypes.byref(data))
        self.available = success
        return success

    def _menu(self):
        menu = self.user.CreatePopupMenu()
        try:
            self.user.AppendMenuW(menu, 0, 1, f"Otevřít {APP_NAME}")
            self.user.AppendMenuW(menu, 8 if self.enabled else 0, 2, "Oznámení zapnuta")
            self.user.AppendMenuW(menu, 0x800, 0, None)
            self.user.AppendMenuW(menu, 0, 3, "Ukončit aplikaci")
            position = wt.POINT()
            self.user.GetCursorPos(ctypes.byref(position))
            # Only a user's tray-menu request can activate this otherwise hidden window.
            self.user.SetForegroundWindow(self.hwnd)
            result = self.user.TrackPopupMenu(menu, 0x100 | 2, position.x, position.y, 0, self.hwnd, None)
            if result:
                self.events.put(({1: "show", 2: "toggle_notifications", 3: "quit"}[result], None))
            self.user.PostMessageW(self.hwnd, 0, 0, 0)
        finally:
            self.user.DestroyMenu(menu)

    def _callback(self, hwnd, message, wparam, lparam):
        try:
            if message == self.taskbar_created:
                self._add_icon()
                return 0
            if message == WM_TRAY:
                event = lparam & 0xFFFF
                if event in (0x0203, 0x0400, 0x0401, 0x0405):
                    self.events.put(("show", None))
                elif event in (0x007B, 0x0205):
                    self._menu()
                return 0
            if message == WM_SHOW:
                self.events.put(("show", None))
                return 0
            if message in (WM_STOP, 0x0010):
                self.user.DestroyWindow(hwnd)
                return 0
            if message == 0x0002:
                self.user.PostQuitMessage(0)
                return 0
        except Exception as error:
            self.error = str(error)
        return self.user.DefWindowProcW(hwnd, message, wparam, lparam)

    def _run(self):
        registered = False
        try:
            self._configure_api()
            self.taskbar_created = self.user.RegisterWindowMessageW("TaskbarCreated")
            self._wndproc = WNDPROC(self._callback)
            self.module = self.kernel.GetModuleHandleW(None)
            self.class_name = "TodoTray." + instance_key(self.directory)
            window_class = WNDCLASSW()
            window_class.lpfnWndProc = self._wndproc
            window_class.hInstance = self.module
            window_class.lpszClassName = self.class_name
            if not self.user.RegisterClassW(ctypes.byref(window_class)):
                raise OSError(ctypes.get_last_error(), "RegisterClassW failed")
            registered = True
            self.hwnd = self.user.CreateWindowExW(0, self.class_name, self.window_title, 0, 0, 0, 0, 0, None, None, self.module, None)
            if not self.hwnd:
                raise OSError(ctypes.get_last_error(), "CreateWindowExW failed")
            self.owned_icon = False
            if self.icon_path and self.icon_path.exists():
                self.icon = self.user.LoadImageW(None, str(self.icon_path), 1, 32, 32, 0x10)
                self.owned_icon = bool(self.icon)
            if not self.icon:
                self.icon = self.user.LoadIconW(None, ctypes.c_void_p(32512))
            if not self._add_icon():
                raise OSError(ctypes.get_last_error(), "Shell_NotifyIconW failed")
            self._ready.set()
            message = wt.MSG()
            while self.user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                self.user.TranslateMessage(ctypes.byref(message))
                self.user.DispatchMessageW(ctypes.byref(message))
        except Exception as error:
            self.error = str(error)
        finally:
            self._ready.set()
            if self.hwnd:
                self.shell.Shell_NotifyIconW(2, ctypes.byref(self._data(0)))
            self.available = False
            if self.icon and getattr(self, "owned_icon", False):
                self.user.DestroyIcon(self.icon)
            if registered:
                self.user.UnregisterClassW(self.class_name, self.module)

    def notify(self, title, message, *, sound=True, dry_run=False):
        if not self.available:
            return False
        data = self._data(0x10)
        data.szInfoTitle = clipped(title, 64)
        data.szInfo = clipped(message, 256)
        data.dwInfoFlags = 1 | 0x80 | (0 if sound else 0x10)
        if dry_run:
            return bool(data.hWnd and data.szInfoTitle and data.szInfo)
        return bool(self.shell.Shell_NotifyIconW(1, ctypes.byref(data)))

    def dismiss_notification(self):
        if self.available:
            self.shell.Shell_NotifyIconW(1, ctypes.byref(self._data(0x10)))

    def close(self):
        if self.hwnd and getattr(self, "user", None):
            self.user.PostMessageW(self.hwnd, WM_STOP, 0, 0)
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)


def set_app_identity():
    if os.name == "nt":
        import winreg

        # Windows uses this registration for the notification sender's name.
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                    rf"Software\Classes\AppUserModelId\{APP_ID}",
                                    access=winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        except OSError:
            # Restricted registry access must not prevent the app from opening.
            pass
        shell = ctypes.WinDLL("shell32")
        shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]
        shell.SetCurrentProcessExplicitAppUserModelID(APP_ID)
