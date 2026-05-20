from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.icons import resource_icon
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

_ZH_EN = {"zh", "en"}


class GameSubtitlePanel(QFrame):
    sig_start_requested = Signal()
    sig_stop_requested = Signal()
    sig_overlay_toggle = Signal()
    sig_subtitle_flushed = Signal(str)  # buffered text ready for overlay

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._is_running = False
        self._source_buffer = SubtitleBuffer(self._set_source_text)
        self._translation_buffer = SubtitleBuffer(self._set_translation_text)
        self._source_text = ""
        self._translation_text = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self._title_label = QLabel("游戏字幕")
        self._title_label.setObjectName("panelTitle")
        title_block.addWidget(self._title_label)
        self._desc_label = QLabel("捕获游戏声音并显示翻译字幕")
        self._desc_label.setObjectName("panelDesc")
        title_block.addWidget(self._desc_label)
        title_row.addLayout(title_block, 1)

        self._state_chip = QLabel("未启动")
        self._state_chip.setObjectName("statusChipWarn")
        title_row.addWidget(self._state_chip)
        layout.addLayout(title_row)

        self._route_label = QLabel()
        self._route_label.setObjectName("routeLabel")
        layout.addWidget(self._route_label)

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

        # Constraint hint (shown when neither side is zh/en)
        self._lang_hint = QLabel("⚠ 源语言或字幕语言中，至少有一个需为中文或英语")
        self._lang_hint.setObjectName("routeLabel")
        self._lang_hint.setStyleSheet("color: #f5a623;")
        self._lang_hint.setVisible(False)
        layout.addWidget(self._lang_hint)

        # Stage (subtitle area + empty overlay)
        stage_container = QWidget()
        stage_stack = QStackedLayout(stage_container)
        stage_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stage_stack.setContentsMargins(0, 0, 0, 0)

        self._subtitle_edit = QTextEdit()
        self._subtitle_edit.setObjectName("stageLarge")
        self._subtitle_edit.setReadOnly(True)
        stage_stack.addWidget(self._subtitle_edit)

        self._empty_overlay = QWidget()
        self._empty_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_overlay.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(self._empty_overlay)
        empty_layout.setContentsMargins(20, 22, 20, 22)
        empty_layout.setSpacing(8)
        self._empty_title = QLabel("等待开始游戏字幕")
        self._empty_title.setObjectName("emptyTitle")
        self._empty_copy = QLabel(
            "确认游戏音频输出到 VB-Cable 后，点击下方按钮开始。字幕会显示在这里，也可以投到悬浮窗口。"
        )
        self._empty_copy.setObjectName("emptyCopy")
        self._empty_copy.setWordWrap(True)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_copy)
        empty_layout.addStretch()
        stage_stack.addWidget(self._empty_overlay)

        layout.addWidget(stage_container, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._toggle_btn = QPushButton("开始游戏字幕")
        self._toggle_btn.setIcon(resource_icon("play"))
        self._toggle_btn.setIconSize(QSize(14, 14))
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self._toggle_btn)

        self._overlay_btn = QPushButton("显示悬浮字幕")
        self._overlay_btn.setObjectName("secondary")
        self._overlay_btn.clicked.connect(self.sig_overlay_toggle.emit)
        btn_row.addWidget(self._overlay_btn)

        layout.addLayout(btn_row)

        # Wire language change events
        self._src_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._tgt_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._on_lang_changed()

    @Slot()
    def _on_lang_changed(self) -> None:
        src = self._src_combo.currentData() or "en"
        tgt = self._tgt_combo.currentData() or "zh"
        src_name = self._src_combo.currentText()
        tgt_name = self._tgt_combo.currentText()

        self._route_label.setText(f"{src_name}  →  {tgt_name}")

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
        if not running:
            self._source_buffer.reset()
            self._translation_buffer.reset()
            self._toggle_btn.setText("开始游戏字幕")
            self._toggle_btn.setIcon(resource_icon("play"))
            self._toggle_btn.setObjectName("")
            self._toggle_btn.style().polish(self._toggle_btn)
            self._state_chip.setText("未启动")
            self._state_chip.setObjectName("statusChipWarn")
            self._state_chip.style().polish(self._state_chip)
            self._empty_overlay.setVisible(True)
            self._on_lang_changed()
        else:
            self._toggle_btn.setText("停止游戏字幕")
            self._toggle_btn.setIcon(resource_icon("stop"))
            self._toggle_btn.setObjectName("danger")
            self._toggle_btn.style().polish(self._toggle_btn)
            self._toggle_btn.setEnabled(True)
            self._state_chip.setText("运行中")
            self._state_chip.setObjectName("statusChip")
            self._state_chip.style().polish(self._state_chip)
            self._empty_overlay.setVisible(False)

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

    def _render_combined_text(self) -> None:
        parts = []
        if self._source_text.strip():
            parts.append(self._source_text)
        if self._translation_text.strip():
            parts.append(self._translation_text)
        text = "\n".join(parts)
        self._subtitle_edit.setPlainText(text)
        sb = self._subtitle_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.sig_subtitle_flushed.emit(text)
