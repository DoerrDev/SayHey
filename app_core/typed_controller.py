from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app_core.audio_devices import DeviceResolver
from app_core.audio_io import AudioOutputSink
from app_core.typed_engine import (
    DoubaoTranslateConfig,
    DoubaoTtsConfig,
    doubao_translate_text,
    doubao_tts_stream,
)


StatusCallback = Callable[[str], None]
TextCallback = Callable[[str, str], None]  # source, translated


@dataclass
class TypedConfig:
    translate: DoubaoTranslateConfig
    tts: DoubaoTtsConfig
    source_language: str
    target_language: str
    auto_tts: bool
    cable_input_name: str = "CABLE Input"
    sample_rate: int = 24000


class TypedTranslateController:
    def __init__(self, cfg: TypedConfig, on_status: Optional[StatusCallback] = None,
                 on_result: Optional[TextCallback] = None) -> None:
        self.cfg = cfg
        self.on_status = on_status
        self.on_result = on_result
        self._resolver = DeviceResolver()
        self._sink: Optional[AudioOutputSink] = None

    def _emit(self, msg: str) -> None:
        if self.on_status:
            self.on_status(msg)

    def _ensure_sink(self) -> None:
        if self._sink is not None:
            return
        cable = self._resolver.resolve_cable_input(self.cfg.cable_input_name)
        for dev in self._resolver.stable_output_candidates(cable):
            sink = AudioOutputSink(
                device=dev,
                source_sample_rate=self.cfg.sample_rate,
                output_sample_rate=int(dev.default_samplerate),
                source_channels=1,
                output_channels=min(2, dev.max_output_channels),
                record_dir=Path("."),
                record_wav=False,
                on_status=self._emit,
            )
            try:
                sink.start()
                self._sink = sink
                self._emit(f"[typed] CABLE 输出已就绪: #{dev.index} {dev.name}")
                return
            except Exception as exc:
                sink.stop()
                self._emit(f"[typed] CABLE 启动失败: {exc}")
        raise RuntimeError("无法打开 CABLE Input 输出")

    def close(self) -> None:
        if self._sink is not None:
            try:
                self._sink.stop()
            except Exception:
                pass
            self._sink = None

    def translate_and_send(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._emit(f"[typed] 翻译开始：{text[:60]}")
        translated = doubao_translate_text(
            self.cfg.translate, text, self.cfg.source_language, self.cfg.target_language
        )
        self._emit(f"[typed] 翻译完成：{translated[:60]}")
        if self.on_result:
            self.on_result(text, translated)
        if not self.cfg.auto_tts:
            return
        self._ensure_sink()

        def on_pcm(chunk: bytes) -> None:
            if self._sink is not None:
                self._sink.write(chunk)

        asyncio.run(doubao_tts_stream(self.cfg.tts, translated, on_pcm, self._emit))
        self._emit("[typed] TTS 完成")
