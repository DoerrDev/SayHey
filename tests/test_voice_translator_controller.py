import unittest
import json
from pathlib import Path

import numpy as np

from app_core.audio_devices import AudioDevice
from app_core.audio_io import AudioOutputSink, AudioRouteConfig
from app_core.controller import AppConfig, VoiceTranslatorController
from app_core.qwen_engine import QwenLiveTranslateEngine


def _config(simultaneous_interpretation_enabled: bool) -> AppConfig:
    return AppConfig(
        ws_url="ws://example.test",
        api_key="key",
        resource_id="resource",
        source_language="en",
        target_language="zh",
        audio_route=AudioRouteConfig(input_device_index=None, input_device_name=None),
        translated_record_dir=Path("recordings_s2s"),
        speaker_id=None,
        speech_rate=0,
        simultaneous_interpretation_enabled=simultaneous_interpretation_enabled,
    )


class _Sink:
    def __init__(self) -> None:
        self.writes: list[tuple[bytes, int]] = []

    def write(self, pcm_bytes: bytes, segment_id: int = 0) -> None:
        self.writes.append((pcm_bytes, segment_id))


class _Engine:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    async def send_audio(self, pcm_bytes: bytes) -> None:
        self.sent.append(pcm_bytes)


class _Ws:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


class VoiceTranslatorControllerTests(unittest.TestCase):
    def test_passthrough_mode_writes_microphone_audio_directly_to_output_sink(self) -> None:
        controller = VoiceTranslatorController(_config(simultaneous_interpretation_enabled=False))
        sink = _Sink()
        controller.output_sink = sink

        controller._send_audio_from_callback(b"mic-pcm")

        self.assertEqual(sink.writes, [(b"mic-pcm", 0)])

    def test_interpretation_mode_sends_microphone_audio_to_engine(self) -> None:
        controller = VoiceTranslatorController(_config(simultaneous_interpretation_enabled=True))
        engine = _Engine()
        controller.engine = engine

        class _Loop:
            def is_closed(self) -> bool:
                return False

        controller.loop = _Loop()

        futures = []

        def run_now(coroutine, loop):
            futures.append(coroutine)
            try:
                coroutine.send(None)
            except StopIteration:
                pass

        import app_core.controller as controller_module

        original = controller_module.asyncio.run_coroutine_threadsafe
        controller_module.asyncio.run_coroutine_threadsafe = run_now
        try:
            controller._send_audio_from_callback(b"mic-pcm")
        finally:
            controller_module.asyncio.run_coroutine_threadsafe = original

        self.assertEqual(engine.sent, [b"mic-pcm"])
        self.assertEqual(len(futures), 1)

    def test_qwen_s2s_engine_uses_selected_voice(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        cfg.engine_name = "qwen"
        cfg.speaker_id = "Tina"
        controller = VoiceTranslatorController(cfg)

        engine = controller._build_engine()

        self.assertIsInstance(engine, QwenLiveTranslateEngine)
        self.assertEqual(engine.voice, "Tina")

    def test_qwen_s2s_engine_uses_clone_when_voice_is_empty(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        cfg.engine_name = "qwen"
        cfg.speaker_id = ""
        controller = VoiceTranslatorController(cfg)

        engine = controller._build_engine()

        self.assertIsInstance(engine, QwenLiveTranslateEngine)
        self.assertEqual(engine.voice, "default")

    def test_qwen_s2s_session_update_clones_when_voice_is_default(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        ws = _Ws()
        engine = QwenLiveTranslateEngine(api_key="key", mode="s2s")
        engine.config = cfg
        engine.ws = ws

        import asyncio

        asyncio.run(engine._send_session_update())

        message = json.loads(ws.sent[0])
        self.assertEqual(message["session"]["sample_rate"], 16000)
        self.assertEqual(message["session"]["input_audio_format"], "pcm")
        self.assertEqual(message["session"]["output_audio_format"], "pcm")
        self.assertEqual(message["session"]["voice"], "default")
        self.assertTrue(message["session"]["enable_voice_clone"])
        self.assertEqual(message["session"]["voice_clone_options"], {"frequency": "once"})

    def test_qwen_s2s_session_update_uses_selected_preset_voice_without_clone(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        ws = _Ws()
        engine = QwenLiveTranslateEngine(api_key="key", mode="s2s", voice="Tina")
        engine.config = cfg
        engine.ws = ws

        import asyncio

        asyncio.run(engine._send_session_update())

        message = json.loads(ws.sent[0])
        self.assertEqual(message["session"]["voice"], "Tina")
        self.assertNotIn("enable_voice_clone", message["session"])
        self.assertNotIn("voice_clone_options", message["session"])

    def test_qwen_s2s_session_update_uses_precloned_voice_without_new_clone(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        ws = _Ws()
        engine = QwenLiveTranslateEngine(api_key="key", mode="s2s", voice="qwen-translate-vc-demo")
        engine.config = cfg
        engine.ws = ws

        import asyncio

        asyncio.run(engine._send_session_update())

        message = json.loads(ws.sent[0])
        self.assertEqual(message["session"]["voice"], "qwen-translate-vc-demo")
        self.assertTrue(message["session"]["enable_voice_clone"])
        self.assertEqual(message["session"]["voice_clone_options"], {"frequency": "never"})

    def test_qwen_translated_audio_uses_24k_sample_rate(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        cfg.engine_name = "qwen"
        cfg.sample_rate = 16000
        controller = VoiceTranslatorController(cfg)

        self.assertEqual(controller._translated_audio_sample_rate(), 24000)

    def test_huoshan_translated_audio_uses_config_sample_rate(self) -> None:
        cfg = _config(simultaneous_interpretation_enabled=True)
        cfg.engine_name = "huoshan"
        cfg.sample_rate = 16000
        controller = VoiceTranslatorController(cfg)

        self.assertEqual(controller._translated_audio_sample_rate(), 16000)

    def test_audio_output_sink_applies_gain_with_clipping(self) -> None:
        sink = AudioOutputSink(
            device=AudioDevice(0, "out", "host", 0, 2, 48000),
            source_sample_rate=48000,
            output_sample_rate=48000,
            source_channels=1,
            output_channels=1,
            record_dir=Path("."),
            record_wav=False,
            gain=2.0,
        )
        audio = np.array([[1000], [20000], [-20000]], dtype=np.int16)

        amplified = sink._apply_gain(audio)

        self.assertEqual(amplified.tolist(), [[2000], [32767], [-32768]])


if __name__ == "__main__":
    unittest.main()
