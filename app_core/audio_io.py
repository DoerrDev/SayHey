from __future__ import annotations

import math
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from app_core.audio_devices import AudioDevice, DeviceResolver


AudioCallback = Callable[[bytes], None]
StatusCallback = Callable[[str], None]
SpeechStartCallback = Callable[[float], None]


@dataclass(frozen=True)
class AudioRouteConfig:
    input_device_index: Optional[int]
    input_device_name: Optional[str]
    output_device_index: Optional[int] = None
    output_device_name: str = "CABLE Input"
    verification_device_name: str = "CABLE Output"
    record_translated_wav: bool = True


class AudioInputSource:
    def __init__(
        self,
        device: AudioDevice,
        source_sample_rate: int,
        target_sample_rate: int,
        channels: int,
        chunk_ms: int,
        on_audio: AudioCallback,
        on_status: Optional[StatusCallback] = None,
        on_speech_start: Optional[SpeechStartCallback] = None,
        speech_threshold: float = 0.012,
        speech_cooldown_seconds: float = 1.2,
        noise_gate_threshold: float = 0.0,
    ) -> None:
        self.device = device
        self.source_sample_rate = source_sample_rate
        self.target_sample_rate = target_sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.on_audio = on_audio
        self.on_status = on_status
        self.on_speech_start = on_speech_start
        self.speech_threshold = speech_threshold
        self.speech_cooldown_seconds = speech_cooldown_seconds
        self.noise_gate_threshold = max(0.0, float(noise_gate_threshold))
        self.stream: Optional[sd.InputStream] = None
        self.last_speech_start = 0.0
        self.first_frame_event = threading.Event()

    def start(self) -> None:
        blocksize = int(self.source_sample_rate * self.chunk_ms / 1000)
        self.stream = sd.InputStream(
            device=self.device.index,
            samplerate=self.source_sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=blocksize,
            callback=self._callback,
        )
        self.stream.start()
        if not self.first_frame_event.wait(timeout=1.0):
            self.stop()
            raise RuntimeError(
                f"未收到设备 #{self.device.index} {self.device.name} ({self.device.hostapi}) 的音频流，"
                "该设备无效，请切换有效的麦克风设备"
            )

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        if not self.first_frame_event.is_set():
            self.first_frame_event.set()
        if status and self.on_status:
            self.on_status(f"[audio-status] {status}")
        mono = indata[:, 0].copy()
        now = time.monotonic()
        level = float(np.sqrt(np.mean(np.square(mono.astype(np.float32)))) / np.iinfo(np.int16).max)
        if (
            self.on_speech_start
            and level >= self.speech_threshold
            and now - self.last_speech_start >= self.speech_cooldown_seconds
        ):
            self.last_speech_start = now
            self.on_speech_start(now)
        mono = self._resample_if_needed(mono)
        if self.noise_gate_threshold > 0.0 and level < self.noise_gate_threshold:
            mono = np.zeros_like(mono)
        self.on_audio(mono.tobytes())

    def _resample_if_needed(self, audio: np.ndarray) -> np.ndarray:
        if self.source_sample_rate == self.target_sample_rate or audio.size == 0:
            return audio
        ratio = self.target_sample_rate / self.source_sample_rate
        output_frames = max(1, int(round(audio.shape[0] * ratio)))
        source_positions = np.arange(audio.shape[0], dtype=np.float32)
        target_positions = np.linspace(0, audio.shape[0] - 1, output_frames, dtype=np.float32)
        resampled = np.interp(target_positions, source_positions, audio.astype(np.float32))
        return np.clip(resampled, -32768, 32767).astype(np.int16)


