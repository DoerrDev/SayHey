import asyncio
import threading
import unittest
from unittest import mock

import app_core.typed_controller as typed_controller
from app_core.typed_controller import TypedConfig, TypedTranslateCancelled, TypedTranslateController
from app_core.typed_engine import DoubaoTranslateConfig, DoubaoTtsConfig
from core import bridge


def _typed_cfg(**kw) -> TypedConfig:
    base = dict(
        translate=DoubaoTranslateConfig(api_key="k"),
        tts=DoubaoTtsConfig(api_key="k", speaker_id="s"),
        source_language="zh",
        target_language="en",
        auto_tts=True,
    )
    base.update(kw)
    return TypedConfig(**base)


class TypedCancelTests(unittest.TestCase):
    def test_cancel_before_tts_skips_audio(self):
        ctrl = TypedTranslateController(_typed_cfg())

        def fake_translate(*_a, **_k):
            ctrl.request_cancel()
            return "hello"

        ctrl._ensure_sink = mock.Mock()
        with mock.patch.object(typed_controller, "doubao_translate_text", fake_translate):
            with self.assertRaises(TypedTranslateCancelled):
                ctrl.translate_and_send("你好")
        ctrl._ensure_sink.assert_not_called()

    def test_cancel_interrupts_running_tts(self):
        ctrl = TypedTranslateController(_typed_cfg())
        ctrl._ensure_sink = lambda: None
        started = threading.Event()
        cancelled = threading.Event()
        errors = []

        async def endless_tts(*_a, **_k):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        def worker():
            try:
                ctrl.translate_and_send("你好")
            except BaseException as exc:
                errors.append(exc)

        with mock.patch.object(typed_controller, "doubao_translate_text", lambda *a, **k: "hello"), \
                mock.patch.object(typed_controller, "doubao_tts_stream", endless_tts):
            t = threading.Thread(target=worker)
            t.start()
            self.assertTrue(started.wait(2))
            ctrl.request_cancel()
            t.join(2)
        self.assertFalse(t.is_alive())
        self.assertTrue(cancelled.is_set())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], TypedTranslateCancelled)

    def test_cancel_still_raises_when_tts_swallows_cancellation(self):
        ctrl = TypedTranslateController(_typed_cfg())
        ctrl._ensure_sink = lambda: None
        statuses = []
        ctrl.on_status = statuses.append

        async def swallowing_tts(*_a, **_k):
            ctrl.request_cancel()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                return  # returns normally, like wait_for losing the cancel

        with mock.patch.object(typed_controller, "doubao_translate_text", lambda *a, **k: "hello"),                 mock.patch.object(typed_controller, "doubao_tts_stream", swallowing_tts):
            with self.assertRaises(TypedTranslateCancelled):
                ctrl.translate_and_send("你好")
        self.assertNotIn("[typed] TTS 完成", statuses)

    def test_reset_cancel_allows_next_request(self):
        ctrl = TypedTranslateController(_typed_cfg(auto_tts=False))
        results = []
        ctrl.on_result = lambda s, t: results.append(t)
        ctrl.request_cancel()
        ctrl.reset_cancel()
        with mock.patch.object(typed_controller, "doubao_translate_text", lambda *a, **k: "hello"):
            ctrl.translate_and_send("你好")
        self.assertEqual(results, ["hello"])


class _FakeController:
    instances = []

    def __init__(self, *_a, **_k):
        self.stopped = False
        _FakeController.instances.append(self)

    def set_translation_held(self, _held):
        pass

    def request_stop(self):
        self.stopped = True

    async def run(self):
        pass


class EarlyStopRequestTests(unittest.TestCase):
    def _check(self, thread_cls, controller_attr):
        _FakeController.instances.clear()
        with mock.patch.object(bridge, controller_attr, _FakeController):
            t = thread_cls(config=object())
            t.request_stop()  # controller does not exist yet
            t.run()           # run synchronously
        self.assertEqual(len(_FakeController.instances), 1)
        self.assertTrue(_FakeController.instances[0].stopped)

    def test_mic_thread(self):
        self._check(bridge.ControllerThread, "VoiceTranslatorController")

    def test_game_thread(self):
        self._check(bridge.GameSubtitleThread, "GameSubtitleController")


if __name__ == "__main__":
    unittest.main()
