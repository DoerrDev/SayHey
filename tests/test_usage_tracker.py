import tempfile
import unittest
from pathlib import Path

from core.usage_tracker import extract_event, UsageTracker


class UsageTrackerTests(unittest.TestCase):
    def test_qwen_realtime_usage_records_raw_tokens_without_cost(self) -> None:
        ev = extract_event("qwen-realtime", {
            "input_tokens": 10,
            "output_tokens": 20,
            "input_tokens_details": {"text_tokens": 3, "audio_tokens": 7},
            "output_tokens_details": {"text_tokens": 5, "audio_tokens": 15},
        })

        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.provider, "qwen")
        self.assertEqual(ev.cost, 0.0)
        self.assertEqual(ev.tokens, {
            "input_text_tokens": 3.0,
            "input_audio_tokens": 7.0,
            "output_text_tokens": 5.0,
            "output_audio_tokens": 15.0,
        })

    def test_tracker_parses_qwen_tts_usage_line(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tracker = UsageTracker(Path(d) / "usage.json")
            tracker.feed_log_line(
                "[qwen-tts-usage] {'input_tokens': 4, 'output_tokens': 6, "
                "'input_tokens_details': {'text_tokens': 4}, "
                "'output_tokens_details': {'audio_tokens': 6}}"
            )

            self.assertEqual(tracker.state.session_tokens, 10)
            self.assertEqual(tracker.state.total_tokens, 10)
            self.assertEqual(tracker.state.total_cost, 0.0)
            self.assertEqual(tracker.state.events[0].source, "qwen-tts")


if __name__ == "__main__":
    unittest.main()
