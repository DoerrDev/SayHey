from __future__ import annotations

import json
import urllib.request
from dataclasses import replace

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.machine_id import get_machine_id_hash
from core.settings_store import SettingsStore


class _NetThread(QThread):
    sig_done = Signal(bool, object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.sig_done.emit(True, self._fn())
        except Exception as exc:
            self.sig_done.emit(False, str(exc))


def _api_get(url: str, machine_id: str) -> object:
    req = urllib.request.Request(url, headers={"X-Machine-Id": machine_id})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _api_post(url: str, body: dict, machine_id: str = "") -> object:
    headers = {"Content-Type": "application/json"}
    if machine_id:
        headers["X-Machine-Id"] = machine_id
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


class _MessageBubble(QFrame):
    def __init__(self, author: str, timestamp: str, content: str, incoming: bool, via: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("feedbackBubbleWrap")
        self.setProperty("incoming", incoming)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        meta = QLabel()
        meta.setObjectName("feedbackBubbleMeta")
        if incoming:
            meta.setText(f"{author}  {timestamp}" + (f"  ·  {via}" if via else ""))
        else:
            meta.setText(f"{author}  {timestamp}")
        root.addWidget(meta, alignment=Qt.AlignmentFlag.AlignLeft if incoming else Qt.AlignmentFlag.AlignRight)

        bubble = QFrame()
        bubble.setObjectName("feedbackBubble")
        bubble.setProperty("incoming", incoming)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 12, 14, 12)

        text = QLabel(content)
        text.setObjectName("feedbackBubbleText")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(text)
        root.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft if incoming else Qt.AlignmentFlag.AlignRight)


