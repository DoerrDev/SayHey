from __future__ import annotations

import asyncio
import inspect
import sys
import uuid
from pathlib import Path
from typing import Optional

import websockets
from google.protobuf.json_format import MessageToDict

CURRENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CURRENT_DIR))

from app_core.translator import TranslatorConfig, TranslatorEvent, TranslatorEventCallback
from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateResponse


class VolcAstS2SEngine:
    def __init__(self, ws_url: str, api_key: str, resource_id: str) -> None:
        self.ws_url = ws_url
        self.api_key = api_key
        self.resource_id = resource_id
        self.session_id = str(uuid.uuid4())
        self.connection_id = str(uuid.uuid4())
        self.config: Optional[TranslatorConfig] = None
        self.on_event: Optional[TranslatorEventCallback] = None
        self.ws = None
        self.sender_task: Optional[asyncio.Task] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.audio_queue: Optional[asyncio.Queue[bytes | None]] = None
        self.dropped_audio_chunks = 0
        self.seen_source = ""
        self.seen_translation = ""
        self._source_acc = ""
        self._translation_acc = ""
        self.audio_segment_id = 0

    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        self.config = config
        self.on_event = on_event
        self.ws = await websockets.connect(self.ws_url, **self._connect_kwargs())
        self.audio_queue = asyncio.Queue(maxsize=64)
        response_headers = getattr(self.ws, "response_headers", None)
        if response_headers is None and hasattr(self.ws, "response"):
            response_headers = self.ws.response.headers
        log_id = response_headers.get("X-Tt-Logid") if response_headers else None
        self._emit("status", message=f"[connect] X-Tt-Logid={log_id}")
        await self.ws.send(self._build_start_request().SerializeToString())
        self.sender_task = asyncio.create_task(self._send_loop())
        self.receiver_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if self.audio_queue is None:
            return
        try:
            self.audio_queue.put_nowait(pcm_bytes)
        except asyncio.QueueFull:
            self.dropped_audio_chunks += 1
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.audio_queue.put_nowait(pcm_bytes)
            except asyncio.QueueFull:
                pass
            if self.dropped_audio_chunks == 1 or self.dropped_audio_chunks % 50 == 0:
                self._emit(
                    "status",
                    message=f"[audio-drop] realtime queue full, dropped {self.dropped_audio_chunks} chunks",
                )

    async def stop(self) -> None:
        if self.audio_queue is not None:
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                self.audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        if self.sender_task is not None:
            try:
                await asyncio.wait_for(self.sender_task, timeout=1.5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.sender_task.cancel()
        if self.receiver_task is not None:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
        if self.ws is not None:
            await self.ws.close()
        self.ws = None
        self.audio_queue = None

    def _connect_kwargs(self) -> dict:
        headers = {
            "X-Api-Key": self.api_key,
            "X-Api-App-Key": self.api_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": self.connection_id,
        }
        kwargs = {"max_size": 16 * 1024 * 1024, "ping_interval": None}
        connect_signature = inspect.signature(websockets.connect)
        if "additional_headers" in connect_signature.parameters:
            kwargs["additional_headers"] = headers
        else:
            kwargs["extra_headers"] = headers
        return kwargs

    async def _send_loop(self) -> None:
        assert self.ws is not None
        assert self.audio_queue is not None
        while True:
            chunk = await self.audio_queue.get()
            if chunk is None:
                try:
                    await self.ws.send(self._build_finish_request().SerializeToString())
                except Exception:
                    pass
                break
            try:
                await self.ws.send(self._build_audio_request(chunk).SerializeToString())
            except Exception as exc:
                self._emit("error", message=f"websocket send failed: {exc}")
                break

    async def _receive_loop(self) -> None:
        assert self.ws is not None
        try:
            while True:
                raw = await self.ws.recv()
                if isinstance(raw, str):
                    self._emit("status", message=f"[text-frame] {raw}")
                    continue
                self._handle_response(raw)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._emit("error", message=f"websocket receive failed: {exc}")

    def _handle_response(self, raw: bytes) -> None:
        response = TranslateResponse()
        response.ParseFromString(raw)

        if response.event == Type.SessionStarted:
            self._emit("status", message=f"[session] started: {self.session_id}")
        elif response.event == Type.SourceSubtitleResponse and response.text != self.seen_source:
            self.seen_source = response.text
            self._source_acc += response.text
            self._emit("source_text", text=self._source_acc)
        elif response.event == Type.TranslationSubtitleResponse and response.text != self.seen_translation:
            self.seen_translation = response.text
            self._translation_acc += response.text
            self._emit("translated_text", text=self._translation_acc)
        elif response.event == Type.TTSResponse and response.data:
            self._emit("translated_audio", data=response.data, segment_id=self.audio_segment_id)
            self._emit("status", message=f"[tts] {len(response.data)} bytes")
        elif response.event == Type.TTSSentenceStart:
            self.audio_segment_id += 1
            self._source_acc = ""
            self._translation_acc = ""
            self.seen_source = ""
            self.seen_translation = ""
            self._emit("status", message="[tts] sentence start")
        elif response.event == Type.TTSSentenceEnd:
            self._emit("status", message="[tts] sentence end")
        elif response.event == Type.UsageResponse:
            usage = MessageToDict(response, preserving_proto_field_name=True)
            self._emit("status", message=f"[usage] {usage}")
        elif response.event == Type.AudioMuted:
            self._emit("status", message=f"[muted] {response.muted_duration_ms} ms")
        elif response.event == Type.SessionFailed:
            message = response.response_meta.Message or "unknown error"
            self._emit("error", message=f"session failed: {message}")
        elif response.event == Type.SessionFinished:
            self._emit("status", message="[session] finished")

    def _build_start_request(self) -> TranslateRequest:
        assert self.config is not None
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.StartSession
        request.user.uid = "gt_game_translator"
        request.user.did = "windows_vb_cable"
        request.user.platform = "Windows"
        request.user.sdk_version = "demo"

        request.source_audio.format = "wav"
        request.source_audio.codec = "raw"
        request.source_audio.rate = self.config.sample_rate
        request.source_audio.bits = 16
        request.source_audio.channel = 1

        request.target_audio.format = "pcm"
        request.target_audio.rate = self.config.sample_rate

        request.request.mode = "s2s"
        request.request.source_language = self.config.source_language
        request.request.target_language = self.config.target_language
        request.request.speech_rate = self.config.speech_rate
        if self.config.speaker_id:
            request.request.speaker_id = self.config.speaker_id
        return request

    def _build_audio_request(self, pcm_bytes: bytes) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.TaskRequest
        request.source_audio.binary_data = pcm_bytes
        return request

    def _build_finish_request(self) -> TranslateRequest:
        request = TranslateRequest()
        request.request_meta.SessionID = self.session_id
        request.request_meta.ConnectionID = self.connection_id
        request.request_meta.ResourceID = self.resource_id
        request.request_meta.Endpoint = "translate"
        request.event = Type.FinishSession
        return request

    def _emit(
        self,
        event_type: str,
        data: bytes = b"",
        text: str = "",
        message: str = "",
        segment_id: int = 0,
    ) -> None:
        if self.on_event is not None:
            self.on_event(
                TranslatorEvent(type=event_type, data=data, text=text, message=message, segment_id=segment_id)
            )
