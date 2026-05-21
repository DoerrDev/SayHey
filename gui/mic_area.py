from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout

from gui.mic_panel import MicTranslatePanel
from gui.typed_panel import TypedTranslatePanel


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
        layout.addLayout(head)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("micTabs")
        self.voice = MicTranslatePanel()
        self.typed = TypedTranslatePanel()
        self._tabs.addTab(self.voice, "同声传译")
        self._tabs.addTab(self.typed, "打字翻译")
        layout.addWidget(self._tabs, 1)

    def select_typed(self) -> None:
        self._tabs.setCurrentIndex(1)