class FeedbackDialog(QDialog):
    def __init__(self, store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._api_base = store.get().volc_trial_api_base.rstrip("/")
        self._machine_id = get_machine_id_hash()
        self._thread: _NetThread | None = None
        self._ack_thread: _NetThread | None = None
        self.setObjectName("feedbackDialog")
        self.setWindowTitle("需求反馈")
        self.setMinimumSize(680, 700)
        self.resize(760, 760)
        self._build_ui()
        self._load_history()
        self._ack_unread_async()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        title = QLabel("需求反馈")
        title.setObjectName("feedbackDialogTitle")
        top_row.addWidget(title, 1)

        self._status_label = QLabel("正在同步")
        self._status_label.setObjectName("feedbackStatusBadge")
        top_row.addWidget(self._status_label, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_label = QLabel("昵称")
        name_label.setObjectName("feedbackFieldLabel")
        name_row.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setObjectName("feedbackNameInput")
        self._name_input.setPlaceholderText("例如：张哥")
        self._name_input.setMaxLength(64)
        self._name_input.setText(self._store.get().feedback_nickname)
        name_row.addWidget(self._name_input, 1)
        root.addLayout(name_row)

        chat_card = QFrame()
        chat_card.setObjectName("feedbackPanel")
        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        chat_head = QHBoxLayout()
        chat_head.setContentsMargins(16, 14, 16, 10)
        chat_title = QLabel("对话记录")
        chat_title.setObjectName("feedbackPanelTitle")
        chat_head.addWidget(chat_title)
        chat_head.addStretch()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setObjectName("secondary")
        self._refresh_btn.clicked.connect(self._load_history)
        chat_head.addWidget(self._refresh_btn)
        chat_layout.addLayout(chat_head)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setObjectName("feedbackScrollArea")
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._chat_content = QWidget()
        self._chat_content.setObjectName("feedbackChatContent")
        self._chat_column = QVBoxLayout(self._chat_content)
        self._chat_column.setContentsMargins(16, 6, 16, 16)
        self._chat_column.setSpacing(14)
        self._chat_column.addStretch()

        self._chat_scroll.setWidget(self._chat_content)
        chat_layout.addWidget(self._chat_scroll, 1)
        root.addWidget(chat_card, 1)

        composer = QFrame()
        composer.setObjectName("feedbackPanel")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(16, 14, 16, 16)
        composer_layout.setSpacing(10)

        composer_title = QLabel("新消息")
        composer_title.setObjectName("feedbackPanelTitle")
        composer_layout.addWidget(composer_title)

        self._msg_input = QTextEdit()
        self._msg_input.setObjectName("feedbackInput")
        self._msg_input.setPlaceholderText("输入新的需求或问题，Ctrl+Enter 发送。")
        self._msg_input.setFixedHeight(124)
        composer_layout.addWidget(self._msg_input)

        hint = QLabel("尽量写清场景、问题现象和你期待的结果。")
        hint.setObjectName("feedbackDialogTip")
        composer_layout.addWidget(hint)
        root.addWidget(composer)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)

        self._send_btn = QPushButton("发送反馈")
        self._send_btn.clicked.connect(self._on_submit)
        btns.addWidget(self._send_btn)
        root.addLayout(btns)

    def keyPressEvent(self, event) -> None:
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._on_submit()
            return
        super().keyPressEvent(event)

    def _clear_messages(self) -> None:
        while self._chat_column.count() > 1:
            item = self._chat_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _append_empty_state(self) -> None:
        empty = QLabel("还没有对话记录，直接把你的想法发出来就行。")
        empty.setObjectName("feedbackEmptyState")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chat_column.insertWidget(0, empty)

    def _render(self, items: list[dict]) -> None:
        self._clear_messages()
        if not items:
            self._append_empty_state()
            return

        insert_at = 0
        for item in items:
            is_incoming = item.get("type") != "user"
            author = "开发者" if is_incoming else (item.get("user_name") or "我")
            timestamp = (item.get("created_at") or "").replace("T", " ")[:19]
            content = item.get("content") or ""
            via = item.get("via") or ""
            bubble = _MessageBubble(author, timestamp, content, is_incoming, via)
            self._chat_column.insertWidget(insert_at, bubble)
            insert_at += 1

        scroll_bar = self._chat_scroll.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _set_busy(self, busy: bool, status: str) -> None:
        self._refresh_btn.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._status_label.setText(status)

    def _load_history(self) -> None:
        self._set_busy(True, "同步中")
        base, mid = self._api_base, self._machine_id
        self._thread = _NetThread(lambda: _api_get(f"{base}/api/chat", mid), self)
        self._thread.sig_done.connect(self._on_history_loaded)
        self._thread.start()

    def _on_history_loaded(self, ok: bool, payload: object) -> None:
        self._set_busy(False, "已同步")
        if not ok or not isinstance(payload, list):
            self._clear_messages()
            error = QLabel(f"加载失败：{payload}")
            error.setObjectName("feedbackErrorState")
            error.setWordWrap(True)
            self._chat_column.insertWidget(0, error)
            self._status_label.setText("同步失败")
            return
        self._render(payload)

    def _ack_unread_async(self) -> None:
        base, mid = self._api_base, self._machine_id
        try:
            rows = _api_get(f"{base}/api/messages", mid)
        except Exception:
            return
        if not isinstance(rows, list) or not rows:
            return
        ids = [int(row["id"]) for row in rows if "id" in row]
        if not ids:
            return
        self._ack_thread = _NetThread(
            lambda: _api_post(f"{base}/api/messages/ack", {"ids": ids}, mid),
            self,
        )
        self._ack_thread.sig_done.connect(lambda *_: None)
        self._ack_thread.start()

    def _on_submit(self) -> None:
        name = self._name_input.text().strip()
        message = self._msg_input.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入昵称。")
            return
        if len(message) < 2:
            QMessageBox.warning(self, "提示", "请输入反馈内容。")
            return

        settings = self._store.get()
        if settings.feedback_nickname != name:
            self._store.save(replace(settings, feedback_nickname=name))

        self._send_btn.setEnabled(False)
        self._send_btn.setText("发送中...")
        self._status_label.setText("正在发送")
        base, mid = self._api_base, self._machine_id
        body = {"name": name, "message": message, "machine_id_hash": mid}
        self._thread = _NetThread(lambda: _api_post(f"{base}/api/feature-request", body), self)
        self._thread.sig_done.connect(self._on_submitted)
        self._thread.start()

    def _on_submitted(self, ok: bool, payload: object) -> None:
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送反馈")
        if not ok:
            self._status_label.setText("发送失败")
            QMessageBox.critical(self, "发送失败", f"无法连接服务：\n{payload}")
            return
        self._status_label.setText("发送成功")
        self._msg_input.clear()
        self._load_history()