class AudioOutputSink:
    def __init__(
        self,
        device: AudioDevice,
        source_sample_rate: int,
        output_sample_rate: int,
        source_channels: int,
        output_channels: int,
        record_dir: Path,
        record_wav: bool,
        on_status: Optional[StatusCallback] = None,
        on_first_write: Optional[Callable[[float, int], None]] = None,
        gain: float = 1.0,
        monitor_device: Optional[AudioDevice] = None,
        monitor_gain: float = 1.0,
    ) -> None:
        self.device = device
        self.monitor_device = monitor_device
        self.monitor_gain = max(0.0, monitor_gain)
        self.monitor_stream: Optional[sd.OutputStream] = None
        self.source_sample_rate = source_sample_rate
        self.output_sample_rate = output_sample_rate
        self.source_channels = source_channels
        self.output_channels = output_channels
        self.record_dir = record_dir
        self.record_wav = record_wav
        self.on_status = on_status
        self.on_first_write = on_first_write
        self.gain = max(0.0, gain)
        self.stream: Optional[sd.OutputStream] = None
        self.wav_file: Optional[wave.Wave_write] = None
        self.output_path: Optional[Path] = None
        self.bytes_written = 0
        self.last_level_report = 0.0
        self.output_queue: Queue[tuple[bytes, int] | None] = Queue(maxsize=128)
        self.worker_thread: Optional[threading.Thread] = None
        self.dropped_chunks = 0
        self.monitor_queue: Queue[bytes | None] = Queue(maxsize=128)
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_dropped_chunks = 0

    def start(self) -> None:
        self.stream = sd.OutputStream(
            device=self.device.index,
            samplerate=self.output_sample_rate,
            channels=self.output_channels,
            dtype="int16",
        )
        self.stream.start()

        if self.monitor_device is not None:
            try:
                self.monitor_stream = sd.OutputStream(
                    device=self.monitor_device.index,
                    samplerate=int(self.monitor_device.default_samplerate),
                    channels=min(max(1, self.output_channels), self.monitor_device.max_output_channels),
                    dtype="int16",
                )
                self.monitor_stream.start()
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()
                if self.on_status:
                    self.on_status(
                        f"Monitor active: #{self.monitor_device.index} {self.monitor_device.name}"
                    )
            except Exception as exc:
                self.monitor_stream = None
                if self.on_status:
                    self.on_status(f"[monitor-error] {exc}")

        if self.record_wav:
            self.record_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.output_path = self.record_dir / f"translated_{timestamp}.wav"
            self.wav_file = wave.open(str(self.output_path), "wb")
            self.wav_file.setnchannels(self.source_channels)
            self.wav_file.setsampwidth(2)
            self.wav_file.setframerate(self.source_sample_rate)
        self.worker_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.worker_thread.start()

    def write(self, pcm_bytes: bytes, segment_id: int = 0) -> None:
        if not pcm_bytes:
            return
        try:
            self.output_queue.put_nowait((pcm_bytes, segment_id))
        except Full:
            self.dropped_chunks += 1
            try:
                self.output_queue.get_nowait()
            except Empty:
                pass
            try:
                self.output_queue.put_nowait((pcm_bytes, segment_id))
            except Full:
                pass
            if self.on_status and (self.dropped_chunks == 1 or self.dropped_chunks % 20 == 0):
                self.on_status(f"[out-drop] output queue full, dropped {self.dropped_chunks} chunks")

    def stop(self) -> None:
        while True:
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
        self.output_queue.put(None)
        if self.worker_thread is not None:
            self.worker_thread.join(timeout=2.0)
            self.worker_thread = None
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.monitor_thread is not None:
            while True:
                try:
                    self.monitor_queue.get_nowait()
                except Empty:
                    break
            self.monitor_queue.put(None)
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
        if self.monitor_stream is not None:
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except Exception:
                pass
            self.monitor_stream = None
        if self.wav_file is not None:
            self.wav_file.close()
            self.wav_file = None

    def _write_loop(self) -> None:
        while True:
            item = self.output_queue.get()
            if item is None:
                break
            pcm_bytes, segment_id = item
            try:
                self._write_now(pcm_bytes, segment_id)
            except Exception as exc:
                if self.on_status:
                    self.on_status(f"[out-error] {exc}")
                break

    def _write_now(self, pcm_bytes: bytes, segment_id: int) -> None:
        self.bytes_written += len(pcm_bytes)
        now = time.monotonic()
        if self.on_first_write is not None:
            self.on_first_write(now, segment_id)
        if now - self.last_level_report > 2.5:
            level = self._pcm_level(pcm_bytes)
            if self.on_status:
                self.on_status(f"[out-level] {level:.4f}, bytes={self.bytes_written}")
            self.last_level_report = now
        if self.wav_file is not None:
            self.wav_file.writeframes(pcm_bytes)
        if self.stream is not None:
            self.stream.write(
                self._fit_output_channels(pcm_bytes, self.output_sample_rate, self.output_channels, self.gain)
            )
        if self.monitor_stream is not None:
            try:
                self.monitor_queue.put_nowait(pcm_bytes)
            except Full:
                self.monitor_dropped_chunks += 1
                try:
                    self.monitor_queue.get_nowait()
                except Empty:
                    pass
                try:
                    self.monitor_queue.put_nowait(pcm_bytes)
                except Full:
                    pass
                if self.on_status and (
                    self.monitor_dropped_chunks == 1 or self.monitor_dropped_chunks % 20 == 0
                ):
                    self.on_status(
                        f"[monitor-drop] monitor queue full, dropped {self.monitor_dropped_chunks} chunks"
                    )

    def _monitor_loop(self) -> None:
        while True:
            pcm_bytes = self.monitor_queue.get()
            if pcm_bytes is None:
                break
            if self.monitor_stream is None:
                continue
            try:
                self.monitor_stream.write(
                    self._fit_output_channels(
                        pcm_bytes,
                        int(self.monitor_device.default_samplerate),
                        self.monitor_stream.channels,
                        self.gain * self.monitor_gain,
                    )
                )
            except Exception as exc:
                if self.on_status:
                    self.on_status(f"[monitor-error] {exc}")
                try:
                    self.monitor_stream.close()
                except Exception:
                    pass
                self.monitor_stream = None
                break

    def _fit_output_channels(
        self, pcm_bytes: bytes, output_sample_rate: int, output_channels: int, gain: float
    ) -> np.ndarray:
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).reshape(-1, self.source_channels)
        audio = self._apply_gain(audio, gain)
        audio = self._resample_if_needed(audio, output_sample_rate)
        if self.source_channels == output_channels:
            return audio
        if self.source_channels == 1 and output_channels > 1:
            return np.repeat(audio, output_channels, axis=1)
        if self.source_channels > output_channels:
            return audio[:, :output_channels]

        padding = np.zeros((audio.shape[0], output_channels - self.source_channels), dtype=audio.dtype)
        return np.concatenate([audio, padding], axis=1)

    def _pcm_level(self, pcm_bytes: bytes) -> float:
        audio = np.frombuffer(pcm_bytes, dtype=np.int16)
        if audio.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio.astype(np.float32)))) / np.iinfo(np.int16).max)

    def _apply_gain(self, audio: np.ndarray, gain: float) -> np.ndarray:
        if gain == 1.0 or audio.size == 0:
            return audio
        amplified = audio.astype(np.float32) * gain
        return np.clip(amplified, -32768, 32767).astype(np.int16)

    def _resample_if_needed(self, audio: np.ndarray, output_sample_rate: int) -> np.ndarray:
        if self.source_sample_rate == output_sample_rate or audio.size == 0:
            return audio

        ratio = output_sample_rate / self.source_sample_rate
        output_frames = max(1, int(round(audio.shape[0] * ratio)))
        source_positions = np.arange(audio.shape[0], dtype=np.float32)
        target_positions = np.linspace(0, audio.shape[0] - 1, output_frames, dtype=np.float32)
        channels = []
        for channel in range(audio.shape[1]):
            resampled = np.interp(target_positions, source_positions, audio[:, channel].astype(np.float32))
            channels.append(np.clip(resampled, -32768, 32767).astype(np.int16))
        return np.stack(channels, axis=1)


