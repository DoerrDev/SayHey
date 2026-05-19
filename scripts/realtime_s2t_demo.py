from __future__ import annotations

import asyncio
import inspect
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Optional

import numpy as np
import sounddevice as sd
import websockets
from google.protobuf.json_format import MessageToDict

CURRENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CURRENT_DIR))

from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateResponse


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class Settings:
    ws_url: str
    api_key: str
    resource_id: str
    source_language: str
    target_language: str
    mode: str
    chunk_ms: int
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "int16"
    audio_input_name: Optional[str] = None
    audio_input_index: Optional[int] = None
    text_log: Optional[Path] = None


class RealtimeAstClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.audio_queue: Queue[bytes | None] = Queue(maxsize=64)
        self.session_id = str(uuid.uuid4())
        self.connection_id = str(uuid.uuid4())
        self.seen_source = ""
        self.seen_translation = ""
        self.text_log_handle = None

    def _device_index(self) -> int:
        if self.settings.audio_input_index is not None:
            return self.settings.audio_input_index

        devices = sd.query_devices()
        keyword = (self.settings.audio_input_name or "").lower()
        candidates = []
        for index, device in enumerate(devices):
            if device["max_input_channels"] < 1:
                continue
            name = device["name"]
            if keyword and keyword in name.lower():
                candidates.append(index)

        if not candidates:
            raise RuntimeError(
                "找不到匹配的输入设备。先运行 `python list_audio_devices.py`，"
                "然后把 `.env` 里的 `AUDIO_INPUT_NAME` 或 `AUDIO_INPUT_INDEX` 改掉。"
            )
        return candidates[0]

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            print(f"[audio-status] {status}", flush=True)
        mono = indata[:, 0].copy()
        self.audio_queue.put_nowait(mono.tobytes())

    def _build_start_request(self) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.settings.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.StartSession
        request.user.uid = "gt_game_translator_demo"
        request.user.did = "windows_voicemeeter_demo"
        request.user.platform = "Windows"
        request.user.sdk_version = "demo"

        request.source_audio.format = "wav"
        request.source_audio.codec = "raw"
        request.source_audio.rate = self.settings.sample_rate
        request.source_audio.bits = 16
        request.source_audio.channel = self.settings.channels

        request.request.mode = self.settings.mode
        request.request.source_language = self.settings.source_language
        request.request.target_language = self.settings.target_language
        return request

    def _build_audio_request(self, pcm_bytes: bytes) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.settings.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.TaskRequest
        request.source_audio.binary_data = pcm_bytes
        return request

    def _build_finish_request(self) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.settings.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.FinishSession
        return request

    async def _send_audio(self, ws) -> None:
        loop = asyncio.get_running_loop()
        while True:
            chunk = await loop.run_in_executor(None, self.audio_queue.get)
            if chunk is None:
                await ws.send(self._build_finish_request().SerializeToString())
                break
            await ws.send(self._build_audio_request(chunk).SerializeToString())

    def _append_log(self, line: str) -> None:
        if self.text_log_handle is None:
            return
        self.text_log_handle.write(line + "\n")
        self.text_log_handle.flush()

    def _handle_response(self, raw: bytes) -> bool:
        response = TranslateResponse()
        response.ParseFromString(raw)

        if response.event == Type.SessionStarted:
            print(f"[session] started: {self.session_id}", flush=True)
            return False

        if response.event == Type.SourceSubtitleResponse:
            if response.text and response.text != self.seen_source:
                self.seen_source = response.text
                line = f"[src] {response.text}"
                print(line, flush=True)
                self._append_log(line)
            return False

        if response.event == Type.TranslationSubtitleResponse:
            if response.text and response.text != self.seen_translation:
                self.seen_translation = response.text
                line = f"[dst] {response.text}"
                print(line, flush=True)
                self._append_log(line)
            return False

        if response.event == Type.UsageResponse:
            usage = MessageToDict(response, preserving_proto_field_name=True)
            print(f"[usage] {usage}", flush=True)
            return False

        if response.event == Type.AudioMuted:
            print(f"[muted] {response.muted_duration_ms} ms", flush=True)
            return False

        if response.event == Type.SessionFailed:
            message = response.response_meta.Message or "unknown error"
            raise RuntimeError(f"session failed: {message}")

        if response.event == Type.SessionFinished:
            print("[session] finished", flush=True)
            return True

        return False

    async def run(self) -> None:
        headers = {
            "X-Api-Key": self.settings.api_key,
            "X-Api-App-Key": self.settings.api_key,
            "X-Api-Resource-Id": self.settings.resource_id,
            "X-Api-Connect-Id": self.connection_id,
        }
        device_index = self._device_index()
        blocksize = int(self.settings.sample_rate * self.settings.chunk_ms / 1000)

        if self.settings.text_log:
            self.settings.text_log.parent.mkdir(parents=True, exist_ok=True)
            self.text_log_handle = self.settings.text_log.open("a", encoding="utf-8")

        print(
            f"[config] device_index={device_index}, mode={self.settings.mode}, "
            f"{self.settings.source_language}->{self.settings.target_language}, "
            f"chunk_ms={self.settings.chunk_ms}",
            flush=True,
        )

        stream = sd.InputStream(
            device=device_index,
            samplerate=self.settings.sample_rate,
            channels=self.settings.channels,
            dtype=self.settings.dtype,
            blocksize=blocksize,
            callback=self._audio_callback,
        )

        connect_kwargs = {
            "max_size": 16 * 1024 * 1024,
            "ping_interval": None,
        }
        connect_signature = inspect.signature(websockets.connect)
        if "additional_headers" in connect_signature.parameters:
            connect_kwargs["additional_headers"] = headers
        else:
            connect_kwargs["extra_headers"] = headers

        async with websockets.connect(self.settings.ws_url, **connect_kwargs) as ws:
            response_headers = getattr(ws, "response_headers", None)
            if response_headers is None and hasattr(ws, "response"):
                response_headers = ws.response.headers
            log_id = response_headers.get("X-Tt-Logid") if response_headers else None
            print(f"[connect] X-Tt-Logid={log_id}", flush=True)
            await ws.send(self._build_start_request().SerializeToString())

            sender_task = asyncio.create_task(self._send_audio(ws))
            with stream:
                try:
                    while True:
                        raw = await ws.recv()
                        if isinstance(raw, str):
                            print(f"[text-frame] {raw}", flush=True)
                            continue
                        finished = self._handle_response(raw)
                        if finished:
                            break
                except KeyboardInterrupt:
                    print("\n[stop] Ctrl+C detected, closing session...", flush=True)
                finally:
                    self.audio_queue.put(None)
                    await sender_task

        if self.text_log_handle is not None:
            self.text_log_handle.close()


