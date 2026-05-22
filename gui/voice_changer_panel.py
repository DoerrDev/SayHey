from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
)

from app_core.audio_devices import AudioDevice, DeviceResolver
from app_core.rvc_client import install_sidecar, sidecar_installed


STATE_UNINSTALLED = "uninstalled"
STATE_INSTALLING = "installing"
STATE_READY = "ready"
STATE_STARTING = "starting"
STATE_RUNNING = "running"


class RvcInstallerThread(QThread):
    sig_line = Signal(str)
    sig_finished = Signal(bool, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancelled = False

    def run(self) -> None:
        try:
            ok = install_sidecar(
                on_line=self.sig_line.emit,
                cancel_check=lambda: self._cancelled,
            )
            if self._cancelled:
                self.sig_finished.emit(False, "已取消")
            elif ok:
                self.sig_finished.emit(True, "安装完成")
            else:
                self.sig_finished.emit(False, "安装失败，详见日志")
        except Exception as exc:
            self.sig_finished.emit(False, f"安装异常: {exc}")

    def cancel(self) -> None:
        self._cancelled = True


class VoiceChangerPanel(QFrame):
    sig_open_model_manager = Signal()
    sig_pitch_changed = Signal(int)
    sig_index_rate_changed = Signal(float)
    sig_enabled_changed = Signal(bool)
    sig_device_changed = Signal(str)
    sig_mic_changed = Signal(int)
    sig_output_changed = Signal(int)
    sig_action_install = Signal()
    sig_action_start = Signal()
    sig_action_stop = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tabContent")
        self._resolver = DeviceResolver()
        self._mic_devices: list[AudioDevice] = []
        self._current_model = ""
        self._state = STATE_UNINSTALLED
        self._installer: RvcInstallerThread | None = None
        self._build_ui()
        self._populate_devices()
        self.refresh_install_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        info = QLabel(
            "RVC v2 变声器：物理麦克风经 RVC 推理后输出到虚拟麦克风。\n"
            "首次使用需点击「初始化」自动下载 PyTorch + rvc-python（CUDA 优先，无 N 卡走 CPU）。"
        )
        info.setObjectName("routeLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        mic_row = QHBoxLayout()
        mic_row.setSpacing(12)
        mic_label = QLabel("麦克风选择")
        mic_label.setObjectName("sectionTitle")
        mic_row.addWidget(mic_label)
        self._mic_combo = QComboBox()
        self._mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_row.addWidget(self._mic_combo, 1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghost")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self._populate_devices)
        mic_row.addWidget(refresh_btn)
        layout.addLayout(mic_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(12)
        out_label = QLabel("虚拟麦克风")
        out_label.setObjectName("sectionTitle")
        out_label.setToolTip("变声后的音频将输出到该设备（一般选 CABLE Input）")
        out_row.addWidget(out_label)
        self._out_combo = QComboBox()
        self._out_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._out_combo.currentIndexChanged.connect(self._on_out_changed)
        out_row.addWidget(self._out_combo, 1)
        layout.addLayout(out_row)

        enable_row = QHBoxLayout()
        enable_row.setSpacing(10)
        self._enable_chk = QCheckBox("启用变声器")
        self._enable_chk.setToolTip("启用后，同声传译需关闭才会走 RVC 链路")
        self._enable_chk.toggled.connect(self.sig_enabled_changed.emit)
        enable_row.addWidget(self._enable_chk)

        dev_label = QLabel("推理设备")
        dev_label.setObjectName("routeLabel")
        enable_row.addWidget(dev_label)
        self._device_combo = QComboBox()
        self._device_combo.addItem("自动 (auto)", "auto")
        self._device_combo.addItem("CPU", "cpu")
        self._device_combo.addItem("CUDA:0", "cuda:0")
        self._device_combo.currentIndexChanged.connect(
            lambda _i: self.sig_device_changed.emit(self._device_combo.currentData() or "auto")
        )
        enable_row.addWidget(self._device_combo)
        enable_row.addStretch(1)
        layout.addLayout(enable_row)

        model_row = QHBoxLayout()
        model_row.setSpacing(12)
        model_label = QLabel("当前模型")
        model_label.setObjectName("sectionTitle")
        model_row.addWidget(model_label)
        self._model_value = QLabel("未选择")
        self._model_value.setObjectName("routeLabel")
        model_row.addWidget(self._model_value, 1)
        self._manage_btn = QPushButton("管理模型")
        self._manage_btn.setObjectName("ghost")
        self._manage_btn.clicked.connect(self.sig_open_model_manager.emit)
        model_row.addWidget(self._manage_btn)
        layout.addLayout(model_row)

        pitch_row = QHBoxLayout()
        pitch_row.setSpacing(10)
        pitch_lab = QLabel("音高 ±半音")
        pitch_lab.setObjectName("routeLabel")
        pitch_row.addWidget(pitch_lab)
        self._pitch = QSlider(Qt.Orientation.Horizontal)
        self._pitch.setRange(-24, 24)
        self._pitch.setFixedWidth(220)
        self._pitch.valueChanged.connect(self._on_pitch_changed)
        pitch_row.addWidget(self._pitch)
        self._pitch_lbl = QLabel("0")
        self._pitch_lbl.setMinimumWidth(34)
        pitch_row.addWidget(self._pitch_lbl)
        pitch_row.addStretch(1)
        layout.addLayout(pitch_row)

        idx_row = QHBoxLayout()
        idx_row.setSpacing(10)
        idx_lab = QLabel("Index 比例")
        idx_lab.setObjectName("routeLabel")
        idx_row.addWidget(idx_lab)
        self._idx = QSlider(Qt.Orientation.Horizontal)
        self._idx.setRange(0, 100)
        self._idx.setValue(50)
        self._idx.setFixedWidth(220)
        self._idx.valueChanged.connect(self._on_idx_changed)
        idx_row.addWidget(self._idx)
        self._idx_lbl = QLabel("0.50")
        self._idx_lbl.setMinimumWidth(40)
        idx_row.addWidget(self._idx_lbl)
        idx_row.addStretch(1)
        layout.addLayout(idx_row)

        # Progress bar (visible only during install)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Install log (visible only during install)
        self._log = QTextEdit()
        self._log.setObjectName("routeLabel")
        self._log.setReadOnly(True)
        self._log.setVisible(False)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        # Action button + status
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self._action_btn = QPushButton("检测中...")
        self._action_btn.clicked.connect(self._on_action_clicked)
        self._action_btn.setMinimumHeight(36)
        action_row.addWidget(self._action_btn)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("routeLabel")
        action_row.addWidget(self._status_lbl, 1)
        layout.addLayout(action_row)

        layout.addStretch(1)

    def _populate_devices(self) -> None:
        self._resolver.refresh()
        prev_mic = self.selected_mic_device().index if self.selected_mic_device() else None
        self._mic_combo.blockSignals(True)
        self._mic_combo.clear()
        self._mic_devices = []
        for device in self._resolver.input_devices():
            if "cable output" in device.name.lower():
                continue
            self._mic_devices.append(device)
            self._mic_combo.addItem(self._device_label(device), device)
        if prev_mic is not None:
            self.set_mic_by_index(prev_mic)
        self._mic_combo.blockSignals(False)

        prev_out = self.selected_output_device().index if self.selected_output_device() else None
        self._out_combo.blockSignals(True)
        self._out_combo.clear()
        for device in self._resolver.output_devices():
            self._out_combo.addItem(self._device_label(device), device)
        if prev_out is not None:
            self.set_output_by_index(prev_out)
        self._out_combo.blockSignals(False)

    def _device_label(self, d: AudioDevice) -> str:
        return f"#{d.index} | {d.name} | {d.hostapi}"

    @Slot(int)
    def _on_mic_changed(self, _idx: int) -> None:
        d = self.selected_mic_device()
        if d is not None:
            self.sig_mic_changed.emit(d.index)

    @Slot(int)
    def _on_out_changed(self, _idx: int) -> None:
        d = self.selected_output_device()
        if d is not None:
            self.sig_output_changed.emit(d.index)

    @Slot(int)
    def _on_pitch_changed(self, v: int) -> None:
        self._pitch_lbl.setText(f"+{v}" if v > 0 else str(v))
        self.sig_pitch_changed.emit(v)

    @Slot(int)
    def _on_idx_changed(self, v: int) -> None:
        rate = v / 100.0
        self._idx_lbl.setText(f"{rate:.2f}")
        self.sig_index_rate_changed.emit(rate)

    def selected_mic_device(self) -> AudioDevice | None:
        return self._mic_combo.currentData()

    def selected_output_device(self) -> AudioDevice | None:
        return self._out_combo.currentData()

    def set_mic_by_index(self, index: int | None) -> None:
        if index is None:
            return
        for i in range(self._mic_combo.count()):
            d: AudioDevice | None = self._mic_combo.itemData(i)
            if d and d.index == index:
                self._mic_combo.setCurrentIndex(i)
                return

    def set_output_by_index(self, index: int | None) -> None:
        if index is None:
            return
        for i in range(self._out_combo.count()):
            d: AudioDevice | None = self._out_combo.itemData(i)
            if d and d.index == index:
                self._out_combo.setCurrentIndex(i)
                return

    def is_enabled(self) -> bool:
        return self._enable_chk.isChecked()

    def set_enabled_state(self, enabled: bool) -> None:
        self._enable_chk.setChecked(enabled)

    def set_pitch(self, v: int) -> None:
        self._pitch.setValue(int(v))

    def pitch(self) -> int:
        return self._pitch.value()

    def set_index_rate(self, v: float) -> None:
        self._idx.setValue(int(round(float(v) * 100)))

    def index_rate(self) -> float:
        return self._idx.value() / 100.0

    def set_device(self, code: str) -> None:
        idx = self._device_combo.findData(code)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)

    def device(self) -> str:
        return self._device_combo.currentData() or "auto"

    def set_current_model(self, name: str) -> None:
        self._current_model = name
        self._model_value.setText(name or "未选择")
        self._refresh_action_button()

    def current_model(self) -> str:
        return self._current_model

    def set_status(self, text: str) -> None:
        self._status_lbl.setText(text)

    def state(self) -> str:
        return self._state

    def refresh_install_state(self) -> None:
        if self._state in (STATE_INSTALLING, STATE_STARTING, STATE_RUNNING):
            return
        self._state = STATE_READY if sidecar_installed() else STATE_UNINSTALLED
        self._refresh_action_button()

    def set_running(self, running: bool) -> None:
        if running:
            self._state = STATE_RUNNING
        else:
            self._state = STATE_READY if sidecar_installed() else STATE_UNINSTALLED
        self._refresh_action_button()

    def set_starting(self) -> None:
        self._state = STATE_STARTING
        self._refresh_action_button()

    def _refresh_action_button(self) -> None:
        running_locked = self._state in (STATE_INSTALLING, STATE_STARTING, STATE_RUNNING)
        self._mic_combo.setEnabled(not running_locked)
        self._out_combo.setEnabled(not running_locked)
        self._enable_chk.setEnabled(not running_locked)
        self._device_combo.setEnabled(not running_locked)
        self._manage_btn.setEnabled(self._state != STATE_RUNNING)

        if self._state == STATE_UNINSTALLED:
            self._action_btn.setText("初始化变声器环境")
            self._action_btn.setObjectName("")
            self._action_btn.setEnabled(True)
            self._status_lbl.setText("尚未安装 sidecar 依赖")
        elif self._state == STATE_INSTALLING:
            self._action_btn.setText("初始化中...")
            self._action_btn.setEnabled(False)
        elif self._state == STATE_READY:
            self._action_btn.setText("启动变声器")
            self._action_btn.setObjectName("")
            has_model = bool(self._current_model)
            self._action_btn.setEnabled(has_model)
            self._status_lbl.setText("就绪" if has_model else "请先选择模型")
        elif self._state == STATE_STARTING:
            self._action_btn.setText("启动中...")
            self._action_btn.setEnabled(False)
        elif self._state == STATE_RUNNING:
            self._action_btn.setText("停止变声器")
            self._action_btn.setObjectName("danger")
            self._action_btn.setEnabled(True)
            self._status_lbl.setText("运行中")
        self._action_btn.style().unpolish(self._action_btn)
        self._action_btn.style().polish(self._action_btn)

    @Slot()
    def _on_action_clicked(self) -> None:
        if self._state == STATE_UNINSTALLED:
            self.sig_action_install.emit()
        elif self._state == STATE_READY:
            self.sig_action_start.emit()
        elif self._state == STATE_RUNNING:
            self.sig_action_stop.emit()

    def begin_install(self) -> RvcInstallerThread:
        self._state = STATE_INSTALLING
        self._refresh_action_button()
        self._progress.setVisible(True)
        self._log.setVisible(True)
        self._log.clear()
        self._status_lbl.setText("正在下载并安装依赖，可能需要几分钟...")
        thread = RvcInstallerThread(self)
        thread.sig_line.connect(self._append_install_log)
        thread.sig_finished.connect(self._on_install_finished)
        self._installer = thread
        thread.start()
        return thread

    @Slot(str)
    def _append_install_log(self, line: str) -> None:
        self._log.append(line)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(bool, str)
    def _on_install_finished(self, ok: bool, msg: str) -> None:
        self._progress.setVisible(False)
        self._status_lbl.setText(msg)
        self._installer = None
        if ok:
            self._state = STATE_READY
        else:
            self._state = STATE_UNINSTALLED
        self._refresh_action_button()
