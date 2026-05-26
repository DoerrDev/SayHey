from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

TYPED_LANGUAGES = [
    ("中文", "zh"),
    ("English", "en"),
    ("日本語", "ja"),
    ("한국어", "ko"),
    ("Español", "es"),
    ("Français", "fr"),
    ("Deutsch", "de"),
    ("Português", "pt"),
    ("Русский", "ru"),
]
TYPED_LANGUAGES_QWEN = [
    ("中文", "zh"),
    ("粤语 · 粵語", "yue"),
    ("英语 · English", "en"),
    ("日语 · 日本語", "ja"),
    ("韩语 · 한국어", "ko"),
    ("法语 · Français", "fr"),
    ("德语 · Deutsch", "de"),
    ("西班牙语 · Español", "es"),
    ("葡萄牙语 · Português", "pt"),
    ("意大利语 · Italiano", "it"),
    ("俄语 · Русский", "ru"),
    ("荷兰语 · Nederlands", "nl"),
    ("波兰语 · Polski", "pl"),
    ("土耳其语 · Türkçe", "tr"),
    ("阿拉伯语 · العربية", "ar"),
    ("希伯来语 · עברית", "he"),
    ("波斯语 · فارسی", "fa"),
    ("乌尔都语 · اردو", "ur"),
    ("印地语 · हिन्दी", "hi"),
    ("孟加拉语 · বাংলা", "bn"),
    ("泰米尔语 · தமிழ்", "ta"),
    ("泰卢固语 · తెలుగు", "te"),
    ("马拉地语 · मराठी", "mr"),
    ("古吉拉特语 · ગુજરાતી", "gu"),
    ("卡纳达语 · ಕನ್ನಡ", "kn"),
    ("马拉雅拉姆语 · മലയാളം", "ml"),
    ("旁遮普语 · ਪੰਜਾਬੀ", "pa"),
    ("泰语 · ไทย", "th"),
    ("越南语 · Tiếng Việt", "vi"),
    ("印尼语 · Bahasa Indonesia", "id"),
    ("马来语 · Bahasa Melayu", "ms"),
    ("菲律宾语 · Filipino", "tl"),
    ("高棉语 · ខ្មែរ", "km"),
    ("老挝语 · ລາວ", "lo"),
    ("缅甸语 · မြန်မာ", "my"),
    ("希腊语 · Ελληνικά", "el"),
    ("匈牙利语 · Magyar", "hu"),
    ("捷克语 · Čeština", "cs"),
    ("斯洛伐克语 · Slovenčina", "sk"),
    ("斯洛文尼亚语 · Slovenščina", "sl"),
    ("罗马尼亚语 · Română", "ro"),
    ("保加利亚语 · Български", "bg"),
    ("乌克兰语 · Українська", "uk"),
    ("克罗地亚语 · Hrvatski", "hr"),
    ("塞尔维亚语 · Srpski", "sr"),
    ("瑞典语 · Svenska", "sv"),
    ("挪威语 · Norsk", "no"),
    ("丹麦语 · Dansk", "da"),
    ("芬兰语 · Suomi", "fi"),
    ("冰岛语 · Íslenska", "is"),
    ("爱沙尼亚语 · Eesti", "et"),
    ("拉脱维亚语 · Latviešu", "lv"),
    ("立陶宛语 · Lietuvių", "lt"),
    ("加泰罗尼亚语 · Català", "ca"),
    ("加利西亚语 · Galego", "gl"),
    ("巴斯克语 · Euskara", "eu"),
    ("威尔士语 · Cymraeg", "cy"),
    ("爱尔兰语 · Gaeilge", "ga"),
    ("马耳他语 · Malti", "mt"),
    ("阿尔巴尼亚语 · Shqip", "sq"),
    ("马其顿语 · Македонски", "mk"),
    ("波斯尼亚语 · Bosanski", "bs"),
    ("亚美尼亚语 · Հայերեն", "hy"),
    ("格鲁吉亚语 · ქართული", "ka"),
    ("阿塞拜疆语 · Azərbaycan", "az"),
    ("哈萨克语 · Қазақ", "kk"),
    ("吉尔吉斯语 · Кыргыз", "ky"),
    ("乌兹别克语 · Oʻzbek", "uz"),
    ("蒙古语 · Монгол", "mn"),
    ("尼泊尔语 · नेपाली", "ne"),
    ("僧伽罗语 · සිංහල", "si"),
    ("斯瓦希里语 · Swahili", "sw"),
    ("南非荷兰语 · Afrikaans", "af"),
    ("祖鲁语 · isiZulu", "zu"),
    ("阿姆哈拉语 · አማርኛ", "am"),
    ("普什图语 · Pashto", "ps"),
    ("库尔德语 · Kurdî", "ku"),
    ("世界语 · Esperanto", "eo"),
    ("拉丁语 · Latina", "la"),
]
TYPED_SOURCE_LANGUAGES = [("自动检测", "auto")] + TYPED_LANGUAGES


