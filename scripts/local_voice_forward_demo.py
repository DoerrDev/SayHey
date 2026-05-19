from __future__ import annotations

import os
import queue
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import messagebox


CURRENT_DIR = Path(__file__).resolve().parent.parent


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class ForwardSettings:
    input_index: Optional[int]
    input_name: Optional[str]
    output_index: Optional[int]
    output_name: Optional[str]
    record_dir: Path
    sample_rate: Optional[int]
    input_channels: Optional[int]
    output_channels: Optional[int]
    auto_forward_after_save: bool


def _env_int(name: str) -> Optional[int]:
    value = os.environ.get(name, "").strip()
    return int(value) if value else None


def build_settings() -> ForwardSettings:
    load_env_file(CURRENT_DIR / ".env")
    record_dir = CURRENT_DIR / os.environ.get("FORWARD_RECORD_DIR", "recordings_forward").strip()
    auto_forward = os.environ.get("FORWARD_AUTO_PLAY_AFTER_SAVE", "1").strip()
    return ForwardSettings(
        input_index=_env_int("FORWARD_INPUT_INDEX"),
        input_name=os.environ.get("FORWARD_INPUT_NAME", "").strip() or None,
        output_index=_env_int("FORWARD_OUTPUT_INDEX"),
        output_name=os.environ.get("FORWARD_OUTPUT_NAME", "").strip() or None,
        record_dir=record_dir,
        sample_rate=_env_int("FORWARD_SAMPLE_RATE"),
        input_channels=_env_int("FORWARD_INPUT_CHANNELS"),
        output_channels=_env_int("FORWARD_OUTPUT_CHANNELS"),
        auto_forward_after_save=auto_forward not in {"0", "false", "False"},
    )


