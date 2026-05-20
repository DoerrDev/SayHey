from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_core.audio_devices import DeviceResolver
from app_core.audio_io import AudioRouteVerifier
from gui.icons import icon_path


_STATE_TO_ICON = {
    "ok": "check",
    "warn": "warning",
    "error": "warning",
    "idle": "warning",
}


class _CheckRow(QWidget):
    def __init__(self, title: str, detail: str, button_text: str | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._icon = QLabel()
        self._icon.setFixedSize(22, 22)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self._title = QLabel(title)
        self._title.setObjectName("checkTitle")
        text_col.addWidget(self._title)
        self._detail = QLabel(detail)
        self._detail.setObjectName("checkDetail")
        self._detail.setWordWrap(True)
        text_col.addWidget(self._detail)
        layout.addLayout(text_col, 1)

        self._btn: QPushButton | None = None
        if button_text:
            self._btn = QPushButton(button_text)
            self._btn.setObjectName("secondary")
            self._btn.setFixedHeight(32)
            self._btn.setMinimumWidth(84)
            layout.addWidget(self._btn)

        self.set_state("idle")

    def set_state(self, state: str) -> None:
        pm = QPixmap(str(icon_path(_STATE_TO_ICON.get(state, "warning"))))
        if not pm.isNull():
            self._icon.setPixmap(
                pm.scaled(
                    16,
                    16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._title.setProperty("state", state)
        self._detail.setProperty("state", state)
        for widget in (self._title, self._detail):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def set_content(self, title: str, detail: str, state: str) -> None:
        self._title.setText(title)
        self._detail.setText(detail)
        self.set_state(state)

    def set_button_visible(self, visible: bool) -> None:
        if self._btn is not None:
            self._btn.setVisible(visible)

    @property
    def button(self) -> QPushButton | None:
        return self._btn


class DeviceChecklistPanel(QFrame):
    sig_status = Signal(str)
    sig_summary = Signal(str, str, str)
    sig_test_result = Signal(str)
    sig_test_state_changed = Signal(str)

    def __init__(self, test_state: str = "idle", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._cable_ok = False
        self._test_state = test_state if test_state in {"idle", "ok", "warn", "error"} else "idle"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("设备准备")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self._cable_row = _CheckRow("虚拟声卡检测中", "正在检查 VB-Cable 输入与输出。", "重检")
        if self._cable_row.button:
            self._cable_row.button.clicked.connect(self.check_cable)
        layout.addWidget(self._cable_row)

        self._test_row = _CheckRow("线路尚未测试", "建议开始前先做一次音频连通测试。", "测试")
        if self._test_row.button:
            self._test_row.button.clicked.connect(self.test_cable)
        layout.addWidget(self._test_row)

        self._download_btn = QPushButton("下载 VB-Cable")
        self._download_btn.setObjectName("ghost")
        self._download_btn.setVisible(False)
        self._download_btn.clicked.connect(self._open_download)
        layout.addWidget(self._download_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

        self.sig_test_result.connect(self._update_test_result)
        self._refresh_test_row()
        self.check_cable()

    def summary_state(self) -> tuple[str, str, str]:
        if not self._cable_ok:
            return ("缺少虚拟声卡", "请先安装并配置 VB-Cable，再开始实时字幕。", "error")
        if self._test_state == "error":
            return ("线路测试失败", "请检查游戏输出和 VB-Cable 路由。", "error")
        if self._test_state == "warn":
            return ("设备基本就绪", "已检测到设备，但线路当前偏弱或静音。", "warn")
        if self._test_state == "idle":
            return ("设备基本就绪", "VB-Cable 已就绪，建议先做一次线路测试。", "warn")
        return ("设备已就绪", "VB-Cable 检测通过，线路测试正常。", "normal")

    def _emit_summary(self) -> None:
        self.sig_summary.emit(*self.summary_state())

    def _emit_test_state(self) -> None:
        self.sig_test_state_changed.emit(self._test_state)

    def _refresh_test_row(self) -> None:
        if self._test_state == "ok":
            self._test_row.set_content("线路测试已完成", "已完成首次线路测试，后续无需重复测试。", "ok")
            self._test_row.set_button_visible(False)
            return
        if self._test_state == "warn":
            self._test_row.set_content("线路检测到静音", "已记录本次结果，如需复查可手动再次测试。", "warn")
            self._test_row.set_button_visible(True)
            return
        if self._test_state == "error":
            self._test_row.set_content("线路测试失败", "上次测试失败，建议修正线路后重新测试。", "error")
            self._test_row.set_button_visible(True)
            return
        self._test_row.set_content("线路尚未测试", "建议开始前先做一次音频连通测试。", "warn")
        self._test_row.set_button_visible(True)

    def set_overlay_visible(self, visible: bool) -> None:
        return

    @Slot()
    def check_cable(self) -> None:
        try:
            resolver = DeviceResolver()
            cable_in = resolver.resolve_cable_input()
            cable_out = resolver.resolve_cable_output()
            self._cable_ok = True
            self._cable_row.set_content("虚拟声卡已检测", f"{cable_in.name} -> {cable_out.name}", "ok")
            self._download_btn.setVisible(False)
        except Exception:
            self._cable_ok = False
            self._cable_row.set_content("未找到 VB-Cable", "请安装 VB-Audio Cable 后重新检测。", "error")
            self._download_btn.setVisible(True)
        self._refresh_test_row()
        self._emit_summary()

    def _open_download(self) -> None:
        QDesktopServices.openUrl(QUrl("https://vb-audio.com/Cable/"))

    @Slot()
    def test_cable(self) -> None:
        self._test_state = "idle"
        self._test_row.set_content("正在测试线路", "请确认游戏音频已输出到 CABLE Input。", "idle")
        self._test_row.set_button_visible(False)
        self.sig_status.emit("正在测试 VB-Cable 音频线路...")

        def worker() -> None:
            try:
                resolver = DeviceResolver()
                verifier = AudioRouteVerifier(resolver)
                rms = verifier.verify_vb_cable("CABLE Input", "CABLE Output")
                if rms > 0.01:
                    result = f"VB-Cable 测试通过，电平 {rms:.3f}"
                else:
                    result = f"VB-Cable 检测到静音，电平 {rms:.3f}"
            except Exception as exc:
                result = f"VB-Cable 测试失败：{exc}"
            self.sig_status.emit(result)
            self.sig_test_result.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    @Slot(str)
    def _update_test_result(self, result: str) -> None:
        lowered = result.lower()
        if "通过" in result or "ok" in lowered:
            self._test_state = "ok"
            self._test_row.set_content("线路测试已完成", result, "ok")
            self._test_row.set_button_visible(False)
        elif "静音" in result or "silent" in lowered:
            self._test_state = "warn"
            self._test_row.set_content("线路检测到静音", result, "warn")
            self._test_row.set_button_visible(True)
        else:
            self._test_state = "error"
            self._test_row.set_content("线路测试失败", result, "error")
            self._test_row.set_button_visible(True)
        self._emit_test_state()
        self._emit_summary()
