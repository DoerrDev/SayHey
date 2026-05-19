from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
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


class _CheckRow(QWidget):
    def __init__(self, dot_name: str, text: str, btn_text: str | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setObjectName(dot_name)
        self._dot.setFixedWidth(20)
        layout.addWidget(self._dot)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setObjectName("routeLabel")
        layout.addWidget(self._label, 1)

        self._btn: QPushButton | None = None
        if btn_text:
            self._btn = QPushButton(btn_text)
            self._btn.setObjectName("ghost")
            self._btn.setFixedWidth(100)
            layout.addWidget(self._btn)

    def set_dot(self, name: str) -> None:
        self._dot.setObjectName(name)
        self._dot.setStyleSheet("")  # force QSS re-evaluation
        self._dot.style().polish(self._dot)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    @property
    def button(self) -> QPushButton | None:
        return self._btn


class DeviceChecklistPanel(QFrame):
    sig_status = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("设备准备")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self._cable_row = _CheckRow("dotGray", "VB-Cable 未检测", "重新检测")
        layout.addWidget(self._cable_row)
        if self._cable_row.button:
            self._cable_row.button.clicked.connect(self.check_cable)

        self._download_row = _CheckRow("dotOrange", "需要安装 VB-Audio Cable 虚拟声卡", "打开下载页")
        layout.addWidget(self._download_row)
        if self._download_row.button:
            self._download_row.button.clicked.connect(self._open_download)

        self._test_row = _CheckRow("dotGray", "线路测试 未执行", "测试线路")
        layout.addWidget(self._test_row)
        if self._test_row.button:
            self._test_row.button.clicked.connect(self.test_cable)

        layout.addStretch()
        self.check_cable()

    def check_cable(self) -> None:
        try:
            resolver = DeviceResolver()
            cable_in = resolver.resolve_cable_input()
            cable_out = resolver.resolve_cable_output()
            self._cable_row.set_dot("dotGreen")
            self._cable_row.set_text(f"VB-Cable OK: {cable_in.name} → {cable_out.name}")
            self._download_row.setVisible(False)
        except Exception:
            self._cable_row.set_dot("dotRed")
            self._cable_row.set_text("VB-Cable 未找到，请安装后点击重新检测")
            self._download_row.setVisible(True)
            self._download_row.set_dot("dotOrange")
            self._download_row.set_text("需要安装 VB-Audio Cable 虚拟声卡")

    def _open_download(self) -> None:
        QDesktopServices.openUrl(QUrl("https://vb-audio.com/Cable/"))

    def test_cable(self) -> None:
        self._test_row.set_dot("dotGray")
        self._test_row.set_text("线路测试中...")
        self.sig_status.emit("Testing VB-Cable route...")

        def worker() -> None:
            try:
                resolver = DeviceResolver()
                verifier = AudioRouteVerifier(resolver)
                rms = verifier.verify_vb_cable("CABLE Input", "CABLE Output")
                if rms > 0.01:
                    msg = f"VB-Cable OK (level {rms:.3f})"
                else:
                    msg = f"VB-Cable silent (level {rms:.3f})"
            except Exception as exc:
                msg = f"Cable test failed: {exc}"
            self.sig_status.emit(msg)
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self,
                "_update_test_result",
                Qt.ConnectionType.QueuedConnection,
                msg,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _update_test_result(self, msg: str) -> None:
        if "OK" in msg:
            self._test_row.set_dot("dotGreen")
        elif "silent" in msg.lower():
            self._test_row.set_dot("dotOrange")
        else:
            self._test_row.set_dot("dotRed")
        self._test_row.set_text(msg)
