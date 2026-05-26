from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer

SENTENCE_ENDINGS = set("。！？!?!.．")
FLUSH_DELAY_MS = 700


class SubtitleBuffer:
    """
    Accumulates streaming subtitle tokens and renders complete lines.
    Ported from the Tkinter s2s_gui.py buffering logic, using QTimer instead of root.after().
    Must be created in the Qt main thread (QTimer lives there).
    """

    def __init__(self, on_display: Callable[[str], None], max_lines: int = 5) -> None:
        self._on_display = on_display
        self._max_lines = max_lines
        self._buffer: str = ""
        self._lines: list[str] = []
        self._flush_timer = QTimer()
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush)

    def set_max_lines(self, n: int) -> None:
        self._max_lines = max(1, n)
        self._render(self._lines, self._buffer)  # reflow immediately

    def update(self, token: str) -> None:
        if not token:
            return
        current = token
        self._buffer = current
        self._render(self._lines, current)

        self._flush_timer.stop()
        self._flush_timer.start(FLUSH_DELAY_MS)

    def reset(self) -> None:
        self._flush_timer.stop()
        self._buffer = ""
        self._lines = []
        self._on_display("")

    def _flush(self) -> None:
        current = self._buffer.strip()
        self._flush_timer.stop()
        if not current:
            return
        if not self._lines or self._lines[-1] != current:
            self._lines.append(current)
            del self._lines[:-self._max_lines]
        self._buffer = ""
        self._render(self._lines, "")

    def _join(self, current: str, piece: str) -> str:
        if not current:
            return piece
        if piece in {"。", "，", "、", "！", "？", ".", ",", "!", "?", "．"}:
            return current + piece
        if current[-1:].isascii() and piece[:1].isascii() and piece[:1].isalnum():
            return current + " " + piece
        return current + piece

    def _render(self, lines: list[str], current: str) -> None:
        committed = [line for line in lines if line]
        if current:
            keep = max(0, self._max_lines - 1)
            visible = committed[-keep:] + [current] if keep else [current]
        else:
            visible = committed[-self._max_lines:]
        self._on_display("\n".join(visible))
