from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout

from gui.mic_panel import MicTranslatePanel
from gui.typed_panel import TypedTranslatePanel
from gui.icons import icon as _icon


_VOICE_BTN_TOOLTIP = (
    "选择火山引擎 TTS 音色（同声传译与打字翻译共用）。\n"
    "• 合成 2.0：打字翻译 TTS 推荐，音色池最丰富\n"
    "• S2S/SC-2.0：同声传译推荐，端到端低延迟\n"
    "• 合成 1.0：兼容旧音色，作为降级备选"
)


class MicAreaPanel(QFrame):
    """Container that holds the two mic-area tabs:
    - 同声传译 (existing MicTranslatePanel)
    - 打字翻译 (new TypedTranslatePanel)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("麦克风区域")
        title.setObjectName("panelTitle")
        head.addWidget(title, 1)
        self._voice_btn = QPushButton(_icon("mic-vocal"), " 音色")
        self._voice_btn.setObjectName("ghost")
        self._voice_btn.setFixedWidth(86)
        self._voice_btn.setToolTip(_VOICE_BTN_TOOLTIP)
        head.addWidget(self._voice_btn)
        layout.addLayout(head)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("micTabs")
        self.voice = MicTranslatePanel()
        self.typed = TypedTranslatePanel()
        self._tabs.addTab(self.voice, "同声传译")
        self._tabs.addTab(self.typed, "打字翻译")
        layout.addWidget(self._tabs, 1)

        self._voice_btn.clicked.connect(self.voice.sig_select_voice.emit)
        self.voice.sig_speaker_id_changed.connect(self._on_speaker_id_changed)
        self.voice.sig_running_changed.connect(lambda running: self._voice_btn.setEnabled(not running))

    def _on_speaker_id_changed(self, speaker_id: str) -> None:
        self._voice_btn.setText(" 音色 ✓" if speaker_id else " 音色")

    def select_typed(self) -> None:
        self._tabs.setCurrentIndex(1)
