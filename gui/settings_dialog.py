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
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import Qt

from core.settings_store import AppSettings, SettingsStore
from gui.icons import icon as _icon


VOLC_BILLING_DOC_URL = "https://www.volcengine.com/docs/6561/1359370?lang=zh"
VOLC_BILLING_DOC_TITLE = "火山引擎豆包语音《计费说明》"
VOLC_BILLING_DOC_UPDATED = "2026.05.19"


def _doubao_billing_html() -> str:
    return f"""
    <div style="color:#9fb7ca; font-size:12px; line-height:1.45;">
      <p style="margin:0 0 8px 0;">
        当前应用用到 3 条豆包链路：语音同传 / 字幕走同声传译大模型，打字翻译走机器翻译模型，
        打字后的语音发送走豆包语音合成模型 2.0。所有价格均以官方计费页为准。
      </p>
      <table cellspacing="0" cellpadding="6" style="border-collapse:collapse; width:100%;">
        <tr style="color:#d8ecff;">
          <th align="left">功能</th>
          <th align="left">模型与资源</th>
          <th align="left">主要费率</th>
        </tr>
        <tr>
          <td><b style="color:#eef7ff;">同声传译（S2S）</b><br/>麦克风语音 → 翻译字幕 + 翻译语音</td>
          <td>豆包同声传译大模型<br/><code>volc.service_type.10053</code></td>
          <td>输入 ¥80 / 百万 token<br/>输出文本 ¥80 / 百万 token<br/>输出音频 ¥300 / 百万 token</td>
        </tr>
        <tr>
          <td><b style="color:#eef7ff;">游戏字幕（S2T）</b><br/>电脑声音 → 翻译字幕</td>
          <td>豆包同声传译大模型<br/><code>volc.service_type.10053</code></td>
          <td>输入 ¥80 / 百万 token<br/>输出文本 ¥80 / 百万 token<br/>不生成翻译语音时不产生输出音频项</td>
        </tr>
        <tr>
          <td><b style="color:#eef7ff;">打字翻译</b><br/>文本 → 译文</td>
          <td>豆包机器翻译模型<br/><code>volc.speech.mt</code></td>
          <td>输入 ¥1.8 / 百万 token<br/>输出 ¥5.4 / 百万 token<br/>资源包参考：¥1.62 / 百万 token 起</td>
        </tr>
        <tr>
          <td><b style="color:#eef7ff;">打字语音输出</b><br/>译文 → 语音发送</td>
          <td>豆包语音合成模型 2.0<br/>豆包语音合成模型2.0<br/><code>seed-tts-2.0</code></td>
          <td>后付费 ¥3 / 万字符<br/>资源包参考：¥2.8 / 万字符 起</td>
        </tr>
      </table>
      <p style="margin:8px 0 0 0;">
        <b style="color:#d8ecff;">计费口径：</b>
        同声传译按 token 计费；官方说明中，输入音频约 1 秒折算 6.25 token，输出音频约 1 秒折算 25 token。
        机器翻译按输入 / 输出 token 分项计费；语音合成 2.0 按合成字符数计费。
      </p>
      <p style="margin:8px 0 0 0;">
        <b style="color:#d8ecff;">引用：</b>
        {VOLC_BILLING_DOC_TITLE}，更新时间 {VOLC_BILLING_DOC_UPDATED}：
        <a style="color:#4f8cff;" href="{VOLC_BILLING_DOC_URL}">{VOLC_BILLING_DOC_URL}</a>
      </p>
    </div>
    """


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
        self.resize(900, 600)
        self._store = store
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

        self._tabs.addTab(self._build_volc_tab(), _icon("mountain"), " 火山引擎")
        self._tabs.addTab(self._build_billing_tab(), _icon("wallet"), " AI 模型与费用")
        self._tabs.addTab(self._build_volc_trial_tab(), _icon("gift"), " 火山引擎试用")
        self._tabs.addTab(self._build_overlay_tab(), _icon("captions"), " 字幕外观")
        self._tabs.addTab(self._build_usage_tab(), _icon("bar-chart-3"), " 用量统计")

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

        speech_rate_row = QHBoxLayout()
        self._s2s_speech_rate = QSlider(Qt.Orientation.Horizontal)
        self._s2s_speech_rate.setRange(-50, 100)
        self._s2s_speech_rate.valueChanged.connect(self._update_speech_rate_label)
        self._s2s_speech_rate_label = QLabel("0")
        self._s2s_speech_rate_label.setMinimumWidth(48)
        self._s2s_speech_rate_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        speech_rate_row.addWidget(self._s2s_speech_rate, 1)
        speech_rate_row.addWidget(self._s2s_speech_rate_label)
        form.addRow("同声传译语速", speech_rate_row)

        speech_rate_tip = QLabel("范围：-50 到 100。0 是默认语速，负数更慢，正数更快。")
        speech_rate_tip.setObjectName("routeLabel")
        speech_rate_tip.setWordWrap(True)
        form.addRow("", speech_rate_tip)

        permission_note = QLabel(
            "同一个 Key 需要开通这些资源权限：语音同传 volc.service_type.10053、"
            "机器翻译模型 volc.speech.mt、语音合成 2.0 seed-tts-2.0。"
            "如果打字翻译提示 requested resource not granted，请在控制台给当前 Key 开通对应资源。"
        )
        permission_note.setObjectName("routeLabel")
        permission_note.setWordWrap(True)
        form.addRow("", permission_note)

        return w

    def _build_billing_tab(self) -> QWidget:
        w = self._tab_widget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = _section_title("AI 模型与费率说明")
        layout.addWidget(title)

        doubao_note = QLabel(_doubao_billing_html())
        doubao_note.setObjectName("routeLabel")
        doubao_note.setTextFormat(Qt.TextFormat.RichText)
        doubao_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        doubao_note.setOpenExternalLinks(True)
        doubao_note.setWordWrap(True)
        layout.addWidget(doubao_note)

        layout.addStretch(1)
        return w

    def _build_volc_trial_tab(self) -> QWidget:
        w = self._tab_widget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        intro = QLabel(
            "试用代理由作者自费提供，使用作者购买的火山引擎 App Key。\n"
            "每个用户分配少量额度，超额自动断开。\n"
            "如果体验良好，请前往「🌋 火山引擎」Tab 填写自己的 App Key 以获得无限额度。"
        )
        intro.setObjectName("routeLabel")
        intro.setWordWrap(True)
        form.addRow("", intro)

        self._volc_trial_enabled = QCheckBox("使用试用代理（覆盖火山引擎 Key 与 WS URL）")
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
        apply_btn = QPushButton("🚀 马上使用")
        apply_btn.setObjectName("secondary")
        apply_btn.clicked.connect(self._apply_trial_token)
        btn_row.addWidget(apply_btn)
        refresh_btn = QPushButton("刷新余额")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._refresh_trial_balance)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        form.addRow("", btn_row)

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

        self._show_source = QCheckBox("翻译字幕中同时显示原文")
        self._show_source.setChecked(True)
        form.addRow("", self._show_source)

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
            "  · 输入音频 ¥80   · 输出文本 ¥80   · 输出音频 ¥300\n"
            "  · 缓存输入 ¥5    · 输入文本 ¥10"
        )
        note.setObjectName("routeLabel")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _apply_trial_token(self) -> None:
        import time, json, urllib.request, urllib.error
        from core.machine_id import get_machine_id_hash

        reply = QMessageBox.question(
            self,
            "申请公益试用 Token",
            "该 Token 是作者自费提供的公益额度，配额有限。\n"
            "如果使用效果不错，强烈建议自己去火山引擎申请 App Key\n"
            "（在「🌋 火山引擎」Tab 填写自己的 Key 即可获得无限额度）。\n\n"
            "是否继续申请？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        api_base = self._volc_trial_api_base.text().strip() or "https://huoshanproxy.doerr.work"
        machine_id = get_machine_id_hash()
        body = json.dumps({"machine_id_hash": machine_id, "ts": int(time.time())}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_base.rstrip('/')}/api/apply",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            QMessageBox.warning(self, "申请失败", f"无法连接到试用服务：{exc}")
            return

        token = data.get("token", "")
        proxy_url = data.get("proxy_ws_url", "") or self._volc_trial_proxy_ws_url.text().strip()
        quota = float(data.get("quota_cny", 0))
        used = float(data.get("used_cny", 0))
        self._volc_trial_token.setText(token)
        if proxy_url:
            self._volc_trial_proxy_ws_url.setText(proxy_url)
        self._volc_trial_enabled.setChecked(True)
        self._volc_trial_balance.setText(f"剩余 ¥{max(quota-used,0):.4f} / 共 ¥{quota:.2f}")
        QMessageBox.information(self, "申请成功", "Token 已写入，请记得点击「保存」生效。")

    def _refresh_trial_balance(self) -> None:
        import json, urllib.request
        token = self._volc_trial_token.text().strip()
        api_base = self._volc_trial_api_base.text().strip() or "https://huoshanproxy.doerr.work"
        if not token:
            self._volc_trial_balance.setText("余额：未申请")
            return
        req = urllib.request.Request(
            f"{api_base.rstrip('/')}/api/token/info",
            headers={"X-Api-Key": token},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._volc_trial_balance.setText(f"查询失败：{exc}")
            return
        quota = float(data.get("quota_cny", 0))
        used = float(data.get("used_cny", 0))
        disabled = bool(data.get("is_disabled", False))
        if disabled:
            self._volc_trial_balance.setText("Token 已被禁用")
        else:
            self._volc_trial_balance.setText(f"剩余 ¥{max(quota-used,0):.4f} / 共 ¥{quota:.2f}")

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

    def _populate(self, s: AppSettings) -> None:
        self._volc_api_key.setText(s.volc_api_key)
        self._volc_resource_id.setText(s.volc_resource_id)
        self._volc_ws_url.setText(s.volc_ws_url)
        self._s2s_speech_rate.setValue(s.s2s_speech_rate)

        self._overlay_max_lines.setValue(s.overlay_max_lines)
        self._overlay_font_size.setValue(s.overlay_font_size)
        self._overlay_opacity.setValue(int(s.overlay_opacity * 100))
        self._overlay_width.setValue(s.overlay_width)
        self._color_value = s.overlay_text_color
        self._update_color_preview()
        self._click_through.setChecked(s.overlay_click_through)
        self._show_source.setChecked(s.overlay_show_source)
        self._usage_tracking.setChecked(s.usage_tracking_enabled)
        self._usage_chip_show_token.setChecked(s.usage_chip_show_token)

        self._volc_trial_enabled.setChecked(s.volc_trial_enabled)
        self._volc_trial_token.setText(s.volc_trial_token)
        self._volc_trial_proxy_ws_url.setText(s.volc_trial_proxy_ws_url)
        self._volc_trial_api_base.setText(s.volc_trial_api_base)

        if s.volc_trial_token:
            self._refresh_trial_balance()
        else:
            self._volc_trial_balance.setText("余额：未申请")

    def _collect(self) -> AppSettings:
        s = self._store.get()
        from dataclasses import replace
        return replace(
            s,
            volc_api_key=self._volc_api_key.text().strip(),
            volc_resource_id=self._volc_resource_id.text().strip() or s.volc_resource_id,
            volc_ws_url=self._volc_ws_url.text().strip() or s.volc_ws_url,
            s2s_speech_rate=self._s2s_speech_rate.value(),
            overlay_max_lines=self._overlay_max_lines.value(),
            overlay_font_size=self._overlay_font_size.value(),
            overlay_opacity=self._overlay_opacity.value() / 100.0,
            overlay_width=self._overlay_width.value(),
            overlay_text_color=self._color_value,
            overlay_click_through=self._click_through.isChecked(),
            overlay_show_source=self._show_source.isChecked(),
            usage_tracking_enabled=self._usage_tracking.isChecked(),
            usage_chip_show_token=self._usage_chip_show_token.isChecked(),
            volc_trial_enabled=self._volc_trial_enabled.isChecked(),
            volc_trial_token=self._volc_trial_token.text().strip(),
            volc_trial_proxy_ws_url=self._volc_trial_proxy_ws_url.text().strip() or s.volc_trial_proxy_ws_url,
            volc_trial_api_base=self._volc_trial_api_base.text().strip() or s.volc_trial_api_base,
        )

    @Slot()
    def _on_save(self) -> None:
        settings = self._collect()
        has_trial = settings.volc_trial_enabled and settings.volc_trial_token
        if not settings.volc_api_key and not has_trial and settings.translator_engine == "huoshan":
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

    def _update_speech_rate_label(self, value: int) -> None:
        if value > 0:
            self._s2s_speech_rate_label.setText(f"+{value}")
        else:
            self._s2s_speech_rate_label.setText(str(value))
