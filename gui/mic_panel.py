from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_core.audio_devices import AudioDevice, DeviceResolver
from gui.icons import resource_icon, resource_pixmap
from gui.status_pill import StatusPill
from gui.subtitle_buffer import SubtitleBuffer

HUOSHAN_LANGUAGES = [
    ("中文", "zh"),
    ("英语", "en"),
    ("葡萄牙语", "pt"),
    ("西班牙语", "es"),
    ("日语", "ja"),
    ("印尼语", "id"),
    ("德语", "de"),
    ("法语", "fr"),
]
OPENAI_LANGUAGES = [
    ("英语", "en"),
    ("西班牙语", "es"),
    ("法语", "fr"),
    ("德语", "de"),
    ("意大利语", "it"),
    ("日语", "ja"),
    ("葡萄牙语", "pt"),
    ("中文", "zh"),
    ("韩语", "ko"),
    ("印地语", "hi"),
    ("阿拉伯语", "ar"),
    ("荷兰语", "nl"),
    ("俄语", "ru"),
    ("波兰语", "pl"),
]
OPENAI_SOURCE_LANGUAGES = [("自动识别", "auto")]
LANGUAGES_BY_ENGINE: dict[str, list[tuple[str, str]]] = {
    "huoshan": HUOSHAN_LANGUAGES,
    "openai": OPENAI_LANGUAGES,
    "mock": OPENAI_LANGUAGES,
}


def _source_langs(engine: str) -> list[tuple[str, str]]:
    if engine == "openai":
        return OPENAI_SOURCE_LANGUAGES
    return LANGUAGES_BY_ENGINE.get(engine, HUOSHAN_LANGUAGES)


def _target_langs(engine: str) -> list[tuple[str, str]]:
    return LANGUAGES_BY_ENGINE.get(engine, HUOSHAN_LANGUAGES)


