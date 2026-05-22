from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget


_instance: Optional["_Toast"] = None


class _Toast(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._label = QLabel("", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "QLabel {"
            "color: #ffffff;"
            "background: rgba(20,28,40,0.88);"
            "border: 1px solid rgba(163,207,255,0.28);"
            "border-radius: 14px;"
            "padding: 10px 22px;"
            "font-size: 16px;"
            "font-weight: 700;"
            "}"
        )

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self._on_anim_finished)
        self._fading = False

    def show_text(self, text: str, duration_ms: int = 1200) -> None:
        self._label.setText(text)
        self._label.adjustSize()
        margin_w, margin_h = 24, 12
        w = self._label.width() + margin_w
        h = self._label.height() + margin_h
        self.resize(w, h)
        self._label.move((w - self._label.width()) // 2, (h - self._label.height()) // 2)

        screen = QGuiApplication.screenAt(self.cursor().pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            x = geo.x() + (geo.width() - w) // 2
            y = geo.y() + int(geo.height() * 0.18)
            self.move(x, y)

        self._anim.stop()
        self._effect.setOpacity(1.0)
        self._fading = False
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _fade_out(self) -> None:
        self._fading = True
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._fading and self._effect.opacity() <= 0.01:
            self.hide()
            self._fading = False


def show_toast(text: str, duration_ms: int = 1200) -> None:
    global _instance
    if _instance is None:
        _instance = _Toast()
    _instance.show_text(text, duration_ms)
