from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app_core.audio_devices import AudioDevice, DeviceResolver
from app_core.audio_io import AudioInputSource, AudioOutputSink, AudioRouteConfig
from app_core.mock_engine import MockTranslatorEngine
from app_core.rvc_client import RvcConfig, RvcModel, RvcSidecarManager
from app_core.translator import TranslatorConfig, TranslatorEvent
from app_core.volc_engine import VolcAstS2SEngine


StatusCallback = Callable[[str], None]
TextCallback = Callable[[str], None]


@dataclass
class AppConfig:
    ws_url: str
    api_key: str
    resource_id: str
    source_language: str
    target_language: str
    audio_route: AudioRouteConfig
    translated_record_dir: Path
    speaker_id: Optional[str]
    speech_rate: int
    simultaneous_interpretation_enabled: bool = True
    chunk_ms: int = 80
    sample_rate: int = 16000
    output_channels: int = 2
    engine_name: str = "huoshan"
    rvc: Optional[RvcConfig] = None
    rvc_model: Optional[RvcModel] = None


class VoiceTranslatorController:
    def __init__(
        self,
        config: AppConfig,
        on_status: Optional[StatusCallback] = None,
        on_source: Optional[TextCallback] = None,
        on_translation: Optional[TextCallback] = None,
    ) -> None:
        self.config = config
        self.on_status = on_status
        self.on_source = on_source
        self.on_translation = on_translation
        self.resolver = DeviceResolver()
        self.input_source: Optional[AudioInputSource] = None
        self.output_sink: Optional[AudioOutputSink] = None
        self.engine = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.run_task: Optional[asyncio.Task] = None
        self.stop_event = threading.Event()
        self.runtime_error: Optional[str] = None
        self.latency_trace_id = 0
        self.pending_speech_start: Optional[float] = None
        self.pending_tts_first: Optional[float] = None
        self.pending_output_first = False
        self.latest_audio_segment_id = 0
        self.trace_min_segment_id = 0
        self.latency_segment_id = 0
        self.pending_trace_audio_bytes = 0
        self.latency_grace_seconds = 0.65
        self.rvc_manager: Optional[RvcSidecarManager] = None
        self._rvc_chunk_bytes = 0

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.run_task = asyncio.current_task()

        try:
            mic_device = self.resolver.resolve_input(
                self.config.audio_route.input_device_index,
                self.config.audio_route.input_device_name,
            )
            mic_candidates = self.resolver.stable_input_candidates(mic_device)
            out_idx = self.config.audio_route.output_device_index
            if out_idx is not None and 0 <= int(out_idx) < len(self.resolver.devices):
                cable_input = self.resolver.get(int(out_idx))
            else:
                cable_input = self.resolver.resolve_cable_input(self.config.audio_route.output_device_name)
            self._emit_status(
                f"Input #{mic_device.index} {mic_device.name} ({int(mic_device.default_samplerate)} Hz) -> "
                f"Output #{cable_input.index} {cable_input.name} ({int(cable_input.default_samplerate)} Hz)"
            )

            cable_candidates = self.resolver.stable_output_candidates(cable_input)
            self.output_sink = self._start_output_with_fallback(cable_candidates)

            if (
                not self.config.simultaneous_interpretation_enabled
                and self.config.rvc is not None
                and self.config.rvc.enabled
                and self.config.rvc_model is not None
            ):
                self._start_rvc()

            if self.config.simultaneous_interpretation_enabled:
                self.engine = self._build_engine()
                await self.engine.start(
                    TranslatorConfig(
                        source_language=self.config.source_language,
                        target_language=self.config.target_language,
                        sample_rate=self.config.sample_rate,
                        speaker_id=self.config.speaker_id,
                        speech_rate=self.config.speech_rate,
                    ),
                    self._handle_engine_event,
                )
            else:
                self._emit_status("Microphone passthrough active: service translation disabled")

            self._start_input_with_fallback(mic_candidates)

            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        self.stop_event.set()
        if self.input_source is not None:
            self.input_source.stop()
            self.input_source = None
        if self.engine is not None:
            await self.engine.stop()
            self.engine = None
        if self.rvc_manager is not None:
            self.rvc_manager.stop()
            self.rvc_manager = None
        if self.output_sink is not None:
            self.output_sink.stop()
            if self.output_sink.output_path:
                self._emit_status(
                    f"Saved translated wav: {self.output_sink.output_path} ({self.output_sink.bytes_written} bytes)"
                )
            self.output_sink = None

    def request_stop(self) -> None:
        self.stop_event.set()
        if self.loop is not None and not self.loop.is_closed():
            if self.run_task is not None:
                try:
                    self.loop.call_soon_threadsafe(self.run_task.cancel)
                except RuntimeError:
                    return

    def _start_output_with_fallback(self, devices: list[AudioDevice]) -> AudioOutputSink:
        last_error: Optional[Exception] = None
        for device in devices:
            sink = AudioOutputSink(
                device=device,
                source_sample_rate=self.config.sample_rate,
                output_sample_rate=int(device.default_samplerate),
                source_channels=1,
                output_channels=min(max(1, self.config.output_channels), device.max_output_channels),
                record_dir=self.config.translated_record_dir,
                record_wav=self.config.audio_route.record_translated_wav,
                on_status=self._emit_status,
                on_first_write=self._handle_output_first_write,
            )
            try:
                sink.start()
                self._emit_status(
                    f"Output active: #{device.index} {device.name} | {device.hostapi} "
                    f"({int(device.default_samplerate)} Hz)"
                )
                return sink
            except Exception as exc:
                last_error = exc
                sink.stop()
                self._emit_status(f"Output backend failed: #{device.index} {device.hostapi}: {exc}")
        raise RuntimeError(f"Unable to start output stream. Last error: {last_error}")

    def _start_input_with_fallback(self, devices: list[AudioDevice]) -> None:
        last_error: Optional[Exception] = None
        for device in devices:
            source = AudioInputSource(
                device=device,
                source_sample_rate=int(device.default_samplerate),
                target_sample_rate=self.config.sample_rate,
                channels=1,
                chunk_ms=self.config.chunk_ms,
                on_audio=self._send_audio_from_callback,
                on_status=self._emit_status,
                on_speech_start=self._handle_speech_start,
            )
            try:
                source.start()
                self.input_source = source
                self._emit_status(
                    f"Microphone active: #{device.index} {device.name} | {device.hostapi} "
                    f"({int(device.default_samplerate)} Hz)"
                )
                return
            except Exception as exc:
                last_error = exc
                source.stop()
                self._emit_status(f"Mic backend failed: #{device.index} {device.hostapi}: {exc}")

        raise RuntimeError(f"Unable to start microphone stream. Last error: {last_error}")

    def _build_engine(self):
        if self.config.engine_name == "mock":
            return MockTranslatorEngine()
        return VolcAstS2SEngine(
            ws_url=self.config.ws_url,
            api_key=self.config.api_key,
            resource_id=self.config.resource_id,
        )

    def _start_rvc(self) -> None:
        rvc_cfg = self.config.rvc
        if rvc_cfg is None:
            return
        manager = RvcSidecarManager(rvc_cfg, on_status=self._emit_status)
        if not manager.start():
            self._emit_status("RVC sidecar failed to start; falling back to passthrough")
            manager.stop()
            return
        if self.config.rvc_model is not None:
            if not manager.apply_model(self.config.rvc_model):
                self._emit_status("RVC model load failed; falling back to passthrough")
                manager.stop()
                return
        self.rvc_manager = manager
        self._rvc_chunk_bytes = int(self.config.sample_rate * 2 * 0.5)

    def _send_audio_from_callback(self, pcm_bytes: bytes) -> None:
        if not self.config.simultaneous_interpretation_enabled:
            if self.rvc_manager is not None and self.rvc_manager.is_running():
                out = self.rvc_manager.process_pcm(
                    pcm_bytes, self.config.sample_rate, self._rvc_chunk_bytes
                )
                if out and self.output_sink is not None:
                    self.output_sink.write(out)
            elif self.output_sink is not None:
                self.output_sink.write(pcm_bytes)
            return
        if self.loop is None or self.engine is None:
            return
        if self.loop.is_closed():
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
        elif event.type == "source_text" and self.on_source:
            self.on_source(event.text)
        elif event.type == "translated_text" and self.on_translation:
            self.on_translation(event.text)
        elif event.type == "translated_audio" and self.output_sink is not None:
            self._handle_first_translated_audio(event.segment_id)
            self.output_sink.write(event.data, event.segment_id)

    def _emit_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _handle_speech_start(self, timestamp: float) -> None:
        self.latency_trace_id += 1
        self.pending_speech_start = timestamp
        self.pending_tts_first = None
        self.pending_output_first = False
        self.trace_min_segment_id = self.latest_audio_segment_id
        self.latency_segment_id = 0
        self.pending_trace_audio_bytes = 0
        self._emit_status(f"[latency] trace={self.latency_trace_id} mic-speech-start")

    def _handle_first_translated_audio(self, segment_id: int) -> None:
        if segment_id:
            self.latest_audio_segment_id = max(self.latest_audio_segment_id, segment_id)
        if self.pending_speech_start is None or self.pending_tts_first is not None:
            return
        elapsed_seconds = time.monotonic() - self.pending_speech_start
        if segment_id and segment_id <= self.trace_min_segment_id and elapsed_seconds < self.latency_grace_seconds:
            self.pending_trace_audio_bytes += 1
            return
        if segment_id and segment_id <= self.trace_min_segment_id:
            self._emit_status(
                f"[latency] trace={self.latency_trace_id} fallback same segment={segment_id} after grace"
            )
        self.latency_segment_id = segment_id
        self.pending_tts_first = time.monotonic()
        elapsed_ms = int((self.pending_tts_first - self.pending_speech_start) * 1000)
        segment_label = f", segment={segment_id}" if segment_id else ""
        self._emit_status(f"[latency] trace={self.latency_trace_id}{segment_label} mic_to_tts={elapsed_ms}ms")

    def _handle_output_first_write(self, timestamp: float, segment_id: int) -> None:
        if self.pending_speech_start is None or self.pending_output_first:
            return
        if self.latency_segment_id and segment_id != self.latency_segment_id:
            return
        self.pending_output_first = True
        elapsed_ms = int((timestamp - self.pending_speech_start) * 1000)
        if self.pending_tts_first is not None:
            tts_ms = int((self.pending_tts_first - self.pending_speech_start) * 1000)
            self._emit_status(
                f"[latency] trace={self.latency_trace_id} mic_to_tts={tts_ms}ms, mic_to_output={elapsed_ms}ms"
            )
        else:
            self._emit_status(f"[latency] trace={self.latency_trace_id} mic_to_output={elapsed_ms}ms")


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


