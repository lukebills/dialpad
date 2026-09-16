"""Own Windows global hotkeys on a dedicated message-loop thread.

Importing this module is safe on other platforms. Callbacks must enqueue work;
they must not access Tk from the worker thread.
"""
import ctypes
from ctypes import wintypes
import threading


class WindowsHotkeys:
    KEYS = (0x81, 0x82, 0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0x83)

    def __init__(self, notify, user32=None, kernel32=None):
        self.notify = notify
        self.user32 = user32 if user32 is not None else ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = kernel32 if kernel32 is not None else ctypes.WinDLL('kernel32', use_last_error=True)
        if user32 is None:
            self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self.user32.GetMessageW.restype = wintypes.BOOL
            self.user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self.stopping = threading.Event()
        self.initialized = threading.Event()
        self.thread_id = None
        self.thread = threading.Thread(target=self._run, name='Dialpad hotkeys', daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if not self.thread.is_alive():
            return
        # Initialization creates the message queue before publishing its thread ID.
        if self.initialized.wait(2) and self.thread_id is not None:
            self.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)  # WM_QUIT
        self.thread.join(timeout=2)

    def _run(self):
        registered = []
        try:
            msg = wintypes.MSG()
            self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            self.thread_id = self.kernel32.GetCurrentThreadId()
            self.initialized.set()
            for hotkey_id, key in enumerate(self.KEYS, 1):
                if self.stopping.is_set():
                    return
                if not self.user32.RegisterHotKey(None, hotkey_id, 0x4000, key):
                    self.notify('ready', {'ready': False, 'error': 'A reserved F13–F20 shortcut is in use. Close another app using these keys and reopen.'})
                    return
                registered.append(hotkey_id)
            self.notify('ready', {'ready': True})
            while not self.stopping.is_set():
                result = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    raise RuntimeError('Windows could not read the global shortcut message queue.')
                if msg.message == 0x0312 and 1 <= msg.wParam <= len(self.KEYS):
                    self.notify('hotkey', int(msg.wParam))
        except Exception as exc:
            self.notify('ready', {'ready': False, 'error': str(exc)})
        finally:
            self.initialized.set()
            for hotkey_id in registered:
                self.user32.UnregisterHotKey(None, hotkey_id)
