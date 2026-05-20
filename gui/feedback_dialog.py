from __future__ import annotations

import json
import urllib.request
from dataclasses import replace

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
)

from core.machine_id import get_machine_id_hash
from core.settings_store import SettingsStore


class _NetThread(QThread):
    sig_done = Signal(bool, object)  # ok, payload

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
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


class FeedbackDialog(QDialog):
    def __init__(self, store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._api_base = store.get().volc_trial_api_base.rstrip("/")
        self._machine_id = get_machine_id_hash()
        self._thread: _NetThread | None = None
        self.setWindowTitle("需求反馈")
        self.setMinimumSize(560, 520)
        self._build_ui()
        self._load_history()
        self._ack_unread_async()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        tip = QLabel("提交需求将同步到 GitHub Issue。开发者回复会显示在下方对话区。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#9ab;font-size:12px;")
        root.addWidget(tip)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("昵称"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("例如 张三")
        self._name_input.setMaxLength(64)
        self._name_input.setText(self._store.get().feedback_nickname)
        name_row.addWidget(self._name_input, 1)
        root.addLayout(name_row)

        self._chat_view = QTextBrowser()
        self._chat_view.setOpenExternalLinks(True)
        self._chat_view.setStyleSheet(
            "QTextBrowser{background:#0f1218;border:1px solid #2a3142;border-radius:8px;padding:8px;color:#eef7ff;}"
        )
        root.addWidget(self._chat_view, 1)

        self._msg_input = QTextEdit()
        self._msg_input.setPlaceholderText("输入新的需求或问题，回车换行，Ctrl+Enter 发送")
        self._msg_input.setFixedHeight(80)
        root.addWidget(self._msg_input)

        btns = QHBoxLayout()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setObjectName("secondary")
        self._refresh_btn.clicked.connect(self._load_history)
        btns.addWidget(self._refresh_btn)
        btns.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_submit)
        btns.addWidget(self._send_btn)
        root.addLayout(btns)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._on_submit()
            return
        super().keyPressEvent(event)

    def _render(self, items: list[dict]) -> None:
        if not items:
            self._chat_view.setHtml(
                "<div style='color:#6a8fa8;text-align:center;padding:24px'>"
                "还没有任何对话，发送您的第一个需求吧"
                "</div>"
            )
            return
        html_parts: list[str] = []
        for it in items:
            ts = it.get("created_at", "").replace("T", " ")[:19]
            content = (it.get("content") or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            if it.get("type") == "user":
                name = it.get("user_name") or "我"
                html_parts.append(
                    f"<div style='margin:8px 0;text-align:right'>"
                    f"<div style='color:#6a8fa8;font-size:11px'>{name} · {ts}</div>"
                    f"<div style='display:inline-block;background:#1e3a5f;color:#eef7ff;"
                    f"padding:8px 12px;border-radius:10px;max-width:78%;text-align:left;margin-top:2px'>"
                    f"{content}</div></div>"
                )
            else:
                via = it.get("via") or "admin"
                html_parts.append(
                    f"<div style='margin:8px 0'>"
                    f"<div style='color:#6a8fa8;font-size:11px'>开发者 · {ts} · {via}</div>"
                    f"<div style='display:inline-block;background:#1a1f2b;color:#eef7ff;"
                    f"padding:8px 12px;border-radius:10px;max-width:78%;margin-top:2px;"
                    f"border:1px solid #2a3142'>{content}</div></div>"
                )
        self._chat_view.setHtml("".join(html_parts))
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _load_history(self) -> None:
        self._refresh_btn.setEnabled(False)
        base, mid = self._api_base, self._machine_id
        self._thread = _NetThread(lambda: _api_get(f"{base}/api/chat", mid), self)
        self._thread.sig_done.connect(self._on_history_loaded)
        self._thread.start()

    def _on_history_loaded(self, ok: bool, payload: object) -> None:
        self._refresh_btn.setEnabled(True)
        if not ok or not isinstance(payload, list):
            self._chat_view.setHtml(
                f"<div style='color:#d44;padding:12px'>加载失败：{payload}</div>"
            )
            return
        self._render(payload)

    def _ack_unread_async(self) -> None:
        base, mid = self._api_base, self._machine_id
        try:
            ls = _api_get(f"{base}/api/messages", mid)
        except Exception:
            return
        if not isinstance(ls, list) or not ls:
            return
        ids = [int(r["id"]) for r in ls if "id" in r]
        if not ids:
            return
        t = _NetThread(lambda: _api_post(f"{base}/api/messages/ack", {"ids": ids}, mid), self)
        t.sig_done.connect(lambda *_: None)
        t.start()
        self._ack_thread = t  # keep ref

    def _on_submit(self) -> None:
        name = self._name_input.text().strip()
        message = self._msg_input.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入昵称")
            return
        if len(message) < 2:
            QMessageBox.warning(self, "提示", "请输入需求内容")
            return

        s = self._store.get()
        if s.feedback_nickname != name:
            self._store.save(replace(s, feedback_nickname=name))

        self._send_btn.setEnabled(False)
        self._send_btn.setText("发送中…")
        base, mid = self._api_base, self._machine_id
        body = {"name": name, "message": message, "machine_id_hash": mid}
        self._thread = _NetThread(lambda: _api_post(f"{base}/api/feature-request", body), self)
        self._thread.sig_done.connect(self._on_submitted)
        self._thread.start()

    def _on_submitted(self, ok: bool, payload: object) -> None:
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送")
        if not ok:
            QMessageBox.critical(self, "发送失败", f"无法连接服务器：\n{payload}")
            return
        self._msg_input.clear()
        self._load_history()
