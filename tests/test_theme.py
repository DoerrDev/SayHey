import os
import pathlib
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QToolButton

from gui.theme import apply_theme


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_spinbox_arrows_use_local_icon_assets(self) -> None:
        apply_theme(self.app)

        stylesheet = self.app.styleSheet()

        self.assertIn("spinbox-chevron-up.svg", stylesheet)
        self.assertIn("spinbox-chevron-down.svg", stylesheet)

    def test_referenced_svg_files_exist(self) -> None:
        apply_theme(self.app)
        ss = self.app.styleSheet()
        urls = re.findall(r"url\(([^)]+)\)", ss)
        self.assertTrue(urls, "stylesheet should reference at least one url(...)")
        for raw in urls:
            p = pathlib.Path(raw.strip().strip("'\""))
            self.assertTrue(p.exists(), f"missing icon asset: {p}")
            self.assertEqual(p.suffix.lower(), ".svg")

    def test_no_tofu_glyphs_in_buttons(self) -> None:
        apply_theme(self.app)
        from gui.header_bar import HeaderBar
        from gui.game_panel import GameSubtitlePanel
        from gui.mic_panel import MicTranslatePanel

        forbidden = {"⚙", "▶", "◼", "■"}
        widgets = [HeaderBar(), GameSubtitlePanel(), MicTranslatePanel()]
        for root in widgets:
            for btn in root.findChildren(QPushButton) + root.findChildren(QToolButton):
                text = btn.text() or ""
                for ch in forbidden:
                    self.assertNotIn(
                        ch,
                        text,
                        f"{type(root).__name__} button text {text!r} contains forbidden glyph {ch!r}",
                    )


if __name__ == "__main__":
    unittest.main()
