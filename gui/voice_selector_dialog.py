from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


_VOICE_DATA_PATH = Path(__file__).resolve().parent.parent / "resource" / "volc_voice_list.json"
_SECTION_ORDER = ["s2s", "tts20", "tts10"]

_SECTION_TOOLTIPS = {
    "tts20": "豆包语音合成 2.0\n打字翻译 TTS 推荐使用：音色池最丰富，质量稳定。",
    "s2s": "端到端实时语音大模型 / SC-2.0\n同声传译推荐使用：低延迟、贴近自然对话。",
    "tts10": "豆包语音合成 1.0\n兼容旧音色，作为降级备选；如 2.0 没有匹配音色再选它。",
}


@dataclass(frozen=True)
class VoiceItem:
    section_id: str
    section_title: str
    scene: str
    name: str
    voice_type: str
    language: str
    ability: str
    tag: str


def _row_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return ""


def load_volc_voices() -> list[VoiceItem]:
    raw = json.loads(_VOICE_DATA_PATH.read_text(encoding="utf-8"))
    voices: list[VoiceItem] = []
    for section in raw.get("sections", []):
        section_id = str(section.get("id", "")).strip()
        section_title = str(section.get("title", "")).strip()
        for row in section.get("rows", []):
            voice_type = _row_value(row, "voice_type")
            if not voice_type:
                continue
            voices.append(
                VoiceItem(
                    section_id=section_id,
                    section_title=section_title,
                    scene=_row_value(row, "场景"),
                    name=_row_value(row, "音色名称", "场景"),
                    voice_type=voice_type,
                    language=_row_value(row, "语种/方言", "语种"),
                    ability=_row_value(row, "支持能力", "支持的情感"),
                    tag=_row_value(row, "特殊标签", "是否支持MIX"),
                )
            )
    return voices


def _section_label(section_id: str, count: int) -> str:
    if section_id == "s2s":
        return f"S2S/SC-2.0 {count}"
    if section_id == "tts20":
        return f"合成2.0 {count}"
    if section_id == "tts10":
        return f"合成1.0 {count}"
    return f"官方音色 {count}"


class VoiceRow(QFrame):
    clicked = Signal(str)

    def __init__(self, voice: VoiceItem, parent=None) -> None:
        super().__init__(parent)
        self.voice = voice
        self.setObjectName("voiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._radio = QLabel()
        self._radio.setObjectName("voiceRadio")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(3)

        layout.addWidget(self._radio, 0, 0, 2, 1, Qt.AlignmentFlag.AlignVCenter)

        name = QLabel(self.voice.name)
        name.setObjectName("voiceName")
        scene = QLabel(self.voice.scene or "官方音色")
        scene.setObjectName("voiceMeta")
        layout.addWidget(name, 0, 1)
        layout.addWidget(scene, 1, 1)

        voice_type = QLabel(self.voice.voice_type)
        voice_type.setObjectName("voiceType")
        language = QLabel(self.voice.language or "未标注语种")
        language.setObjectName("voiceMeta")
        layout.addWidget(voice_type, 0, 2)
        layout.addWidget(language, 1, 2)

        extra_text = " · ".join(part for part in [self.voice.ability, self.voice.tag] if part) or "官方音色"
        extra = QLabel(extra_text)
        extra.setObjectName("voiceExtra")
        extra.setWordWrap(True)
        layout.addWidget(extra, 0, 3, 2, 1)

        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 3)
        layout.setColumnStretch(3, 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.voice.voice_type)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._radio.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self._radio.style().unpolish(self._radio)
        self._radio.style().polish(self._radio)


