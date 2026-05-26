from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import hotword_store
from core.hotword_store import HOTWORDS_DIR, HotwordSet, MAX_ENTRIES


class HotwordsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("热词管理")
        self.resize(720, 480)
        self._current_title: str = ""
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        hint = QHBoxLayout()
        hint.setSpacing(8)
        hotword_store.ensure_dir()
        lbl = QLabel(f"热词文件保存在：{HOTWORDS_DIR}")
        lbl.setObjectName("routeLabel")
        hint.addWidget(lbl)
        open_btn = QPushButton("打开文件夹")
        open_btn.setObjectName("ghost")
        open_btn.clicked.connect(self._open_folder)
        hint.addWidget(open_btn)
        hint.addStretch(1)
        root.addLayout(hint)

        body = QHBoxLayout()
        body.setSpacing(10)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        left.addWidget(self._list, 1)
        btns = QHBoxLayout()
        btns.setSpacing(6)
        for text, slot in (("新建", self._on_new), ("删除", self._on_delete), ("刷新", self._refresh_list)):
            b = QPushButton(text)
            b.setObjectName("ghost")
            b.setMinimumWidth(0)
            b.setStyleSheet("padding: 6px 8px; min-width: 0;")
            b.clicked.connect(slot)
            btns.addWidget(b, 1)
        left.addLayout(btns)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(220)
        body.addWidget(left_w)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._title_lbl = QLabel("（未选择）")
        self._title_lbl.setObjectName("sectionTitle")
        right.addWidget(self._title_lbl)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["key（源词）", "value（译文）"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right.addWidget(self._table, 1)
        row_btns = QHBoxLayout()
        row_btns.setSpacing(6)
        add_row = QPushButton("+ 加一行")
        add_row.setObjectName("ghost")
        add_row.clicked.connect(lambda: self._table.insertRow(self._table.rowCount()))
        row_btns.addWidget(add_row)
        del_row = QPushButton("- 删除选中行")
        del_row.setObjectName("ghost")
        del_row.clicked.connect(self._delete_selected_rows)
        row_btns.addWidget(del_row)
        row_btns.addStretch(1)
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._on_save)
        row_btns.addWidget(self._save_btn)
        right.addLayout(row_btns)
        right_w = QWidget()
        right_w.setLayout(right)
        body.addWidget(right_w, 1)

        root.addLayout(body, 1)

    def _open_folder(self) -> None:
        hotword_store.ensure_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(HOTWORDS_DIR)))

    def _refresh_list(self) -> None:
        prev = self._current_title
        self._list.clear()
        for title in hotword_store.list_titles():
            self._list.addItem(QListWidgetItem(title))
        if prev:
            items = self._list.findItems(prev, Qt.MatchFlag.MatchExactly)
            if items:
                self._list.setCurrentItem(items[0])
                return
        self._current_title = ""
        self._title_lbl.setText("（未选择）")
        self._table.setRowCount(0)

    def _on_select(self, current: QListWidgetItem, _prev) -> None:
        if current is None:
            return
        title = current.text()
        hw = hotword_store.load(title)
        self._current_title = title
        self._title_lbl.setText(f"标题：{title}")
        self._fill_table(hw.entries)

    def _fill_table(self, entries: dict[str, str]) -> None:
        self._table.setRowCount(0)
        for k, v in entries.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(k))
            self._table.setItem(row, 1, QTableWidgetItem(v))

    def _on_new(self) -> None:
        title, ok = QInputDialog.getText(self, "新建热词表", "标题：")
        if not ok:
            return
        title = title.strip()
        if not title:
            QMessageBox.warning(self, "新建热词表", "标题不能为空")
            return
        if title in hotword_store.list_titles():
            QMessageBox.warning(self, "新建热词表", "已存在同名热词表")
            return
        hotword_store.save(HotwordSet(title=title, entries={}))
        self._current_title = title
        self._refresh_list()

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        title = item.text()
        resp = QMessageBox.question(
            self, "删除", f"删除热词表「{title}」？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        hotword_store.delete(title)
        self._current_title = ""
        self._refresh_list()

    def _delete_selected_rows(self) -> None:
        rows = sorted({i.row() for i in self._table.selectedIndexes()}, reverse=True)
        for r in rows:
            self._table.removeRow(r)

    def _on_save(self) -> None:
        if not self._current_title:
            QMessageBox.warning(self, "保存", "请先在左侧选择或新建一个热词表")
            return
        entries: dict[str, str] = {}
        for row in range(self._table.rowCount()):
            k_item = self._table.item(row, 0)
            v_item = self._table.item(row, 1)
            k = k_item.text().strip() if k_item else ""
            v = v_item.text().strip() if v_item else ""
            if not k:
                continue
            entries[k] = v
        if len(entries) > MAX_ENTRIES:
            QMessageBox.warning(self, "保存", f"超过条数上限 {MAX_ENTRIES}")
            return
        try:
            hotword_store.save(HotwordSet(title=self._current_title, entries=entries))
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        QMessageBox.information(self, "保存", f"已保存 {len(entries)} 条")
