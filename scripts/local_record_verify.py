from __future__ import annotations

import os
import queue
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
class RecorderSettings:
    device_index: Optional[int]
    device_name: Optional[str]
    record_dir: Path
    sample_rate: Optional[int]
    channels: Optional[int]
    auto_play_after_save: bool


def build_settings() -> RecorderSettings:
    load_env_file(CURRENT_DIR / ".env")
    device_index_raw = os.environ.get("AUDIO_INPUT_INDEX", "").strip()
    device_name = os.environ.get("AUDIO_INPUT_NAME", "").strip() or None
    record_dir = CURRENT_DIR / os.environ.get("VERIFY_RECORD_DIR", "recordings").strip()
    sample_rate_raw = os.environ.get("RECORD_SAMPLE_RATE", "").strip()
    channels_raw = os.environ.get("RECORD_CHANNELS", "").strip()
    auto_play = os.environ.get("AUTO_PLAY_AFTER_SAVE", "1").strip() not in {"0", "false", "False"}
    return RecorderSettings(
        device_index=int(device_index_raw) if device_index_raw else None,
        device_name=device_name,
        record_dir=record_dir,
        sample_rate=int(sample_rate_raw) if sample_rate_raw else None,
        channels=int(channels_raw) if channels_raw else None,
        auto_play_after_save=auto_play,
    )


class LocalRecorderApp:
    def __init__(self, settings: RecorderSettings) -> None:
        self.settings = settings
        self.root = tk.Tk()
        self.root.title("VoiceMeeter Local Record Verify")
        self.root.geometry("520x280")
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="Ready")
        self.device_var = tk.StringVar(value="")
        self.file_var = tk.StringVar(value="Last file: none")
        self.elapsed_var = tk.StringVar(value="00:00")

        self.stream: Optional[sd.InputStream] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.audio_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=128)
        self.is_recording = False
        self.last_output: Optional[Path] = None
        self.start_time: Optional[float] = None

        self.device_index, self.device_info = self._resolve_device()
        self.sample_rate = self.settings.sample_rate or int(self.device_info["default_samplerate"])
        max_channels = int(self.device_info["max_input_channels"])
        requested_channels = self.settings.channels or (2 if max_channels >= 2 else 1)
        self.channels = min(max(1, requested_channels), max_channels)

        self.device_var.set(
            f"Input device: #{self.device_index} | {self.device_info['name']} | "
            f"{self.sample_rate} Hz | {self.channels} ch"
        )

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resolve_device(self) -> tuple[int, dict]:
        devices = sd.query_devices()
        if self.settings.device_index is not None:
            return self.settings.device_index, devices[self.settings.device_index]

        keyword = (self.settings.device_name or "").lower()
        for index, device in enumerate(devices):
            if device["max_input_channels"] < 1:
                continue
            if keyword and keyword in device["name"].lower():
                return index, device

        raise RuntimeError(
            "No matching input device found. Run `python list_audio_devices.py` "
            "and set AUDIO_INPUT_INDEX or AUDIO_INPUT_NAME in .env."
        )

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Local WAV Recorder", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(frame, textvariable=self.device_var, justify="left", wraplength=480).pack(anchor="w", pady=(8, 8))
        tk.Label(frame, textvariable=self.status_var, fg="#0a6b2d").pack(anchor="w")
        tk.Label(frame, textvariable=self.elapsed_var, font=("Consolas", 16, "bold")).pack(anchor="w", pady=(8, 12))

        buttons = tk.Frame(frame)
        buttons.pack(anchor="w", pady=(0, 12))

        self.start_button = tk.Button(buttons, text="Start", width=12, command=self.start_recording)
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = tk.Button(buttons, text="Stop", width=12, state="disabled", command=self.stop_recording)
        self.stop_button.pack(side="left", padx=(0, 8))

        self.play_button = tk.Button(buttons, text="Play Last", width=12, command=self.play_last_file)
        self.play_button.pack(side="left", padx=(0, 8))

        self.folder_button = tk.Button(buttons, text="Open Folder", width=12, command=self.open_folder)
        self.folder_button.pack(side="left")

        tk.Label(
            frame,
            text=(
                "Use this first to verify that browser audio really reaches your VoiceMeeter route.\n"
                "Recommended browser path: Browser Output -> Voicemeeter In 1 -> B1/B2 -> this recorder."
            ),
            justify="left",
            wraplength=480,
        ).pack(anchor="w", pady=(0, 12))

        tk.Label(frame, textvariable=self.file_var, justify="left", wraplength=480).pack(anchor="w")

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            self.root.after(0, lambda: self.status_var.set(f"Audio status: {status}"))
        self.audio_queue.put_nowait(indata.copy().tobytes())

    def _writer_loop(self, output_path: Path) -> None:
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
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
        self.last_output = self.settings.record_dir / f"verify_{timestamp}.wav"

        self.audio_queue = queue.Queue(maxsize=128)
        self.writer_thread = threading.Thread(target=self._writer_loop, args=(self.last_output,), daemon=True)
        self.writer_thread.start()

        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=self._audio_callback,
        )
        self.stream.start()

        self.is_recording = True
        self.start_time = time.time()
        self.status_var.set("Recording...")
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

        self.audio_queue.put(None)
        if self.writer_thread is not None:
            self.writer_thread.join(timeout=5)
            self.writer_thread = None

        self.status_var.set("Saved")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.file_var.set(f"Last file: {self.last_output}")

        if self.settings.auto_play_after_save and self.last_output and self.last_output.exists():
            try:
                os.startfile(self.last_output)  # type: ignore[attr-defined]
            except OSError:
                pass

    def play_last_file(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showinfo("No file", "No recorded WAV file yet.")
            return
        os.startfile(self.last_output)  # type: ignore[attr-defined]

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
    app = LocalRecorderApp(settings)
    app.run()


if __name__ == "__main__":
    main()
