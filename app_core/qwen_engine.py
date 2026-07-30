from __future__ import annotations

import asyncio
import base64
import inspect
import json
import uuid
from dataclasses import dataclass
from typing import Callable, Optional
from urllib import error, request

import websockets

from app_core.qwen_languages import QWEN_LANG_NAME_BY_CODE
from app_core.translator import TranslatorConfig, TranslatorEvent, TranslatorEventCallback


_LANG_NAME_BY_CODE: dict[str, str] = {"auto": "auto", **QWEN_LANG_NAME_BY_CODE}


def lang_name(code: str) -> str:
    if not code:
        return "auto"
    return _LANG_NAME_BY_CODE.get(code.strip().lower(), code)


# ---------- qwen-mt-turbo REST ----------

_QWEN_MT_MAX_TERMS = 20

@dataclass
class QwenMtConfig:
    api_key: str
    base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    model: str = "qwen-mt-turbo"
    timeout: float = 10.0


def _filter_qwen_mt_terms(text: str, hotwords: Optional[dict[str, str]]) -> list[dict[str, str]]:
    if not hotwords:
        return []
    text_raw = text or ""
    text_lower = text_raw.lower()
    terms: list[dict[str, str]] = []
    for source, target in hotwords.items():
        source = (source or "").strip()
        target = (target or "").strip()
        if not source or not target:
            continue
        if source in text_raw or source.lower() in text_lower:
            terms.append({"source": source, "target": target})
            if len(terms) >= _QWEN_MT_MAX_TERMS:
                break
    return terms


def qwen_mt_translate(
    cfg: QwenMtConfig,
    text: str,
    source_lang: str,
    target_lang: str,
    on_status: Optional[Callable[[str], None]] = None,
    hotwords: Optional[dict[str, str]] = None,
) -> str:
    if not cfg.api_key:
        raise RuntimeError("未配置 Qwen API Key")
    url = cfg.base_url.rstrip("/") + "/services/aigc/text-generation/generation"
    translation_options: dict = {
        "source_lang": lang_name(source_lang),
        "target_lang": lang_name(target_lang or "en"),
    }
    terms = _filter_qwen_mt_terms(text, hotwords)
    if terms:
        translation_options["terms"] = terms
    if on_status and hotwords:
        try:
            on_status(f"[qwen-mt-hotwords] matched {len(terms)}/{len(hotwords)}")
        except Exception:
            pass
    body = {
        "model": cfg.model,
        "input": {"messages": [{"role": "user", "content": text}]},
        "parameters": {"translation_options": translation_options},
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "disable",
    }
    req = request.Request(url, data=raw, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=cfg.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"Qwen MT HTTP {exc.code}: {detail or exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Qwen MT 请求失败：{exc}") from exc
    if on_status:
        try:
            usage = payload.get("usage") or {}
            on_status(f"[qwen-mt-raw] {payload}")
            if usage:
                on_status(f"[qwen-mt-usage] {usage}")
        except Exception:
            pass
    out = payload.get("output") or {}
    text_out = out.get("text")
    if not text_out:
        choices = out.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, list):
                text_out = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            else:
                text_out = content
    if not text_out:
        raise RuntimeError(f"Qwen MT 响应缺少译文：{payload}")
    return text_out.strip()


# ---------- qwen3-livetranslate-flash-realtime WebSocket ----------

_QWEN_REALTIME_WS = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
_QWEN_LT_MODEL = "qwen3.5-livetranslate-flash-realtime"


def _qwen_usage_from_message(msg: dict) -> dict:
    response = msg.get("response") or {}
    usage = response.get("usage") or msg.get("usage") or {}
    return usage if isinstance(usage, dict) else {}


def _emit_qwen_usage(on_status: Optional[Callable[[str], None]], tag: str, usage: dict) -> None:
    if on_status and usage:
        on_status(f"[{tag}] {usage}")


