import logging
import tempfile
import unittest
from pathlib import Path

from core.runtime_log import RuntimeLogWriter


class RuntimeLogWriterTests(unittest.TestCase):
    def test_lines_are_written_after_close(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "logs" / "runtime.log"
            writer = RuntimeLogWriter(path)
            writer.write("[12:00] hello")
            writer.write("[12:01] 你好")
            writer.close()
            self.assertEqual(path.read_text(encoding="utf-8"), "[12:00] hello\n[12:01] 你好\n")
            writer.write("ignored after close")

    def test_file_rotates_at_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "runtime.log"
            writer = RuntimeLogWriter(path, max_bytes=200, backup_count=2)
            for i in range(50):
                writer.write(f"line {i:03d} " + "x" * 20)
            writer.close()
            self.assertLessEqual(path.stat().st_size, 200)
            self.assertTrue(path.with_name("runtime.log.1").exists())
            self.assertTrue(path.with_name("runtime.log.2").exists())
            self.assertFalse(path.with_name("runtime.log.3").exists())
            self.assertIn("line 049", path.read_text(encoding="utf-8"))

    def test_recreating_writer_reuses_logger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "runtime.log"
            old = RuntimeLogWriter(path)
            registered = len(logging.Logger.manager.loggerDict)
            new = RuntimeLogWriter(path)
            self.assertEqual(len(logging.Logger.manager.loggerDict), registered)

            old.write("from old")  # superseded: dropped
            old.close()            # must not detach the new writer
            new.write("from new")
            new.close()
            self.assertEqual(path.read_text(encoding="utf-8"), "from new\n")


if __name__ == "__main__":
    unittest.main()
