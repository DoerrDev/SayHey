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
from core.default_mic_switcher import DefaultMicSwitcher


def main() -> None:
    app = create_app()
    icon_path = _APP_ROOT / "resource" / "app-icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_theme(app)
    store = SettingsStore()

    settings = store.get()
    mic_switcher = DefaultMicSwitcher(keyword=settings.auto_switch_mic_keyword)
    mic_switcher.recover_from_crash()
    switched_to: str | None = None
    if settings.auto_switch_default_mic:
        switched_to = mic_switcher.switch()
    app.aboutToQuit.connect(mic_switcher.restore)

    window = MainWindow(store)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    if switched_to:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QMessageBox
        QTimer.singleShot(0, lambda: QMessageBox.information(
            window,
            "默认麦克风已切换",
            f"已自动将系统默认麦克风切换为：\n\n  {switched_to}\n\n"
            f"软件关闭时会自动恢复。\n如不需要此功能，请在「设置 → 音频设备 → 默认麦克风切换」中关闭。",
        ))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
