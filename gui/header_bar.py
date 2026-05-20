from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.version import __version__
from gui.icons import resource_icon
from gui.status_pill import StatusPill


_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "resource" / "app-icon.png"


class HeaderBar(QWidget):
    sig_start_all = Signal()
    sig_toggle_overlay = Signal()
    sig_adjust_overlay = Signal(bool)
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
        layout.setSpacing(16)

        logo = QLabel()
        logo.setFixedSize(46, 46)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _APP_ICON_PATH.exists():
            logo.setPixmap(
                QPixmap(str(_APP_ICON_PATH)).scaled(
                    46,
                    46,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo.setText("SH")
            logo.setObjectName("logoFallback")
        layout.addWidget(logo)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("SayHey")
        title.setObjectName("headerTitle")
        title_block.addWidget(title)
        subtitle = QLabel("实时语音翻译字幕")
        subtitle.setObjectName("headerSubtitle")
        title_block.addWidget(subtitle)
        layout.addLayout(title_block)

        self._usage_chip = QPushButton("本次 0 tokens")
        self._usage_chip.setObjectName("secondary")
        self._usage_chip.setVisible(False)
        self._usage_chip.setToolTip("点击查看用量详情")
        self._usage_chip.clicked.connect(self.sig_open_usage.emit)
        layout.addWidget(self._usage_chip)

        layout.addStretch()

        self._status_pill = StatusPill("", "warn")
        self._status_pill.setVisible(False)
        layout.addWidget(self._status_pill)

        self._start_all_btn = QPushButton("一键开启")
        self._start_all_btn.setIcon(resource_icon("play"))
        self._start_all_btn.setIconSize(QSize(14, 14))
        self._start_all_btn.setFixedWidth(108)
        self._start_all_btn.clicked.connect(self.sig_start_all.emit)
        layout.addWidget(self._start_all_btn)

        self._overlay_btn = QPushButton("显示字幕")
        self._overlay_btn.setObjectName("secondary")
        self._overlay_btn.setIcon(resource_icon("eye"))
        self._overlay_btn.setIconSize(QSize(14, 14))
        self._overlay_btn.setFixedWidth(94)
        self._overlay_btn.clicked.connect(self.sig_toggle_overlay.emit)
        layout.addWidget(self._overlay_btn)

        self._adjust_btn = QPushButton("调整位置")
        self._adjust_btn.setObjectName("secondary")
        self._adjust_btn.setIcon(resource_icon("move"))
        self._adjust_btn.setIconSize(QSize(14, 14))
        self._adjust_btn.setFixedWidth(94)
        self._adjust_btn.setCheckable(True)
        self._adjust_btn.setEnabled(False)
        self._adjust_btn.toggled.connect(self.sig_adjust_overlay.emit)
        layout.addWidget(self._adjust_btn)

        self._feedback_btn = QPushButton("提需求")
        self._feedback_btn.setObjectName("secondary")
        self._feedback_btn.setIcon(resource_icon("message"))
        self._feedback_btn.setIconSize(QSize(14, 14))
        self._feedback_btn.setFixedWidth(82)
        self._feedback_btn.setToolTip("提交反馈或需求，会同步到项目问题列表。")
        self._feedback_btn.clicked.connect(self.sig_open_feedback.emit)
        layout.addWidget(self._feedback_btn)

        settings_btn = QToolButton()
        settings_btn.setIcon(resource_icon("gear"))
        settings_btn.setIconSize(QSize(18, 18))
        settings_btn.setToolTip("设置")
        settings_btn.clicked.connect(self.sig_open_settings.emit)
        layout.addWidget(settings_btn)

        self._version_btn = QPushButton(f"v{__version__}")
        self._version_btn.setObjectName("versionChip")
        self._version_btn.clicked.connect(self._on_version_clicked)
        layout.addWidget(self._version_btn)

    def set_overlay_visible(self, visible: bool) -> None:
        self._overlay_btn.setText("隐藏字幕" if visible else "显示字幕")
        self._overlay_btn.setIcon(resource_icon("eye-off" if visible else "eye"))
        self._adjust_btn.setEnabled(visible)
        if not visible and self._adjust_btn.isChecked():
            self._adjust_btn.setChecked(False)

    def set_feedback_unread(self, count: int) -> None:
        if count > 0:
            self._feedback_btn.setText(f"提需求 {count}")
            self._feedback_btn.setStyleSheet(
                "QPushButton{background: rgba(255,116,116,0.18); color:#ffd1d1; border:1px solid rgba(255,116,116,0.34);}"
                "QPushButton:hover{background: rgba(255,116,116,0.24);}"
            )
        else:
            self._feedback_btn.setText("提需求")
            self._feedback_btn.setStyleSheet("")

    def set_update_available(self, info) -> None:
        self._pending_update = info
        self._version_btn.setProperty("hasUpdate", True)
        self._version_btn.setText(f"v{__version__} 更新")
        self._version_btn.setToolTip(f"发现新版本 {info.latest_tag}，点击查看详情。")
        style = self._version_btn.style()
        style.unpolish(self._version_btn)
        style.polish(self._version_btn)

    def _on_version_clicked(self) -> None:
        if self._pending_update and self._pending_update.has_update:
            from gui.update_dialog import UpdateDialog

            UpdateDialog(self._pending_update, self).exec()
            return
        QMessageBox.information(self, "版本", f"当前版本 v{__version__}\n暂未检测到可用更新。")

    def set_usage_visible(self, visible: bool) -> None:
        self._usage_chip.setVisible(visible)

    def set_usage_mode(self, show_token: bool) -> None:
        self._show_token = show_token
        self._update_chip_text()

    def set_usage(
        self,
        session_cost: float,
        total_cost: float,
        session_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self._session_cost = session_cost
        self._total_cost = total_cost
        self._session_tokens = session_tokens
        self._total_tokens = total_tokens
        self._update_chip_text()

    def _update_chip_text(self) -> None:
        if self._show_token:
            self._usage_chip.setText(f"本次 {self._session_tokens:,} tokens · 累计 {self._total_tokens:,}")
        else:
            self._usage_chip.setText(f"本次 ${self._session_cost:.4f} · 累计 ${self._total_cost:.2f}")

    def set_status(self, text: str, kind: str = "normal") -> None:
        short = text[:56] + "..." if len(text) > 56 else text
        self._status_pill.set_status(short, kind)
        idle = kind == "normal" and text in ("", "就绪")
        self._status_pill.setVisible(not idle)
