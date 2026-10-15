from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class StatusPill(QFrame):
    def __init__(self, text: str = "", kind: str = "warn", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panelStatePill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(30)
        self._kind = kind

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        self._dot = QLabel()
        self._dot.setObjectName("panelStatePillDot")
        self._dot.setFixedSize(8, 8)
        layout.addWidget(self._dot)

        self._label = QLabel(text)
        self._label.setObjectName("panelStatePillText")
        layout.addWidget(self._label)

        self.set_status(text, kind)

    def set_status(self, text: str, kind: str) -> None:
        self._label.setText(text)
        self._kind = kind
        self._dot.setProperty("kind", kind)
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        fill, stroke = self._colors_for_kind(self._kind)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(stroke, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)

    @staticmethod
    def _colors_for_kind(kind: str) -> tuple[QColor, QColor]:
        if kind == "normal":
            return QColor(66, 221, 146, 31), QColor(66, 221, 146, 87)
        if kind == "error":
            return QColor(255, 80, 80, 31), QColor(255, 80, 80, 87)
        return QColor(255, 209, 102, 31), QColor(255, 209, 102, 87)
