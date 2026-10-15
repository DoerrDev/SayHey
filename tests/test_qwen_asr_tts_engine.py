import asyncio
import unittest
from unittest.mock import patch

from app_core import qwen_engine
from app_core.qwen_engine import QwenAsrTtsEngine


def _run(coro):
    return asyncio.run(coro)


class QwenAsrTtsEngineTests(unittest.TestCase):
    def _engine_with_events(self):
        engine = QwenAsrTtsEngine(api_key="key")
        events = []
        engine.on_event = events.append
        return engine, events

    def test_sentences_are_synthesized_and_emitted_in_order(self) -> None:
        engine, events = self._engine_with_events()
        started = []

        async def fake_tts(cfg, text, on_pcm, on_status=None):
            started.append(text)
            # 第一句合成得比第二句慢，若并发会导致 B 的音频插在 A 中间。
            delay = 0.03 if text == "A" else 0.0
            on_pcm(f"{text}1".encode())
            await asyncio.sleep(delay)
            on_pcm(f"{text}2".encode())

        async def scenario():
            engine.tts_queue = asyncio.Queue(maxsize=4)
            engine.tts_task = asyncio.create_task(engine._tts_loop())
            engine._enqueue_tts("A", 1)
            engine._enqueue_tts("B", 2)
            await asyncio.sleep(0.1)
            engine.tts_queue.put_nowait(None)
            await asyncio.wait_for(engine.tts_task, timeout=1)

        with patch.object(qwen_engine, "qwen_tts_stream", fake_tts):
            _run(scenario())

        audio = [(e.data.decode(), e.segment_id) for e in events if e.type == "translated_audio"]
        self.assertEqual(started, ["A", "B"])
        self.assertEqual(audio, [("A1", 1), ("A2", 1), ("B1", 2), ("B2", 2)])

    def test_queue_overflow_drops_oldest_sentence(self) -> None:
        engine, events = self._engine_with_events()

        async def scenario():
            engine.tts_queue = asyncio.Queue(maxsize=2)
            engine._enqueue_tts("A", 1)
            engine._enqueue_tts("B", 2)
            engine._enqueue_tts("C", 3)
            items = []
            while not engine.tts_queue.empty():
                items.append(engine.tts_queue.get_nowait())
            return items

        items = _run(scenario())
        self.assertEqual(items, [("B", 2), ("C", 3)])
        self.assertEqual(engine.dropped_tts_sentences, 1)
        self.assertTrue(any("[qwen-tts-drop]" in e.message for e in events if e.type == "status"))

    def test_tts_failure_does_not_stop_later_sentences(self) -> None:
        engine, events = self._engine_with_events()

        async def fake_tts(cfg, text, on_pcm, on_status=None):
            if text == "A":
                raise RuntimeError("boom")
            on_pcm(text.encode())

        async def scenario():
            engine.tts_queue = asyncio.Queue(maxsize=4)
            engine.tts_task = asyncio.create_task(engine._tts_loop())
            engine._enqueue_tts("A", 1)
            engine._enqueue_tts("B", 2)
            engine.tts_queue.put_nowait(None)
            await asyncio.wait_for(engine.tts_task, timeout=1)

        with patch.object(qwen_engine, "qwen_tts_stream", fake_tts):
            _run(scenario())

        self.assertEqual([e.data for e in events if e.type == "translated_audio"], [b"B"])
        self.assertTrue(any("qwen tts failed" in e.message for e in events if e.type == "error"))

    def test_stop_cancels_tts_worker_and_clears_queue(self) -> None:
        engine, _ = self._engine_with_events()

        async def fake_tts(cfg, text, on_pcm, on_status=None):
            await asyncio.sleep(10)

        async def scenario():
            engine.tts_queue = asyncio.Queue(maxsize=4)
            engine.tts_task = asyncio.create_task(engine._tts_loop())
            engine._enqueue_tts("A", 1)
            await asyncio.sleep(0)
            task = engine.tts_task
            await asyncio.wait_for(engine.stop(), timeout=1)
            return task

        with patch.object(qwen_engine, "qwen_tts_stream", fake_tts):
            task = _run(scenario())

        self.assertTrue(task.cancelled())
        self.assertIsNone(engine.tts_task)
        self.assertIsNone(engine.tts_queue)


if __name__ == "__main__":
    unittest.main()
