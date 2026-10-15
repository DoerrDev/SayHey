from __future__ import annotations

from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.runtime_log import runtime_log
from gui.icons import resource_pixmap

_MAX_LINES = 10000
_MAX_EVENTS = 6

# High-frequency diagnostic tags (per audio frame / per protocol event). They go
# to the full log only, so they neither flood "最近状态" nor rebuild its rows.
_VERBOSE_TAGS = (
    "[typed-tts-raw]",
    "[typed-mt-raw]",
    "[qwen-tts-evt]",
    "[qwen-mt-raw]",
    "[qwen-mt-hotwords]",
    "[out-level]",
    "[audio-status]",
    "[usage]",
    "[game-s2t-usage]",
    "[mt-usage]",
    "[tts-usage]",
    "[qwen-mt-usage]",
    "[qwen-realtime-usage]",
    "[qwen-tts-usage]",
)


def is_verbose_status(message: str) -> bool:
    return message.startswith(_VERBOSE_TAGS)


def _message_kind(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ("error", "failed", "traceback")) or any(
        token in message for token in ("错误", "失败", "异常")
    ):
        return "error"
    if any(token in lowered for token in ("warn", "waiting", "silent", "stopping")) or any(
        token in message for token in ("等待", "静音", "停止中")
    ):
        return "warn"
    if any(token in lowered for token in ("saved", "started", "ready", "ok")) or any(
        token in message for token in ("已保存", "已启动", "通过", "就绪")
    ):
        return "normal"
    return "info"


class _EventRow(QWidget):
    def __init__(self, stamp: str, message: str, kind: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        time_label = QLabel(stamp)
        time_label.setObjectName("activityTime")
        time_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(time_label)

        dot = QLabel()
        dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        dot.setFixedWidth(14)
        icon_name = {
            "normal": "dot-green",
            "warn": "dot-yellow",
            "error": "dot-red",
        }.get(kind, "dot-blue")
        dot.setPixmap(resource_pixmap(icon_name, 8, 8))
        layout.addWidget(dot)

        text = QLabel(message)
        text.setObjectName("activityText")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(text, 1)


class RuntimeLogPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._event_rows: deque[_EventRow] = deque()
        self._log_expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title = QLabel("最近状态")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._toggle_btn = QPushButton("展开运行日志")
        self._toggle_btn.setObjectName("secondary")
        self._toggle_btn.setFixedHeight(32)
        self._toggle_btn.clicked.connect(self._toggle_log)
        header.addWidget(self._toggle_btn)
        layout.addLayout(header)

        self._events_container = QWidget()
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setContentsMargins(0, 0, 0, 0)
        self._events_layout.setSpacing(9)
        self._empty_label = QLabel("运行中的关键状态会显示在这里，方便快速判断当前卡在哪一步。")
        self._empty_label.setObjectName("panelDesc")
        self._empty_label.setWordWrap(True)
        self._events_layout.addWidget(self._empty_label)
        self._events_layout.addStretch()
        layout.addWidget(self._events_container)

        self._edit = QPlainTextEdit()
        self._edit.setObjectName("log")
        self._edit.setReadOnly(True)
        self._edit.setMaximumBlockCount(_MAX_LINES)
        self._edit.setVisible(False)
        self._edit.setMinimumHeight(130)
        layout.addWidget(self._edit)

    def append(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M")
        line = f"[{stamp}] {message}"
        if not is_verbose_status(message):
            self._add_event(stamp, message, _message_kind(message))

        self._edit.appendPlainText(line)
        self._edit.verticalScrollBar().setValue(self._edit.verticalScrollBar().maximum())
        runtime_log().write(line)

    def _add_event(self, stamp: str, message: str, kind: str) -> None:
        self._empty_label.setVisible(False)
        row = _EventRow(stamp, message, kind)
        self._events_layout.insertWidget(1, row)
        self._event_rows.appendleft(row)
        while len(self._event_rows) > _MAX_EVENTS:
            old = self._event_rows.pop()
            self._events_layout.removeWidget(old)
            old.deleteLater()

    def _toggle_log(self) -> None:
        self._log_expanded = not self._log_expanded
        self._edit.setVisible(self._log_expanded)
        self._toggle_btn.setText("收起运行日志" if self._log_expanded else "展开运行日志")
