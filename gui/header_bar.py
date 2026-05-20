from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.version import __version__


_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "resource" / "app-icon.png"


class HeaderBar(QWidget):
    sig_start_all = Signal()
    sig_toggle_overlay = Signal()
    sig_adjust_overlay = Signal(bool)  # True = enter drag mode, False = exit
    sig_open_settings = Signal()
    sig_open_usage = Signal()
    sig_open_feedback = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._show_token = False
        self._session_cost = 0.0
        self._total_cost = 0.0
        self._session_tokens = 0
        self._total_tokens = 0
        self._pending_update = None
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

        # Usage cost chip — anchored left, next to title banner
        self._usage_chip = QPushButton("¥0.0000 · 累计 ¥0.00")
        self._usage_chip.setObjectName("statusChip")
        self._usage_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._usage_chip.setFlat(True)
        self._usage_chip.setToolTip("点击查看用量详情")
        self._usage_chip.setVisible(False)
        self._usage_chip.clicked.connect(self.sig_open_usage.emit)
        layout.addWidget(self._usage_chip)

        layout.addStretch()

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

        feedback_btn = QPushButton("提需求")
        feedback_btn.setObjectName("secondary")
        feedback_btn.setFixedWidth(80)
        feedback_btn.setToolTip("快速提交需求/反馈，将同步到 GitHub Issue")
        feedback_btn.clicked.connect(self.sig_open_feedback.emit)
        layout.addWidget(feedback_btn)

        settings_btn = QToolButton()
        settings_btn.setText("⚙")
        settings_btn.setToolTip("设置")
        settings_btn.clicked.connect(self.sig_open_settings.emit)
        layout.addWidget(settings_btn)

        self._version_btn = QPushButton(f"v{__version__}")
        self._version_btn.setObjectName("versionChip")
        self._version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._version_btn.setFlat(True)
        self._version_btn.setToolTip("当前版本，点击检查更新")
        self._version_btn.setStyleSheet(
            "QPushButton#versionChip{padding:2px 10px;border-radius:8px;"
            "background:#2a2f3a;color:#bbb;font-size:12px;}"
            "QPushButton#versionChip[hasUpdate=\"true\"]{background:#5a2a2a;color:#fff;}"
        )
        self._version_btn.setProperty("hasUpdate", False)
        self._version_btn.clicked.connect(self._on_version_clicked)
        layout.addWidget(self._version_btn)

    def set_update_available(self, info) -> None:
        self._pending_update = info
        self._version_btn.setText(f"v{__version__} ●")
        self._version_btn.setToolTip(f"发现新版本 {info.latest_tag}，点击查看")
        self._version_btn.setProperty("hasUpdate", True)
        s = self._version_btn.style()
        s.unpolish(self._version_btn)
        s.polish(self._version_btn)

    def _on_version_clicked(self) -> None:
        if self._pending_update and self._pending_update.has_update:
            from gui.update_dialog import UpdateDialog
            UpdateDialog(self._pending_update, self).exec()
        else:
            QMessageBox.information(
                self, "版本", f"当前版本 v{__version__}\n暂无可用更新"
            )

    def set_usage_visible(self, visible: bool) -> None:
        self._usage_chip.setVisible(visible)

    def set_usage_mode(self, show_token: bool) -> None:
        self._show_token = show_token
        self._update_chip_text()

    def set_usage(self, session_cost: float, total_cost: float, session_tokens: int = 0, total_tokens: int = 0) -> None:
        self._session_cost = session_cost
        self._total_cost = total_cost
        self._session_tokens = session_tokens
        self._total_tokens = total_tokens
        self._update_chip_text()

    def _update_chip_text(self) -> None:
        if self._show_token:
            self._usage_chip.setText(f"{self._session_tokens:,} tokens · 累计 {self._total_tokens:,}")
        else:
            self._usage_chip.setText(f"¥{self._session_cost:.4f} · 累计 ¥{self._total_cost:.2f}")

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
