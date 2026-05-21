from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FloatingInputWindow(QWidget):
    sig_submit = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(720)
        self.resize(760, 200)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        # Meta chips
        meta = QHBoxLayout()
        meta.setSpacing(6)
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip_hotkey = self._make_chip("Ctrl + Alt + T 呼出")
        self._chip_route = self._make_chip("中文 → English")
        self._chip_tts = self._make_chip("自动 TTS：开")
        meta.addStretch(1)
        meta.addWidget(self._chip_hotkey)
        meta.addWidget(self._chip_route)
        meta.addWidget(self._chip_tts)
        meta.addStretch(1)
        root.addLayout(meta)

        # Result panel
        self._result = QWidget()
        self._result.setObjectName("floatResult")
        rl = QVBoxLayout(self._result)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(4)
        self._src_lbl = QLabel("等待输入…")
        self._src_lbl.setObjectName("floatSource")
        self._src_lbl.setWordWrap(True)
        self._tgt_lbl = QLabel("")
        self._tgt_lbl.setObjectName("floatTarget")
        self._tgt_lbl.setWordWrap(True)
        rl.addWidget(self._wrap_row("原文", self._src_lbl))
        rl.addWidget(self._wrap_row("译文", self._tgt_lbl))
        root.addWidget(self._result)

        # Input bar
        bar = QWidget()
        bar.setObjectName("floatInputBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 6, 6, 6)
        bl.setSpacing(8)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("输入文字 后按 Enter 翻译并发送…")
        self._edit.returnPressed.connect(self._on_submit)
        self._edit.setObjectName("floatLineEdit")
        bl.addWidget(self._edit, 1)
        self._send_btn = QPushButton("Enter 发送")
        self._send_btn.setObjectName("floatSendBtn")
        self._send_btn.clicked.connect(self._on_submit)
        bl.addWidget(self._send_btn)
        root.addWidget(bar)

    def _wrap_row(self, title: str, body: QLabel) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        cap = QLabel(title)
        cap.setObjectName("floatLabel")
        cap.setFixedWidth(40)
        h.addWidget(cap)
        h.addWidget(body, 1)
        return w

    def _make_chip(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("floatChip")
        return lbl

    def _on_submit(self) -> None:
        text = self._edit.text().strip()
        if not text:
            return
        self._src_lbl.setText(text)
        self._tgt_lbl.setText("翻译中…")
        self._edit.clear()
        self.sig_submit.emit(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(8, 13, 24, 230))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 16, 16)

    # ── public API ──
    def show_centered(self, screen) -> None:
        if screen is not None:
            g = screen.geometry()
            self.move(
                g.x() + (g.width() - self.width()) // 2,
                g.y() + int(g.height() * 0.72),
            )
        self.show()
        self.raise_()
        self.activateWindow()
        self._edit.setFocus()

    def update_chips(self, hotkey: str, route: str, tts_on: bool) -> None:
        self._chip_hotkey.setText(f"{hotkey} 呼出")
        self._chip_route.setText(route)
        self._chip_tts.setText(f"自动 TTS：{'开' if tts_on else '关'}")

    def show_result(self, source: str, translated: str) -> None:
        self._src_lbl.setText(source)
        self._tgt_lbl.setText(translated)
