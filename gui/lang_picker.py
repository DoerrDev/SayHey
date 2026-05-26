from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from gui.icons import icon as _icon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

REGION_BY_CODE: dict[str, str] = {
    "zh": "东亚", "yue": "东亚", "ja": "东亚", "ko": "东亚",
    "yue-CN": "东亚", "sh-CN": "东亚",
    "id": "东南亚", "ms": "东南亚", "vi": "东南亚", "th": "东南亚",
    "fil": "东南亚", "jv": "东南亚", "ceb": "东南亚", "tl": "东南亚",
    "km": "东南亚", "lo": "东南亚", "my": "东南亚",
    "hi": "南亚", "ur": "南亚", "bn": "南亚", "gu": "南亚",
    "kn": "南亚", "ml": "南亚", "mr": "南亚", "pa": "南亚",
    "ta": "南亚", "te": "南亚", "ne": "南亚", "si": "南亚",
    "ar": "中东", "he": "中东", "fa": "中东", "tr": "中东",
    "ps": "中东", "ku": "中东", "hy": "中东", "ka": "中东",
    "kk": "中亚", "ky": "中亚", "tg": "中亚", "az": "中亚",
    "uz": "中亚", "mn": "中亚",
    "en": "欧洲", "fr": "欧洲", "de": "欧洲", "es": "欧洲",
    "pt": "欧洲", "it": "欧洲", "nl": "欧洲", "ca": "欧洲",
    "gl": "欧洲", "ast": "欧洲", "eu": "欧洲", "ru": "欧洲",
    "pl": "欧洲", "cs": "欧洲", "sk": "欧洲", "hu": "欧洲",
    "ro": "欧洲", "bg": "欧洲", "uk": "欧洲", "hr": "欧洲",
    "bs": "欧洲", "sl": "欧洲", "mk": "欧洲", "et": "欧洲",
    "lv": "欧洲", "lt": "欧洲", "be": "欧洲", "nb": "欧洲",
    "no": "欧洲", "sv": "欧洲", "da": "欧洲", "fi": "欧洲",
    "is": "欧洲", "el": "欧洲", "sr": "欧洲", "cy": "欧洲",
    "ga": "欧洲", "mt": "欧洲", "sq": "欧洲",
    "af": "非洲", "sw": "非洲", "zu": "非洲", "am": "非洲",
    "auto": "其他", "la": "其他", "eo": "其他",
}

_REGION_ORDER = ["东亚", "东南亚", "南亚", "中东", "中亚", "欧洲", "非洲", "其他"]

COMMON_CODES = ["zh", "en", "ja", "ko", "fr", "de", "es", "ru", "ar", "pt"]


class LangPicker(QPushButton):
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, Any]] = []
        self._idx: int = -1
        self.setStyleSheet(
            "QPushButton { text-align: left; padding: 6px 12px; }"
        )
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setIcon(_icon("chevron-down", color="#1f2937"))
        self._refresh_label()
        self.clicked.connect(self._open)

    def _refresh_label(self) -> None:
        if 0 <= self._idx < len(self._items):
            self.setText(self._items[self._idx][0])
        else:
            self.setText("请选择…")

    def addItem(self, name: str, data: Any = None) -> None:
        self._items.append((name, data))
        if self._idx < 0:
            self._idx = 0
            self._refresh_label()

    def clear(self) -> None:
        self._items.clear()
        self._idx = -1
        self._refresh_label()

    def count(self) -> int:
        return len(self._items)

    def itemText(self, i: int) -> str:
        return self._items[i][0] if 0 <= i < len(self._items) else ""

    def itemData(self, i: int) -> Any:
        return self._items[i][1] if 0 <= i < len(self._items) else None

    def findData(self, data: Any) -> int:
        for i, (_, d) in enumerate(self._items):
            if d == data:
                return i
        return -1

    def findText(self, text: str) -> int:
        for i, (n, _) in enumerate(self._items):
            if n == text:
                return i
        return -1

    def currentIndex(self) -> int:
        return self._idx

    def currentData(self) -> Any:
        return self._items[self._idx][1] if 0 <= self._idx < len(self._items) else None

    def currentText(self) -> str:
        return self._items[self._idx][0] if 0 <= self._idx < len(self._items) else ""

    def setCurrentIndex(self, i: int) -> None:
        if not (0 <= i < len(self._items)) or i == self._idx:
            if 0 <= i < len(self._items):
                self._idx = i
                self._refresh_label()
            return
        self._idx = i
        self._refresh_label()
        if not self.signalsBlocked():
            self.currentIndexChanged.emit(i)

    def _open(self) -> None:
        if not self._items:
            return
        dlg = LangPickerDialog(self._items, self._idx, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            idx = dlg.selected_index()
            if idx >= 0 and idx != self._idx:
                self.setCurrentIndex(idx)


class LangPickerDialog(QDialog):
    def __init__(self, items: list[tuple[str, Any]], current_idx: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择语言")
        self.resize(620, 480)
        self._items = items

        root = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 搜索：中文 / English / 代码 zh,en,ja…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._refill)
        root.addWidget(self._search)

        body = QHBoxLayout()
        body.setSpacing(8)
        self._region_list = QListWidget()
        self._region_list.setFixedWidth(110)
        self._region_list.currentItemChanged.connect(lambda *_: self._refill())
        body.addWidget(self._region_list)

        self._lang_list = QListWidget()
        self._lang_list.itemDoubleClicked.connect(lambda *_: self.accept())
        body.addWidget(self._lang_list, 1)
        root.addLayout(body, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._build_regions()
        self._refill()
        self._select_idx(current_idx)
        self._search.setFocus()

    def _build_regions(self) -> None:
        seen: set[str] = set()
        for _, code in self._items:
            seen.add(REGION_BY_CODE.get(str(code), "其他"))
        regions = ["全部", "常用"] + [r for r in _REGION_ORDER if r in seen]
        for r in regions:
            self._region_list.addItem(r)
        self._region_list.setCurrentRow(0)

    def _refill(self) -> None:
        q = self._search.text().strip().lower()
        item = self._region_list.currentItem()
        region = item.text() if item else "全部"
        self._lang_list.clear()
        for i, (name, code) in enumerate(self._items):
            code_s = str(code)
            if region == "常用":
                if code_s not in COMMON_CODES:
                    continue
            elif region != "全部":
                if REGION_BY_CODE.get(code_s, "其他") != region:
                    continue
            if q and q not in name.lower() and q not in code_s.lower():
                continue
            row = QListWidgetItem(name)
            row.setData(Qt.ItemDataRole.UserRole, i)
            self._lang_list.addItem(row)
        if self._lang_list.count() and self._lang_list.currentRow() < 0:
            self._lang_list.setCurrentRow(0)

    def _select_idx(self, target: int) -> None:
        for r in range(self._lang_list.count()):
            if int(self._lang_list.item(r).data(Qt.ItemDataRole.UserRole)) == target:
                self._lang_list.setCurrentRow(r)
                return

    def selected_index(self) -> int:
        it = self._lang_list.currentItem()
        return int(it.data(Qt.ItemDataRole.UserRole)) if it else -1
