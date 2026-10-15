from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Callable, Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject, QTimer

_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_WM_HOTKEY = 0x0312

_VK_MAP = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
}

_VK_XBUTTON1 = 0x05
_VK_XBUTTON2 = 0x06

# Mouse side buttons: bound through a low-level mouse hook instead of RegisterHotKey.
MOUSE_KEYS = {"mouse4", "mouse5"}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    if not text:
        return None
    parts = [p.strip().lower() for p in text.replace("++", "+plus").split("+") if p.strip()]
    mods = 0
    vk: Optional[int] = None
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= _MOD_CONTROL
        elif p == "alt":
            mods |= _MOD_ALT
        elif p == "shift":
            mods |= _MOD_SHIFT
        elif p in ("win", "meta", "super"):
            mods |= _MOD_WIN
        elif p == "plus":
            vk = 0xBB
        elif p in _VK_MAP:
            vk = _VK_MAP[p]
        elif len(p) == 1:
            vk = ord(p.upper())
    if vk is None:
        return None
    return mods, vk


def parse_mouse_hotkey(text: str) -> tuple[int, str] | None:
    """Parse a mouse-side-button combo, e.g. 'mouse4' or 'ctrl+mouse5'.
    Returns (mods, key) where key is 'mouse4' or 'mouse5'. None if not a mouse combo."""
    if not text:
        return None
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    mods = 0
    key: Optional[str] = None
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= _MOD_CONTROL
        elif p == "alt":
            mods |= _MOD_ALT
        elif p == "shift":
            mods |= _MOD_SHIFT
        elif p in ("win", "meta", "super"):
            mods |= _MOD_WIN
        elif p in MOUSE_KEYS:
            key = p
        else:
            return None
    if key is None:
        return None
    return mods, key


def format_hotkey(raw: str) -> str:
    parts = [p.strip() for p in (raw or "").split("+") if p.strip()]
    if not parts:
        return "未绑定"
    def _cap(p: str) -> str:
        if p.lower() == "mouse4":
            return "Mouse4"
        if p.lower() == "mouse5":
            return "Mouse5"
        return p[:1].upper() + p[1:] if len(p) > 1 else p.upper()
    return " + ".join(_cap(p) for p in parts)


def parse_hold_hotkey(text: str) -> tuple[int, int] | None:
    mouse = parse_mouse_hotkey(text)
    if mouse is not None:
        mods, key = mouse
        return mods, _VK_XBUTTON1 if key == "mouse4" else _VK_XBUTTON2
    return parse_hotkey(text)


