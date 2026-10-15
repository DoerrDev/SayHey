import unittest

from gui.log_panel import is_verbose_status


class VerboseStatusTests(unittest.TestCase):
    def test_known_diagnostic_tags_are_verbose(self) -> None:
        for msg in (
            "[typed-tts-raw] msg_type=11 audio_bytes=320",
            "[qwen-tts-evt] response.created",
            "[out-level] 0.0123, bytes=100",
            "[usage] {'response_meta': {}}",
            "[mt-usage] {}",
            "[qwen-realtime-usage] {}",
        ):
            self.assertTrue(is_verbose_status(msg), msg)

    def test_usage_substring_elsewhere_is_not_verbose(self) -> None:
        for msg in (
            "Error: [mt-usage] parse failed",
            "设置已保存",
            "billing-usage] 不是已知标签",
        ):
            self.assertFalse(is_verbose_status(msg), msg)


if __name__ == "__main__":
    unittest.main()