class LocalVoiceForwardApp:
    def __init__(self, settings: ForwardSettings) -> None:
        self.settings = settings
        self.root = tk.Tk()
        self.root.title("Local Voice Forward Demo")
        self.root.geometry("640x360")
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="Ready")
        self.input_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value="")
        self.file_var = tk.StringVar(value="Last file: none")
        self.elapsed_var = tk.StringVar(value="00:00")

        self.stream: Optional[sd.InputStream] = None
        self.output_stream: Optional[sd.OutputStream] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.play_thread: Optional[threading.Thread] = None
        self.audio_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=128)
        self.is_recording = False
        self.is_playing = False
        self.last_output: Optional[Path] = None
        self.start_time: Optional[float] = None

        self.input_index, self.input_info = self._resolve_device(
            index=self.settings.input_index,
            name=self.settings.input_name,
            direction="input",
        )
        self.output_index, self.output_info = self._resolve_device(
            index=self.settings.output_index,
            name=self.settings.output_name,
            direction="output",
        )

        self.sample_rate = self.settings.sample_rate or int(self.input_info["default_samplerate"])
        max_input_channels = int(self.input_info["max_input_channels"])
        requested_input_channels = self.settings.input_channels or 1
        self.input_channels = min(max(1, requested_input_channels), max_input_channels)

        max_output_channels = int(self.output_info["max_output_channels"])
        requested_output_channels = self.settings.output_channels or (2 if max_output_channels >= 2 else 1)
        self.output_channels = min(max(1, requested_output_channels), max_output_channels)

        self.input_var.set(
            f"Mic input: #{self.input_index} | {self.input_info['name']} | "
            f"{self.sample_rate} Hz | {self.input_channels} ch"
        )
        self.output_var.set(
            f"Forward output: #{self.output_index} | {self.output_info['name']} | "
            f"{self.sample_rate} Hz | {self.output_channels} ch"
        )

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resolve_device(self, index: Optional[int], name: Optional[str], direction: str) -> tuple[int, dict]:
        devices = sd.query_devices()
        channel_key = "max_input_channels" if direction == "input" else "max_output_channels"

        if index is not None:
            device = devices[index]
            if device[channel_key] < 1:
                raise RuntimeError(f"Device #{index} is not a valid {direction} device.")
            return index, device

        keyword = (name or "").lower()
        if keyword:
            for device_index, device in enumerate(devices):
                if device[channel_key] < 1:
                    continue
                if keyword in device["name"].lower():
                    return device_index, device

        default_device = sd.default.device[0 if direction == "input" else 1]
        if default_device is None or default_device < 0:
            raise RuntimeError(
                f"No {direction} device configured. Run `python list_audio_devices.py` "
                f"and set FORWARD_{direction.upper()}_INDEX or FORWARD_{direction.upper()}_NAME."
            )
        return int(default_device), devices[int(default_device)]

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Local Voice Live Forward", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(frame, textvariable=self.input_var, justify="left", wraplength=600).pack(anchor="w", pady=(8, 2))
        tk.Label(frame, textvariable=self.output_var, justify="left", wraplength=600).pack(anchor="w", pady=(0, 8))
        tk.Label(frame, textvariable=self.status_var, fg="#0a6b2d").pack(anchor="w")
        tk.Label(frame, textvariable=self.elapsed_var, font=("Consolas", 16, "bold")).pack(anchor="w", pady=(8, 12))

        buttons = tk.Frame(frame)
        buttons.pack(anchor="w", pady=(0, 12))

        self.start_button = tk.Button(buttons, text="Start Live", width=14, command=self.start_recording)
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = tk.Button(buttons, text="Stop", width=14, state="disabled", command=self.stop_recording)
        self.stop_button.pack(side="left", padx=(0, 8))

        self.forward_button = tk.Button(buttons, text="Forward Last", width=14, command=self.forward_last_file)
        self.forward_button.pack(side="left", padx=(0, 8))

        self.folder_button = tk.Button(buttons, text="Open Folder", width=14, command=self.open_folder)
        self.folder_button.pack(side="left")

        tk.Label(
            frame,
            text=(
                "This local demo forwards your mic live to the selected playback device and saves a WAV.\n"
                "To feed another recorder, choose a virtual playback device such as Voicemeeter AUX Input."
            ),
            justify="left",
            wraplength=600,
        ).pack(anchor="w", pady=(0, 12))

        tk.Label(frame, textvariable=self.file_var, justify="left", wraplength=600).pack(anchor="w")

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            self.root.after(0, lambda: self.status_var.set(f"Audio status: {status}"))
        audio = indata.copy()
        self.audio_queue.put_nowait(audio.tobytes())
        if self.output_stream is not None:
            self.output_stream.write(self._fit_channels(audio, self.input_channels))

    def _writer_loop(self, output_path: Path) -> None:
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.input_channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            while True:
                chunk = self.audio_queue.get()
                if chunk is None:
                    break
                wav_file.writeframes(chunk)

    def start_recording(self) -> None:
        if self.is_recording:
            return

        self.settings.record_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.last_output = self.settings.record_dir / f"voice_forward_{timestamp}.wav"

        self.audio_queue = queue.Queue(maxsize=128)
        self.writer_thread = threading.Thread(target=self._writer_loop, args=(self.last_output,), daemon=True)
        self.writer_thread.start()

        self.stream = sd.InputStream(
            device=self.input_index,
            samplerate=self.sample_rate,
            channels=self.input_channels,
            dtype="int16",
            callback=self._audio_callback,
        )
        self.output_stream = sd.OutputStream(
            device=self.output_index,
            samplerate=self.sample_rate,
            channels=self.output_channels,
            dtype="int16",
        )
        self.output_stream.start()
        self.stream.start()

        self.is_recording = True
        self.start_time = time.time()
        self.status_var.set("Live forwarding and saving...")
        self.file_var.set(f"Recording to: {self.last_output}")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self._tick()

    def stop_recording(self) -> None:
        if not self.is_recording:
            return

        self.is_recording = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.output_stream is not None:
            self.output_stream.stop()
            self.output_stream.close()
            self.output_stream = None

        self.audio_queue.put(None)
        if self.writer_thread is not None:
            self.writer_thread.join(timeout=5)
            self.writer_thread = None

        self.status_var.set("Stopped and saved")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.file_var.set(f"Last file: {self.last_output}")

    def _fit_channels(self, audio: np.ndarray, source_channels: int) -> np.ndarray:
        if source_channels == self.output_channels:
            return audio
        if source_channels == 1 and self.output_channels > 1:
            return np.repeat(audio, self.output_channels, axis=1)
        if source_channels > self.output_channels:
            return audio[:, : self.output_channels]

        padding = np.zeros((audio.shape[0], self.output_channels - source_channels), dtype=audio.dtype)
        return np.concatenate([audio, padding], axis=1)

    def _forward_loop(self, wav_path: Path) -> None:
        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                source_channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                with sd.OutputStream(
                    device=self.output_index,
                    samplerate=sample_rate,
                    channels=self.output_channels,
                    dtype="int16",
                ) as output_stream:
                    while True:
                        data = wav_file.readframes(2048)
                        if not data:
                            break
                        audio = np.frombuffer(data, dtype=np.int16).reshape(-1, source_channels)
                        output_stream.write(self._fit_channels(audio, source_channels))
            self.root.after(0, lambda: self.status_var.set("Forward finished"))
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("Forward failed", str(exc)))
            self.root.after(0, lambda: self.status_var.set("Forward failed"))
        finally:
            self.is_playing = False

    def forward_last_file(self) -> None:
        if self.is_playing:
            return
        if not self.last_output or not self.last_output.exists():
            messagebox.showinfo("No file", "No recorded WAV file yet.")
            return

        self.is_playing = True
        self.status_var.set("Forwarding to output device...")
        self.play_thread = threading.Thread(target=self._forward_loop, args=(self.last_output,), daemon=True)
        self.play_thread.start()

    def open_folder(self) -> None:
        self.settings.record_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.settings.record_dir)  # type: ignore[attr-defined]

    def _tick(self) -> None:
        if self.is_recording and self.start_time is not None:
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.elapsed_var.set(f"{minutes:02d}:{seconds:02d}")
            self.root.after(250, self._tick)
        elif not self.is_recording:
            self.elapsed_var.set("00:00")

    def _on_close(self) -> None:
        if self.is_recording:
            self.stop_recording()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    settings = build_settings()
    app = LocalVoiceForwardApp(settings)
    app.run()


if __name__ == "__main__":
    main()
