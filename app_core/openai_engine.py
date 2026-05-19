from __future__ import annotations

import asyncio
import base64
import inspect
import json
from typing import Optional

import websockets

from app_core.translator import TranslatorConfig, TranslatorEvent, TranslatorEventCallback


class OpenAIRealtimeTranslateEngine:
    def __init__(
        self,
        api_key: str,
        ws_url: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.ws_url = ws_url
        self.model = model
        self.config: Optional[TranslatorConfig] = None
        self.on_event: Optional[TranslatorEventCallback] = None
        self.ws = None
        self.sender_task: Optional[asyncio.Task] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.audio_queue: Optional[asyncio.Queue[bytes | None]] = None
        self.dropped_audio_chunks = 0
        self.audio_segment_id = 0
        self.in_audio_segment = False
        self.current_audio_item_id = ""
        self._source_acc = ""
        self._translation_acc = ""

    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Fill demo/volc_ast_voicemeeter/openapi.env first.")

        self.config = config
        self.on_event = on_event
        self.audio_queue = asyncio.Queue(maxsize=96)
        self.ws = await websockets.connect(self._connect_url(), **self._connect_kwargs())
        session_update = self._session_update()
        self._emit("status", message=f"[openai] connected url={self._connect_url()}")
        self._emit("status", message=f"[openai-session] {json.dumps(session_update, ensure_ascii=False)}")
        await self.ws.send(json.dumps(session_update))
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
                    message=f"[openai-audio-drop] realtime queue full, dropped {self.dropped_audio_chunks} chunks",
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
            self.sender_task = None

        if self.receiver_task is not None:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
            self.receiver_task = None

        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        self.audio_queue = None
        self._emit("status", message="[openai] stopped")

    def _connect_url(self) -> str:
        separator = "&" if "?" in self.ws_url else "?"
        if "model=" in self.ws_url:
            return self.ws_url
        return f"{self.ws_url}{separator}model={self.model}"

    def _connect_kwargs(self) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        kwargs = {"max_size": 16 * 1024 * 1024, "ping_interval": 20, "ping_timeout": 20}
        connect_signature = inspect.signature(websockets.connect)
        if "additional_headers" in connect_signature.parameters:
            kwargs["additional_headers"] = headers
        else:
            kwargs["extra_headers"] = headers
        return kwargs

    def _session_update(self) -> dict:
        assert self.config is not None
        return {
            "type": "session.update",
            "session": {
                "audio": {
                    "input": {},
                    "output": {
                        "language": self.config.target_language,
                    },
                },
            },
        }

    async def _send_loop(self) -> None:
        assert self.ws is not None
        assert self.audio_queue is not None
        while True:
            chunk = await self.audio_queue.get()
            if chunk is None:
                break
            payload = {
                "type": "session.input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode("ascii"),
            }
            try:
                await self.ws.send(json.dumps(payload))
            except Exception as exc:
                self._emit("error", message=f"openai websocket send failed: {exc}")
                break

    async def _receive_loop(self) -> None:
        assert self.ws is not None
        try:
            async for raw in self.ws:
                event = json.loads(raw)
                self._handle_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._emit("error", message=f"openai websocket receive failed: {exc}")

    def _handle_event(self, event: dict) -> None:
        event_type = event.get("type", "")
        if event_type in {"session.created", "session.updated"}:
            self._emit("status", message=f"[openai] {event_type}")
        elif event_type == "conversation.item.input_audio_transcription.delta":
            self._source_acc += event.get("delta", "")
            self._emit("source_text", text=self._source_acc)
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            self._source_acc = transcript
            self._emit("source_text", text=transcript)
        elif event_type in {
            "response.output_audio_transcript.delta",
            "session.output_audio_transcript.delta",
            "session.output_transcript.delta",
        }:
            self._translation_acc += event.get("delta", "")
            self._emit("translated_text", text=self._translation_acc)
        elif event_type in {
            "response.output_audio_transcript.done",
            "session.output_audio_transcript.done",
            "session.output_transcript.done",
        }:
            transcript = event.get("transcript") or event.get("text") or ""
            if transcript:
                self._translation_acc = transcript
                self._emit("translated_text", text=transcript)
            self._translation_acc = ""
            self._source_acc = ""
            self._emit("status", message="[openai] transcript done")
        elif event_type in {"response.output_audio.delta", "session.output_audio.delta"}:
            item_id = self._output_item_key(event)
            if item_id and item_id != self.current_audio_item_id:
                self.current_audio_item_id = item_id
                self.in_audio_segment = False
            if not self.in_audio_segment:
                self.audio_segment_id += 1
                self.in_audio_segment = True
                id_label = f", item={item_id}" if item_id else ""
                self._emit("status", message=f"[openai] audio segment start #{self.audio_segment_id}{id_label}")
            audio = base64.b64decode(event.get("delta", ""))
            self._emit("translated_audio", data=audio, segment_id=self.audio_segment_id)
            self._emit("status", message=f"[openai-tts] {len(audio)} bytes")
        elif event_type in {"response.output_audio.done", "session.output_audio.done"}:
            self.in_audio_segment = False
            self.current_audio_item_id = ""
            self._emit("status", message="[openai] audio done")
        elif event_type in {"input_audio_buffer.speech_started", "session.input_audio_buffer.speech_started"}:
            self._emit("status", message="[openai] speech started")
        elif event_type in {"input_audio_buffer.speech_stopped", "session.input_audio_buffer.speech_stopped"}:
            self._emit("status", message="[openai] speech stopped")
        elif event_type == "error":
            error = event.get("error", {})
            message = error.get("message") if isinstance(error, dict) else str(error)
            self._emit("error", message=f"openai error: {message or event}")
        elif event_type:
            self._emit("status", message=f"[openai-event] {event_type}")

    def _output_item_key(self, event: dict) -> str:
        for key in ("item_id", "response_id", "output_index", "content_index"):
            value = event.get(key)
            if value is not None:
                return str(value)
        return ""

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
