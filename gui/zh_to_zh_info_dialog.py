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


class ZhToZhInfoDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("中文 → 中文")
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("中文转中文：方言/口音过滤")
        title.setStyleSheet("font-size: 15px; font-weight: 900; color: #eef7ff;")
        layout.addWidget(title)

        body = QLabel(
            "中文转中文将使用语音识别 + 语音合成功能。\n\n"
            "适用于普通话不标准、带方言口音的情况：\n"
            "识别成标准文字后再合成为标准普通话语音输出。"
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
