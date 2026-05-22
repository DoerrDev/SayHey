from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QSizePolicy,
)

from app_core.audio_devices import AudioDevice, DeviceResolver
from gui.subtitle_buffer import SubtitleBuffer
from gui.icons import icon as _icon
from gui.voice_selector_dialog import S2S_VOICE_TYPES

_S2S_ALLOWED_TARGETS = {"zh", "en"}

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
LANGUAGES_BY_ENGINE: dict[str, list[tuple[str, str]]] = {
    "huoshan": HUOSHAN_LANGUAGES,
    "mock": HUOSHAN_LANGUAGES,
}


def _source_langs(engine: str) -> list[tuple[str, str]]:
    return LANGUAGES_BY_ENGINE.get(engine, HUOSHAN_LANGUAGES)


def _target_langs(engine: str) -> list[tuple[str, str]]:
    return LANGUAGES_BY_ENGINE.get(engine, HUOSHAN_LANGUAGES)


class MicTranslatePanel(QFrame):
    sig_start_requested = Signal()
    sig_stop_requested = Signal()
    sig_test_cable = Signal()
    sig_select_voice = Signal()
    sig_speaker_id_changed = Signal(str)
    sig_running_changed = Signal(bool)
    sig_voice_warning = Signal(str)
    sig_output_device_changed = Signal()
    sig_speech_rate_changed = Signal(int)
    sig_simultaneous_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tabContent")
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

        # Mic device row
        mic_row = QHBoxLayout()
        mic_row.setSpacing(12)
        mic_label = QLabel("麦克风选择")
        mic_label.setObjectName("sectionTitle")
        mic_row.addWidget(mic_label)
        self._mic_combo = QComboBox()
        self._mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mic_row.addWidget(self._mic_combo, 1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghost")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self._populate_devices)
        mic_row.addWidget(refresh_btn)
        layout.addLayout(mic_row)

        # Virtual mic output row
        out_row = QHBoxLayout()
        out_row.setSpacing(12)
        out_label = QLabel("虚拟麦克风")
        out_label.setObjectName("sectionTitle")
        out_label.setToolTip("翻译后的音频将输出到该设备（一般选 CABLE Input）")
        out_row.addWidget(out_label)
        self._out_combo = QComboBox()
        self._out_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._out_combo.currentIndexChanged.connect(self._on_output_changed)
        out_row.addWidget(self._out_combo, 1)
        layout.addLayout(out_row)

        # Engine (hidden — kept for state; configure via settings dialog)
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["huoshan", "mock"])
        self._engine_combo.currentTextChanged.connect(self._on_engine_changed)
        self._engine_combo.setVisible(False)

        sim_row = QHBoxLayout()
        sim_row.setSpacing(10)
        self._simultaneous_checkbox = QCheckBox("同声传译")
        self._simultaneous_checkbox.setChecked(True)
        self._simultaneous_checkbox.setToolTip("选中：麦克风发送到服务商，转译音频输出到虚拟声卡；取消：麦克风直接输出到虚拟声卡。")
        self._simultaneous_checkbox.stateChanged.connect(self._on_simultaneous_changed)
        sim_row.addWidget(self._simultaneous_checkbox)
        rate_label = QLabel("语速")
        rate_label.setObjectName("routeLabel")
        sim_row.addWidget(rate_label)
        self._speech_rate = QSlider(Qt.Orientation.Horizontal)
        self._speech_rate.setRange(-50, 100)
        self._speech_rate.setFixedWidth(140)
        self._speech_rate.setToolTip("范围：-50 到 100。0 是默认语速，负数更慢，正数更快。")
        self._speech_rate.valueChanged.connect(self._on_speech_rate_changed)
        sim_row.addWidget(self._speech_rate)
        self._speech_rate_label = QLabel("0")
        self._speech_rate_label.setMinimumWidth(34)
        sim_row.addWidget(self._speech_rate_label)
        sim_row.addStretch(1)
        layout.addLayout(sim_row)

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
        self._tgt_lang_combo.currentIndexChanged.connect(self._enforce_s2s_voice_constraint)

        # Source text (single-line compact)
        self._source_edit = QLabel("")
        self._source_edit.setObjectName("routeLabel")
        self._source_edit.setText("")
        self._source_edit.setMinimumHeight(20)
        self._source_edit.setWordWrap(False)
        self._source_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._source_edit)

        # Translation text (main stage)
        self._translation_edit = QTextEdit()
        self._translation_edit.setObjectName("stageLarge")
        self._translation_edit.setReadOnly(True)
        self._translation_edit.setPlaceholderText("翻译文字将在此显示...")
        layout.addWidget(self._translation_edit, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._toggle_btn = QPushButton(_icon("mic", color="#0a1218"), " 开启麦克风")
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self._toggle_btn)

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

        prev_out_index = self.selected_output_device().index if self.selected_output_device() else None
        self._out_combo.blockSignals(True)
        self._out_combo.clear()
        for device in self._resolver.output_devices():
            self._out_combo.addItem(self._device_label(device), device)
        if prev_out_index is not None:
            self.set_output_by_index(prev_out_index)
        self._out_combo.blockSignals(False)

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

    def selected_output_device(self) -> AudioDevice | None:
        return self._out_combo.currentData()

    def set_output_by_index(self, index: int | None) -> None:
        if index is None:
            return
        for i in range(self._out_combo.count()):
            device: AudioDevice | None = self._out_combo.itemData(i)
            if device and device.index == index:
                self._out_combo.setCurrentIndex(i)
                return

    @Slot()
    def _on_output_changed(self) -> None:
        self.sig_output_device_changed.emit()

    def selected_speech_rate(self) -> int:
        return self._speech_rate.value()

    def set_speech_rate(self, value: int) -> None:
        self._speech_rate.setValue(int(value))

    @Slot(int)
    def _on_speech_rate_changed(self, value: int) -> None:
        self._speech_rate_label.setText(f"+{value}" if value > 0 else str(value))
        self.sig_speech_rate_changed.emit(value)

    def selected_engine(self) -> str:
        return self._engine_combo.currentText()

    def selected_source_language(self) -> str:
        return self._src_lang_combo.currentData() or "en"

    def selected_target_language(self) -> str:
        return self._tgt_lang_combo.currentData() or "zh"

    def selected_speaker_id(self) -> str:
        return self._speaker_id

    def simultaneous_interpretation_enabled(self) -> bool:
        return self._simultaneous_checkbox.isChecked()

    def set_simultaneous_interpretation_enabled(self, enabled: bool) -> None:
        self._simultaneous_checkbox.setChecked(enabled)

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
        self.sig_speaker_id_changed.emit(self._speaker_id)
        self._enforce_s2s_voice_constraint()

    def _enforce_s2s_voice_constraint(self) -> None:
        if self._speaker_id not in S2S_VOICE_TYPES:
            return
        target = self.selected_target_language()
        if target in _S2S_ALLOWED_TARGETS:
            return
        self._speaker_id = ""
        self.sig_speaker_id_changed.emit("")
        self.sig_voice_warning.emit("当前同传音色仅支持中/英目标语言，已切换为默认音色")

    @Slot()
    def _on_toggle(self) -> None:
        if self._is_running:
            self.sig_stop_requested.emit()
        else:
            self.sig_start_requested.emit()

    def set_running(self, running: bool) -> None:
        self._is_running = running
        if running:
            self._toggle_btn.setIcon(_icon("square", color="#ffffff"))
            self._toggle_btn.setText(" 关闭麦克风")
            self._toggle_btn.setObjectName("danger")
        else:
            self._toggle_btn.setIcon(_icon("mic", color="#0a1218"))
            self._toggle_btn.setText(" 开启麦克风")
            self._toggle_btn.setObjectName("")
        self._toggle_btn.style().polish(self._toggle_btn)
        self._mic_combo.setEnabled(not running)
        self._out_combo.setEnabled(not running)
        self._engine_combo.setEnabled(not running)
        self._simultaneous_checkbox.setEnabled(not running)
        self._speech_rate.setEnabled(not running)
        self._src_lang_combo.setEnabled(not running)
        self._tgt_lang_combo.setEnabled(not running)
        self.sig_running_changed.emit(running)
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

    @Slot(int)
    def _on_simultaneous_changed(self, state: int) -> None:
        self.sig_simultaneous_changed.emit(bool(state))

    def set_route_text(self, text: str) -> None:
        self._route_label.setText(text)
