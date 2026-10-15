from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer

SENTENCE_ENDINGS = set("。！？!?．.")
COMMA_BREAKS = set("，、,;；:：")
FLUSH_DELAY_MS = 700
SOFT_WRAP_CHARS = 25  # 单段超过此长度时，按逗号兜底换行


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
        # 边界检测：若新快照不是旧 buffer 的前缀延伸，说明引擎刚刚重置了累计器
        # （火山的 TTSSentenceStart、Qwen 的 response.created 都会触发这种情况），
        # 此时必须先把旧 buffer flush 到 _lines，否则 700ms 自动 flush 还没来得及触发
        # 就被覆盖，那一段译文就永远丢了。
        if self._buffer and not current.startswith(self._buffer):
            self._flush()
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
        parts = _split_for_display(current)
        for part in parts:
            if not self._lines or self._lines[-1] != part:
                self._lines.append(part)
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
            cur_parts = _split_for_display(current)
            keep = max(0, self._max_lines - len(cur_parts))
            visible = (committed[-keep:] + cur_parts if keep else cur_parts)[-self._max_lines:]
        else:
            visible = committed[-self._max_lines:]
        self._on_display("\n".join(visible))


def _split_for_display(text: str) -> list[str]:
    """按句末标点拆行；单段过长时再按逗号兜底拆一次。"""
    sentences: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in SENTENCE_ENDINGS:
            stripped = cur.strip()
            if stripped:
                sentences.append(stripped)
            cur = ""
    tail = cur.strip()
    if tail:
        sentences.append(tail)

    out: list[str] = []
    for seg in sentences:
        if len(seg) <= SOFT_WRAP_CHARS:
            out.append(seg)
            continue
        buf = ""
        for ch in seg:
            buf += ch
            if ch in COMMA_BREAKS and len(buf) >= SOFT_WRAP_CHARS:
                out.append(buf.strip())
                buf = ""
        rest = buf.strip()
        if rest:
            out.append(rest)
    return out
