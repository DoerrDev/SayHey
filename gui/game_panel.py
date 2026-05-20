from __future__ import annotations

from html import escape

from PySide6.QtCore import QSize, Qt, Signal, Slot
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

from gui.icons import resource_icon, resource_pixmap
from gui.status_pill import StatusPill
from gui.subtitle_buffer import SubtitleBuffer

HUOSHAN_FOREIGN_LANGUAGES: list[tuple[str, str]] = [
    ("中文", "zh"),
    ("英语", "en"),
    ("日语", "ja"),
    ("韩语", "ko"),
    ("法语", "fr"),
    ("德语", "de"),
    ("西班牙语", "es"),
    ("葡萄牙语", "pt"),
    ("俄语", "ru"),
    ("意大利语", "it"),
    ("印尼语", "id"),
    ("马来语", "ms"),
    ("越南语", "vi"),
    ("泰语", "th"),
    ("阿拉伯语", "ar"),
    ("土耳其语", "tr"),
    ("荷兰语", "nl"),
    ("波兰语", "pl"),
    ("罗马尼亚语", "ro"),
    ("捷克语", "cs"),
]

HUOSHAN_DIALECTS: list[tuple[str, str]] = [
    ("粤语", "yue-CN"),
    ("上海话", "sh-CN"),
]

_ZH_EN = {"zh", "en"}


class GameSubtitlePanel(QFrame):
    sig_start_requested = Signal()
    sig_stop_requested = Signal()
    sig_subtitle_flushed = Signal(str)

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
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(3)

        title = QLabel("游戏字幕")
        title.setObjectName("panelTitle")
        title_block.addWidget(title)

        desc = QLabel("捕获游戏声音并显示实时翻译字幕。")
        desc.setObjectName("panelDesc")
        title_block.addWidget(desc)

        title_row.addLayout(title_block, 1)

        self._state_chip = StatusPill("未启动", "warn")
        title_row.addWidget(self._state_chip)
        layout.addLayout(title_row)

        route_row = QHBoxLayout()
        route_row.setSpacing(8)

        self._src_combo = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._src_combo.addItem(f"{name} ({code})", code)
        for name, code in HUOSHAN_DIALECTS:
            self._src_combo.addItem(f"{name} ({code})", code)
        self._src_combo.setCurrentIndex(max(0, self._src_combo.findData("en")))
        route_row.addWidget(self._src_combo, 1)

        arrow = QLabel()
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(18)
        arrow.setPixmap(resource_pixmap("arrow-right", 12, 12))
        route_row.addWidget(arrow)

        self._tgt_combo = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._tgt_combo.addItem(f"{name} ({code})", code)
        self._tgt_combo.setCurrentIndex(max(0, self._tgt_combo.findData("zh")))
        route_row.addWidget(self._tgt_combo, 1)
        layout.addLayout(route_row)

        self._hint_label = QLabel("启动后，原文与译文会按字幕节奏显示，并同步到悬浮字幕。")
        self._hint_label.setObjectName("routeLabel")
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)

        self._lang_hint = QLabel("源语言和目标语言中，至少需要有一个是中文或英文。")
        self._lang_hint.setObjectName("routeHintWarn")
        self._lang_hint.setVisible(False)
        self._lang_hint.setWordWrap(True)
        layout.addWidget(self._lang_hint)

        stage_container = QWidget()
        stack = QStackedLayout(stage_container)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack.setContentsMargins(0, 0, 0, 0)

        self._subtitle_edit = QTextEdit()
        self._subtitle_edit.setObjectName("stage")
        self._subtitle_edit.setReadOnly(True)
        stack.addWidget(self._subtitle_edit)

        self._empty_overlay = QWidget()
        self._empty_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self._empty_overlay)
        empty_layout.setContentsMargins(20, 20, 20, 20)
        empty_layout.setSpacing(8)

        empty_title = QLabel("等待开始游戏字幕")
        empty_title.setObjectName("emptyTitle")
        empty_layout.addWidget(empty_title)
        empty_layout.addStretch()

        stack.addWidget(self._empty_overlay)
        layout.addWidget(stage_container, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._toggle_btn = QPushButton("开始游戏字幕")
        self._toggle_btn.setIcon(resource_icon("play"))
        self._toggle_btn.setIconSize(QSize(14, 14))
        self._toggle_btn.clicked.connect(self._on_toggle)
        footer.addWidget(self._toggle_btn)
        layout.addLayout(footer)

        self._src_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._tgt_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._on_lang_changed()

    def set_overlay_visible(self, visible: bool) -> None:
        return

    @Slot()
    def _on_lang_changed(self) -> None:
        src = self.selected_source_language()
        tgt = self.selected_target_language()
        dialect_codes = {code for _, code in HUOSHAN_DIALECTS}
        constraint_ok = src in dialect_codes or bool(_ZH_EN & {src, tgt})
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
        if running:
            self._toggle_btn.setText("停止游戏字幕")
            self._toggle_btn.setIcon(resource_icon("stop"))
            self._toggle_btn.setObjectName("danger")
            self._state_chip.set_status("运行中", "normal")
            self._empty_overlay.setVisible(False)
        else:
            self._source_buffer.reset()
            self._translation_buffer.reset()
            self._subtitle_edit.clear()
            self._toggle_btn.setText("开始游戏字幕")
            self._toggle_btn.setIcon(resource_icon("play"))
            self._toggle_btn.setObjectName("")
            self._state_chip.set_status("未启动", "warn")
            self._empty_overlay.setVisible(True)
            self._on_lang_changed()

        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)

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
        source_html = ""
        translation_html = ""

        if self._source_text.strip():
            source_html = (
                '<div style="color:#86a7bd;font-size:14px;font-weight:600;line-height:1.45;">'
                + "<br>".join(escape(line) for line in self._source_text.splitlines())
                + "</div>"
            )
        if self._translation_text.strip():
            translation_html = (
                '<div style="margin-top:10px;color:#eef7ff;font-size:24px;font-weight:900;line-height:1.4;">'
                + "<br>".join(escape(line) for line in self._translation_text.splitlines())
                + "</div>"
            )

        html = f'<div style="padding:4px 2px;">{source_html}{translation_html}</div>'
        self._subtitle_edit.setHtml(html if (source_html or translation_html) else "")
        self._subtitle_edit.verticalScrollBar().setValue(
            self._subtitle_edit.verticalScrollBar().maximum()
        )

        combined: list[str] = []
        if self._source_text.strip():
            combined.append(self._source_text)
        if self._translation_text.strip():
            combined.append(self._translation_text)
        self.sig_subtitle_flushed.emit("\n".join(combined))
