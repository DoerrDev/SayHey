from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMessageBox,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import Qt

from app_core.audio_devices import AudioDevice, DeviceResolver
from core.settings_store import AppSettings, SettingsStore


def _password_line() -> QLineEdit:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    return edit


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionTitle")
    return lbl


class SettingsDialog(QDialog):
    settings_saved = Signal(object)  # AppSettings — use object for PySide6 compat

    def __init__(self, store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("配置中心")
        self.setMinimumWidth(680)
        self.setMinimumHeight(500)
        self._store = store
        self._resolver = DeviceResolver()
        self._build_ui()
        self._populate(store.get())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        header_lbl = QLabel("配置中心")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: 900; color: #eef7ff;")
        root.addWidget(header_lbl)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)

        self._tabs.addTab(self._build_volc_tab(), "🌋 火山引擎")
        self._tabs.addTab(self._build_openai_tab(), "✨ OpenAI")
        self._tabs.addTab(self._build_audio_tab(), "🎧 音频设备")
        self._tabs.addTab(self._build_overlay_tab(), "💬 字幕外观")
        self._tabs.addTab(self._build_usage_tab(), "📊 用量统计")

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _tab_widget(self) -> QWidget:
        w = QWidget()
        return w

    def _build_volc_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        key_row = QHBoxLayout()
        self._volc_api_key = _password_line()
        self._volc_api_key.setPlaceholderText("您的火山引擎 App Key")
        key_row.addWidget(self._volc_api_key, 1)
        get_key_btn = QPushButton("获取 Key")
        get_key_btn.setObjectName("secondary")
        get_key_btn.setToolTip("打开火山引擎控制台申请 App Key")
        get_key_btn.clicked.connect(self._open_volc_key_page)
        key_row.addWidget(get_key_btn)
        form.addRow("App Key", key_row)

        self._volc_resource_id = QLineEdit()
        self._volc_resource_id.setPlaceholderText("volc.service_type.10053")
        form.addRow("Resource ID", self._volc_resource_id)

        self._volc_ws_url = QLineEdit()
        self._volc_ws_url.setPlaceholderText("wss://openspeech.bytedance.com/api/v4/ast/v2/translate")
        form.addRow("WS URL", self._volc_ws_url)

        form.addRow(_section_title("游戏字幕语言（S2T 模式）"))

        from gui.game_panel import HUOSHAN_FOREIGN_LANGUAGES, HUOSHAN_DIALECTS

        self._game_src_lang = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._game_src_lang.addItem(name, code)
        for name, code in HUOSHAN_DIALECTS:
            self._game_src_lang.addItem(name, code)
        form.addRow("游戏语言（源）", self._game_src_lang)

        self._game_tgt_lang = QComboBox()
        for name, code in HUOSHAN_FOREIGN_LANGUAGES:
            self._game_tgt_lang.addItem(name, code)
        form.addRow("字幕语言（目标）", self._game_tgt_lang)

        note = QLabel("提示：源语言或目标语言中，至少有一个须为中文或英语。方言仅可作为源语言。")
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _build_openai_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._openai_api_key = _password_line()
        self._openai_api_key.setPlaceholderText("sk-...")
        form.addRow("API Key", self._openai_api_key)

        self._openai_ws_url = QLineEdit()
        self._openai_ws_url.setPlaceholderText("wss://translate.doerr.work/v1/realtime/translations")
        form.addRow("WS URL (Proxy)", self._openai_ws_url)

        note = QLabel("使用代理服务器时填写 WS URL，留空使用默认官方节点。")
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _build_audio_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._mic_combo = QComboBox()
        self._mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._populate_mic_combo()
        form.addRow("麦克风设备", self._mic_combo)

        self._vb_cable_input_name = QLineEdit()
        form.addRow("Cable Input 名称", self._vb_cable_input_name)

        self._vb_cable_output_name = QLineEdit()
        form.addRow("Cable Output 名称", self._vb_cable_output_name)

        self._game_audio_device = QLineEdit()
        self._game_audio_device.setPlaceholderText("留空自动选择系统默认扬声器")
        form.addRow("游戏音频设备名称", self._game_audio_device)

        refresh_btn = QPushButton("刷新设备列表")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._populate_mic_combo)
        form.addRow("", refresh_btn)

        return w

    def _build_overlay_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._overlay_max_lines = QSpinBox()
        self._overlay_max_lines.setRange(1, 8)
        self._overlay_max_lines.setValue(2)
        self._overlay_max_lines.setSuffix(" 行")
        form.addRow("字幕保留行数", self._overlay_max_lines)

        self._overlay_font_size = QSpinBox()
        self._overlay_font_size.setRange(12, 72)
        self._overlay_font_size.setValue(32)
        self._overlay_font_size.setSuffix(" px")
        form.addRow("字体大小", self._overlay_font_size)

        opacity_row = QHBoxLayout()
        self._overlay_opacity = QSlider(Qt.Orientation.Horizontal)
        self._overlay_opacity.setRange(10, 100)
        self._overlay_opacity.setValue(85)
        self._opacity_label = QLabel("85%")
        self._overlay_opacity.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(self._overlay_opacity)
        opacity_row.addWidget(self._opacity_label)
        form.addRow("背景不透明度", opacity_row)

        self._overlay_width = QSpinBox()
        self._overlay_width.setRange(300, 1920)
        self._overlay_width.setValue(800)
        self._overlay_width.setSuffix(" px")
        form.addRow("字幕宽度", self._overlay_width)

        color_row = QHBoxLayout()
        self._color_preview = QPushButton()
        self._color_preview.setFixedSize(32, 32)
        self._color_preview.setObjectName("secondary")
        self._color_value = "#ffffff"
        self._color_preview.clicked.connect(self._pick_color)
        self._update_color_preview()
        color_row.addWidget(self._color_preview)
        color_row.addStretch()
        form.addRow("字体颜色", color_row)

        self._click_through = QCheckBox("鼠标穿透（游戏内不阻挡点击）")
        self._click_through.setChecked(True)
        form.addRow("", self._click_through)

        return w

    def _build_usage_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._usage_tracking = QCheckBox("启用用量与费用统计")
        self._usage_tracking.setToolTip(
            "开启后顶栏显示本次会话/累计费用 chip，点击查看明细，可按天/月聚合、导出 CSV。\n"
            "数据保存在本地 usage_data.json。默认关闭。"
        )
        form.addRow("", self._usage_tracking)

        self._usage_chip_show_token = QCheckBox("顶栏 chip 显示 Token 数量（默认显示人民币）")
        form.addRow("", self._usage_chip_show_token)

        note = QLabel(
            "依据火山引擎计费(每百万 token):\n"
            "  · 输入音频 ¥80   · 输出文本 ¥30   · 输出音频 ¥300\n"
            "  · 缓存输入 ¥5    · 输入文本 ¥10"
        )
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _open_volc_key_page(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://console.volcengine.com/speech/new/setting/apikeys?projectName=default"))

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color_value), self, "选择字体颜色")
        if color.isValid():
            self._color_value = color.name()
            self._update_color_preview()

    def _update_color_preview(self) -> None:
        self._color_preview.setStyleSheet(
            f"background-color: {self._color_value}; border: 1px solid rgba(163,207,255,0.3); border-radius: 6px;"
        )

    def _populate_mic_combo(self) -> None:
        self._resolver.refresh()
        current = self._mic_combo.currentData()
        self._mic_combo.clear()
        self._mic_combo.addItem("（自动选择）", None)
        for device in self._resolver.input_devices():
            if "cable output" in device.name.lower():
                continue
            label = f"#{device.index} | {device.name}"
            self._mic_combo.addItem(label, device.index)
        if current is not None:
            for i in range(self._mic_combo.count()):
                if self._mic_combo.itemData(i) == current:
                    self._mic_combo.setCurrentIndex(i)
                    break

    def _populate(self, s: AppSettings) -> None:
        self._volc_api_key.setText(s.volc_api_key)
        self._volc_resource_id.setText(s.volc_resource_id)
        self._volc_ws_url.setText(s.volc_ws_url)

        def _set_combo(combo: QComboBox, code: str) -> None:
            idx = combo.findData(code)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        _set_combo(self._game_src_lang, s.game_subtitle_source_language)
        _set_combo(self._game_tgt_lang, s.game_subtitle_target_language)

        self._openai_api_key.setText(s.openai_api_key)
        self._openai_ws_url.setText(s.openai_ws_url)

        if s.mic_input_index is not None:
            for i in range(self._mic_combo.count()):
                if self._mic_combo.itemData(i) == s.mic_input_index:
                    self._mic_combo.setCurrentIndex(i)
                    break

        self._vb_cable_input_name.setText(s.vb_cable_input_name)
        self._vb_cable_output_name.setText(s.vb_cable_output_name)
        self._game_audio_device.setText(s.game_audio_device_name)

        self._overlay_max_lines.setValue(s.overlay_max_lines)
        self._overlay_font_size.setValue(s.overlay_font_size)
        self._overlay_opacity.setValue(int(s.overlay_opacity * 100))
        self._overlay_width.setValue(s.overlay_width)
        self._color_value = s.overlay_text_color
        self._update_color_preview()
        self._click_through.setChecked(s.overlay_click_through)
        self._usage_tracking.setChecked(s.usage_tracking_enabled)
        self._usage_chip_show_token.setChecked(s.usage_chip_show_token)

    def _collect(self) -> AppSettings:
        s = self._store.get()
        from dataclasses import replace
        return replace(
            s,
            volc_api_key=self._volc_api_key.text().strip(),
            volc_resource_id=self._volc_resource_id.text().strip() or s.volc_resource_id,
            volc_ws_url=self._volc_ws_url.text().strip() or s.volc_ws_url,
            game_subtitle_source_language=self._game_src_lang.currentData() or s.game_subtitle_source_language,
            game_subtitle_target_language=self._game_tgt_lang.currentData() or s.game_subtitle_target_language,
            openai_api_key=self._openai_api_key.text().strip(),
            openai_ws_url=self._openai_ws_url.text().strip() or s.openai_ws_url,
            mic_input_index=self._mic_combo.currentData(),
            vb_cable_input_name=self._vb_cable_input_name.text().strip() or s.vb_cable_input_name,
            vb_cable_output_name=self._vb_cable_output_name.text().strip() or s.vb_cable_output_name,
            game_audio_device_name=self._game_audio_device.text().strip(),
            overlay_max_lines=self._overlay_max_lines.value(),
            overlay_font_size=self._overlay_font_size.value(),
            overlay_opacity=self._overlay_opacity.value() / 100.0,
            overlay_width=self._overlay_width.value(),
            overlay_text_color=self._color_value,
            overlay_click_through=self._click_through.isChecked(),
            usage_tracking_enabled=self._usage_tracking.isChecked(),
            usage_chip_show_token=self._usage_chip_show_token.isChecked(),
        )

    @Slot()
    def _on_save(self) -> None:
        settings = self._collect()
        if not settings.volc_api_key and settings.translator_engine == "huoshan":
            reply = QMessageBox.question(
                self,
                "火山引擎 Key 未填写",
                "火山引擎 App Key 为空，使用火山翻译时将无法启动。\n确认保存吗？",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Save:
                return
        self._store.save(settings)
        self.settings_saved.emit(settings)
        QMessageBox.information(self, "已保存", "设置已保存 ✓")
        self.accept()
