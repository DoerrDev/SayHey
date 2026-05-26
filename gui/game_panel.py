from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.subtitle_buffer import SubtitleBuffer

# All S2T supported foreign languages (source OR target)
HUOSHAN_FOREIGN_LANGUAGES: list[tuple[str, str]] = [
    ("中文 zh", "zh"),
    ("英语 en", "en"),
    ("日语 ja", "ja"),
    ("韩语 ko", "ko"),
    ("法语 fr", "fr"),
    ("德语 de", "de"),
    ("西班牙语 es", "es"),
    ("葡萄牙语 pt", "pt"),
    ("俄语 ru", "ru"),
    ("意大利语 it", "it"),
    ("印尼语 id", "id"),
    ("马来语 ms", "ms"),
    ("越南语 vi", "vi"),
    ("泰语 th", "th"),
    ("阿拉伯语 ar", "ar"),
    ("土耳其语 tr", "tr"),
    ("荷兰语 nl", "nl"),
    ("波兰语 pl", "pl"),
    ("罗马尼亚语 ro", "ro"),
    ("捷克语 cs", "cs"),
]

# Dialects: only valid as source language
HUOSHAN_DIALECTS: list[tuple[str, str]] = [
    ("粤语 (Cantonese)", "yue-CN"),
    ("上海话 (Shanghai)", "sh-CN"),
]

QWEN_LANGUAGES: list[tuple[str, str]] = [
    ("中文 zh", "zh"),
    ("英语 en", "en"),
    ("日语 ja", "ja"),
    ("韩语 ko", "ko"),
    ("法语 fr", "fr"),
    ("德语 de", "de"),
    ("西班牙语 es", "es"),
    ("葡萄牙语 pt", "pt"),
    ("俄语 ru", "ru"),
    ("意大利语 it", "it"),
    ("印尼语 id", "id"),
    ("越南语 vi", "vi"),
    ("泰语 th", "th"),
    ("阿拉伯语 ar", "ar"),
    ("粵語 yue", "yue"),
    ("印地语 hi", "hi"),
    ("希腊语 el", "el"),
    ("土耳其语 tr", "tr"),
]

_ZH_EN = {"zh", "en"}


