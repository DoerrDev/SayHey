from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter

_ICON_DIR = Path(__file__).resolve().parent.parent / "resource" / "icons"
BRAND = "#42dd92"


def _render(name: str, color: str, size: int) -> QPixmap:
    path = _ICON_DIR / f"{name}.svg"
    data = path.read_bytes().replace(b"currentColor", color.encode())
    renderer = QSvgRenderer(QByteArray(data))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def icon(name: str, color: str = BRAND, size: int = 20) -> QIcon:
    return QIcon(_render(name, color, size))
