from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QVBoxLayout, QPlainTextEdit, QLabel

_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "runtime.log"
_MAX_LINES = 300


class RuntimeLogPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("运行日志")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self._edit = QPlainTextEdit()
        self._edit.setObjectName("log")
        self._edit.setReadOnly(True)
        self._edit.setMaximumBlockCount(_MAX_LINES)
        layout.addWidget(self._edit)

    def append(self, message: str) -> None:
        self._edit.appendPlainText(message)
        self._edit.verticalScrollBar().setValue(self._edit.verticalScrollBar().maximum())
        self._write_to_file(message)

    def _write_to_file(self, message: str) -> None:
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        except OSError:
            pass