class HoldHotkeyMonitor(QObject):
    """Poll a global key state so both press and release transitions are observable."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._user32 = ctypes.windll.user32
        self._binding: tuple[int, int] | None = None
        self._pressed = False
        self._on_pressed: Optional[Callable[[], None]] = None
        self._on_released: Optional[Callable[[], None]] = None
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._poll)

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def configure(
        self,
        combo: str,
        on_pressed: Callable[[], None],
        on_released: Callable[[], None],
    ) -> bool:
        self.clear()
        binding = parse_hold_hotkey(combo)
        if binding is None:
            return False
        self._binding = binding
        self._on_pressed = on_pressed
        self._on_released = on_released
        self._timer.start()
        return True

    def clear(self) -> None:
        self._timer.stop()
        if self._pressed and self._on_released is not None:
            self._on_released()
        self._pressed = False
        self._binding = None
        self._on_pressed = None
        self._on_released = None

    def _key_down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _poll(self) -> None:
        if self._binding is None:
            return
        mods, vk = self._binding
        down = self._key_down(vk)
        if mods & _MOD_CONTROL:
            down = down and (self._key_down(_VK_LCONTROL) or self._key_down(_VK_RCONTROL))
        if mods & _MOD_ALT:
            down = down and (self._key_down(_VK_LMENU) or self._key_down(_VK_RMENU))
        if mods & _MOD_SHIFT:
            down = down and (self._key_down(_VK_LSHIFT) or self._key_down(_VK_RSHIFT))
        if mods & _MOD_WIN:
            down = down and (self._key_down(_VK_LWIN) or self._key_down(_VK_RWIN))
        if down == self._pressed:
            return
        self._pressed = down
        callback = self._on_pressed if down else self._on_released
        if callback is not None:
            callback()


# --- Low-level mouse hook (for binding mouse side buttons globally) ---
_WH_MOUSE_LL = 14
_WM_XBUTTONDOWN = 0x020B
_VK_LCONTROL = 0xA2
_VK_RCONTROL = 0xA3
_VK_LMENU = 0xA4
_VK_RMENU = 0xA5
_VK_LSHIFT = 0xA0
_VK_RSHIFT = 0xA1
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


# WPARAM / LPARAM / LRESULT are pointer-sized on Windows. wintypes uses c_long (32-bit)
# which truncates on x64 and causes OverflowError. Use ssize_t/size_t to match LONG_PTR.
_LRESULT = ctypes.c_ssize_t
_WPARAM = ctypes.c_size_t
_LPARAM = ctypes.c_ssize_t

_LL_HOOK_PROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, _WPARAM, _LPARAM)


class _MouseHook:
    """Global low-level mouse hook for side buttons. Non-intercepting (passes events through)."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._hook = None
        # key ('mouse4'/'mouse5', mods_bitmask) -> callback
        self._bindings: dict[tuple[str, int], Callable[[], None]] = {}
        self._proc_ref = _LL_HOOK_PROC(self._proc)

    def _ensure_installed(self) -> bool:
        if self._hook is not None:
            return True
        # SetWindowsHookExW(idHook, lpfn, hMod, dwThreadId)
        SetWindowsHookExW = self._user32.SetWindowsHookExW
        SetWindowsHookExW.argtypes = [ctypes.c_int, _LL_HOOK_PROC, wt.HINSTANCE, wt.DWORD]
        SetWindowsHookExW.restype = wt.HHOOK
        get_mod = self._kernel32.GetModuleHandleW
        get_mod.argtypes = [wt.LPCWSTR]
        get_mod.restype = wt.HMODULE
        # Declare CallNextHookEx with pointer-sized LPARAM/WPARAM/LRESULT.
        cnh = self._user32.CallNextHookEx
        cnh.argtypes = [wt.HHOOK, ctypes.c_int, _WPARAM, _LPARAM]
        cnh.restype = _LRESULT
        h_module = get_mod(None)
        self._hook = SetWindowsHookExW(_WH_MOUSE_LL, self._proc_ref, h_module, 0)
        return self._hook is not None and self._hook != 0

    def _uninstall_if_empty(self) -> None:
        if self._hook and not self._bindings:
            try:
                self._user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None

    def _current_mods(self) -> int:
        gks = self._user32.GetAsyncKeyState
        mods = 0
        if (gks(_VK_LCONTROL) & 0x8000) or (gks(_VK_RCONTROL) & 0x8000):
            mods |= _MOD_CONTROL
        if (gks(_VK_LMENU) & 0x8000) or (gks(_VK_RMENU) & 0x8000):
            mods |= _MOD_ALT
        if (gks(_VK_LSHIFT) & 0x8000) or (gks(_VK_RSHIFT) & 0x8000):
            mods |= _MOD_SHIFT
        if (gks(_VK_LWIN) & 0x8000) or (gks(_VK_RWIN) & 0x8000):
            mods |= _MOD_WIN
        return mods

    def _proc(self, nCode: int, wParam: int, lParam: int) -> int:
        try:
            if nCode >= 0 and wParam == _WM_XBUTTONDOWN:
                info = ctypes.cast(lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                # HIWORD of mouseData: 1 = XButton1 (mouse4), 2 = XButton2 (mouse5)
                xbtn = (info.mouseData >> 16) & 0xFFFF
                key = "mouse4" if xbtn == 1 else ("mouse5" if xbtn == 2 else "")
                if key:
                    mods = self._current_mods()
                    cb = self._bindings.get((key, mods))
                    if cb is not None:
                        try:
                            cb()
                        except Exception:
                            pass
        except Exception:
            pass
        # Always pass the event through (non-intercepting)
        return self._user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def register(self, combo: str, callback: Callable[[], None]) -> bool:
        parsed = parse_mouse_hotkey(combo)
        if parsed is None:
            return False
        mods, key = parsed
        if not self._ensure_installed():
            return False
        self._bindings[(key, mods)] = callback
        return True

    def unregister(self, combo: str) -> None:
        parsed = parse_mouse_hotkey(combo)
        if parsed is None:
            return
        mods, key = parsed
        self._bindings.pop((key, mods), None)
        self._uninstall_if_empty()


class HotkeyManager(QAbstractNativeEventFilter):
    """Manage multiple global hotkeys, each identified by a string action key.
    Supports keyboard combos via RegisterHotKey, and mouse side buttons via a low-level hook."""

    def __init__(self) -> None:
        super().__init__()
        self._user32 = ctypes.windll.user32
        # action -> (id_or_zero, callback, combo, is_mouse)
        self._actions: dict[str, tuple[int, Callable[[], None], str, bool]] = {}
        # id -> action (keyboard hotkeys only)
        self._id_to_action: dict[int, str] = {}
        self._next_id = 1
        self._mouse_hook = _MouseHook()

    def register_action(self, action: str, combo: str, callback: Callable[[], None]) -> bool:
        self.unregister_action(action)
        if not combo:
            return False
        # Mouse combo path
        mouse_parsed = parse_mouse_hotkey(combo)
        if mouse_parsed is not None:
            ok = self._mouse_hook.register(combo, callback)
            if not ok:
                return False
            self._actions[action] = (0, callback, combo, True)
            return True
        # Keyboard combo path
        parsed = parse_hotkey(combo)
        if parsed is None:
            return False
        mods, vk = parsed
        hk_id = self._next_id
        self._next_id += 1
        ok = bool(self._user32.RegisterHotKey(None, hk_id, mods, vk))
        if not ok:
            return False
        self._actions[action] = (hk_id, callback, combo, False)
        self._id_to_action[hk_id] = action
        return True

    def unregister_action(self, action: str) -> None:
        entry = self._actions.pop(action, None)
        if entry is None:
            return
        hk_id, _, combo, is_mouse = entry
        if is_mouse:
            self._mouse_hook.unregister(combo)
            return
        self._id_to_action.pop(hk_id, None)
        try:
            self._user32.UnregisterHotKey(None, hk_id)
        except Exception:
            pass

    def unregister_all(self) -> None:
        for action in list(self._actions.keys()):
            self.unregister_action(action)

    def nativeEventFilter(self, eventType, message):  # type: ignore[override]
        if eventType in (b"windows_generic_MSG", QByteArray(b"windows_generic_MSG")):
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
            except Exception:
                return False, 0
            if msg.message == _WM_HOTKEY:
                action = self._id_to_action.get(int(msg.wParam))
                if action is not None:
                    entry = self._actions.get(action)
                    if entry is not None:
                        try:
                            entry[1]()
                        except Exception:
                            pass
                        return True, 0
        return False, 0


# Backwards-compat single-hotkey wrapper (unused by new code; keep until removed elsewhere)
class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback
        self._id = 1
        self._registered = False
        self._user32 = ctypes.windll.user32

    def register(self, hotkey_text: str) -> bool:
        self.unregister()
        parsed = parse_hotkey(hotkey_text)
        if parsed is None:
            return False
        mods, vk = parsed
        ok = bool(self._user32.RegisterHotKey(None, self._id, mods, vk))
        self._registered = ok
        return ok

    def unregister(self) -> None:
        if self._registered:
            try:
                self._user32.UnregisterHotKey(None, self._id)
            except Exception:
                pass
            self._registered = False

    def nativeEventFilter(self, eventType, message):  # type: ignore[override]
        if eventType in (b"windows_generic_MSG", QByteArray(b"windows_generic_MSG")):
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
            except Exception:
                return False, 0
            if msg.message == _WM_HOTKEY and msg.wParam == self._id:
                try:
                    self._callback()
                except Exception:
                    pass
                return True, 0
        return False, 0
