from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Optional

from PySide6.QtCore import Qt, QPoint, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020


def _set_win32_click_through(hwnd: int, enabled: bool) -> None:
    try:
        style = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        if enabled:
            style |= _WS_EX_LAYERED | _WS_EX_TRANSPARENT
        else:
            style = (style | _WS_EX_LAYERED) & ~_WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
    except Exception:
        pass


class SubtitleOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._click_through = True
        self._bg_opacity: float = 0.85
        self._drag_mode = False
        self._drag_mode_saved_ct = True
        self._drag_pos: Optional[QPoint] = None
        self._on_pos_saved = None  # callable(x, y)
        self._text_color = "#ffffff"
        self._font_size = 32
        self._overlay_width = 800
        self._build_ui()
        self.resize(self._overlay_width, 80)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(0)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._apply_label_style()

    def _apply_label_style(self) -> None:
        font = QFont("Segoe UI Variable", self._font_size)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setStyleSheet(
            f"background-color: transparent; color: {self._text_color}; "
            f"font-size: {self._font_size}px; font-weight: 900;"
        )

    def _adjust_height(self) -> None:
        m = self.layout().contentsMargins()
        inner_w = self.width() - m.left() - m.right()
        if inner_w <= 0:
            return
        lh = self._label.heightForWidth(inner_w)
        if lh <= 0:
            lh = self._label.sizeHint().height()
        total = max(50, lh + m.top() + m.bottom())
        if total != self.height():
            self.resize(self.width(), total)

    # ── public setters (called from _apply_settings) ──────────────────────

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        self._apply_label_style()
        self._adjust_height()

    def set_text_color(self, color: str) -> None:
        self._text_color = color
        self._apply_label_style()

    def set_opacity(self, value: float) -> None:
        self._bg_opacity = max(0.1, min(1.0, value))
        self.update()

    def set_overlay_width(self, w: int) -> None:
        self._overlay_width = max(300, w)
        self.resize(self._overlay_width, self.height())
        self._adjust_height()

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        if not self._drag_mode and self.isVisible():
            _set_win32_click_through(int(self.winId()), enabled)

    def set_drag_mode(self, enabled: bool) -> None:
        self._drag_mode = enabled
        if enabled:
            self._drag_mode_saved_ct = self._click_through
            if self.isVisible():
                _set_win32_click_through(int(self.winId()), False)
        else:
            if self.isVisible():
                _set_win32_click_through(int(self.winId()), self._click_through)
        self.update()

    # ── slot ──────────────────────────────────────────────────────────────

    @Slot(str)
    def update_text(self, text: str) -> None:
        self._label.setText(text)
        self._adjust_height()

    # ── Qt events ────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _set_win32_click_through(int(self.winId()), self._click_through)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = int(220 * self._bg_opacity)
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 18, 18)
        if self._drag_mode:
            painter.setPen(QPen(QColor(66, 221, 146), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 17, 17)
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor(66, 221, 146))
            painter.drawText(
                self.rect().adjusted(12, 6, -12, 0),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                "拖动调整位置",
            )

    def mousePressEvent(self, event) -> None:
        if (self._drag_mode or not self._click_through) and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (self._drag_mode or not self._click_through):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_pos is not None:
            self._drag_pos = None
            if self._on_pos_saved:
                pos = self.pos()
                self._on_pos_saved(pos.x(), pos.y())
        super().mouseReleaseEvent(event)
