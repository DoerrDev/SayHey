from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

TYPED_LANGUAGES = [
    ("中文", "zh"),
    ("English", "en"),
    ("日本語", "ja"),
    ("한국어", "ko"),
    ("Español", "es"),
    ("Français", "fr"),
    ("Deutsch", "de"),
    ("Português", "pt"),
    ("Русский", "ru"),
]
TYPED_SOURCE_LANGUAGES = [("自动检测", "auto")] + TYPED_LANGUAGES


class _EnterTextEdit(QPlainTextEdit):
    sig_submit = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.sig_submit.emit()
            return
        super().keyPressEvent(event)


class TypedTranslatePanel(QFrame):
    sig_translate_requested = Signal(str)
    sig_settings_changed = Signal()
    sig_rebind_hotkey = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        route = QLabel("文本输入 → 火山翻译 → 可选 TTS → CABLE Input")
        route.setObjectName("routeLabel")
        layout.addWidget(route)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._src = QComboBox()
        for name, code in TYPED_SOURCE_LANGUAGES:
            self._src.addItem(f"{name} ({code})", code)
        self._src.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._src, 1)
        arrow = QLabel("→")
        arrow.setObjectName("routeLabel")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(20)
        lang_row.addWidget(arrow)
        self._tgt = QComboBox()
        for name, code in TYPED_LANGUAGES:
            self._tgt.addItem(f"{name} ({code})", code)
        self._tgt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._tgt, 1)
        layout.addLayout(lang_row)

        self._auto_tts = QCheckBox("自动合成语音并发送到虚拟声卡")
        self._auto_tts.setChecked(True)
        layout.addWidget(self._auto_tts)

        self._input = _EnterTextEdit()
        self._input.setPlaceholderText("输入要发送给队友的句子。按 Enter 翻译，Shift + Enter 换行。")
        self._input.setMinimumHeight(96)
        self._input.sig_submit.connect(self._on_submit)
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._send_btn = QPushButton("翻译并发送")
        self._send_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._send_btn)
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._input.clear)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Result boxes
        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        self._source_lbl = QLabel("")
        self._source_lbl.setObjectName("resultBox")
        self._source_lbl.setWordWrap(True)
        self._source_lbl.setMinimumHeight(54)
        self._source_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._target_lbl = QLabel("")
        self._target_lbl.setObjectName("resultBox")
        self._target_lbl.setWordWrap(True)
        self._target_lbl.setMinimumHeight(54)
        self._target_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        result_row.addWidget(self._wrap_result("原文", self._source_lbl), 1)
        result_row.addWidget(self._wrap_result("译文", self._target_lbl), 1)
        layout.addLayout(result_row)

        # Hotkey row
        hk_row = QHBoxLayout()
        hk_row.setSpacing(8)
        self._hotkey_lbl = QLabel("Ctrl + Alt + T")
        self._hotkey_lbl.setObjectName("hotkeyBox")
        self._hotkey_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hotkey_lbl.setMinimumHeight(32)
        hk_row.addWidget(self._hotkey_lbl, 1)
        rebind = QPushButton("重新绑定热键")
        rebind.setObjectName("ghost")
        rebind.clicked.connect(self.sig_rebind_hotkey.emit)
        hk_row.addWidget(rebind)
        layout.addLayout(hk_row)

        self._src.currentIndexChanged.connect(lambda *_: self.sig_settings_changed.emit())
        self._tgt.currentIndexChanged.connect(lambda *_: self.sig_settings_changed.emit())
        self._auto_tts.toggled.connect(lambda *_: self.sig_settings_changed.emit())

    def _wrap_result(self, title: str, body: QLabel) -> QFrame:
        wrap = QFrame()
        wrap.setObjectName("resultWrap")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(4)
        cap = QLabel(title)
        cap.setObjectName("routeLabel")
        v.addWidget(cap)
        v.addWidget(body, 1)
        return wrap

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.sig_translate_requested.emit(text)

    # ── public API ──
    def selected_source(self) -> str:
        return self._src.currentData() or "zh"

    def selected_target(self) -> str:
        return self._tgt.currentData() or "en"

    def auto_tts(self) -> bool:
        return self._auto_tts.isChecked()

    def set_source(self, code: str) -> None:
        i = self._src.findData(code)
        if i >= 0:
            self._src.setCurrentIndex(i)

    def set_target(self, code: str) -> None:
        i = self._tgt.findData(code)
        if i >= 0:
            self._tgt.setCurrentIndex(i)

    def set_auto_tts(self, on: bool) -> None:
        self._auto_tts.setChecked(on)

    def set_hotkey_label(self, text: str) -> None:
        self._hotkey_lbl.setText(text)

    def show_result(self, source: str, translated: str) -> None:
        self._source_lbl.setText(source)
        self._target_lbl.setText(translated)
        self._input.clear()

    def set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._send_btn.setText("翻译中..." if busy else "翻译并发送")
