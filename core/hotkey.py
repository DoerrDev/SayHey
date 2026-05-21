from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Callable, Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

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
