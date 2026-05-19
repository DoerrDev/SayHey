from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtGui import QIcon

# Ensure app root is on path when running as Nuitka onedir exe
_APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_APP_ROOT))

from gui.app import create_app
from gui.main_window import MainWindow
from gui.theme import apply_theme
from core.settings_store import SettingsStore


def main() -> None:
    app = create_app()
    icon_path = _APP_ROOT / "resource" / "app-icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_theme(app)
    store = SettingsStore()

    window = MainWindow(store)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
