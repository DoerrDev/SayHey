from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.version import __version__


def create_app() -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SayHey")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("SayHey")
    return app