def build_app_config(env_path: Path) -> AppConfig:
    load_env_file(env_path)
    current_dir = env_path.parent
    api_key = os.environ.get("VOLC_APP_KEY", "").strip() or os.environ.get("VOLC_API_KEY", "").strip()
    engine_name = os.environ.get("TRANSLATOR_ENGINE", "huoshan").strip().lower()
    if engine_name == "volc":
        engine_name = "huoshan"
    sample_rate = int(os.environ.get("S2S_SAMPLE_RATE", "16000").strip())
    return AppConfig(
        ws_url=os.environ.get("VOLC_WS_URL", "").strip(),
        api_key=api_key,
        resource_id=os.environ.get("VOLC_RESOURCE_ID", "volc.service_type.10053").strip(),
        source_language=os.environ.get("S2S_SOURCE_LANGUAGE", "").strip()
        or os.environ.get("SOURCE_LANGUAGE", "en").strip(),
        target_language=os.environ.get("S2S_TARGET_LANGUAGE", "").strip()
        or os.environ.get("TARGET_LANGUAGE", "zh").strip(),
        audio_route=AudioRouteConfig(
            input_device_index=_env_int("MIC_INPUT_INDEX"),
            input_device_name=os.environ.get("MIC_INPUT_NAME", "").strip() or None,
            output_device_name=os.environ.get("VB_CABLE_INPUT_NAME", "CABLE Input").strip(),
            verification_device_name=os.environ.get("VB_CABLE_OUTPUT_NAME", "CABLE Output").strip(),
            record_translated_wav=os.environ.get("RECORD_TRANSLATED_WAV", "1").strip() not in {"0", "false", "False"},
        ),
        translated_record_dir=current_dir / os.environ.get("S2S_RECORD_DIR", "recordings_s2s").strip(),
        speaker_id=os.environ.get("S2S_SPEAKER_ID", "").strip() or None,
        speech_rate=int(os.environ.get("S2S_SPEECH_RATE", "0").strip()),
        simultaneous_interpretation_enabled=os.environ.get(
            "MIC_SIMULTANEOUS_INTERPRETATION",
            "1",
        ).strip() not in {"0", "false", "False"},
        chunk_ms=int(os.environ.get("CHUNK_MS", "80").strip()),
        sample_rate=sample_rate,
        output_channels=int(os.environ.get("VB_CABLE_OUTPUT_CHANNELS", "2").strip()),
        engine_name=engine_name,
    )
