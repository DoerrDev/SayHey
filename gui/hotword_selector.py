from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from core import hotword_store
from gui.hotwords_dialog import HotwordsDialog

_NONE_LABEL = "（无）"


class HotwordSelector(QWidget):
    sig_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel("热词：")
        label.setObjectName("sectionTitle")
        row.addWidget(label)
        self._combo = QComboBox()
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        row.addWidget(self._combo, 1)
        manage = QPushButton("管理")
        manage.setObjectName("ghost")
        manage.clicked.connect(self._open_manage)
        row.addWidget(manage)
        self.refresh()

    def _on_index_changed(self, _i: int) -> None:
        self.sig_changed.emit(self.current_title())

    def refresh(self) -> None:
        prev = self.current_title()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem(_NONE_LABEL, "")
        for title in hotword_store.list_titles():
            self._combo.addItem(title, title)
        idx = self._combo.findData(prev) if prev else 0
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo.blockSignals(False)

    def current_title(self) -> str:
        return self._combo.currentData() or ""

    def set_current(self, title: str) -> None:
        idx = self._combo.findData(title or "")
        if idx < 0:
            idx = 0
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(idx)
        self._combo.blockSignals(False)

    def _open_manage(self) -> None:
        dlg = HotwordsDialog(self)
        dlg.exec()
        self.refresh()
        self.sig_changed.emit(self.current_title())
