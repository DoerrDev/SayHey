from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

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
