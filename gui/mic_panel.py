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
    QSizePolicy,
    QWidget,
)

from app_core.audio_devices import AudioDevice, DeviceResolver
from gui.icons import resource_icon
from gui.subtitle_buffer import SubtitleBuffer

HUOSHAN_LANGUAGES = [
    ("Chinese", "zh"),
    ("English", "en"),
    ("Portuguese", "pt"),
    ("Spanish", "es"),
    ("Japanese", "ja"),
    ("Indonesian", "id"),
    ("German", "de"),
    ("French", "fr"),
]
OPENAI_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Japanese", "ja"),
    ("Portuguese", "pt"),
    ("Chinese", "zh"),
    ("Korean", "ko"),
    ("Hindi", "hi"),
    ("Arabic", "ar"),
    ("Dutch", "nl"),
    ("Russian", "ru"),
    ("Polish", "pl"),
]
OPENAI_SOURCE_LANGUAGES = [("Auto detect", "auto")]
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
    sig_overlay_toggle = Signal()

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
        layout.setSpacing(10)

        # Title
        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("麦克风同声传译")
        title.setObjectName("panelTitle")
        title_block.addWidget(title)
        desc = QLabel("监听麦克风并输出实时翻译文字")
        desc.setObjectName("panelDesc")
        title_block.addWidget(desc)
        title_row.addLayout(title_block, 1)

        self._state_chip = QLabel("未启动")
        self._state_chip.setObjectName("statusChipWarn")
        title_row.addWidget(self._state_chip)

        self._voice_btn = QPushButton("音色")
        self._voice_btn.setObjectName("ghost")
        self._voice_btn.setFixedWidth(72)
        self._voice_btn.clicked.connect(self.sig_select_voice.emit)
        title_row.addWidget(self._voice_btn)
        layout.addLayout(title_row)

        # Mic device row (no label prefix)
        mic_row = QHBoxLayout()
        mic_row.setSpacing(8)
        self._mic_combo = QComboBox()
        self._mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mic_row.addWidget(self._mic_combo, 1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghost")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self._populate_devices)
        mic_row.addWidget(refresh_btn)
        layout.addLayout(mic_row)

        # Engine (hidden — kept for state; configure via settings dialog)
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["huoshan", "openai", "mock"])
        self._engine_combo.currentTextChanged.connect(self._on_engine_changed)
        self._engine_combo.setVisible(False)

        # Compact language row: [src] → [tgt]
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._src_lang_combo = QComboBox()
        self._src_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._src_lang_combo, 1)
        arrow = QLabel("→")
        arrow.setObjectName("routeLabel")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(20)
        lang_row.addWidget(arrow)
        self._tgt_lang_combo = QComboBox()
        self._tgt_lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._tgt_lang_combo, 1)
        layout.addLayout(lang_row)
        self._populate_language_combos("huoshan")

        # Source text (single-line compact)
        self._source_edit = QLabel("")
        self._source_edit.setObjectName("routeLabel")
        self._source_edit.setText("")
        self._source_edit.setMinimumHeight(20)
        self._source_edit.setWordWrap(False)
        self._source_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._source_edit)

        # Translation text + empty overlay
        stage_container = QWidget()
        stage_stack = QStackedLayout(stage_container)
        stage_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stage_stack.setContentsMargins(0, 0, 0, 0)

        self._translation_edit = QTextEdit()
        self._translation_edit.setObjectName("stageLarge")
        self._translation_edit.setReadOnly(True)
        stage_stack.addWidget(self._translation_edit)

        self._empty_overlay = QWidget()
        self._empty_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_overlay.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(self._empty_overlay)
        empty_layout.setContentsMargins(20, 22, 20, 22)
        empty_layout.setSpacing(8)
        self._empty_title = QLabel("等待开始麦克风翻译")
        self._empty_title.setObjectName("emptyTitle")
        self._empty_copy = QLabel(
            "选择麦克风设备并点击下方按钮开始。翻译文字会显示在这里，也可同步到悬浮字幕。"
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

        self._toggle_btn = QPushButton("开始翻译")
        self._toggle_btn.setIcon(resource_icon("play"))
        self._toggle_btn.setIconSize(QSize(14, 14))
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self._toggle_btn)

        self._overlay_btn = QPushButton("显示悬浮字幕")
        self._overlay_btn.setObjectName("secondary")
        self._overlay_btn.clicked.connect(self.sig_overlay_toggle.emit)
        btn_row.addWidget(self._overlay_btn)

        layout.addLayout(btn_row)

    def _populate_devices(self) -> None:
        self._resolver.refresh()
        self._mic_devices = self._stable_logical_inputs()
        current = self._mic_combo.currentText()
        self._mic_combo.clear()
        for device in self._mic_devices:
            label = self._device_label(device)
            self._mic_combo.addItem(label, device)
        if current:
            idx = self._mic_combo.findText(current)
            if idx >= 0:
                self._mic_combo.setCurrentIndex(idx)

    def _stable_logical_inputs(self) -> list[AudioDevice]:
        by_name: dict[str, list[AudioDevice]] = {}
        for device in self._resolver.input_devices():
            if "cable output" in device.name.lower():
                continue
            key = device.name.lower().strip()[:28]
            by_name.setdefault(key, []).append(device)
        logical: list[AudioDevice] = []
        for devices in by_name.values():
            logical.append(self._resolver.stable_input_candidates(devices[0])[0])
        return sorted(logical, key=lambda d: d.index)

    def _device_label(self, device: AudioDevice) -> str:
        return f"#{device.index} | {device.name} | {device.hostapi}"

    def _populate_language_combos(self, engine: str) -> None:
        self._src_lang_combo.clear()
        for name, code in _source_langs(engine):
            self._src_lang_combo.addItem(f"{name} ({code})", code)

        self._tgt_lang_combo.clear()
        for name, code in _target_langs(engine):
            self._tgt_lang_combo.addItem(f"{name} ({code})", code)
        # default target to Chinese
        zh_idx = self._tgt_lang_combo.findData("zh")
        if zh_idx >= 0:
            self._tgt_lang_combo.setCurrentIndex(zh_idx)

    def _on_engine_changed(self, engine: str) -> None:
        self._populate_language_combos(engine)

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
            device: AudioDevice | None = self._mic_combo.itemData(i)
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
        self._voice_btn.setText("音色 ✓" if self._speaker_id else "音色")

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
            self._state_chip.setText("正在监听")
            self._state_chip.setObjectName("statusChip")
            self._empty_overlay.setVisible(False)
        else:
            self._toggle_btn.setText("开始翻译")
            self._toggle_btn.setIcon(resource_icon("play"))
            self._toggle_btn.setObjectName("")
            self._state_chip.setText("未启动")
            self._state_chip.setObjectName("statusChipWarn")
            self._empty_overlay.setVisible(True)
        self._toggle_btn.style().polish(self._toggle_btn)
        self._state_chip.style().polish(self._state_chip)
        self._mic_combo.setEnabled(not running)
        self._engine_combo.setEnabled(not running)
        self._src_lang_combo.setEnabled(not running)
        self._tgt_lang_combo.setEnabled(not running)
        self._voice_btn.setEnabled(not running)
        if not running:
            self._source_buffer.reset()
            self._translation_buffer.reset()

    @Slot(str)
    def update_source(self, text: str) -> None:
        self._source_buffer.update(text)

    @Slot(str)
    def update_translation(self, text: str) -> None:
        self._translation_buffer.update(text)

    def _set_source_text(self, text: str) -> None:
        last = text.strip().splitlines()[-1] if text.strip() else ""
        if len(last) > 120:
            last = "…" + last[-120:]
        self._source_edit.setText(last)

    def _set_translation_text(self, text: str) -> None:
        self._translation_edit.setPlainText(text)
        sb = self._translation_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_route_text(self, text: str) -> None:
        self._route_label.setText(text)