class GameSubtitlePanel(QFrame):
    sig_start_requested = Signal()
    sig_stop_requested = Signal()
    sig_overlay_toggle = Signal()
    sig_subtitle_flushed = Signal(str)  # buffered text ready for overlay
    sig_audio_device_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("cardLeft")
        self._is_running = False
        self._source_buffer = SubtitleBuffer(self._set_source_text)
        self._translation_buffer = SubtitleBuffer(self._set_translation_text)
        self._source_text = ""
        self._translation_text = ""
        self._show_source = True
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._title_label = QLabel("翻译字幕")
        self._title_label.setObjectName("panelTitle")
        title_row.addWidget(self._title_label, 1)
        layout.addLayout(title_row)

        # Language selectors row
        lang_row = QHBoxLayout()
        lang_row.setSpacing(12)

        src_label = QLabel("游戏语言")
        src_label.setObjectName("sectionTitle")
        lang_row.addWidget(src_label)

        self._src_combo = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._src_combo.addItem(name, code)
        for name, code in HUOSHAN_DIALECTS:
            self._src_combo.addItem(name, code)
        # Default: English
        self._src_combo.setCurrentIndex(
            next((i for i, (_, c) in enumerate(HUOSHAN_FOREIGN_LANGUAGES) if c == "en"), 1)
        )
        lang_row.addWidget(self._src_combo)

        lang_row.addSpacing(16)

        tgt_label = QLabel("字幕语言")
        tgt_label.setObjectName("sectionTitle")
        lang_row.addWidget(tgt_label)

        self._tgt_combo = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._tgt_combo.addItem(name, code)
        # Default: Chinese
        self._tgt_combo.setCurrentIndex(0)
        lang_row.addWidget(self._tgt_combo)

        lang_row.addStretch()
        layout.addLayout(lang_row)

        # Audio source row (hidden in simplified mode)
        self._audio_row_widget = QWidget()
        audio_row = QHBoxLayout(self._audio_row_widget)
        audio_row.setContentsMargins(0, 0, 0, 0)
        audio_row.setSpacing(12)
        audio_label = QLabel("音频源")
        audio_label.setObjectName("sectionTitle")
        audio_row.addWidget(audio_label)
        self._audio_combo = QComboBox()
        self._audio_combo.setToolTip(
            "选择要监听的扬声器设备（loopback 捕获）。\n"
            "把游戏音频输出到 CABLE Input 后选它，物理扬声器放音乐不影响翻译。"
        )
        self._audio_combo.setMinimumWidth(260)
        self._audio_combo.currentIndexChanged.connect(
            lambda _i: self.sig_audio_device_changed.emit(self.selected_audio_device())
        )
        audio_row.addWidget(self._audio_combo, 1)
        layout.addWidget(self._audio_row_widget)

        # Constraint hint (shown when neither side is zh/en)
        self._lang_hint = QLabel("⚠ 源语言或字幕语言中，至少有一个需为中文或英语")
        self._lang_hint.setObjectName("routeLabel")
        self._lang_hint.setStyleSheet("color: #f5a623;")
        self._lang_hint.setVisible(False)
        layout.addWidget(self._lang_hint)

        # Subtitle stage
        self._subtitle_edit = QTextEdit()
        self._subtitle_edit.setObjectName("stageLarge")
        self._subtitle_edit.setReadOnly(True)
        self._subtitle_edit.setPlaceholderText("游戏语音翻译字幕将在此显示...")
        layout.addWidget(self._subtitle_edit, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._toggle_btn = QPushButton("▶ 开始字幕")
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self._toggle_btn)

        layout.addLayout(btn_row)

        # Wire language change events
        self._src_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._tgt_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._on_lang_changed()

    @Slot()
    def _on_lang_changed(self) -> None:
        src = self._src_combo.currentData() or "en"
        tgt = self._tgt_combo.currentData() or "zh"

        dialect_codes = {code for _, code in HUOSHAN_DIALECTS}
        is_dialect = src in dialect_codes
        constraint_ok = is_dialect or bool(_ZH_EN & {src, tgt})
        self._lang_hint.setVisible(not constraint_ok)
        if not self._is_running:
            self._toggle_btn.setEnabled(constraint_ok)

    def selected_source_language(self) -> str:
        return self._src_combo.currentData() or "en"

    def selected_target_language(self) -> str:
        return self._tgt_combo.currentData() or "zh"

    def set_source_language(self, code: str) -> None:
        idx = self._src_combo.findData(code)
        if idx >= 0:
            self._src_combo.setCurrentIndex(idx)

    def set_target_language(self, code: str) -> None:
        idx = self._tgt_combo.findData(code)
        if idx >= 0:
            self._tgt_combo.setCurrentIndex(idx)

    def set_engine(self, engine: str) -> None:
        cur_src = self._src_combo.currentData()
        cur_tgt = self._tgt_combo.currentData()
        langs = QWEN_LANGUAGES if engine == "qwen" else HUOSHAN_FOREIGN_LANGUAGES
        self._src_combo.blockSignals(True)
        self._tgt_combo.blockSignals(True)
        self._src_combo.clear()
        for name, code in langs:
            self._src_combo.addItem(name, code)
        if engine != "qwen":
            for name, code in HUOSHAN_DIALECTS:
                self._src_combo.addItem(name, code)
        self._tgt_combo.clear()
        for name, code in langs:
            self._tgt_combo.addItem(name, code)
        si = self._src_combo.findData(cur_src)
        self._src_combo.setCurrentIndex(si if si >= 0 else max(0, self._src_combo.findData("en")))
        ti = self._tgt_combo.findData(cur_tgt)
        self._tgt_combo.setCurrentIndex(ti if ti >= 0 else max(0, self._tgt_combo.findData("zh")))
        self._src_combo.blockSignals(False)
        self._tgt_combo.blockSignals(False)

    def set_audio_devices(self, device_names: list[str], current: str = "") -> None:
        self._audio_combo.blockSignals(True)
        self._audio_combo.clear()
        self._audio_combo.addItem("默认扬声器（系统）", "")
        for name in device_names:
            self._audio_combo.addItem(name, name)
        if current:
            idx = self._audio_combo.findData(current)
            if idx >= 0:
                self._audio_combo.setCurrentIndex(idx)
        self._audio_combo.blockSignals(False)

    def selected_audio_device(self) -> str:
        return self._audio_combo.currentData() or ""

    def set_audio_device(self, name: str) -> None:
        self._audio_combo.blockSignals(True)
        idx = self._audio_combo.findData(name or "")
        if idx >= 0:
            self._audio_combo.setCurrentIndex(idx)
        else:
            self._audio_combo.setCurrentIndex(0)
        self._audio_combo.blockSignals(False)

    def set_advanced(self, show: bool) -> None:
        self._audio_row_widget.setVisible(show)

    @Slot()
    def _on_toggle(self) -> None:
        if self._is_running:
            self.sig_stop_requested.emit()
        else:
            self.sig_start_requested.emit()

    def set_max_lines(self, n: int) -> None:
        self._source_buffer.set_max_lines(n)
        self._translation_buffer.set_max_lines(n)

    def set_running(self, running: bool) -> None:
        self._is_running = running
        self._src_combo.setEnabled(not running)
        self._tgt_combo.setEnabled(not running)
        self._audio_combo.setEnabled(not running)
        if not running:
            self._source_buffer.reset()
            self._translation_buffer.reset()
            self._toggle_btn.setText("▶ 开始字幕")
            self._toggle_btn.setObjectName("")
            self._toggle_btn.style().polish(self._toggle_btn)
            self._on_lang_changed()
        else:
            self._toggle_btn.setText("◼ 停止字幕")
            self._toggle_btn.setObjectName("danger")
            self._toggle_btn.style().polish(self._toggle_btn)
            self._toggle_btn.setEnabled(True)

    @Slot(str, str)
    def append_subtitle_token(self, kind: str, text: str) -> None:
        if kind == "source":
            self._source_buffer.update(text)
        else:
            self._translation_buffer.update(text)

    def _set_source_text(self, text: str) -> None:
        self._source_text = text
        self._render_combined_text()

    def _set_translation_text(self, text: str) -> None:
        self._translation_text = text
        self._render_combined_text()

    def set_show_source(self, show: bool) -> None:
        self._show_source = bool(show)
        self._render_combined_text()

    def _render_combined_text(self) -> None:
        parts = []
        if self._show_source and self._source_text.strip():
            parts.append(self._source_text)
        if self._translation_text.strip():
            parts.append(self._translation_text)
        text = "\n".join(parts)
        self._subtitle_edit.setPlainText(text)
        sb = self._subtitle_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.sig_subtitle_flushed.emit(text)
