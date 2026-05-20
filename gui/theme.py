from __future__ import annotations

from gui.icons import icons_dir_qss

STYLESHEET = """
QWidget {
    background-color: #0a1016;
    color: #eef7ff;
    font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #0a1016;
}
QDialog {
    background-color: #0f1923;
}
QDialog#feedbackDialog {
    background: #101923;
}
QLabel {
    background: transparent;
}
QLabel#headerTitle {
    color: #eef7ff;
    font-size: 18px;
    font-weight: 900;
}
QLabel#headerSubtitle {
    color: #82a4b9;
    font-size: 12px;
}
QLabel#logoFallback {
    color: #42dd92;
    font-size: 24px;
    font-weight: 900;
    border-radius: 12px;
    background: rgba(66,221,146,0.10);
    border: 1px solid rgba(66,221,146,0.26);
}

QFrame#card {
    background-color: rgba(17, 27, 37, 0.95);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 20px;
}
QLabel#feedbackDialogTitle {
    color: #f3fbff;
    font-size: 26px;
    font-weight: 900;
}
QLabel#feedbackDialogTip {
    color: #88a7bc;
    font-size: 13px;
}
QLabel#feedbackStatusBadge {
    color: #b9d7ea;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#feedbackFieldLabel, QLabel#feedbackPanelTitle {
    color: #d8ebf8;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.5px;
}
QLineEdit#feedbackNameInput {
    min-height: 24px;
    border-radius: 12px;
}
QFrame#feedbackPanel {
    background: rgba(14, 23, 32, 0.96);
    border: 1px solid rgba(163, 207, 255, 0.12);
    border-radius: 18px;
}
QScrollArea#feedbackScrollArea {
    background: transparent;
    border: none;
}
QWidget#feedbackChatContent {
    background: rgba(8, 13, 19, 0.94);
    border-top: 1px solid rgba(163, 207, 255, 0.08);
}
QFrame#feedbackBubbleWrap {
    background: transparent;
    border: none;
}
QLabel#feedbackBubbleMeta {
    color: #7d9ab0;
    font-size: 11px;
}
QFrame#feedbackBubble {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(163, 207, 255, 0.14);
    border-radius: 16px 16px 16px 6px;
    max-width: 440px;
}
QFrame#feedbackBubble[incoming="false"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(35, 73, 116, 0.98), stop:1 rgba(28, 53, 84, 0.98));
    border: 1px solid rgba(118, 169, 255, 0.22);
    border-radius: 16px 16px 6px 16px;
}
QLabel#feedbackBubbleText {
    color: #eef7ff;
    font-size: 13px;
    line-height: 1.55;
}
QLabel#feedbackEmptyState {
    color: #7f9bb1;
    font-size: 14px;
    padding: 36px 16px;
}
QLabel#feedbackErrorState {
    color: #ffb3b3;
    font-size: 13px;
    padding: 24px 16px;
}
QTextEdit#feedbackInput {
    background: rgba(7, 12, 18, 0.96);
    border: 1px solid rgba(163, 207, 255, 0.14);
    border-radius: 16px;
    color: #eef7ff;
    padding: 12px 14px;
    font-size: 13px;
    selection-background-color: rgba(66, 221, 146, 0.22);
}
QTextEdit#feedbackInput:focus {
    border-color: rgba(66, 221, 146, 0.36);
}

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
    min-height: 22px;
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
QPushButton#versionChip {
    background: rgba(255, 255, 255, 0.05);
    color: #b9d7ea;
    border: 1px solid rgba(163, 207, 255, 0.16);
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 800;
}
QPushButton#versionChip[hasUpdate="true"] {
    background: rgba(255, 116, 116, 0.12);
    color: #ffd7d7;
    border-color: rgba(255, 116, 116, 0.30);
}

QFrame#panelStatePill {
    background: transparent;
    border: none;
}
QFrame#panelStatePill[kind="normal"] {
}
QFrame#panelStatePill[kind="error"] {
}
QLabel#panelStatePillDot {
    background: #ffd166;
    border-radius: 4px;
    min-width: 8px;
    min-height: 8px;
    max-width: 8px;
    max-height: 8px;
}
QLabel#panelStatePillDot[kind="normal"] {
    background: #42dd92;
}
QLabel#panelStatePillDot[kind="error"] {
    background: #ff7474;
}
QLabel#panelStatePillText {
    color: #ffe6a5;
    font-size: 12px;
    font-weight: 800;
}
QFrame#panelStatePill[kind="normal"] QLabel#panelStatePillText {
    color: #bfffdc;
}
QFrame#panelStatePill[kind="error"] QLabel#panelStatePillText {
    color: #ffd1d1;
}

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

QLabel#emptyTitle {
    color: #d5e5ef;
    font-size: 22px;
    font-weight: 900;
}
QLabel#emptyCopy {
    color: #89a7bc;
    font-size: 13px;
}
QLabel#routeHintWarn {
    color: #ffd166;
    font-size: 12px;
    font-weight: 700;
}
QLabel#sourceLine {
    color: #86a7bd;
    font-size: 14px;
    font-weight: 700;
}

QLabel#panelDesc {
    color: #89a7bc;
    font-size: 12px;
}

QFrame#previewBox {
    border-radius: 16px;
    border: 1px solid rgba(66, 221, 146, 0.24);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(12, 26, 36, 0.94), stop:1 rgba(8, 16, 24, 0.98));
}
QLabel#overlaySample {
    background: rgba(0, 0, 0, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    color: #14f2ef;
    font-size: 22px;
    font-weight: 900;
    padding: 12px 14px;
}
QLabel#previewLabel {
    color: #89a7bc;
    font-size: 12px;
    font-weight: 800;
}

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
    image: url({ICONS_DIR}/combobox-chevron-down.svg);
    width: 12px;
    height: 12px;
    margin-right: 6px;
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
QComboBox QAbstractItemView::item {
    background: #111b25;
    color: #eef7ff;
    min-height: 26px;
    padding: 3px 8px;
}
QComboBox QAbstractItemView::item:selected {
    background: rgba(66, 221, 146, 0.22);
    color: #eef7ff;
}
QComboBox QListView {
    background: #111b25;
    border: 1px solid rgba(163, 207, 255, 0.18);
    outline: none;
}
QComboBox QListView::viewport {
    background: #111b25;
    border-radius: 10px;
}

QPlainTextEdit#log {
    background: rgba(5, 9, 13, 0.85);
    color: #7a9db5;
    border: 1px solid rgba(163, 207, 255, 0.08);
    border-radius: 16px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    padding: 12px;
}

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
    image: url({ICONS_DIR}/spinbox-chevron-up.svg);
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url({ICONS_DIR}/spinbox-chevron-down.svg);
    width: 10px;
    height: 10px;
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

QCheckBox {
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
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: rgba(163, 207, 255, 0.22);
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    border: none;
}

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: rgba(163, 207, 255, 0.10);
}

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
QLabel#checkTitle {
    color: #eef7ff;
    font-size: 13px;
    font-weight: 800;
}
QLabel#checkDetail {
    color: #89a7bc;
    font-size: 12px;
}
QLabel#checkTitle[state="error"] {
    color: #ffd1d1;
}
QLabel#checkDetail[state="error"] {
    color: #ffb3b3;
}
QLabel#checkTitle[state="warn"] {
    color: #ffe7ad;
}
QLabel#checkDetail[state="warn"] {
    color: #d9bf78;
}
QLabel#activityTime {
    color: #7e9cb2;
    font-size: 12px;
    min-width: 38px;
}
QLabel#activityText {
    color: #c7dfef;
    font-size: 13px;
}
QLabel#eventDotNormal {
    color: #58e6a4;
    font-size: 14px;
}
QLabel#eventDotWarn {
    color: #ffd166;
    font-size: 14px;
}
QLabel#eventDotError {
    color: #ff7474;
    font-size: 14px;
}
QLabel#eventDotInfo {
    color: #76a9ff;
    font-size: 14px;
}
"""


def apply_theme(app) -> None:
    from PySide6.QtGui import QFont

    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET.replace("{ICONS_DIR}", icons_dir_qss()))
    font = QFont("Segoe UI Variable", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
