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


class HotwordUsageDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("同声传译热词提示")
        self.setFixedWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("同声传译中如何使用热词？")
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #eef7ff;")
        layout.addWidget(title)

        body = QLabel(
            "热词会在启动同声传译或游戏字幕时发送给模型，用来提升游戏术语、人名、地名等专有词的翻译稳定性。\n\n"
            "热词表越大，启动时需要发送给模型的上下文越多，可能带来额外 token 消耗和启动延迟。"
            "如果只是普通对话，建议选择「无」；如果是特定游戏或场景，选择对应的小热词表即可。"
        )
        body.setWordWrap(True)
        body.setStyleSheet("color: #cce4f7; font-size: 13px; line-height: 1.6;")
        layout.addWidget(body)

        self._checkbox = QCheckBox("我已了解，不再显示此提示")
        self._checkbox.setStyleSheet("color: #9ab8d0; font-size: 12px;")
        layout.addWidget(self._checkbox)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("我知道了")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def dont_show_again(self) -> bool:
        return self._checkbox.isChecked()