class MicTranslatePanel(QFrame):
    sig_start_requested = Signal()
    sig_stop_requested = Signal()
    sig_test_cable = Signal()
    sig_select_voice = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._is_running = False
        self._resolver = DeviceResolver()
        self._mic_devices: list[AudioDevice] = []
        self._speaker_id = "zh_female_xiaohe_jupiter_bigtts"
        self._source_buffer = SubtitleBuffer(self._set_source_text)
        self._translation_buffer = SubtitleBuffer(self._set_translation_text)
        self._build_ui()
        self._populate_devices()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        title = QLabel("麦克风同声传译")
        title.setObjectName("panelTitle")
        title_block.addWidget(title)
        desc = QLabel("监听麦克风输入，并输出实时翻译结果。")
        desc.setObjectName("panelDesc")
        title_block.addWidget(desc)
        title_row.addLayout(title_block, 1)

        self._state_chip = StatusPill("未启动", "warn")
        title_row.addWidget(self._state_chip)

        self._voice_btn = QPushButton("选择音色")
        self._voice_btn.setObjectName("ghost")
        self._voice_btn.setIcon(resource_icon("voice"))
        self._voice_btn.setIconSize(QSize(14, 14))
        self._voice_btn.clicked.connect(self.sig_select_voice.emit)
        title_row.addWidget(self._voice_btn)
        layout.addLayout(title_row)

        mic_row = QHBoxLayout()
        self._mic_combo = QComboBox()
        self._mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mic_row.addWidget(self._mic_combo, 1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghost")
        refresh_btn.setFixedWidth(64)
        refresh_btn.clicked.connect(self._populate_devices)
        mic_row.addWidget(refresh_btn)
        layout.addLayout(mic_row)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["huoshan", "openai", "mock"])
        self._engine_combo.currentTextChanged.connect(self._on_engine_changed)
        self._engine_combo.setVisible(False)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._src_lang_combo = QComboBox()
        self._src_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._src_lang_combo, 1)
        arrow = QLabel()
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(18)
        arrow.setPixmap(resource_pixmap("arrow-right", 12, 12))
        lang_row.addWidget(arrow)
        self._tgt_lang_combo = QComboBox()
        self._tgt_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._tgt_lang_combo, 1)
        layout.addLayout(lang_row)

        self._hint_label = QLabel()
        self._hint_label.setObjectName("routeLabel")
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)
        self._populate_language_combos("huoshan")

        self._source_edit = QLabel("")
        self._source_edit.setObjectName("sourceLine")
        self._source_edit.setMinimumHeight(24)
        self._source_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._source_edit)

        stage_container = QWidget()
        stack = QStackedLayout(stage_container)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack.setContentsMargins(0, 0, 0, 0)

        self._translation_edit = QTextEdit()
        self._translation_edit.setObjectName("stageLarge")
        self._translation_edit.setReadOnly(True)
        stack.addWidget(self._translation_edit)

        self._empty_overlay = QWidget()
        self._empty_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self._empty_overlay)
        empty_layout.setContentsMargins(20, 20, 20, 20)
        empty_layout.setSpacing(8)
        empty_title = QLabel("等待开始麦克风翻译")
        empty_title.setObjectName("emptyTitle")
        empty_layout.addWidget(empty_title)
        empty_copy = QLabel("选择一个可用麦克风后点击开始。翻译结果会显示在这里，并同步到悬浮字幕。")
        empty_copy.setObjectName("emptyCopy")
        empty_copy.setWordWrap(True)
        empty_layout.addWidget(empty_copy)
        empty_layout.addStretch()
        stack.addWidget(self._empty_overlay)
        layout.addWidget(stage_container, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._toggle_btn = QPushButton("开始翻译")
        self._toggle_btn.setIcon(resource_icon("play"))
        self._toggle_btn.setIconSize(QSize(14, 14))
        self._toggle_btn.clicked.connect(self._on_toggle)
        footer.addWidget(self._toggle_btn)
        layout.addLayout(footer)

        self._refresh_hint()

    def set_overlay_visible(self, visible: bool) -> None:
        return

    def _populate_devices(self) -> None:
        self._resolver.refresh()
        self._mic_devices = self._stable_logical_inputs()
        current = self._mic_combo.currentText()
        self._mic_combo.clear()
        for device in self._mic_devices:
            self._mic_combo.addItem(self._device_label(device), device)
        if current:
            idx = self._mic_combo.findText(current)
            if idx >= 0:
                self._mic_combo.setCurrentIndex(idx)

    def _stable_logical_inputs(self) -> list[AudioDevice]:
        grouped: dict[str, list[AudioDevice]] = {}
        for device in self._resolver.input_devices():
            if "cable output" in device.name.lower():
                continue
            grouped.setdefault(device.name.lower().strip()[:28], []).append(device)

        logical: list[AudioDevice] = []
        for candidates in grouped.values():
            logical.append(self._resolver.stable_input_candidates(candidates[0])[0])
        return sorted(logical, key=lambda item: item.index)

    def _device_label(self, device: AudioDevice) -> str:
        return f"#{device.index} | {device.name} | {device.hostapi}"

    def _populate_language_combos(self, engine: str) -> None:
        self._src_lang_combo.clear()
        for name, code in _source_langs(engine):
            self._src_lang_combo.addItem(f"{name} ({code})", code)

        self._tgt_lang_combo.clear()
        for name, code in _target_langs(engine):
            self._tgt_lang_combo.addItem(f"{name} ({code})", code)

        zh_idx = self._tgt_lang_combo.findData("zh")
        if zh_idx >= 0:
            self._tgt_lang_combo.setCurrentIndex(zh_idx)
        self._refresh_hint()

    def _on_engine_changed(self, engine: str) -> None:
        self._populate_language_combos(engine)

    def _refresh_hint(self) -> None:
        voice_label = "当前音色：已选择" if self._speaker_id else "当前音色：服务默认"
        self._hint_label.setText(f"{voice_label}。运行中会锁定设备和语言，避免误操作。")

    def selected_mic_device(self) -> AudioDevice | None:
        return self._mic_combo.currentData()

    def selected_engine(self) -> str:
        return self._engine_combo.currentText()

    def selected_source_language(self) -> str:
        return self._src_lang_combo.currentData() or "en"

    def selected_target_language(self) -> str:
        return self._tgt_lang_combo.currentData() or "zh"

    def selected_speaker_id(self) -> str:
        return self._speaker_id

    def set_mic_by_index(self, index: int | None) -> None:
        if index is None:
            return
        for i in range(self._mic_combo.count()):
            device = self._mic_combo.itemData(i)
            if device and device.index == index:
                self._mic_combo.setCurrentIndex(i)
                return

    def set_engine(self, engine: str) -> None:
        idx = self._engine_combo.findText(engine)
        if idx >= 0:
            self._engine_combo.setCurrentIndex(idx)

    def set_source_language(self, code: str) -> None:
        idx = self._src_lang_combo.findData(code)
        if idx >= 0:
            self._src_lang_combo.setCurrentIndex(idx)

    def set_target_language(self, code: str) -> None:
        idx = self._tgt_lang_combo.findData(code)
        if idx >= 0:
            self._tgt_lang_combo.setCurrentIndex(idx)

    def set_speaker_id(self, speaker_id: str) -> None:
        self._speaker_id = speaker_id.strip()
        self._voice_btn.setText("音色已选" if self._speaker_id else "选择音色")
        self._refresh_hint()

    @Slot()
    def _on_toggle(self) -> None:
        if self._is_running:
            self.sig_stop_requested.emit()
        else:
            self.sig_start_requested.emit()

    def set_running(self, running: bool) -> None:
        self._is_running = running
        if running:
            self._toggle_btn.setText("停止翻译")
            self._toggle_btn.setIcon(resource_icon("stop"))
            self._toggle_btn.setObjectName("danger")
            self._state_chip.set_status("正在监听", "normal")
            self._empty_overlay.setVisible(False)
        else:
            self._toggle_btn.setText("开始翻译")
            self._toggle_btn.setIcon(resource_icon("play"))
            self._toggle_btn.setObjectName("")
            self._state_chip.set_status("未启动", "warn")
            self._empty_overlay.setVisible(True)
            self._source_buffer.reset()
            self._translation_buffer.reset()
            self._source_edit.clear()
            self._translation_edit.clear()

        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)

        self._mic_combo.setEnabled(not running)
        self._engine_combo.setEnabled(not running)
        self._src_lang_combo.setEnabled(not running)
        self._tgt_lang_combo.setEnabled(not running)
        self._voice_btn.setEnabled(not running)

    @Slot(str)
    def update_source(self, text: str) -> None:
        self._source_buffer.update(text)

    @Slot(str)
    def update_translation(self, text: str) -> None:
        self._translation_buffer.update(text)

    def _set_source_text(self, text: str) -> None:
        last = text.strip().splitlines()[-1] if text.strip() else ""
        if len(last) > 120:
            last = "..." + last[-120:]
        self._source_edit.setText(last)

    def _set_translation_text(self, text: str) -> None:
        self._translation_edit.setPlainText(text)
        self._translation_edit.verticalScrollBar().setValue(self._translation_edit.verticalScrollBar().maximum())