def _connect_kwargs(api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    kwargs = {"max_size": 16 * 1024 * 1024, "ping_interval": None}
    sig = inspect.signature(websockets.connect)
    if "additional_headers" in sig.parameters:
        kwargs["additional_headers"] = headers
    else:
        kwargs["extra_headers"] = headers
    return kwargs


class QwenLiveTranslateEngine:
    """Realtime S2S/字幕：单一 WS 同时给出译文文本 + 译文音频。

    mode='s2s' → 启用音频输出；mode='s2t' → 只输出文本（字幕）。
    """

    def __init__(
        self,
        api_key: str,
        mode: str = "s2s",
        model: str = _QWEN_LT_MODEL,
        voice: str = "default",
        realtime_url: str = _QWEN_REALTIME_WS,
    ) -> None:
        self.api_key = api_key
        self.mode = mode
        self.model = model
        self.voice = voice or "default"
        self.realtime_url = realtime_url or _QWEN_REALTIME_WS
        self.config: Optional[TranslatorConfig] = None
        self.on_event: Optional[TranslatorEventCallback] = None
        self.ws = None
        self.sender_task: Optional[asyncio.Task] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.audio_queue: Optional[asyncio.Queue[bytes | None]] = None
        self.audio_segment_id = 0
        self.dropped_audio_chunks = 0
        self._source_acc = ""
        # 译文累计采用 part-aware 双层结构：
        #   _trans_done_parts —— 已被 response.content_part.done 收口的 content_part 文本，按到达顺序排列
        #   _trans_active_part —— 当前正在通过 delta / 快照构建的 content_part
        # 任何 emit 出去的译文都用 "".join(done) + active 计算，跨 part 边界不会再被
        # 单个 part 的快照覆盖回退（这是火山引擎事件流不需要担心的细节，但 Qwen 会）。
        self._trans_done_parts: list[str] = []
        self._trans_active_part: str = ""

    def _trans_text(self) -> str:
        return "".join(self._trans_done_parts) + self._trans_active_part

    def _commit_active_part(self) -> None:
        if self._trans_active_part:
            self._trans_done_parts.append(self._trans_active_part)
        self._trans_active_part = ""

    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        self.config = config
        self.on_event = on_event
        self.audio_queue = asyncio.Queue(maxsize=128)
        url = f"{self.realtime_url}?model={self.model}"
        self.ws = await websockets.connect(url, **_connect_kwargs(self.api_key))
        await self._send_session_update()
        self.sender_task = asyncio.create_task(self._send_loop())
        self.receiver_task = asyncio.create_task(self._receive_loop())
        self._emit("status", message=f"[qwen-{self.mode}] session.update sent")

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

    async def _send_session_update(self) -> None:
        assert self.ws is not None and self.config is not None
        src = (self.config.source_language or "auto").lower()
        tgt = (self.config.target_language or "en").lower()
        modalities = ["text", "audio"] if self.mode == "s2s" else ["text"]
        translation: dict = {"language": tgt}
        if self.config.hotwords:
            translation["corpus"] = {"phrases": dict(self.config.hotwords)}
        session: dict = {
            "sample_rate": self.config.sample_rate,
            "input_audio_format": "pcm",
            "modalities": modalities,
            "translation": translation,
            "input_audio_transcription": {"model": "qwen3-asr-flash-realtime"},
        }
        if self.mode == "s2s":
            session["output_audio_format"] = "pcm"
            if self.voice.startswith("qwen-translate-vc-"):
                session["voice"] = self.voice
                session["enable_voice_clone"] = True
                session["voice_clone_options"] = {"frequency": "never"}
            elif self.voice == "default":
                session["voice"] = "default"
                session["enable_voice_clone"] = True
                session["voice_clone_options"] = {"frequency": "once"}
            else:
                session["voice"] = self.voice
        evt = {"event_id": f"evt_{uuid.uuid4().hex[:8]}", "type": "session.update", "session": session}
        await self.ws.send(json.dumps(evt, ensure_ascii=False))

    async def _send_loop(self) -> None:
        assert self.ws is not None and self.audio_queue is not None
        while True:
            chunk = await self.audio_queue.get()
            if chunk is None:
                try:
                    await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                except Exception:
                    pass
                break
            try:
                b64 = base64.b64encode(chunk).decode("ascii")
                await self.ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64}))
            except Exception as exc:
                self._emit("error", message=f"qwen send failed: {exc}")
                break

    async def _receive_loop(self) -> None:
        assert self.ws is not None
        try:
            while True:
                raw = await self.ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="ignore")
                try:
                    msg = json.loads(raw)
                except Exception:
                    self._emit("status", message=f"[qwen-text-frame] {raw[:200]}")
                    continue
                self._handle_event(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._emit("error", message=f"qwen recv failed: {exc}")

    def _handle_event(self, msg: dict) -> None:
        et = msg.get("type", "")
        if et == "error":
            err = msg.get("error", {})
            self._emit("error", message=f"qwen error: {err}")
            return
        if et in ("session.created", "session.updated"):
            self._emit("status", message=f"[qwen] {et}")
            return
        if et == "response.created":
            self.audio_segment_id += 1
            self._source_acc = ""
            self._trans_done_parts = []
            self._trans_active_part = ""
            return
        if et == "conversation.item.input_audio_transcription.delta":
            d = msg.get("delta") or ""
            if d:
                self._source_acc += d
                self._emit("source_text", text=self._source_acc)
            return
        if et == "conversation.item.input_audio_transcription.text":
            committed = msg.get("text") or ""
            stash = msg.get("stash") or ""
            full = committed + stash
            if full:
                self._source_acc = full
                self._emit("source_text", text=full)
            return
        if et == "conversation.item.input_audio_transcription.completed":
            t = msg.get("transcript") or ""
            if t:
                self._source_acc = t
                self._emit("source_text", text=t)
            self._emit("source_text_final", text=self._source_acc)
            return
        if et in ("response.audio_transcript.delta", "response.text.delta"):
            d = msg.get("delta") or ""
            if d:
                self._trans_active_part += d
                self._emit("translated_text", text=self._trans_text())
            return
        if et == "response.text.text":
            # 当前 content_part 的快照（committed 部分 + stash 未确认部分）。仅在它
            # 不短于当前累计时采纳，避免下一个 part 的开头碎片把这个 part 已经累到的
            # 译文截短。
            committed = msg.get("text") or ""
            stash = msg.get("stash") or ""
            full = committed + stash
            if full and len(full) >= len(self._trans_active_part):
                self._trans_active_part = full
                self._emit("translated_text", text=self._trans_text())
            return
        if et in ("response.audio_transcript.done", "response.text.done"):
            # 单个 content_part 的"音频转写"或"文本"轨道完结。把权威 transcript 吸收进
            # 当前 active part，但不在这里收口——收口统一由 content_part.done 负责，
            # 防止 .done 和 content_part.done 串行触达时双重 commit。
            t = msg.get("transcript") or msg.get("text") or ""
            if t and len(t) >= len(self._trans_active_part):
                self._trans_active_part = t
            self._emit("translated_text", text=self._trans_text())
            return
        if et == "response.content_part.done":
            # content_part 真正收口：先吸收权威文本，再把 active part 推入 done_parts。
            # 下一个 part 的 delta 会从空 active 重新累计，因此不会"接在上一个 part 后面"
            # 也不会"把上一个 part 覆盖掉"。
            part = msg.get("part") or {}
            t = part.get("text") or ""
            if t and len(t) >= len(self._trans_active_part):
                self._trans_active_part = t
            self._commit_active_part()
            self._emit("translated_text", text=self._trans_text())
            return
        if et == "response.audio.delta":
            b64 = msg.get("delta") or ""
            if b64:
                try:
                    data = base64.b64decode(b64)
                except Exception:
                    return
                self._emit("translated_audio", data=data, segment_id=self.audio_segment_id)
            return
        if et == "response.done":
            usage = _qwen_usage_from_message(msg)
            if usage:
                self._emit("status", message=f"[qwen-realtime-usage] {usage}")
            self._emit("translated_text_final", text=self._trans_text())
            self._emit("status", message="[qwen] response.done")
            return
        self._emit("status", message=f"[qwen-evt] {et}")

    def _emit(self, event_type: str, data: bytes = b"", text: str = "", message: str = "", segment_id: int = 0) -> None:
        if self.on_event is not None:
            self.on_event(TranslatorEvent(type=event_type, data=data, text=text, message=message, segment_id=segment_id))


# ---------- src==tgt 旁路：ASR + TTS（不经翻译） ----------


class QwenAsrTtsEngine:
    """src==tgt 场景：使用 LiveTranslate 仅做 ASR，再把识别结果直接 TTS 出来。"""

    def __init__(
        self,
        api_key: str,
        voice: str = "Cherry",
        model: str = _QWEN_LT_MODEL,
        realtime_url: str = _QWEN_REALTIME_WS,
    ) -> None:
        self.api_key = api_key
        self.voice = voice or "Cherry"
        self.model = model
        self.realtime_url = realtime_url or _QWEN_REALTIME_WS
        self.config: Optional[TranslatorConfig] = None
        self.on_event: Optional[TranslatorEventCallback] = None
        self.ws = None
        self.sender_task: Optional[asyncio.Task] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.audio_queue: Optional[asyncio.Queue[bytes | None]] = None
        self.audio_segment_id = 0
        self.dropped_audio_chunks = 0
        self._source_acc = ""
        self._tts_tasks: list[asyncio.Task] = []

    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        self.config = config
        self.on_event = on_event
        self.audio_queue = asyncio.Queue(maxsize=128)
        url = f"{self.realtime_url}?model={self.model}"
        self.ws = await websockets.connect(url, **_connect_kwargs(self.api_key))
        tgt = (config.target_language or "zh").lower()
        session = {
            "sample_rate": config.sample_rate,
            "input_audio_format": "pcm",
            "modalities": ["text"],
            "translation": {"language": tgt},
            "input_audio_transcription": {"model": "qwen3-asr-flash-realtime"},
        }
        await self.ws.send(json.dumps({
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": "session.update",
            "session": session,
        }, ensure_ascii=False))
        self.sender_task = asyncio.create_task(self._send_loop())
        self.receiver_task = asyncio.create_task(self._receive_loop())
        self._emit("status", message="[qwen-asr+tts] session.update sent")

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
        for t in self._tts_tasks:
            t.cancel()
        self._tts_tasks.clear()
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        self.audio_queue = None

    async def _send_loop(self) -> None:
        assert self.ws is not None and self.audio_queue is not None
        while True:
            chunk = await self.audio_queue.get()
            if chunk is None:
                try:
                    await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                except Exception:
                    pass
                break
            try:
                b64 = base64.b64encode(chunk).decode("ascii")
                await self.ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64}))
            except Exception as exc:
                self._emit("error", message=f"qwen send failed: {exc}")
                break

    async def _receive_loop(self) -> None:
        assert self.ws is not None
        try:
            while True:
                raw = await self.ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="ignore")
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                et = msg.get("type", "")
                if et == "error":
                    self._emit("error", message=f"qwen error: {msg.get('error', {})}")
                    continue
                if et == "response.done":
                    usage = _qwen_usage_from_message(msg)
                    if usage:
                        self._emit("status", message=f"[qwen-realtime-usage] {usage}")
                    continue
                if et == "conversation.item.input_audio_transcription.delta":
                    d = msg.get("delta") or ""
                    if d:
                        self._source_acc += d
                        self._emit("source_text", text=self._source_acc)
                    continue
                if et == "conversation.item.input_audio_transcription.completed":
                    t = msg.get("transcript") or self._source_acc
                    if t:
                        self.audio_segment_id += 1
                        seg = self.audio_segment_id
                        self._emit("source_text", text=t)
                        self._emit("translated_text", text=t)
                        task = asyncio.create_task(self._run_tts(t, seg))
                        self._tts_tasks.append(task)
                    self._source_acc = ""
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._emit("error", message=f"qwen recv failed: {exc}")

    async def _run_tts(self, text: str, segment_id: int) -> None:
        cfg = QwenTtsConfig(api_key=self.api_key, voice=self.voice, realtime_url=self.realtime_url)

        def on_pcm(data: bytes) -> None:
            self._emit("translated_audio", data=data, segment_id=segment_id)

        def on_status(msg: str) -> None:
            self._emit("status", message=msg)

        try:
            await qwen_tts_stream(cfg, text, on_pcm, on_status)
        except Exception as exc:
            self._emit("error", message=f"qwen tts failed: {exc}")

    def _emit(self, event_type: str, data: bytes = b"", text: str = "", message: str = "", segment_id: int = 0) -> None:
        if self.on_event is not None:
            self.on_event(TranslatorEvent(type=event_type, data=data, text=text, message=message, segment_id=segment_id))