class AudioRouteVerifier:
    def __init__(self, resolver: DeviceResolver) -> None:
        self.resolver = resolver

    def verify_vb_cable(
        self,
        cable_input_name: str = "CABLE Input",
        cable_output_name: str = "CABLE Output",
        sample_rate: Optional[int] = None,
        duration_seconds: float = 1.2,
    ) -> float:
        output_device = self.resolver.resolve_cable_input(cable_input_name)
        input_device = self.resolver.resolve_cable_output(cable_output_name)
        last_error: Optional[Exception] = None
        for candidate_output in self.resolver.stable_output_candidates(output_device):
            for candidate_input in self.resolver.stable_input_candidates(input_device):
                try:
                    return self._verify_pair(candidate_output, candidate_input, sample_rate, duration_seconds)
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"Unable to verify VB-Cable route. Last error: {last_error}")

    def _verify_pair(
        self,
        output_device: AudioDevice,
        input_device: AudioDevice,
        sample_rate: Optional[int],
        duration_seconds: float,
    ) -> float:
        sample_rate = sample_rate or int(output_device.default_samplerate)
        frames = int(sample_rate * duration_seconds)
        frequency = 880
        t = np.arange(frames) / sample_rate
        tone = (0.25 * np.sin(2 * math.pi * frequency * t) * np.iinfo(np.int16).max).astype(np.int16)
        stereo_tone = np.repeat(tone.reshape(-1, 1), min(2, output_device.max_output_channels), axis=1)

        recorded_queue: Queue[np.ndarray] = Queue()

        def callback(indata, frame_count, time_info, status) -> None:
            recorded_queue.put(indata[:, 0].copy())

        with sd.InputStream(
            device=input_device.index,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            with sd.OutputStream(
                device=output_device.index,
                samplerate=sample_rate,
                channels=stereo_tone.shape[1],
                dtype="int16",
            ) as output_stream:
                output_stream.write(stereo_tone)
                time.sleep(duration_seconds + 0.2)

        chunks = []
        while not recorded_queue.empty():
            chunks.append(recorded_queue.get())
        if not chunks:
            return 0.0
        recorded = np.concatenate(chunks).astype(np.float32)
        return float(np.sqrt(np.mean(np.square(recorded))) / np.iinfo(np.int16).max)