def build_settings() -> Settings:
    load_env_file(CURRENT_DIR / ".env")

    ws_url = os.environ.get("VOLC_WS_URL", "").strip()
    api_key = (
        os.environ.get("VOLC_APP_KEY", "").strip()
        or os.environ.get("VOLC_API_KEY", "").strip()
    )
    resource_id = os.environ.get("VOLC_RESOURCE_ID", "volc.service_type.10053").strip()
    source_language = os.environ.get("SOURCE_LANGUAGE", "ja").strip()
    target_language = os.environ.get("TARGET_LANGUAGE", "zh").strip()
    mode = os.environ.get("MODE", "s2t").strip()
    chunk_ms = int(os.environ.get("CHUNK_MS", "80").strip())
    audio_input_name = os.environ.get("AUDIO_INPUT_NAME", "").strip() or None

    audio_input_index = os.environ.get("AUDIO_INPUT_INDEX", "").strip()
    input_index = int(audio_input_index) if audio_input_index else None

    text_log = os.environ.get("TEXT_LOG", "").strip()
    text_log_path = CURRENT_DIR / text_log if text_log else None

    if not ws_url or not api_key:
        raise RuntimeError(
            "请先复制 `.env.example` 为 `.env`，并填好 `VOLC_APP_KEY` "
            "或兼容旧写法 `VOLC_API_KEY`。"
        )
    if mode != "s2t":
        raise RuntimeError("这个 demo 先只实现了 `s2t`，后续再扩成 `s2s` 会更稳。")

    return Settings(
        ws_url=ws_url,
        api_key=api_key,
        resource_id=resource_id,
        source_language=source_language,
        target_language=target_language,
        mode=mode,
        chunk_ms=chunk_ms,
        audio_input_name=audio_input_name,
        audio_input_index=input_index,
        text_log=text_log_path,
    )


async def main() -> None:
    settings = build_settings()
    client = RealtimeAstClient(settings)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
