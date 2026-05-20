from __future__ import annotations

import json
import urllib.request

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.machine_id import get_machine_id_hash


class _SubmitThread(QThread):
    sig_done = Signal(bool, str)

    def __init__(self, api_base: str, name: str, message: str, parent=None) -> None:
        super().__init__(parent)
        self._api_base = api_base.rstrip("/")
        self._name = name
        self._message = message

    def run(self) -> None:
        body = json.dumps({
            "name": self._name,
            "message": self._message,
            "machine_id_hash": get_machine_id_hash(),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._api_base}/api/feature-request",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.sig_done.emit(True, data.get("ack", "需求已收到"))
        except Exception as exc:
            self.sig_done.emit(False, str(exc))


class FeedbackDialog(QDialog):
    def __init__(self, api_base: str, default_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self._api_base = api_base
        self.setWindowTitle("快速提需求")
        self.setMinimumSize(480, 360)
        self._thread: _SubmitThread | None = None
        self._build_ui()
        if default_name:
            self._name_input.setText(default_name)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        tip = QLabel(
            "提交后将同步到 GitHub Issue 并通知开发者，开发完成会在软件内通知您。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#9ab;font-size:12px;")
        root.addWidget(tip)

        root.addWidget(QLabel("您的昵称（用于联系）"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("例如 张三")
        self._name_input.setMaxLength(64)
        root.addWidget(self._name_input)

        root.addWidget(QLabel("需求 / 建议内容"))
        self._msg_input = QTextEdit()
        self._msg_input.setPlaceholderText(
            "请描述您希望添加的功能或遇到的问题，越具体越好。"
        )
        root.addWidget(self._msg_input, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self._cancel_btn)

        self._submit_btn = QPushButton("发送")
        self._submit_btn.clicked.connect(self._on_submit)
        btns.addWidget(self._submit_btn)
        root.addLayout(btns)

    def _on_submit(self) -> None:
        name = self._name_input.text().strip()
        message = self._msg_input.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入昵称")
            return
        if len(message) < 2:
            QMessageBox.warning(self, "提示", "请输入需求内容")
            return
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("发送中…")
        self._thread = _SubmitThread(self._api_base, name, message, self)
        self._thread.sig_done.connect(self._on_done)
        self._thread.start()

    def _on_done(self, ok: bool, msg: str) -> None:
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("发送")
        if ok:
            QMessageBox.information(self, "已提交", f"感谢您的反馈！{msg}")
            self.accept()
        else:
            QMessageBox.critical(self, "提交失败", f"无法连接服务器：\n{msg}")
