from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


class _Downloader(QObject):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, dst: str) -> None:
        super().__init__()
        self.url = url
        self.dst = dst

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                self.url, headers={"User-Agent": "SayHey-Updater"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                total = int(r.headers.get("Content-Length", "0"))
                received = 0
                with open(self.dst, "wb") as f:
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                        self.progress.emit(received, total)
            self.done.emit(self.dst)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, info, parent=None) -> None:
        super().__init__(parent)
        self.info = info
        self.setWindowTitle(f"发现新版本 {info.latest_tag}")
        self.resize(580, 460)
        v = QVBoxLayout(self)
        header = QLabel(
            f"<b>{info.name or info.latest_tag}</b>  "
            f"<span style='color:#888'>来源: {info.source}</span>"
        )
        v.addWidget(header)
        nb = QTextBrowser()
        nb.setMarkdown(info.notes or "(无说明)")
        nb.setOpenExternalLinks(True)
        v.addWidget(nb)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        v.addWidget(self.progress)
        self.btn = QPushButton("立即升级")
        v.addWidget(self.btn)
        self.btn.clicked.connect(self._start)

    def _start(self) -> None:
        if not self.info.zip_url:
            QMessageBox.warning(self, "升级", "未找到下载包，请稍后再试")
            return
        tmp_dir = Path(tempfile.gettempdir()) / "sayhey_update"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        safe_tag = "".join(c for c in self.info.latest_tag if c.isalnum() or c in "._-")
        tmp_zip = tmp_dir / f"{safe_tag or 'update'}.zip"
        self.progress.setVisible(True)
        self.btn.setEnabled(False)
        self.btn.setText("下载中...")
        self._t = QThread()
        self._d = _Downloader(self.info.zip_url, str(tmp_zip))
        self._d.moveToThread(self._t)
        self._t.started.connect(self._d.run)
        self._d.progress.connect(self._on_progress)
        self._d.done.connect(self._on_done)
        self._d.failed.connect(self._on_failed)
        self._t.start()

    def _on_progress(self, recv: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(recv)
        else:
            self.progress.setRange(0, 0)

    def _on_failed(self, msg: str) -> None:
        QMessageBox.critical(self, "下载失败", msg)
        self.btn.setEnabled(True)
        self.btn.setText("立即升级")
        self.progress.setVisible(False)

    def _on_done(self, zip_path: str) -> None:
        if QMessageBox.question(
            self, "升级", "下载完成。即将关闭软件以进行升级，确认？"
        ) != QMessageBox.Yes:
            self.btn.setEnabled(True)
            self.btn.setText("立即升级")
            return
        exe = Path(sys.executable)
        exe_dir = exe.parent
        updater = exe_dir / "updater.exe"
        if not updater.exists():
            QMessageBox.critical(
                self,
                "升级",
                f"未找到 {updater}\n请前往官网下载完整包重装一次。",
            )
            return
        creationflags = 0x00000008 if os.name == "nt" else 0
        subprocess.Popen(
            [
                str(updater),
                "--zip", zip_path,
                "--target", str(exe_dir),
                "--restart", str(exe),
                "--pid", str(os.getpid()),
            ],
            creationflags=creationflags,
            close_fds=True,
        )
        QApplication.quit()
