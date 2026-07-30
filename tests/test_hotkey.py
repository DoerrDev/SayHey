import unittest

from PySide6.QtWidgets import QApplication

from core.hotkey import HoldHotkeyMonitor, parse_hold_hotkey


class HoldHotkeyTests(unittest.TestCase):
    def test_parses_keyboard_combo(self) -> None:
        self.assertEqual(parse_hold_hotkey("ctrl+space"), (0x0002, 0x20))

    def test_parses_mouse_side_buttons(self) -> None:
        self.assertEqual(parse_hold_hotkey("mouse4"), (0, 0x05))
        self.assertEqual(parse_hold_hotkey("shift+mouse5"), (0x0004, 0x06))

    def test_monitor_emits_press_and_release_once_per_edge(self) -> None:
        app = QApplication.instance() or QApplication([])
        monitor = HoldHotkeyMonitor()
        events = []
        down = False
        monitor._binding = (0, 0x20)
        monitor._on_pressed = lambda: events.append("pressed")
        monitor._on_released = lambda: events.append("released")
        monitor._key_down = lambda _vk: down

        monitor._poll()
        down = True
        monitor._poll()
        monitor._poll()
        down = False
        monitor._poll()

        self.assertEqual(events, ["pressed", "released"])
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
