import unittest
from pathlib import Path

from app_core.audio_io import AudioRouteConfig
from app_core.controller import AppConfig, VoiceTranslatorController


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


if __name__ == "__main__":
    unittest.main()