# ---------- qwen-tts-realtime (typed 翻译后 TTS) ----------

_QWEN_TTS_MODEL = "qwen3-tts-flash-realtime"

PcmCallback = Callable[[bytes], None]
StatusCallback = Callable[[str], None]


@dataclass
class QwenTtsConfig:
    api_key: str
    voice: str = "Cherry"
    sample_rate: int = 24000
    model: str = _QWEN_TTS_MODEL
    realtime_url: str = _QWEN_REALTIME_WS


async def qwen_tts_stream(
    cfg: QwenTtsConfig,
    text: str,
    on_pcm: PcmCallback,
    on_status: Optional[StatusCallback] = None,
) -> None:
    if not cfg.api_key:
        raise RuntimeError("未配置 Qwen API Key")
    if not text:
        return
    url = f"{(cfg.realtime_url or _QWEN_REALTIME_WS)}?model={cfg.model}"
    ws = await websockets.connect(url, **_connect_kwargs(cfg.api_key))
    try:
        session = {
            "voice": cfg.voice or "Cherry",
            "output_audio_format": "pcm",
            "mode": "server_commit",
            "modalities": ["audio"],
        }
        await ws.send(json.dumps({
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": "session.update",
            "session": session,
        }))
        await ws.send(json.dumps({"type": "input_text_buffer.append", "text": text}))
        await ws.send(json.dumps({"type": "input_text_buffer.commit"}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            except asyncio.TimeoutError:
                if on_status:
                    on_status("[qwen-tts] timeout")
                break
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            et = msg.get("type", "")
            if et == "response.audio.delta":
                b64 = msg.get("delta") or ""
                if b64:
                    try:
                        on_pcm(base64.b64decode(b64))
                    except Exception:
                        pass
            elif et == "response.done":
                _emit_qwen_usage(on_status, "qwen-tts-usage", _qwen_usage_from_message(msg))
                break
            elif et == "response.audio.done":
                break
            elif et == "error":
                err = msg.get("error", {})
                raise RuntimeError(f"Qwen TTS error: {err}")
            else:
                if on_status:
                    on_status(f"[qwen-tts-evt] {et}")
    finally:
        try:
            await ws.close()
        except Exception:
            pass
