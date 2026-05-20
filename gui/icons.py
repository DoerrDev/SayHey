from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

_ICONS_DIR = Path(__file__).resolve().parent.parent / "resource" / "icons"


def icons_dir() -> Path:
    return _ICONS_DIR


def icons_dir_qss() -> str:
    return str(_ICONS_DIR).replace("\\", "/")


def icon_path(name: str) -> Path:
    if not name.endswith(".svg"):
        name = name + ".svg"
    return _ICONS_DIR / name


def resource_icon(name: str) -> QIcon:
    p = icon_path(name)
    return QIcon(str(p)) if p.exists() else QIcon()


def resource_pixmap(name: str, width: int, height: int | None = None) -> QPixmap:
    pixmap = QPixmap(str(icon_path(name)))
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        width,
        height or width,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
