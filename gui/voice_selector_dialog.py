from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


_VOICE_JSON_PATH = Path(__file__).resolve().parent.parent / "resource" / "volc_voice_list_seed_tts_2.0.json"

S2S_VOICE_TYPES = {"zh_female_vv_uranus_bigtts", "zh_male_jingqiangkanye_emo_mars_bigtts"}

_LANG_LABEL = {
    "zh-cn": ("🇨🇳", "中文"),
    "en": ("🇺🇸", "英语"),
    "ja": ("🇯🇵", "日语"),
    "id": ("🇮🇩", "印尼语"),
    "es-mx": ("🇲🇽", "西语"),
    "pt-br": ("🇧🇷", "葡语"),
    "ko": ("🇰🇷", "韩语"),
    "fr": ("🇫🇷", "法语"),
    "de": ("🇩🇪", "德语"),
}


@dataclass
class Voice:
    voice_type: str
    name: str
    gender: str
    age: str
    description: str
    emoji: str
    trial_url: str
    languages: list[str] = field(default_factory=list)
    is_s2s: bool = False


def _extra_s2s_voices() -> list[Voice]:
    return [
        Voice(
            voice_type="zh_male_jingqiangkanye_emo_mars_bigtts",
            name="京腔侃爷",
            gender="男",
            age="中年",
            description="同声传译专用音色，京味儿地道、带感官情绪。",
            emoji="🎙️",
            trial_url="",
            languages=["zh-cn"],
            is_s2s=True,
        ),
    ]


def load_voices() -> list[Voice]:
    voices: list[Voice] = []
    try:
        data = json.loads(_VOICE_JSON_PATH.read_text(encoding="utf-8"))
        for s in data.get("Result", {}).get("Speakers", []):
            vt = str(s.get("VoiceType", "")).strip()
            if not vt:
                continue
            langs = [str(l.get("Language", "")).strip().lower() for l in (s.get("Languages") or [])]
            voices.append(Voice(
                voice_type=vt,
                name=str(s.get("Name", "")).strip() or vt,
                gender=str(s.get("Gender", "")).strip(),
                age=str(s.get("Age", "")).strip(),
                description=str(s.get("Description", "")).strip(),
                emoji=str(s.get("Emoji", "")).strip(),
                trial_url=str(s.get("TrialURL", "")).strip(),
                languages=[l for l in langs if l],
                is_s2s=vt in S2S_VOICE_TYPES,
            ))
    except (OSError, json.JSONDecodeError):
        pass

    have = {v.voice_type for v in voices}
    for extra in _extra_s2s_voices():
        if extra.voice_type not in have:
            voices.append(extra)
    return voices


