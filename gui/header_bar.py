from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "resource" / "app-icon.png"


class HeaderBar(QWidget):
    sig_start_all = Signal()
    sig_toggle_overlay = Signal()
    sig_adjust_overlay = Signal(bool)  # True = enter drag mode, False = exit
    sig_open_settings = Signal()
    sig_open_usage = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 12)
        layout.setSpacing(14)

        logo = QLabel()
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _APP_ICON_PATH.exists():
            logo.setPixmap(
                QPixmap(str(_APP_ICON_PATH)).scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo.setText("SH")
            logo.setStyleSheet(
                "color: #42dd92; font-size: 26px; font-weight: 900; "
                "padding: 4px 10px; border-radius: 10px; "
                "background: rgba(66,221,146,0.12); border: 1px solid rgba(66,221,146,0.3);"
            )
        layout.addWidget(logo)

        # Title block
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("SayHey")
        title.setStyleSheet("color: #eef7ff; font-size: 18px; font-weight: 900;")
        subtitle = QLabel("实时语音翻译字幕")
        subtitle.setStyleSheet("color: #6a8fa8; font-size: 12px;")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        layout.addLayout(title_block)

        layout.addStretch()

        # Usage cost chip (hidden unless tracking enabled)
        self._usage_chip = QPushButton("¥0.0000 · 累计 ¥0.00")
        self._usage_chip.setObjectName("statusChip")
        self._usage_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._usage_chip.setFlat(True)
        self._usage_chip.setToolTip("点击查看用量详情")
        self._usage_chip.setVisible(False)
        self._usage_chip.clicked.connect(self.sig_open_usage.emit)
        layout.addWidget(self._usage_chip)

        layout.addSpacing(8)

        # Status chip (hidden when idle)
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusChip")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Action buttons
        self._start_all_btn = QPushButton("一键开始")
        self._start_all_btn.setFixedWidth(100)
        self._start_all_btn.clicked.connect(self.sig_start_all.emit)
        layout.addWidget(self._start_all_btn)

        overlay_btn = QPushButton("悬浮字幕")
        overlay_btn.setObjectName("secondary")
        overlay_btn.setFixedWidth(90)
        overlay_btn.clicked.connect(self.sig_toggle_overlay.emit)
        layout.addWidget(overlay_btn)

        self._adjust_btn = QPushButton("调整位置")
        self._adjust_btn.setObjectName("secondary")
        self._adjust_btn.setFixedWidth(90)
        self._adjust_btn.setCheckable(True)
        self._adjust_btn.toggled.connect(self.sig_adjust_overlay.emit)
        layout.addWidget(self._adjust_btn)

        settings_btn = QToolButton()
        settings_btn.setText("⚙")
        settings_btn.setToolTip("设置")
        settings_btn.clicked.connect(self.sig_open_settings.emit)
        layout.addWidget(settings_btn)

    def set_usage_visible(self, visible: bool) -> None:
        self._usage_chip.setVisible(visible)

    def set_usage(self, session_cost: float, total_cost: float) -> None:
        self._usage_chip.setText(f"¥{session_cost:.4f} · 累计 ¥{total_cost:.2f}")

    def set_status(self, text: str, kind: str = "normal") -> None:
        """kind: 'normal', 'warn', 'error'. Chip hidden when idle."""
        name_map = {
            "normal": "statusChip",
            "warn": "statusChipWarn",
            "error": "statusChipError",
        }
        name = name_map.get(kind, "statusChip")
        self._status_label.setObjectName(name)
        self._status_label.setStyleSheet("")
        self._status_label.style().polish(self._status_label)
        short = text[:50] + "..." if len(text) > 50 else text
        self._status_label.setText(short)
        idle = kind == "normal" and text in ("", "就绪")
        self._status_label.setVisible(not idle)
