from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class AdvancedAudioWarningDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("高级音频模式")
        self.setFixedWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._dont_show = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("高级音频模式能做什么？")
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #eef7ff;")
        layout.addWidget(title)

        body = QLabel(
            "开启后可以实现：\n"
            "• 边听歌、边翻译字幕、边同声传译\n"
            "• 将同声传译的合成语音回放到自己的耳机\n\n"
            "⚠ 高级功能意味着更高的门槛\n\n"
            "你需要了解 VoiceMeeter 是什么，以及如何配置虚拟音频路由，"
            "否则很容易出现声音回环、没有声音等问题。\n\n"
            "如果你不确定，建议继续使用默认模式。"
        )
        body.setWordWrap(True)
        body.setStyleSheet("color: #cce4f7; font-size: 13px; line-height: 1.6;")
        layout.addWidget(body)

        self._checkbox = QCheckBox("我已了解，不再显示此提示")
        self._checkbox.setStyleSheet("color: #9ab8d0; font-size: 12px;")
        layout.addWidget(self._checkbox)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消，继续使用默认模式")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("我知道了，继续开启")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def dont_show_again(self) -> bool:
        return self._checkbox.isChecked()
