from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.settings_store import AppSettings, SettingsStore
from gui.icons import resource_icon


def _password_line() -> QLineEdit:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    return edit


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


class SettingsDialog(QDialog):
    settings_saved = Signal(object)

    def __init__(self, store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("配置中心")
        self.setMinimumWidth(760)
        self.setMinimumHeight(560)
        self._store = store
        self._build_ui()
        self._populate(store.get())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        header = QLabel("配置中心")
        header.setStyleSheet("font-size: 19px; font-weight: 900; color: #eef7ff;")
        root.addWidget(header)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)

        self._tabs.addTab(self._build_volc_tab(), "火山引擎")
        self._tabs.addTab(self._build_openai_tab(), "OpenAI")
        self._tabs.addTab(self._build_volc_trial_tab(), "试用代理")
        self._tabs.addTab(self._build_overlay_tab(), "字幕外观")
        self._tabs.addTab(self._build_usage_tab(), "用量统计")
        self._tabs.setTabIcon(0, resource_icon("flame"))
        self._tabs.setTabIcon(1, resource_icon("sparkles"))
        self._tabs.setTabIcon(2, resource_icon("gift"))
        self._tabs.setTabIcon(3, resource_icon("subtitle"))
        self._tabs.setTabIcon(4, resource_icon("usage"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _tab_widget(self) -> QWidget:
        return QWidget()

    def _build_volc_tab(self) -> QWidget:
        widget = self._tab_widget()
        form = QFormLayout(widget)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        key_row = QHBoxLayout()
        self._volc_api_key = _password_line()
        self._volc_api_key.setPlaceholderText("你的火山引擎 App Key")
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

        from gui.game_panel import HUOSHAN_DIALECTS, HUOSHAN_FOREIGN_LANGUAGES

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

        note = QLabel("提示：源语言和目标语言中，至少要有一个是中文或英语。方言仅支持作为源语言。")
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)
        return widget

    def _build_openai_tab(self) -> QWidget:
        widget = self._tab_widget()
        form = QFormLayout(widget)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._openai_api_key = _password_line()
        self._openai_api_key.setPlaceholderText("sk-...")
        form.addRow("API Key", self._openai_api_key)

        self._openai_ws_url = QLineEdit()
        self._openai_ws_url.setPlaceholderText("wss://translate.doerr.work/v1/realtime/translations")
        form.addRow("WS URL（代理）", self._openai_ws_url)

        note = QLabel("使用代理服务时填写 WS URL，留空则使用默认地址。")
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)
        return widget

    def _build_volc_trial_tab(self) -> QWidget:
        widget = self._tab_widget()
        form = QFormLayout(widget)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        intro = QLabel(
            "试用代理由作者提供公益额度，适合先体验整体效果。"
            "\n如果体验稳定，建议尽快切换为你自己的火山引擎 App Key。"
        )
        intro.setObjectName("routeLabel")
        intro.setWordWrap(True)
        form.addRow("", intro)

        self._volc_trial_enabled = QCheckBox("使用试用代理（会覆盖火山引擎的 Key 与 WS URL）")
        form.addRow("", self._volc_trial_enabled)

        self._volc_trial_api_base = QLineEdit()
        self._volc_trial_api_base.setPlaceholderText("https://huoshanproxy.doerr.work")
        form.addRow("服务地址", self._volc_trial_api_base)

        self._volc_trial_proxy_ws_url = QLineEdit()
        self._volc_trial_proxy_ws_url.setPlaceholderText("wss://huoshanproxy.doerr.work/api/v4/ast/v2/translate")
        form.addRow("代理 WS URL", self._volc_trial_proxy_ws_url)

        self._volc_trial_token = QLineEdit()
        self._volc_trial_token.setReadOnly(True)
        self._volc_trial_token.setPlaceholderText("尚未申请")
        form.addRow("当前 Token", self._volc_trial_token)

        self._volc_trial_balance = QLabel("余额：未知")
        self._volc_trial_balance.setStyleSheet("color:#4f8cff;font-weight:600;")
        form.addRow("额度", self._volc_trial_balance)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("立即申请")
        apply_btn.setObjectName("secondary")
        apply_btn.clicked.connect(self._apply_trial_token)
        btn_row.addWidget(apply_btn)
        refresh_btn = QPushButton("刷新余额")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._refresh_trial_balance)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        form.addRow("", btn_row)
        return widget

    def _build_overlay_tab(self) -> QWidget:
        widget = self._tab_widget()
        outer = QHBoxLayout(widget)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(18)

        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._overlay_max_lines = QSpinBox()
        self._overlay_max_lines.setRange(1, 8)
        self._overlay_max_lines.setSuffix(" 行")
        form.addRow("字幕保留行数", self._overlay_max_lines)

        self._overlay_font_size = QSpinBox()
        self._overlay_font_size.setRange(12, 72)
        self._overlay_font_size.setSuffix(" px")
        form.addRow("字体大小", self._overlay_font_size)

        opacity_row = QHBoxLayout()
        self._overlay_opacity = QSlider(Qt.Orientation.Horizontal)
        self._overlay_opacity.setRange(10, 100)
        self._opacity_label = QLabel("85%")
        self._overlay_opacity.valueChanged.connect(lambda value: self._opacity_label.setText(f"{value}%"))
        opacity_row.addWidget(self._overlay_opacity)
        opacity_row.addWidget(self._opacity_label)
        form.addRow("背景不透明度", opacity_row)

        self._overlay_width = QSpinBox()
        self._overlay_width.setRange(300, 1920)
        self._overlay_width.setSuffix(" px")
        form.addRow("字幕宽度", self._overlay_width)

        color_row = QHBoxLayout()
        self._color_preview = QPushButton()
        self._color_preview.setFixedSize(32, 32)
        self._color_preview.setObjectName("secondary")
        self._color_value = "#ffffff"
        self._color_preview.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_preview)
        color_row.addStretch()
        form.addRow("字体颜色", color_row)

        self._click_through = QCheckBox("鼠标穿透（游戏内点击不会被字幕遮挡）")
        self._click_through.setChecked(True)
        form.addRow("", self._click_through)
        outer.addWidget(form_container, 1)

        preview = QFrame()
        preview.setObjectName("previewBox")
        preview.setMinimumWidth(280)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(16, 16, 16, 16)
        pv.setSpacing(10)

        plabel = QLabel("实时预览")
        plabel.setObjectName("previewLabel")
        pv.addWidget(plabel)
        self._preview_meta = QLabel()
        self._preview_meta.setObjectName("panelDesc")
        self._preview_meta.setWordWrap(True)
        pv.addWidget(self._preview_meta)
        pv.addStretch()
        self._overlay_sample = QLabel("我们准备好了。现在开始行动。")
        self._overlay_sample.setObjectName("overlaySample")
        self._overlay_sample.setWordWrap(True)
        self._overlay_sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv.addWidget(self._overlay_sample)
        outer.addWidget(preview)

        self._overlay_font_size.valueChanged.connect(self._refresh_overlay_preview)
        self._overlay_opacity.valueChanged.connect(self._refresh_overlay_preview)
        self._overlay_width.valueChanged.connect(self._refresh_overlay_preview)
        self._overlay_max_lines.valueChanged.connect(self._refresh_overlay_preview)
        self._click_through.toggled.connect(self._refresh_overlay_preview)
        self._refresh_overlay_preview()
        return widget

    def _refresh_overlay_preview(self) -> None:
        if not hasattr(self, "_overlay_sample"):
            return
        size = self._overlay_font_size.value()
        opacity = self._overlay_opacity.value() / 100.0
        bg_alpha = max(0.1, min(1.0, opacity))
        self._overlay_sample.setStyleSheet(
            f"background: rgba(0,0,0,{bg_alpha});"
            f"border:1px solid rgba(255,255,255,0.10); border-radius:12px;"
            f"color:{self._color_value}; font-size:{size}px; font-weight:900; padding:12px 14px;"
        )
        width = self._overlay_width.value()
        self._overlay_sample.setMaximumWidth(min(max(width // 2, 200), 520))
        click_state = "已开启鼠标穿透" if self._click_through.isChecked() else "可接收鼠标点击"
        self._preview_meta.setText(
            f"{self._overlay_max_lines.value()} 行保留 · 宽度 {width}px · 背景 {int(opacity * 100)}% · {click_state}"
        )

    def _build_usage_tab(self) -> QWidget:
        widget = self._tab_widget()
        form = QFormLayout(widget)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._usage_tracking = QCheckBox("启用用量与费用统计")
        self._usage_tracking.setToolTip("开启后，顶部会显示本次会话与累计用量，可在详情页中查看和导出。")
        form.addRow("", self._usage_tracking)

        self._usage_chip_show_token = QCheckBox("顶部信息显示 Token 数量（关闭后显示人民币）")
        form.addRow("", self._usage_chip_show_token)

        note = QLabel(
            "参考火山引擎计费口径（每百万 token）：\n"
            "输入音频 ￥80，输出文本 ￥30，输出音频 ￥300，缓存输入 ￥5，输入文本 ￥10。"
        )
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)
        return widget

    def _apply_trial_token(self) -> None:
        import json
        import time
        import urllib.request

        from core.machine_id import get_machine_id_hash

        reply = QMessageBox.question(
            self,
            "申请试用 Token",
            "试用 Token 使用的是公益额度，配额有限。\n"
            "如果体验不错，建议尽快切换到你自己的火山引擎 App Key。\n\n"
            "是否继续申请？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        api_base = self._volc_trial_api_base.text().strip() or "https://huoshanproxy.doerr.work"
        body = json.dumps(
            {"machine_id_hash": get_machine_id_hash(), "ts": int(time.time())}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{api_base.rstrip('/')}/api/apply",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            QMessageBox.warning(self, "申请失败", f"无法连接试用服务：{exc}")
            return

        token = data.get("token", "")
        proxy_url = data.get("proxy_ws_url", "") or self._volc_trial_proxy_ws_url.text().strip()
        quota = float(data.get("quota_cny", 0))
        used = float(data.get("used_cny", 0))
        self._volc_trial_token.setText(token)
        if proxy_url:
            self._volc_trial_proxy_ws_url.setText(proxy_url)
        self._volc_trial_enabled.setChecked(True)
        self._volc_trial_balance.setText(f"剩余 ￥{max(quota - used, 0):.4f} / 共 ￥{quota:.2f}")
        QMessageBox.information(self, "申请成功", "Token 已写入，记得点击“保存”后生效。")

    def _refresh_trial_balance(self) -> None:
        import json
        import urllib.request

        token = self._volc_trial_token.text().strip()
        api_base = self._volc_trial_api_base.text().strip() or "https://huoshanproxy.doerr.work"
        if not token:
            self._volc_trial_balance.setText("余额：未申请")
            return

        request = urllib.request.Request(
            f"{api_base.rstrip('/')}/api/token/info",
            headers={"X-Api-Key": token},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self._volc_trial_balance.setText(f"查询失败：{exc}")
            return

        quota = float(data.get("quota_cny", 0))
        used = float(data.get("used_cny", 0))
        if bool(data.get("is_disabled", False)):
            self._volc_trial_balance.setText("Token 已被禁用")
        else:
            self._volc_trial_balance.setText(f"剩余 ￥{max(quota - used, 0):.4f} / 共 ￥{quota:.2f}")

    def _open_volc_key_page(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(
            QUrl("https://console.volcengine.com/speech/new/setting/apikeys?projectName=default")
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color_value), self, "选择字幕颜色")
        if color.isValid():
            self._color_value = color.name()
            self._update_color_preview()

    def _update_color_preview(self) -> None:
        self._color_preview.setStyleSheet(
            f"background-color: {self._color_value}; border: 1px solid rgba(163,207,255,0.3); border-radius: 6px;"
        )
        if hasattr(self, "_overlay_sample"):
            self._refresh_overlay_preview()

    def _populate(self, settings: AppSettings) -> None:
        self._volc_api_key.setText(settings.volc_api_key)
        self._volc_resource_id.setText(settings.volc_resource_id)
        self._volc_ws_url.setText(settings.volc_ws_url)

        def set_combo(combo: QComboBox, code: str) -> None:
            idx = combo.findData(code)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        set_combo(self._game_src_lang, settings.game_subtitle_source_language)
        set_combo(self._game_tgt_lang, settings.game_subtitle_target_language)

        self._openai_api_key.setText(settings.openai_api_key)
        self._openai_ws_url.setText(settings.openai_ws_url)

        self._overlay_max_lines.setValue(settings.overlay_max_lines)
        self._overlay_font_size.setValue(settings.overlay_font_size)
        self._overlay_opacity.setValue(int(settings.overlay_opacity * 100))
        self._overlay_width.setValue(settings.overlay_width)
        self._color_value = settings.overlay_text_color
        self._update_color_preview()
        self._click_through.setChecked(settings.overlay_click_through)

        self._usage_tracking.setChecked(settings.usage_tracking_enabled)
        self._usage_chip_show_token.setChecked(settings.usage_chip_show_token)

        self._volc_trial_enabled.setChecked(settings.volc_trial_enabled)
        self._volc_trial_token.setText(settings.volc_trial_token)
        self._volc_trial_proxy_ws_url.setText(settings.volc_trial_proxy_ws_url)
        self._volc_trial_api_base.setText(settings.volc_trial_api_base)
        if settings.volc_trial_token:
            self._refresh_trial_balance()
        else:
            self._volc_trial_balance.setText("余额：未申请")

    def _collect(self) -> AppSettings:
        settings = self._store.get()
        from dataclasses import replace

        return replace(
            settings,
            volc_api_key=self._volc_api_key.text().strip(),
            volc_resource_id=self._volc_resource_id.text().strip() or settings.volc_resource_id,
            volc_ws_url=self._volc_ws_url.text().strip() or settings.volc_ws_url,
            game_subtitle_source_language=self._game_src_lang.currentData() or settings.game_subtitle_source_language,
            game_subtitle_target_language=self._game_tgt_lang.currentData() or settings.game_subtitle_target_language,
            openai_api_key=self._openai_api_key.text().strip(),
            openai_ws_url=self._openai_ws_url.text().strip() or settings.openai_ws_url,
            overlay_max_lines=self._overlay_max_lines.value(),
            overlay_font_size=self._overlay_font_size.value(),
            overlay_opacity=self._overlay_opacity.value() / 100.0,
            overlay_width=self._overlay_width.value(),
            overlay_text_color=self._color_value,
            overlay_click_through=self._click_through.isChecked(),
            usage_tracking_enabled=self._usage_tracking.isChecked(),
            usage_chip_show_token=self._usage_chip_show_token.isChecked(),
            volc_trial_enabled=self._volc_trial_enabled.isChecked(),
            volc_trial_token=self._volc_trial_token.text().strip(),
            volc_trial_proxy_ws_url=self._volc_trial_proxy_ws_url.text().strip() or settings.volc_trial_proxy_ws_url,
            volc_trial_api_base=self._volc_trial_api_base.text().strip() or settings.volc_trial_api_base,
        )

    @Slot()
    def _on_save(self) -> None:
        settings = self._collect()
        has_trial = settings.volc_trial_enabled and settings.volc_trial_token
        if not settings.volc_api_key and not has_trial and settings.translator_engine == "huoshan":
            reply = QMessageBox.question(
                self,
                "火山引擎 Key 未填写",
                "火山引擎 App Key 为空，使用火山翻译时将无法启动。\n确认仍然保存吗？",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Save:
                return

        self._store.save(settings)
        self.settings_saved.emit(settings)
        QMessageBox.information(self, "已保存", "设置已保存。")
        self.accept()
