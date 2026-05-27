from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app_core.controller import load_env_file
from app_core.huoshan_s2t_engine import HuoshanS2TSubtitleEngine
from app_core.qwen_engine import QwenLiveTranslateEngine
from app_core.system_audio import SystemAudioCapture
from app_core.translator import TranslatorConfig, TranslatorEvent


StatusCallback = Callable[[str], None]
SubtitleCallback = Callable[[str, str], None]


@dataclass
class GameSubtitleConfig:
    ws_url: str
    api_key: str
    resource_id: str
    source_language: str
    target_language: str = "zh"
    audio_device_name: Optional[str] = None
    sample_rate: int = 16000
    source_sample_rate: int = 48000
    chunk_ms: int = 80
    engine_name: str = "huoshan_s2t"
    hotwords: dict = field(default_factory=dict)


class GameSubtitleController:
    def __init__(
        self,
        config: GameSubtitleConfig,
        on_status: Optional[StatusCallback] = None,
        on_subtitle: Optional[SubtitleCallback] = None,
    ) -> None:
        self.config = config
        self.on_status = on_status
        self.on_subtitle = on_subtitle
        self.engine = None
        self.capture: Optional[SystemAudioCapture] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.run_task: Optional[asyncio.Task] = None
        self.stop_event = threading.Event()
        self.runtime_error: Optional[str] = None
        self.latency_trace_id = 0
        self.pending_speech_start: Optional[float] = None
        self.pending_first_text = False

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.run_task = asyncio.current_task()
        try:
            if self.config.engine_name == "qwen":
                self.engine = QwenLiveTranslateEngine(
                    api_key=self.config.api_key,
                    mode="s2t",
                    realtime_url=self.config.ws_url,
                )
            else:
                self.engine = HuoshanS2TSubtitleEngine(
                    ws_url=self.config.ws_url,
                    api_key=self.config.api_key,
                    resource_id=self.config.resource_id,
                )
            await self.engine.start(
                TranslatorConfig(
                    source_language=self.config.source_language,
                    target_language=self.config.target_language,
                    sample_rate=self.config.sample_rate,
                    hotwords=dict(self.config.hotwords or {}),
                ),
                self._handle_engine_event,
            )
            self.capture = SystemAudioCapture(
                device_name=self.config.audio_device_name,
                source_sample_rate=self.config.source_sample_rate,
                target_sample_rate=self.config.sample_rate,
                chunk_ms=self.config.chunk_ms,
                on_audio=self._send_audio_from_callback,
                on_status=self._emit_status,
                on_speech_start=self._handle_speech_start,
                on_error=self._handle_capture_error,
            )
            self.capture.start()
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        self.stop_event.set()
        if self.capture is not None:
            self.capture.stop()
            self.capture = None
        if self.engine is not None:
            await self.engine.stop()
            self.engine = None

    def request_stop(self) -> None:
        self.stop_event.set()
        if self.loop is not None and not self.loop.is_closed() and self.run_task is not None:
            try:
                self.loop.call_soon_threadsafe(self.run_task.cancel)
            except RuntimeError:
                return

    def _send_audio_from_callback(self, pcm_bytes: bytes) -> None:
        if self.loop is None or self.engine is None or self.loop.is_closed():
            return
        coroutine = self.engine.send_audio(pcm_bytes)
        try:
            asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        except RuntimeError:
            coroutine.close()

    def _handle_engine_event(self, event: TranslatorEvent) -> None:
        if event.type == "status":
            self._emit_status(event.message)
        elif event.type == "error":
            self.runtime_error = event.message
            self._emit_status(f"Error: {event.message}")
            self.request_stop()
        elif event.type == "source_text":
            if self.on_subtitle:
                self.on_subtitle("source", event.text)
        elif event.type == "translated_text":
            self._handle_first_text_latency()
            if self.on_subtitle:
                self.on_subtitle("translation", event.text)

    def _handle_capture_error(self, exc: Exception) -> None:
        self.runtime_error = str(exc)
        self._emit_status(f"Game audio capture error: {exc}")
        self.request_stop()

    def _handle_speech_start(self, timestamp: float) -> None:
        self.latency_trace_id += 1
        self.pending_speech_start = timestamp
        self.pending_first_text = False
        self._emit_status(f"[game-latency] trace={self.latency_trace_id} audio-speech-start")

    def _handle_first_text_latency(self) -> None:
        if self.pending_speech_start is None or self.pending_first_text:
            return
        self.pending_first_text = True
        elapsed_ms = int((time.monotonic() - self.pending_speech_start) * 1000)
        self._emit_status(f"[game-latency] trace={self.latency_trace_id} audio_to_text={elapsed_ms}ms")

    def _emit_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)


_DEFAULT_VOLC_WS_URL = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"


def build_game_subtitle_config(env_path: Path) -> GameSubtitleConfig:
    load_env_file(env_path)
    engine_global = os.environ.get("TRANSLATOR_ENGINE", "huoshan").strip().lower()
    if engine_global == "qwen":
        api_key = os.environ.get("QWEN_API_KEY", "").strip()
        engine_name = "qwen"
        ws_url = os.environ.get("QWEN_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime").strip()
    else:
        api_key = os.environ.get("VOLC_APP_KEY", "").strip() or os.environ.get("VOLC_API_KEY", "").strip()
        engine_name = os.environ.get("GAME_SUBTITLE_ENGINE", "huoshan_s2t").strip()
        ws_url = os.environ.get("VOLC_WS_URL", "").strip() or _DEFAULT_VOLC_WS_URL
    return GameSubtitleConfig(
        ws_url=ws_url,
        api_key=api_key,
        resource_id=os.environ.get("VOLC_RESOURCE_ID", "volc.service_type.10053").strip(),
        source_language=os.environ.get("GAME_SUBTITLE_SOURCE_LANGUAGE", "en").strip(),
        target_language=os.environ.get("GAME_SUBTITLE_TARGET_LANGUAGE", "zh").strip(),
        audio_device_name=os.environ.get("GAME_AUDIO_DEVICE_NAME", "").strip() or None,
        chunk_ms=int(os.environ.get("GAME_SUBTITLE_CHUNK_MS", "80").strip()),
        engine_name=engine_name,
    )