class VoiceSelectorDialog(QDialog):
    voice_selected = Signal(str)

    def __init__(self, current_voice: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("选择火山引擎音色")
        self.setMinimumSize(960, 720)
        self._voices = load_volc_voices()
        self._current_voice = current_voice
        self._active_section = "s2s"
        self._section_buttons: dict[str, QPushButton] = {}
        self._rows: list[VoiceRow] = []
        self._search = QLineEdit()
        self._selected_label = QLabel()
        self._list_layout = QVBoxLayout()
        self._build_ui()
        self._refresh_rows()
        self._update_selected_label()

    @property
    def selected_voice(self) -> str:
        return self._current_voice

    def _build_ui(self) -> None:
        self.setObjectName("voiceDialog")
        self.setStyleSheet(_VOICE_DIALOG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(20, 18, 18, 14)
        header.setSpacing(14)
        title_box = QVBoxLayout()
        title_box.setSpacing(6)
        title = QLabel("选择火山引擎音色")
        title.setObjectName("voiceDialogTitle")
        subtitle = QLabel("数据来自火山引擎「音色列表」文档，已内嵌 482 个官方音色。S2S 场景建议优先使用「端到端实时语音大模型」分组。")
        subtitle.setObjectName("voiceDialogSubtitle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        close_btn = QPushButton("×")
        close_btn.setObjectName("voiceCloseButton")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 14, 20, 14)
        toolbar.setSpacing(10)
        self._search.setObjectName("voiceSearch")
        self._search.setPlaceholderText("搜索音色名称、voice_type、语种或场景")
        self._search.textChanged.connect(self._refresh_rows)
        toolbar.addWidget(self._search, 1)

        counts = self._section_counts()
        for section_id in ["tts20", "s2s", "tts10"]:
            button = QPushButton(_section_label(section_id, counts.get(section_id, 0)))
            button.setObjectName("voiceFilterButton")
            button.setToolTip(_SECTION_TOOLTIPS.get(section_id, ""))
            button.clicked.connect(lambda _checked=False, sid=section_id: self._set_active_section(sid))
            self._section_buttons[section_id] = button
            toolbar.addWidget(button)
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("voiceFilterButton")
        clear_btn.clicked.connect(self._clear_selection)
        toolbar.addWidget(clear_btn)
        root.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setObjectName("voiceScroll")
        scroll.setWidgetResizable(True)
        list_host = QWidget()
        list_host.setObjectName("voiceListHost")
        self._list_layout = QVBoxLayout(list_host)
        self._list_layout.setContentsMargins(20, 18, 20, 18)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch(1)
        scroll.setWidget(list_host)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 14, 20, 14)
        footer.setSpacing(12)
        self._selected_label.setObjectName("voiceSelectedLabel")
        footer.addWidget(self._selected_label, 1)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("voiceSecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        apply_btn = QPushButton("应用音色")
        apply_btn.setObjectName("voiceApplyButton")
        apply_btn.clicked.connect(self._accept_selection)
        footer.addWidget(apply_btn)
        root.addLayout(footer)

        self._sync_filter_buttons()

    def _section_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for voice in self._voices:
            counts[voice.section_id] = counts.get(voice.section_id, 0) + 1
        return counts

    @Slot()
    def _refresh_rows(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        query = self._search.text().strip().lower()
        matches = [voice for voice in self._voices if voice.section_id == self._active_section]
        if query:
            matches = [voice for voice in matches if query in self._voice_haystack(voice)]

        if not matches:
            empty = QLabel("没有匹配的音色")
            empty.setObjectName("voiceEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.insertWidget(0, empty)
            return

        for voice in matches:
            row = VoiceRow(voice)
            row.clicked.connect(self._select_voice)
            row.set_selected(voice.voice_type == self._current_voice)
            self._rows.append(row)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _voice_haystack(self, voice: VoiceItem) -> str:
        return " ".join(
            [
                voice.scene,
                voice.name,
                voice.voice_type,
                voice.language,
                voice.ability,
                voice.tag,
            ]
        ).lower()

    @Slot()
    def _set_active_section(self, section_id: str) -> None:
        self._active_section = section_id
        self._sync_filter_buttons()
        self._refresh_rows()

    def _sync_filter_buttons(self) -> None:
        for section_id, button in self._section_buttons.items():
            button.setProperty("active", section_id == self._active_section)
            button.style().unpolish(button)
            button.style().polish(button)

    @Slot(str)
    def _select_voice(self, voice_type: str) -> None:
        self._current_voice = voice_type
        for row in self._rows:
            row.set_selected(row.voice.voice_type == voice_type)
        self._update_selected_label()

    @Slot()
    def _clear_selection(self) -> None:
        self._current_voice = ""
        for row in self._rows:
            row.set_selected(False)
        self._update_selected_label()

    def _update_selected_label(self) -> None:
        self._selected_label.setText(f"当前选择：{self._current_voice or '服务默认音色'}")

    @Slot()
    def _accept_selection(self) -> None:
        self.voice_selected.emit(self._current_voice)
        self.accept()


_VOICE_DIALOG_QSS = """
QDialog#voiceDialog {
    background: #07131c;
    border: 1px solid rgba(115, 215, 255, 0.28);
}
QLabel#voiceDialogTitle {
    color: #eef7ff;
    font-size: 21px;
    font-weight: 900;
}
QLabel#voiceDialogSubtitle,
QLabel#voiceSelectedLabel {
    color: #7fb7d5;
    font-size: 12px;
}
QPushButton#voiceCloseButton {
    background: rgba(255, 255, 255, 0.06);
    color: #c9d9e5;
    border: 1px solid rgba(163, 207, 255, 0.16);
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
    font-size: 22px;
    font-weight: 900;
}
QPushButton#voiceCloseButton:hover {
    background: rgba(255, 255, 255, 0.12);
}
QLineEdit#voiceSearch {
    background: #050d13;
    color: #eef7ff;
    border: 1px solid rgba(115, 164, 194, 0.35);
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 36px;
    font-size: 14px;
}
QLineEdit#voiceSearch:focus {
    border-color: rgba(94, 231, 162, 0.55);
}
QPushButton#voiceFilterButton {
    background: #0b1a24;
    color: #9ecbe2;
    border: 1px solid rgba(115, 164, 194, 0.28);
    border-radius: 8px;
    min-height: 36px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 800;
}
QPushButton#voiceFilterButton[active="true"] {
    background: #5ee7a2;
    color: #03140d;
    border-color: #5ee7a2;
}
QScrollArea#voiceScroll {
    background: #061018;
    border-top: 1px solid rgba(115, 164, 194, 0.18);
    border-bottom: 1px solid rgba(115, 164, 194, 0.18);
}
QWidget#voiceListHost {
    background: #061018;
}
QFrame#voiceCard {
    background: #0c1c27;
    border: 1px solid rgba(89, 147, 183, 0.35);
    border-radius: 8px;
}
QFrame#voiceCard:hover {
    border-color: rgba(115, 215, 255, 0.52);
    background: #102431;
}
QFrame#voiceCard[selected="true"] {
    border-color: rgba(94, 231, 162, 0.88);
    background: #10281f;
}
QLabel#voiceRadio {
    min-width: 14px;
    max-width: 14px;
    min-height: 14px;
    max-height: 14px;
    border: 2px solid #6497b7;
    border-radius: 7px;
    background: transparent;
}
QLabel#voiceRadio[selected="true"] {
    background: #5ee7a2;
    border-color: #5ee7a2;
}
QLabel#voiceName {
    color: #eef7ff;
    font-size: 16px;
    font-weight: 900;
}
QLabel#voiceType {
    color: #9dffd5;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    font-weight: 800;
}
QLabel#voiceMeta {
    color: #73d7ff;
    font-size: 12px;
}
QLabel#voiceExtra {
    color: #b6d5e8;
    font-size: 12px;
}
QLabel#voiceEmpty {
    color: #7fb7d5;
    border: 1px dashed rgba(115, 164, 194, 0.32);
    border-radius: 8px;
    padding: 28px;
}
QPushButton#voiceSecondaryButton {
    background: #0e1c27;
    color: #eef7ff;
    border: 1px solid rgba(115, 164, 194, 0.3);
    border-radius: 10px;
    min-height: 38px;
    padding: 0 22px;
    font-weight: 800;
}
QPushButton#voiceApplyButton {
    background: #5ee7a2;
    color: #03140d;
    border: none;
    border-radius: 10px;
    min-height: 38px;
    padding: 0 24px;
    font-weight: 900;
}
"""
