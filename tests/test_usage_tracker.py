import json
import tempfile
import time
import unittest
from unittest import mock
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

    def test_record_defers_save_until_flush(self) -> None:
        line = "[qwen-mt-usage] {'input_tokens': 4, 'output_tokens': 6}"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "usage.json"
            tracker = UsageTracker(path, save_delay=60)
            tracker.feed_log_line(line)
            tracker.feed_log_line(line)
            self.assertFalse(path.exists())

            tracker.flush()
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["total_events"], 2)
            self.assertEqual(len(data["events"]), 2)
            self.assertFalse(path.with_name("usage.json.tmp").exists())

            reloaded = UsageTracker(path)
            self.assertEqual(reloaded.state.total_tokens, 20)

    def test_save_timer_writes_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "usage.json"
            tracker = UsageTracker(path, save_delay=0.05)
            tracker.feed_log_line("[qwen-mt-usage] {'input_tokens': 4}")
            for _ in range(100):
                if path.exists():
                    break
                time.sleep(0.02)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["total_events"], 1)
            tracker.flush()

    def test_failed_save_is_retried(self) -> None:
        import core.usage_tracker as usage_tracker

        real_replace = usage_tracker.os.replace
        calls = []

        def flaky_replace(src, dst):
            calls.append(dst)
            if len(calls) == 1:
                raise PermissionError("file locked")
            real_replace(src, dst)

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "usage.json"
            tracker = UsageTracker(path, save_delay=0.05)
            with mock.patch.object(usage_tracker.os, "replace", flaky_replace):
                tracker.feed_log_line("[qwen-mt-usage] {'input_tokens': 4}")
                for _ in range(100):
                    if path.exists():
                        break
                    time.sleep(0.02)
            self.assertEqual(len(calls), 2)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["total_events"], 1)
            tracker.flush()


if __name__ == "__main__":
    unittest.main()