class _Chip(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("voiceChip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class VoiceRow(QFrame):
    clicked = Signal(str)
    preview = Signal(str, str)

    def __init__(self, voice: Voice, parent=None) -> None:
        super().__init__(parent)
        self.voice = voice
        self.setObjectName("voiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(14)

        self._radio = QLabel()
        self._radio.setObjectName("voiceRadio")
        outer.addWidget(self._radio, 0, Qt.AlignmentFlag.AlignVCenter)

        emoji = QLabel(self.voice.emoji or "🎵")
        emoji.setObjectName("voiceEmoji")
        outer.addWidget(emoji, 0, Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        name = QLabel(self.voice.name)
        name.setObjectName("voiceName")
        title_row.addWidget(name)
        if self.voice.is_s2s:
            badge = QLabel("同传可用")
            badge.setObjectName("voiceBadgeS2S")
            title_row.addWidget(badge)
        meta_bits = [b for b in [self.voice.gender, self.voice.age] if b]
        if meta_bits:
            meta = QLabel(" · ".join(meta_bits))
            meta.setObjectName("voiceMetaSmall")
            title_row.addWidget(meta)
        title_row.addStretch(1)
        info.addLayout(title_row)

        vt = QLabel(self.voice.voice_type)
        vt.setObjectName("voiceType")
        info.addWidget(vt)

        desc_text = self.voice.description or "官方音色"
        desc = QLabel(desc_text)
        desc.setObjectName("voiceDesc")
        desc.setWordWrap(True)
        info.addWidget(desc)

        flags = "".join(_LANG_LABEL.get(l, ("🏳️", l))[0] for l in self.voice.languages)
        if flags:
            lang = QLabel(flags)
            lang.setObjectName("voiceLangFlags")
            info.addWidget(lang)

        outer.addLayout(info, 1)

        self._play_btn = QPushButton("▶ 试听")
        self._play_btn.setObjectName("voicePlayBtn")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setEnabled(bool(self.voice.trial_url))
        self._play_btn.clicked.connect(self._on_play_clicked)
        outer.addWidget(self._play_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_play_clicked(self) -> None:
        self.preview.emit(self.voice.voice_type, self.voice.trial_url)

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("■ 停止" if playing else "▶ 试听")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._play_btn.geometry().contains(event.pos()):
                self.clicked.emit(self.voice.voice_type)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._radio.setProperty("selected", selected)
        for w in (self, self._radio):
            w.style().unpolish(w)
            w.style().polish(w)


class VoiceSelectorDialog(QDialog):
    voice_selected = Signal(str)

    def __init__(self, current_voice: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.FramelessWindowHint)
            | Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("音频选择")
        self.setMinimumSize(960, 720)
        self._voices = load_voices()
        self._current_voice = current_voice
        self._rows: list[VoiceRow] = []
        self._search = QLineEdit()
        self._gender_chips: dict[str, _Chip] = {}
        self._lang_chips: dict[str, _Chip] = {}
        self._s2s_only_chip: _Chip | None = None
        self._selected_label = QLabel()
        self._list_layout = QVBoxLayout()
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._playing_voice = ""
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._build_ui()
        self._refresh_rows()
        self._update_selected_label()

    @property
    def selected_voice(self) -> str:
        return self._current_voice

    def _build_ui(self) -> None:
        self.setObjectName("voiceDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_VOICE_DIALOG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(20, 16, 18, 12)
        header.setSpacing(14)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("选择火山引擎音色")
        title.setObjectName("voiceDialogTitle")
        subtitle = QLabel("数据来源 seed-tts-2.0；标有「同传可用」的两个音色可用于同声传译，其余仅打字翻译。")
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

        # Search row
        search_row = QHBoxLayout()
        search_row.setContentsMargins(20, 4, 20, 8)
        search_row.setSpacing(10)
        self._search.setObjectName("voiceSearch")
        self._search.setPlaceholderText("搜索名称 / voice_type / 描述")
        self._search.textChanged.connect(self._refresh_rows)
        search_row.addWidget(self._search, 1)
        self._s2s_only_chip = _Chip("仅同传可用")
        self._s2s_only_chip.toggled.connect(self._refresh_rows)
        search_row.addWidget(self._s2s_only_chip)
        clear_btn = QPushButton("清空筛选")
        clear_btn.setObjectName("voiceSecondaryButton")
        clear_btn.clicked.connect(self._clear_filters)
        search_row.addWidget(clear_btn)
        root.addLayout(search_row)

        # Filter chips: gender + language
        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(20, 0, 20, 10)
        chips_row.setSpacing(6)
        chips_row.addWidget(self._make_section_label("性别"))
        for g in ["女", "男"]:
            chip = _Chip(g)
            chip.toggled.connect(self._refresh_rows)
            self._gender_chips[g] = chip
            chips_row.addWidget(chip)
        chips_row.addSpacing(12)
        chips_row.addWidget(self._make_section_label("语种"))
        present_langs = sorted({l for v in self._voices for l in v.languages})
        for lc in present_langs:
            flag, label = _LANG_LABEL.get(lc, ("🏳️", lc))
            chip = _Chip(f"{flag} {label}")
            chip.toggled.connect(self._refresh_rows)
            self._lang_chips[lc] = chip
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        root.addLayout(chips_row)

        # Voice list
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

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 12, 20, 14)
        footer.setSpacing(12)
        self._selected_label.setObjectName("voiceSelectedLabel")
        footer.addWidget(self._selected_label, 1)
        default_btn = QPushButton("使用默认")
        default_btn.setObjectName("voiceSecondaryButton")
        default_btn.clicked.connect(self._clear_selection)
        footer.addWidget(default_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("voiceSecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        apply_btn = QPushButton("应用音色")
        apply_btn.setObjectName("voiceApplyButton")
        apply_btn.clicked.connect(self._accept_selection)
        footer.addWidget(apply_btn)
        root.addLayout(footer)

    def _make_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("voiceFilterLabel")
        return lbl

    def _clear_filters(self) -> None:
        self._search.clear()
        for chip in list(self._gender_chips.values()) + list(self._lang_chips.values()):
            chip.setChecked(False)
        if self._s2s_only_chip is not None:
            self._s2s_only_chip.setChecked(False)

    def _matches(self, voice: Voice) -> bool:
        if self._s2s_only_chip is not None and self._s2s_only_chip.isChecked() and not voice.is_s2s:
            return False
        active_genders = [g for g, c in self._gender_chips.items() if c.isChecked()]
        if active_genders and voice.gender not in active_genders:
            return False
        active_langs = [l for l, c in self._lang_chips.items() if c.isChecked()]
        if active_langs and not any(l in voice.languages for l in active_langs):
            return False
        q = self._search.text().strip().lower()
        if q:
            hay = " ".join([voice.name, voice.voice_type, voice.description, voice.gender, voice.age]).lower()
            if q not in hay:
                return False
        return True

    @Slot()
    def _refresh_rows(self) -> None:
        self._stop_preview()
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        matches = [v for v in self._voices if self._matches(v)]
        # S2S voices first, then by name
        matches.sort(key=lambda v: (not v.is_s2s, v.name))

        if not matches:
            empty = QLabel("没有匹配的音色")
            empty.setObjectName("voiceEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.insertWidget(0, empty)
            return

        for voice in matches:
            row = VoiceRow(voice)
            row.clicked.connect(self._select_voice)
            row.preview.connect(self._on_preview)
            row.set_selected(voice.voice_type == self._current_voice)
            self._rows.append(row)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

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
        self._stop_preview()
        self.voice_selected.emit(self._current_voice)
        self.accept()

    @Slot(str, str)
    def _on_preview(self, voice_type: str, url: str) -> None:
        if self._playing_voice == voice_type:
            self._stop_preview()
            return
        if not url:
            return
        self._stop_preview()
        self._playing_voice = voice_type
        self._player.setSource(QUrl(url))
        self._player.play()
        for row in self._rows:
            row.set_playing(row.voice.voice_type == voice_type)

    def _stop_preview(self) -> None:
        if self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._player.stop()
        self._playing_voice = ""
        for row in self._rows:
            row.set_playing(False)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._playing_voice = ""
            for row in self._rows:
                row.set_playing(False)

    def closeEvent(self, event) -> None:
        self._stop_preview()
        super().closeEvent(event)


_VOICE_DIALOG_QSS = """
QDialog#voiceDialog {
    background: #07131c;
    border: 1px solid rgba(115, 215, 255, 0.28);
}
QLabel#voiceDialogTitle {
    color: #eef7ff;
    font-size: 20px;
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
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
    padding: 0;
    font-size: 20px;
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
    min-height: 34px;
    font-size: 13px;
}
QLineEdit#voiceSearch:focus {
    border-color: rgba(94, 231, 162, 0.55);
}
QLabel#voiceFilterLabel {
    color: #7fb7d5;
    font-size: 12px;
    font-weight: 800;
    padding: 0 4px;
}
QPushButton#voiceChip {
    background: #0b1a24;
    color: #9ecbe2;
    border: 1px solid rgba(115, 164, 194, 0.28);
    border-radius: 999px;
    min-height: 26px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 700;
    min-width: 0px;
}
QPushButton#voiceChip:checked {
    background: rgba(94, 231, 162, 0.18);
    color: #c6ffdf;
    border-color: rgba(94, 231, 162, 0.55);
}
QPushButton#voiceChip:hover:!checked {
    background: rgba(255, 255, 255, 0.07);
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
    border: 1px solid rgba(89, 147, 183, 0.30);
    border-radius: 10px;
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
    min-width: 14px; max-width: 14px;
    min-height: 14px; max-height: 14px;
    border: 2px solid #6497b7;
    border-radius: 7px;
    background: transparent;
}
QLabel#voiceRadio[selected="true"] {
    background: #5ee7a2;
    border-color: #5ee7a2;
}
QLabel#voiceEmoji {
    font-size: 22px;
    min-width: 28px;
}
QLabel#voiceName {
    color: #eef7ff;
    font-size: 15px;
    font-weight: 900;
}
QLabel#voiceMetaSmall {
    color: #9ecbe2;
    font-size: 11px;
}
QLabel#voiceType {
    color: #9dffd5;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    font-weight: 800;
}
QLabel#voiceDesc {
    color: #b6d5e8;
    font-size: 12px;
}
QLabel#voiceLangFlags {
    font-size: 14px;
}
QLabel#voiceBadgeS2S {
    color: #03140d;
    background: #5ee7a2;
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 900;
}
QPushButton#voicePlayBtn {
    background: rgba(94, 231, 162, 0.12);
    color: #c6ffdf;
    border: 1px solid rgba(94, 231, 162, 0.45);
    border-radius: 8px;
    min-height: 32px;
    padding: 0 14px;
    font-weight: 800;
    font-size: 12px;
    min-width: 76px;
}
QPushButton#voicePlayBtn:hover {
    background: rgba(94, 231, 162, 0.22);
}
QPushButton#voicePlayBtn:disabled {
    background: rgba(255, 255, 255, 0.04);
    color: rgba(198, 255, 223, 0.35);
    border-color: rgba(94, 231, 162, 0.15);
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
    min-height: 34px;
    padding: 0 18px;
    font-weight: 800;
}
QPushButton#voiceSecondaryButton:hover {
    background: #122a38;
}
QPushButton#voiceApplyButton {
    background: #5ee7a2;
    color: #03140d;
    border: none;
    border-radius: 10px;
    min-height: 34px;
    padding: 0 22px;
    font-weight: 900;
}
QPushButton#voiceApplyButton:hover {
    background: #6df0b1;
}
"""
