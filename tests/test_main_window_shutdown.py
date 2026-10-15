import unittest
from unittest import mock

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow

from gui.main_window import MainWindow


class _Window(MainWindow):
    """MainWindow with only the state the shutdown path touches."""

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        self._shutdown_threads = None
        self._shutdown_timer = None
        self._shutdown_complete = False
        self._restart_mic_after_stop = False
        self._mic_thread = None
        self._game_thread = None
        self._typed_thread = None
        self._typed_controller = None
        self._overlay = mock.Mock()
        self._float_input = mock.Mock()
        self._hotkeys = mock.Mock()
        self._usage_tracker = mock.Mock()
        self.close_events = []

    def closeEvent(self, event) -> None:
        self.close_events.append(self._shutdown_complete)
        super().closeEvent(event)


class ShutdownWithoutThreadsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_close_completes_in_a_second_close_event(self) -> None:
        w = _Window()
        w.show()
        with mock.patch.object(self.app, "quit") as quit_mock, \
                mock.patch("gui.main_window.close_runtime_log"):
            w.close()
            # First phase only: _finish_shutdown must not run inside closeEvent.
            self.assertEqual(w.close_events, [False])
            self.assertFalse(w._shutdown_complete)

            for _ in range(50):
                self.app.processEvents()
                if w._shutdown_complete:
                    break
        self.assertTrue(w._shutdown_complete)
        self.assertEqual(w.close_events, [False, True])
        w._usage_tracker.flush.assert_called_once()
        quit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
