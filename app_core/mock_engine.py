from __future__ import annotations

import asyncio
import math

import numpy as np

from app_core.translator import TranslatorConfig, TranslatorEvent, TranslatorEventCallback


class MockTranslatorEngine:
    def __init__(self) -> None:
        self.on_event: TranslatorEventCallback | None = None
        self.config: TranslatorConfig | None = None
        self.audio_chunks = 0
        self.audio_segment_id = 0

    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        self.config = config
        self.on_event = on_event
        on_event(TranslatorEvent(type="status", message="[mock] session started"))

    async def send_audio(self, pcm_bytes: bytes) -> None:
        self.audio_chunks += 1
        if self.on_event is None or self.config is None:
            return
        if self.audio_chunks % 12 != 0:
            return

        self.on_event(TranslatorEvent(type="source_text", text="mock source speech."))
        self.on_event(TranslatorEvent(type="translated_text", text="mock translated speech."))
        self.audio_segment_id += 1
        self.on_event(
            TranslatorEvent(
                type="translated_audio",
                data=self._tone(self.config.sample_rate),
                segment_id=self.audio_segment_id,
            )
        )
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self.on_event:
            self.on_event(TranslatorEvent(type="status", message="[mock] session finished"))

    def _tone(self, sample_rate: int) -> bytes:
        frames = int(sample_rate * 0.35)
        t = np.arange(frames) / sample_rate
        audio = (0.18 * np.sin(2 * math.pi * 660 * t) * np.iinfo(np.int16).max).astype(np.int16)
        return audio.tobytes()
