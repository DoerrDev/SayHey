from __future__ import annotations

import os
import sys

STYLESHEET = """
/* === Global === */
QWidget {
    background-color: #0a1016;
    color: #eef7ff;
    font-family: "MiSans", "Segoe UI Variable", "Segoe UI", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #0a1016;
}
QDialog {
    background-color: #0f1923;
}
QLabel {
    background: transparent;
}

/* === Card panels === */
QFrame#card {
    background-color: rgba(17, 27, 37, 0.95);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 20px;
}
QFrame#cardLeft {
    background-color: rgba(17, 27, 37, 0.95);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-top-left-radius: 20px;
    border-bottom-left-radius: 20px;
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}
QFrame#cardRight {
    background-color: rgba(17, 27, 37, 0.95);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-top-right-radius: 20px;
    border-bottom-right-radius: 20px;
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}

/* === Primary button === */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #42dd92, stop:1 #93f5c4);
    color: #061017;
    font-weight: 900;
    font-size: 13px;
    border: none;
    border-radius: 12px;
    padding: 9px 18px;
    min-width: 70px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #5af0a8, stop:1 #aaffda);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #38c07e, stop:1 #7dd4a8);
}
QPushButton:disabled {
    background: rgba(66, 221, 146, 0.18);
    color: rgba(6, 16, 23, 0.45);
}

/* === Secondary button (objectName="secondary") === */
QPushButton#secondary {
    background: rgba(255, 255, 255, 0.07);
    color: #cce4f7;
    border: 1px solid rgba(163, 207, 255, 0.18);
    font-weight: 700;
}
QPushButton#secondary:hover {
    background: rgba(255, 255, 255, 0.13);
    border-color: rgba(163, 207, 255, 0.30);
}
QPushButton#secondary:disabled {
    background: rgba(255, 255, 255, 0.03);
    color: rgba(204, 228, 247, 0.3);
    border-color: rgba(163, 207, 255, 0.06);
}

/* === Danger/stop button === */
QPushButton#danger {
    background: rgba(255, 80, 80, 0.12);
    color: #ffb3b3;
    border: 1px solid rgba(255, 80, 80, 0.28);
    font-weight: 700;
}
QPushButton#danger:hover {
    background: rgba(255, 80, 80, 0.22);
}
QPushButton#danger:disabled {
    background: rgba(255, 80, 80, 0.05);
    color: rgba(255, 179, 179, 0.3);
    border-color: rgba(255, 80, 80, 0.10);
}

/* === Ghost button === */
QPushButton#ghost {
    background: transparent;
    color: #9ab8d0;
    border: 1px solid rgba(163, 207, 255, 0.14);
    font-weight: 600;
}
QPushButton#ghost:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #cce4f7;
}

/* === Status chip (QLabel#statusChip / #statusChipWarn / #statusChipError) === */
QLabel#statusChip {
    background: rgba(66, 221, 146, 0.10);
    color: #b0ffd6;
    border: 1px solid rgba(66, 221, 146, 0.28);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 800;
}
QLabel#statusChipWarn {
    background: rgba(255, 209, 102, 0.10);
    color: #ffe6a5;
    border: 1px solid rgba(255, 209, 102, 0.35);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 800;
}
QLabel#statusChipError {
    background: rgba(255, 80, 80, 0.10);
    color: #ffb3b3;
    border: 1px solid rgba(255, 80, 80, 0.30);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 800;
}

/* === Subtitle text areas === */
QTextEdit#stage {
    background-color: rgba(8, 14, 20, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    color: #eef7ff;
    font-size: 20px;
    font-weight: 600;
    padding: 14px;
    selection-background-color: rgba(66, 221, 146, 0.28);
}
QTextEdit#stageLarge {
    background-color: rgba(8, 14, 20, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    color: #f0faf5;
    font-size: 28px;
    font-weight: 900;
    padding: 14px;
    selection-background-color: rgba(66, 221, 146, 0.28);
}

/* === Input / ComboBox === */
QLineEdit {
    background: rgba(5, 10, 15, 0.80);
    color: #eef7ff;
    border: 1px solid rgba(163, 207, 255, 0.18);
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: rgba(66, 221, 146, 0.30);
}
QLineEdit:focus {
    border-color: rgba(66, 221, 146, 0.45);
}
QComboBox {
    background: rgba(5, 10, 15, 0.80);
    color: #eef7ff;
    border: 1px solid rgba(163, 207, 255, 0.18);
    border-radius: 10px;
    padding: 7px 12px;
    min-width: 90px;
}
QComboBox:focus {
    border-color: rgba(66, 221, 146, 0.45);
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::down-arrow {
    image: url(resource/icons/chevron-down-brand.svg);
    width: 14px;
    height: 14px;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #111b25;
    border: 1px solid rgba(163, 207, 255, 0.18);
    border-radius: 10px;
    color: #eef7ff;
    selection-background-color: rgba(66, 221, 146, 0.22);
    outline: none;
    padding: 4px;
}

/* === Log panel === */
QPlainTextEdit#log {
    background: rgba(5, 9, 13, 0.85);
    color: #7a9db5;
    border: 1px solid rgba(163, 207, 255, 0.08);
    border-radius: 16px;
    font-family: "JetBrains Mono", "Cascadia Mono", "Cascadia Code", "Consolas", "Microsoft YaHei UI", monospace;
    font-size: 11px;
    padding: 12px;
}

/* === Settings tabs === */
QTabBar::tab {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(163, 207, 255, 0.14);
    border-radius: 999px;
    padding: 7px 18px;
    color: #9ab8d0;
    font-weight: 700;
    font-size: 13px;
    margin-right: 6px;
    margin-bottom: 2px;
}
QTabBar::tab:selected {
    background: rgba(66, 221, 146, 0.12);
    border-color: rgba(66, 221, 146, 0.35);
    color: #c6ffdf;
}
QTabBar::tab:hover:!selected {
    background: rgba(255, 255, 255, 0.07);
}
QTabWidget::pane {
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 16px;
    background: rgba(10, 18, 26, 0.92);
    top: -1px;
}

/* === Settings sidebar === */
QListWidget#settingsNav {
    background: rgba(10, 18, 26, 0.92);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 16px;
    padding: 8px 6px;
    outline: none;
}
QListWidget#settingsNav::item {
    border-radius: 10px;
    padding: 6px 10px;
    color: #9ab8d0;
    font-weight: 700;
    font-size: 13px;
}
QListWidget#settingsNav::item:selected {
    background: rgba(66, 221, 146, 0.12);
    color: #c6ffdf;
}
QListWidget#settingsNav::item:hover:!selected {
    background: rgba(255, 255, 255, 0.06);
}
QStackedWidget#settingsPane {
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 16px;
    background: rgba(10, 18, 26, 0.92);
}

/* === Spinbox, Slider === */
QSpinBox, QDoubleSpinBox {
    background: rgba(5, 10, 15, 0.80);
    color: #eef7ff;
    border: 1px solid rgba(163, 207, 255, 0.18);
    border-radius: 10px;
    padding: 7px 28px 7px 10px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 14px;
    background: rgba(163, 207, 255, 0.08);
    border-left: 1px solid rgba(163, 207, 255, 0.18);
    border-top-right-radius: 10px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background: rgba(66, 221, 146, 0.18);
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 14px;
    background: rgba(163, 207, 255, 0.08);
    border-left: 1px solid rgba(163, 207, 255, 0.18);
    border-bottom-right-radius: 10px;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: rgba(66, 221, 146, 0.18);
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(resource/icons/chevron-up-brand.svg);
    width: 12px;
    height: 12px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(resource/icons/chevron-down-brand.svg);
    width: 12px;
    height: 12px;
}
QSlider::groove:horizontal {
    background: rgba(163, 207, 255, 0.12);
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #42dd92;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal {
    background: rgba(66, 221, 146, 0.55);
    border-radius: 3px;
}

/* === CheckBox === */
QCheckBox {
    background: transparent;
    color: #cce4f7;
    spacing: 8px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(163, 207, 255, 0.25);
    background: rgba(5, 10, 15, 0.80);
}
QCheckBox::indicator:checked {
    background: #42dd92;
    border-color: #42dd92;
}

/* === Scrollbar === */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(163, 207, 255, 0.22);
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: rgba(163, 207, 255, 0.22);
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; border: none; }

/* === Separator === */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: rgba(163, 207, 255, 0.10);
}

/* === Tool button (gear icon) === */
QToolButton {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(163, 207, 255, 0.14);
    border-radius: 10px;
    padding: 7px 10px;
    color: #9ab8d0;
    font-size: 16px;
}
QToolButton:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #eef7ff;
}

/* === Section labels === */
QLabel#sectionTitle {
    color: #b0d4ee;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#panelTitle {
    color: #eef7ff;
    font-size: 15px;
    font-weight: 900;
}
QLabel#routeLabel {
    color: #6a8fa8;
    font-size: 12px;
}

/* === Dot indicator === */
QLabel#dotGreen {
    color: #42dd92;
    font-size: 18px;
}
QLabel#dotOrange {
    color: #ffa042;
    font-size: 18px;
}
QLabel#dotRed {
    color: #ff5050;
    font-size: 18px;
}
QLabel#dotGray {
    color: rgba(163, 207, 255, 0.25);
    font-size: 18px;
}

/* === Typed translate result box === */
QFrame#resultWrap {
    background: rgba(8, 14, 20, 0.85);
    border: 1px solid rgba(163, 207, 255, 0.10);
    border-radius: 12px;
}
QLabel#resultBox {
    color: #f0faf5;
    font-size: 14px;
    font-weight: 700;
}
QLabel#hotkeyBox {
    background: rgba(8, 14, 20, 0.85);
    border: 1px solid rgba(163, 207, 255, 0.18);
    border-radius: 10px;
    padding: 4px 12px;
    color: #eef7ff;
    font-weight: 800;
}

/* === Mic tabs (inner QTabWidget) === */
QTabWidget#micTabs {
    background-color: rgba(17, 27, 37, 0.95);
}
QTabWidget#micTabs QTabBar {
    background-color: rgba(17, 27, 37, 0.95);
}
QTabWidget#micTabs::pane {
    border: none;
    border-top: 1px solid rgba(163, 207, 255, 0.08);
    border-radius: 0px;
    background: transparent;
    top: -1px;
}
QTabWidget#micTabs QTabBar::tab {
    border-radius: 8px;
}
QFrame#tabContent {
    background-color: rgba(17, 27, 37, 0.95);
    border: none;
    border-radius: 0px;
}

/* === Floating input window === */
QLabel#floatChip {
    background: rgba(8, 13, 24, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    color: #c7d5e8;
    padding: 3px 12px;
    font-size: 12px;
    font-weight: 800;
}
QWidget#floatResult {
    background: rgba(7, 12, 22, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 12px;
}
QLabel#floatLabel {
    color: #9db0c8;
    font-weight: 800;
}
QLabel#floatSource {
    color: #cfe0f3;
    font-size: 14px;
}
QLabel#floatTarget {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QWidget#floatInputBar {
    background: rgba(8, 13, 24, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 999px;
}
QLineEdit#floatLineEdit {
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 15px;
    padding: 6px 4px;
}
QPushButton#floatSendBtn {
    background: #19c37d;
    color: #07111f;
    border-radius: 999px;
    padding: 8px 18px;
    font-weight: 900;
}
QPushButton#floatSendBtn:hover {
    background: #2bd690;
}
"""


def _font_dir() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(base, "resource", "fonts")


def _load_bundled_fonts() -> bool:
    from PySide6.QtGui import QFontDatabase
    fdir = _font_dir()
    if not os.path.isdir(fdir):
        return False
    loaded = False
    for name in ("MiSans-Regular.ttf", "MiSans-Bold.ttf"):
        path = os.path.join(fdir, name)
        if os.path.isfile(path) and QFontDatabase.addApplicationFont(path) != -1:
            loaded = True
    return loaded


def apply_theme(app) -> None:
    from PySide6.QtGui import QFont, QFontDatabase
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    has_misans = _load_bundled_fonts()
    families = set(QFontDatabase.families())
    preferred = [
        "MiSans" if has_misans else None,
        "Segoe UI Variable",
        "Segoe UI",
        "HarmonyOS Sans SC",
        "PingFang SC",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
    ]
    chosen = next((f for f in preferred if f and f in families), "Segoe UI")
    font = QFont(chosen, 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
