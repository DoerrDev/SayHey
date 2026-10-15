from __future__ import annotations

from PySide6.QtCore import QTimer

from core import history_store

IDLE_MS = 1500


class HistoryRecorder:
    """把引擎的累计文本快照配对成一条条历史记录写入磁盘。

    引擎每次发出的是当前语句的完整快照；当新快照不再是旧快照的前缀延伸时，
    说明上一句已结束，先落盘再开始新的一句。空闲 IDLE_MS 也落盘。
    """

    def __init__(self, mode: str, enabled: bool = True) -> None:
        self._mode = mode
        self._enabled = bool(enabled)
        self._source = ""
        self._translation = ""
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.commit)

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.commit()
        self._enabled = bool(enabled)

    def update_source(self, text: str) -> None:
        if not self._enabled or not text:
            return
        if self._source and not text.startswith(self._source):
            self.commit()
        self._source = text
        self._restart()

    def update_translation(self, text: str) -> None:
        if not self._enabled or not text:
            return
        if self._translation and not text.startswith(self._translation):
            self.commit()
        self._translation = text
        self._restart()

    def record(self, source: str, translation: str) -> None:
        if not self._enabled:
            return
        try:
            history_store.append(self._mode, source, translation)
        except Exception:
            pass

    def commit(self) -> None:
        self._timer.stop()
        source, translation = self._source, self._translation
        self._source = ""
        self._translation = ""
        if not self._enabled:
            return
        if not source.strip() and not translation.strip():
            return
        try:
            history_store.append(self._mode, source, translation)
        except Exception:
            pass

    def _restart(self) -> None:
        self._timer.stop()
        self._timer.start(IDLE_MS)
