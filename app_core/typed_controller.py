from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app_core.audio_devices import DeviceResolver
from app_core.audio_io import AudioOutputSink
from app_core.qwen_engine import QwenMtConfig, QwenTtsConfig, qwen_mt_translate, qwen_tts_stream
from app_core.typed_engine import (
    DoubaoTranslateConfig,
    DoubaoTtsConfig,
    doubao_translate_text,
    doubao_tts_stream,
)


StatusCallback = Callable[[str], None]
TextCallback = Callable[[str, str], None]  # source, translated

_CANCEL_POLL_SEC = 0.1


class TypedTranslateCancelled(Exception):
    """Raised from translate_and_send() after request_cancel()."""


@dataclass
class TypedConfig:
    translate: DoubaoTranslateConfig
    tts: DoubaoTtsConfig
    source_language: str
    target_language: str
    auto_tts: bool
    cable_input_name: str = "CABLE Input"
    sample_rate: int = 24000
    engine_name: str = "huoshan"
    qwen_mt: Optional[QwenMtConfig] = None
    qwen_tts: Optional[QwenTtsConfig] = None
    hotwords: dict = field(default_factory=dict)


class TypedTranslateController:
    def __init__(self, cfg: TypedConfig, on_status: Optional[StatusCallback] = None,
                 on_result: Optional[TextCallback] = None) -> None:
        self.cfg = cfg
        self.on_status = on_status
        self.on_result = on_result
        self._resolver = DeviceResolver()
        self._sink: Optional[AudioOutputSink] = None
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        """Thread-safe: abort the in-flight translate_and_send() at the next checkpoint."""
        self._cancel.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise TypedTranslateCancelled()

    async def _run_cancellable(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        while not task.done():
            if self._cancel.is_set():
                task.cancel()
                break
            await asyncio.wait({task}, timeout=_CANCEL_POLL_SEC)
        try:
            await task
        except asyncio.CancelledError:
            raise TypedTranslateCancelled() from None
        # The coroutine may swallow the cancellation and return normally (e.g.
        # asyncio.wait_for before 3.12 when recv() completes at the same time).
        self._check_cancel()

    def _emit(self, msg: str) -> None:
        if self.on_status:
            self.on_status(msg)

    def _ensure_sink(self) -> None:
        if self._sink is not None:
            return
        cable = self._resolver.resolve_cable_input(self.cfg.cable_input_name)
        candidates = self._resolver.stable_output_candidates(cable)
        retry_delays = (0.0, 0.3, 0.6, 1.0)
        for attempt, delay in enumerate(retry_delays):
            self._check_cancel()
            if delay > 0:
                self._emit(f"[typed] CABLE 设备繁忙，{int(delay * 1000)}ms 后重试 (#{attempt})")
                time.sleep(delay)
            last_exc: Optional[Exception] = None
            for dev in candidates:
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
                    last_exc = exc
                    sink.stop()
                    self._emit(f"[typed] CABLE 启动失败: {exc}")
            if last_exc is None:
                break
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
        if (
            self.cfg.source_language == self.cfg.target_language
            and self.cfg.source_language not in ("", "auto")
        ):
            translated = text
            self._emit("[typed] 同语言：跳过翻译，直接 TTS")
        elif self.cfg.engine_name == "qwen":
            mt = self.cfg.qwen_mt or QwenMtConfig(api_key="")
            translated = qwen_mt_translate(
                mt, text, self.cfg.source_language, self.cfg.target_language, self._emit,
                hotwords=dict(self.cfg.hotwords or {}),
            )
        else:
            translated = doubao_translate_text(
                self.cfg.translate, text, self.cfg.source_language, self.cfg.target_language, self._emit
            )
        self._check_cancel()
        self._emit(f"[typed] 翻译完成：{translated[:60]}")
        if self.on_result:
            self.on_result(text, translated)
        if not self.cfg.auto_tts:
            return
        self._ensure_sink()

        def on_pcm(chunk: bytes) -> None:
            if self._sink is not None:
                self._sink.write(chunk)

        if self.cfg.engine_name == "qwen":
            tts = self.cfg.qwen_tts or QwenTtsConfig(api_key="")
            asyncio.run(self._run_cancellable(qwen_tts_stream(tts, translated, on_pcm, self._emit)))
        else:
            asyncio.run(self._run_cancellable(doubao_tts_stream(self.cfg.tts, translated, on_pcm, self._emit)))
        self._emit("[typed] TTS 完成")
