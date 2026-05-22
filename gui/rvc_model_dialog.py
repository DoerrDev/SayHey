from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_core.rvc_client import DEFAULT_MODELS_DIR, RvcModel


class _ModelRow(QFrame):
    clicked = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, model: RvcModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.setObjectName("voiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(14)

        self._radio = QLabel()
        self._radio.setObjectName("voiceRadio")
        outer.addWidget(self._radio, 0, Qt.AlignmentFlag.AlignVCenter)

        emoji = QLabel("🎚️")
        emoji.setObjectName("voiceEmoji")
        outer.addWidget(emoji, 0, Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(model.name)
        name.setObjectName("voiceName")
        info.addWidget(name)

        meta = QLabel(f".pth: {model.pth_path.name}" + (f"  ·  .index: {model.index_path.name}" if model.index_path else "  ·  无 index"))
        meta.setObjectName("voiceMetaSmall")
        info.addWidget(meta)

        path = QLabel(str(model.pth_path.parent))
        path.setObjectName("voiceType")
        path.setWordWrap(True)
        info.addWidget(path)

        outer.addLayout(info, 1)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("voiceSecondaryButton")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.model.name))
        outer.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.model.name)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._radio.setProperty("selected", selected)
        for w in (self, self._radio):
            w.style().unpolish(w)
            w.style().polish(w)


class RvcModelDialog(QDialog):
    model_selected = Signal(str)

    def __init__(self, current_model: str = "", models_dir: Path = DEFAULT_MODELS_DIR, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.FramelessWindowHint)
            | Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setWindowTitle("RVC 模型管理")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMinimumSize(820, 600)
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._current_model = current_model
        self._models: list[RvcModel] = []
        self._rows: list[_ModelRow] = []
        self._search = QLineEdit()
        self._list_layout = QVBoxLayout()
        self._selected_label = QLabel()
        self._build_ui()
        self._reload()

    @property
    def selected_model(self) -> str:
        return self._current_model

    def _build_ui(self) -> None:
        self.setObjectName("voiceDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        from gui.voice_selector_dialog import _VOICE_DIALOG_QSS
        self.setStyleSheet(_VOICE_DIALOG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        subtitle = QLabel(f"模型目录：{self._models_dir}。导入 .pth（可选同名 .index）后即可选用。")
        subtitle.setObjectName("voiceDialogSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setContentsMargins(20, 14, 20, 8)
        root.addWidget(subtitle)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(20, 4, 20, 8)
        search_row.setSpacing(10)
        self._search.setObjectName("voiceSearch")
        self._search.setPlaceholderText("搜索模型名")
        self._search.textChanged.connect(self._refresh_rows)
        search_row.addWidget(self._search, 1)
        import_btn = QPushButton("导入模型...")
        import_btn.setObjectName("voiceApplyButton")
        import_btn.clicked.connect(self._on_import)
        search_row.addWidget(import_btn)
        open_dir_btn = QPushButton("打开模型目录")
        open_dir_btn.setObjectName("voiceSecondaryButton")
        open_dir_btn.clicked.connect(self._open_models_dir)
        search_row.addWidget(open_dir_btn)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("voiceSecondaryButton")
        refresh_btn.clicked.connect(self._reload)
        search_row.addWidget(refresh_btn)
        root.addLayout(search_row)

        scroll = QScrollArea()
        scroll.setObjectName("voiceScroll")
        scroll.setWidgetResizable(True)
        list_host = QWidget()
        list_host.setObjectName("voiceListHost")
        self._list_layout = QVBoxLayout(list_host)
        self._list_layout.setContentsMargins(20, 12, 20, 12)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        scroll.setWidget(list_host)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 12, 20, 14)
        footer.setSpacing(12)
        self._selected_label.setObjectName("voiceSelectedLabel")
        footer.addWidget(self._selected_label, 1)
        clear_btn = QPushButton("不使用模型")
        clear_btn.setObjectName("voiceSecondaryButton")
        clear_btn.clicked.connect(self._clear_selection)
        footer.addWidget(clear_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("voiceSecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        apply_btn = QPushButton("应用")
        apply_btn.setObjectName("voiceApplyButton")
        apply_btn.clicked.connect(self._accept_selection)
        footer.addWidget(apply_btn)
        root.addLayout(footer)

    def _reload(self) -> None:
        self._models = RvcModel.scan(self._models_dir)
        self._refresh_rows()
        self._update_selected_label()

    @Slot()
    def _refresh_rows(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()

        q = self._search.text().strip().lower()
        matches = [m for m in self._models if not q or q in m.name.lower()]

        if not matches:
            empty = QLabel("还没有模型，点击右上角「导入模型」添加 .pth 文件")
            empty.setObjectName("voiceEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.insertWidget(0, empty)
            return

        for m in matches:
            row = _ModelRow(m)
            row.clicked.connect(self._select_model)
            row.delete_requested.connect(self._delete_model)
            row.set_selected(m.name == self._current_model)
            self._rows.append(row)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    @Slot(str)
    def _select_model(self, name: str) -> None:
        self._current_model = name
        for row in self._rows:
            row.set_selected(row.model.name == name)
        self._update_selected_label()

    @Slot()
    def _clear_selection(self) -> None:
        self._current_model = ""
        for row in self._rows:
            row.set_selected(False)
        self._update_selected_label()

    def _update_selected_label(self) -> None:
        self._selected_label.setText(f"当前选择：{self._current_model or '未选择'}")

    @Slot()
    def _accept_selection(self) -> None:
        self.model_selected.emit(self._current_model)
        self.accept()

    @Slot()
    def _on_import(self) -> None:
        pth_path, _ = QFileDialog.getOpenFileName(
            self, "选择 RVC .pth 模型", "", "RVC Model (*.pth)"
        )
        if not pth_path:
            return
        pth = Path(pth_path)
        name = pth.stem
        target_dir = self._models_dir / name
        if target_dir.exists():
            ret = QMessageBox.question(
                self, "模型已存在",
                f"目录 {target_dir} 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pth, target_dir / pth.name)

        idx_candidate = pth.with_suffix(".index")
        if not idx_candidate.exists():
            ret = QMessageBox.question(
                self, "是否选择 .index 文件",
                "是否选择对应的 .index 文件？（可选）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.Yes:
                idx_path, _ = QFileDialog.getOpenFileName(
                    self, "选择 .index 文件", "", "RVC Index (*.index)"
                )
                if idx_path:
                    idx_candidate = Path(idx_path)
        if idx_candidate.exists():
            shutil.copy2(idx_candidate, target_dir / idx_candidate.name)

        self._reload()
        self._select_model(name)

    @Slot(str)
    def _delete_model(self, name: str) -> None:
        ret = QMessageBox.question(
            self, "删除模型",
            f"确定删除模型「{name}」吗？此操作会删除磁盘文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        target = self._models_dir / name
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            for f in self._models_dir.glob(f"{name}.*"):
                try:
                    f.unlink()
                except OSError:
                    pass
        if self._current_model == name:
            self._current_model = ""
        self._reload()

    @Slot()
    def _open_models_dir(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._models_dir)))