class _EnterTextEdit(QPlainTextEdit):
    sig_submit = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.sig_submit.emit()
            return
        super().keyPressEvent(event)


class TypedTranslatePanel(QFrame):
    sig_translate_requested = Signal(str)
    sig_settings_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tabContent")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        route = QLabel("文本输入 → 火山翻译 → 可选 TTS → CABLE Input")
        route.setObjectName("routeLabel")
        layout.addWidget(route)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._src = QComboBox()
        for name, code in TYPED_SOURCE_LANGUAGES:
            self._src.addItem(f"{name} ({code})", code)
        self._src.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._src, 1)
        arrow = QLabel("→")
        arrow.setObjectName("routeLabel")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(20)
        lang_row.addWidget(arrow)
        self._tgt = QComboBox()
        for name, code in TYPED_LANGUAGES:
            self._tgt.addItem(f"{name} ({code})", code)
        self._tgt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lang_row.addWidget(self._tgt, 1)
        layout.addLayout(lang_row)

        self._auto_tts = QCheckBox("自动合成语音并发送到虚拟声卡")
        self._auto_tts.setChecked(True)
        layout.addWidget(self._auto_tts)

        self._input = _EnterTextEdit()
        self._input.setPlaceholderText("输入要发送给队友的句子。按 Enter 翻译，Shift + Enter 换行。")
        self._input.setMinimumHeight(96)
        self._input.sig_submit.connect(self._on_submit)
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._send_btn = QPushButton("翻译并发送")
        self._send_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._send_btn)
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._input.clear)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Result boxes
        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        self._source_lbl = QLabel("")
        self._source_lbl.setObjectName("resultBox")
        self._source_lbl.setWordWrap(True)
        self._source_lbl.setMinimumHeight(54)
        self._source_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._target_lbl = QLabel("")
        self._target_lbl.setObjectName("resultBox")
        self._target_lbl.setWordWrap(True)
        self._target_lbl.setMinimumHeight(54)
        self._target_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        result_row.addWidget(self._wrap_result("原文", self._source_lbl), 1)
        result_row.addWidget(self._wrap_result("译文", self._target_lbl), 1)
        layout.addLayout(result_row)

        self._src.currentIndexChanged.connect(lambda *_: self.sig_settings_changed.emit())
        self._tgt.currentIndexChanged.connect(lambda *_: self.sig_settings_changed.emit())
        self._auto_tts.toggled.connect(lambda *_: self.sig_settings_changed.emit())

    def _wrap_result(self, title: str, body: QLabel) -> QFrame:
        wrap = QFrame()
        wrap.setObjectName("resultWrap")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(4)
        cap = QLabel(title)
        cap.setObjectName("routeLabel")
        v.addWidget(cap)
        v.addWidget(body, 1)
        return wrap

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.sig_translate_requested.emit(text)

    # ── public API ──
    def selected_source(self) -> str:
        return self._src.currentData() or "zh"

    def selected_target(self) -> str:
        return self._tgt.currentData() or "en"

    def auto_tts(self) -> bool:
        return self._auto_tts.isChecked()

    def set_source(self, code: str) -> None:
        i = self._src.findData(code)
        if i >= 0:
            self._src.setCurrentIndex(i)

    def set_target(self, code: str) -> None:
        i = self._tgt.findData(code)
        if i >= 0:
            self._tgt.setCurrentIndex(i)

    def set_auto_tts(self, on: bool) -> None:
        self._auto_tts.setChecked(on)

    def set_engine(self, engine: str) -> None:
        cur_src = self._src.currentData()
        cur_tgt = self._tgt.currentData()
        langs = TYPED_LANGUAGES_QWEN if engine == "qwen" else TYPED_LANGUAGES
        src_langs = [("自动检测", "auto")] + langs
        self._src.blockSignals(True)
        self._tgt.blockSignals(True)
        self._src.clear()
        for name, code in src_langs:
            self._src.addItem(f"{name} ({code})", code)
        self._tgt.clear()
        for name, code in langs:
            self._tgt.addItem(f"{name} ({code})", code)
        si = self._src.findData(cur_src)
        self._src.setCurrentIndex(si if si >= 0 else 0)
        ti = self._tgt.findData(cur_tgt)
        self._tgt.setCurrentIndex(ti if ti >= 0 else 0)
        self._src.blockSignals(False)
        self._tgt.blockSignals(False)

    def show_result(self, source: str, translated: str) -> None:
        self._source_lbl.setText(source)
        self._target_lbl.setText(translated)
        self._input.clear()

    def set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._send_btn.setText("翻译中..." if busy else "翻译并发送")
