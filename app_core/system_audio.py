from __future__ import annotations

import ctypes
import threading
import time
import warnings
from typing import Callable, Optional

import numpy as np
import soundcard as sc
from soundcard import SoundcardRuntimeWarning

warnings.filterwarnings("ignore", category=SoundcardRuntimeWarning, message="data discontinuity in recording")


AudioCallback = Callable[[bytes], None]
StatusCallback = Callable[[str], None]
SpeechStartCallback = Callable[[float], None]
ErrorCallback = Callable[[Exception], None]


class SystemAudioCapture:
    def __init__(
        self,
        device_name: Optional[str],
        target_sample_rate: int,
        chunk_ms: int,
        on_audio: AudioCallback,
        on_status: Optional[StatusCallback] = None,
        on_speech_start: Optional[SpeechStartCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        source_sample_rate: int = 48000,
        speech_threshold: float = 0.01,
        speech_cooldown_seconds: float = 1.5,
    ) -> None:
        self.device_name = device_name
        self.source_sample_rate = source_sample_rate
        self.target_sample_rate = target_sample_rate
        self.chunk_ms = chunk_ms
        self.on_audio = on_audio
        self.on_status = on_status
        self.on_speech_start = on_speech_start
        self.on_error = on_error
        self.speech_threshold = speech_threshold
        self.speech_cooldown_seconds = speech_cooldown_seconds
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.last_level_report = 0.0
        self.last_speech_start = 0.0

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None

    def _capture_loop(self) -> None:
        com_initialized = self._co_initialize()
        try:
            speaker = self._resolve_speaker()
            chunk_frames = int(self.source_sample_rate * self.chunk_ms / 1000)
            if self.on_status:
                self.on_status(f"[game-audio] capturing loopback: {speaker.name}")

            with sc.get_microphone(speaker.name, include_loopback=True).recorder(
                samplerate=self.source_sample_rate,
                channels=2,
            ) as recorder:
                while not self.stop_event.is_set():
                    frames = recorder.record(numframes=chunk_frames)
                    pcm = self._frames_to_pcm16_mono(frames)
                    self._report_level_and_speech(pcm)
                    self.on_audio(pcm.tobytes())
        except Exception as exc:
            if self.on_error:
                self.on_error(exc)
            elif self.on_status:
                self.on_status(f"[game-audio-error] {exc}")
        finally:
            if com_initialized:
                ctypes.windll.ole32.CoUninitialize()

    def _co_initialize(self) -> bool:
        # soundcard uses Windows MMDevice APIs, which require COM initialization per thread.
        if not hasattr(ctypes, "windll"):
            return False
        coinit_multithreaded = 0x0
        rpc_e_changed_mode = 0x80010106
        hr = ctypes.windll.ole32.CoInitializeEx(None, coinit_multithreaded)
        unsigned_hr = hr & 0xFFFFFFFF
        if unsigned_hr in (0, 1):
            return True
        if unsigned_hr == rpc_e_changed_mode:
            return False
        raise RuntimeError(f"CoInitializeEx failed: {hex(unsigned_hr)}")

    def _resolve_speaker(self):
        if self.device_name:
            keyword = self.device_name.lower()
            for speaker in sc.all_speakers():
                if keyword in speaker.name.lower():
                    return speaker
            raise RuntimeError(f"System audio output device not found: {self.device_name}")
        return sc.default_speaker()

    def _frames_to_pcm16_mono(self, frames: np.ndarray) -> np.ndarray:
        if frames.size == 0:
            return np.zeros(0, dtype=np.int16)
        mono = frames.mean(axis=1).astype(np.float32)
        mono = self._resample_if_needed(mono)
        mono = np.clip(mono, -1.0, 1.0)
        return (mono * np.iinfo(np.int16).max).astype(np.int16)

    def _resample_if_needed(self, audio: np.ndarray) -> np.ndarray:
        if self.source_sample_rate == self.target_sample_rate or audio.size == 0:
            return audio
        ratio = self.target_sample_rate / self.source_sample_rate
        output_frames = max(1, int(round(audio.shape[0] * ratio)))
        source_positions = np.arange(audio.shape[0], dtype=np.float32)
        target_positions = np.linspace(0, audio.shape[0] - 1, output_frames, dtype=np.float32)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)

    def _report_level_and_speech(self, pcm: np.ndarray) -> None:
        if pcm.size == 0:
            return
        now = time.monotonic()
        level = float(np.sqrt(np.mean(np.square(pcm.astype(np.float32)))) / np.iinfo(np.int16).max)
        if (
            self.on_speech_start
            and level >= self.speech_threshold
            and now - self.last_speech_start >= self.speech_cooldown_seconds
        ):
            self.last_speech_start = now
            self.on_speech_start(now)
        if self.on_status and now - self.last_level_report > 2.5:
            self.on_status(f"[game-audio-level] {level:.4f}")
            self.last_level_report = now
