from __future__ import annotations

import asyncio
import gzip
import json
import struct
import uuid
from dataclasses import dataclass
from typing import Callable, Optional
from urllib import error, request

import websockets
from websockets.exceptions import InvalidStatusCode


# ---------- Doubao Machine Translation (REST) ----------

_DOUBAO_MT_URL = "https://openspeech.bytedance.com/api/v3/machine_translation/matx_translate"
_DOUBAO_MT_RESOURCE_ID = "volc.speech.mt"


@dataclass
class DoubaoTranslateConfig:
    api_key: str = ""
    resource_id: str = _DOUBAO_MT_RESOURCE_ID
    endpoint: str = _DOUBAO_MT_URL
    timeout: float = 8.0


def doubao_translate_text(cfg: DoubaoTranslateConfig, text: str, source_lang: str, target_lang: str, on_status: Optional[Callable[[str], None]] = None) -> str:
    if not cfg.api_key:
        raise RuntimeError("未配置豆包机器翻译 API Key")

    body_obj: dict = {"text_list": [text], "target_language": target_lang}
    if source_lang and source_lang != "auto":
        body_obj["source_language"] = source_lang
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Api-Resource-Id": cfg.resource_id or _DOUBAO_MT_RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    headers["X-Api-Key"] = cfg.api_key

    req = request.Request(cfg.endpoint or _DOUBAO_MT_URL, data=body, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=cfg.timeout) as resp:
            resp_headers = dict(resp.headers)
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = _read_http_error_detail(exc)
        raise RuntimeError(
            f"豆包机器翻译请求失败：HTTP {exc.code} {exc.reason}。{detail}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"豆包机器翻译请求失败：{exc}") from exc

    if on_status:
        try:
            on_status(f"[typed-mt-raw] {payload} | headers={resp_headers}")
        except Exception:
            pass
        try:
            lst = (payload.get("data") or {}).get("translation_list") or []
            usage = (lst[0] if lst else {}).get("usage") or {}
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            if prompt or completion:
                evt = {
                    "response_meta": {
                        "SessionID": resp_headers.get("X-Api-Request-Id", ""),
                        "Billing": {
                            "DurationMsec": 0,
                            "Items": [
                                {"Unit": "input_text_tokens", "Quantity": prompt},
                                {"Unit": "output_text_tokens", "Quantity": completion},
                            ],
                        },
                    }
                }
                on_status(f"[mt-usage] {evt}")
        except Exception:
            pass
    code = payload.get("code")
    if code != 20000000:
        raise RuntimeError(f"豆包机器翻译 API 错误：code={code}, message={payload.get('message')}")
    lst = payload.get("data", {}).get("translation_list") or []
    if not lst:
        raise RuntimeError("豆包机器翻译响应为空")
    return lst[0].get("translation") or ""


def _read_http_error_detail(exc: error.HTTPError) -> str:
    raw = exc.read() if exc.fp is not None else b""
    if not raw:
        return "服务端未返回错误详情；请确认 API Key 已开通 volc.speech.mt 权限。"
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return f"响应体：{text}"
    code = payload.get("code")
    message = payload.get("message") or payload.get("ResponseMetadata", {}).get("Error", {}).get("Message")
    if code or message:
        if isinstance(message, str) and "requested resource not granted" in message:
            return (
                f"code={code}, message={message}。当前 Key 未开通 {_resource_id_from_message(message)} 权限，"
                "请在豆包语音控制台为该 Key 开通机器翻译大模型资源 volc.speech.mt。"
            )
        return f"code={code}, message={message}"
    return f"响应体：{payload}"


def _resource_id_from_message(message: str) -> str:
    prefix = "[resource_id="
    if prefix not in message:
        return "对应资源"
    start = message.find(prefix) + len(prefix)
    end = message.find("]", start)
    if end < 0:
        return "对应资源"
    return message[start:end]


# ---------- Doubao Speech Synthesis WebSocket V3 streaming ----------

_TTS_WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
_TTS_RESOURCE_ID_DEFAULT = "seed-tts-2.0"
_TTS_SPEAKER_DEFAULT = "zh_female_xiaohe_uranus_bigtts"
_S2S_TO_TTS_SPEAKER = {
    "zh_female_vv_jupiter_bigtts": "zh_female_vv_uranus_bigtts",
    "zh_female_xiaohe_jupiter_bigtts": "zh_female_xiaohe_uranus_bigtts",
    "zh_male_yunzhou_jupiter_bigtts": "zh_male_m191_uranus_bigtts",
    "zh_male_xiaotian_jupiter_bigtts": "zh_male_taocheng_uranus_bigtts",
}

# Binary protocol header
_PROTOCOL_VERSION = 0b0001
_HEADER_SIZE = 0b0001  # 4 bytes
_MSG_FULL_CLIENT = 0b0001
_MSG_AUDIO_ONLY_SERVER = 0b1011
_MSG_FULL_SERVER = 0b1001
_MSG_ERROR_SERVER = 0b1111
_FLAGS_NONE = 0b0000
_FLAGS_LAST = 0b0010
_FLAGS_EVENT = 0b0100
_SERIALIZATION_JSON = 0b0001
_SERIALIZATION_NONE = 0b0000
_COMPRESSION_NONE = 0b0000
_COMPRESSION_GZIP = 0b0001

_EVENT_START_CONNECTION = 1
_EVENT_FINISH_CONNECTION = 2
_EVENT_CONNECTION_STARTED = 50
_EVENT_START_SESSION = 100
_EVENT_FINISH_SESSION = 102
_EVENT_TASK_REQUEST = 200
_EVENT_SESSION_STARTED = 150
_EVENT_SESSION_FINISHED = 152
_EVENT_TTS_RESPONSE = 352
_EVENT_TTS_SENTENCE_START = 350
_EVENT_TTS_SENTENCE_END = 351
_EVENT_TTS_ENDED = 359


def _pack_frame(
    msg_type: int,
    flags: int,
    serialization: int,
    compression: int,
    event: Optional[int],
    session_id: Optional[str],
    payload: bytes,
) -> bytes:
    if compression == _COMPRESSION_GZIP:
        payload = gzip.compress(payload)
    header = bytes([
        (_PROTOCOL_VERSION << 4) | _HEADER_SIZE,
        (msg_type << 4) | flags,
        (serialization << 4) | compression,
        0,
    ])
    body = b""
    if event is not None:
        body += struct.pack(">i", event)
    if session_id is not None:
        sid = session_id.encode("utf-8")
        body += struct.pack(">I", len(sid)) + sid
    body += struct.pack(">I", len(payload)) + payload
    return header + body


def _parse_frame(data: bytes) -> dict:
    if len(data) < 4:
        return {"msg_type": 0}
    header_size = (data[0] & 0x0F) * 4
    msg_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    serialization = (data[2] >> 4) & 0x0F
    compression = data[2] & 0x0F
    offset = header_size
    event = None
    session_id = None
    if flags & _FLAGS_EVENT:
        if len(data) < offset + 4:
            return {"msg_type": msg_type}
        event = struct.unpack(">i", data[offset:offset + 4])[0]
        offset += 4
        if msg_type in (_MSG_FULL_SERVER, _MSG_AUDIO_ONLY_SERVER):
            sid_len = struct.unpack(">I", data[offset:offset + 4])[0]
            offset += 4
            session_id = data[offset:offset + sid_len].decode("utf-8", errors="ignore")
            offset += sid_len
    if msg_type == _MSG_ERROR_SERVER:
        err_code = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        payload_len = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        payload = data[offset:offset + payload_len]
        return {
            "msg_type": msg_type,
            "event": event,
            "session_id": session_id,
            "error_code": err_code,
            "payload": payload,
        }
    payload_len = struct.unpack(">I", data[offset:offset + 4])[0]
    offset += 4
    payload = data[offset:offset + payload_len]
    if compression == _COMPRESSION_GZIP and payload:
        try:
            payload = gzip.decompress(payload)
        except Exception:
            pass
    if serialization == _SERIALIZATION_JSON and payload:
        try:
            payload = json.loads(payload.decode("utf-8"))
        except Exception:
            pass
    return {"msg_type": msg_type, "event": event, "session_id": session_id, "payload": payload, "flags": flags}


@dataclass
class DoubaoTtsConfig:
    api_key: str
    speaker_id: str = _TTS_SPEAKER_DEFAULT
    sample_rate: int = 24000
    speech_rate: int = 0
    resource_id: str = _TTS_RESOURCE_ID_DEFAULT


def resolve_doubao_tts_speaker(speaker_id: str) -> str:
    speaker_id = (speaker_id or "").strip()
    if not speaker_id:
        return _TTS_SPEAKER_DEFAULT
    if "_uranus_bigtts" in speaker_id:
        return speaker_id
    return _S2S_TO_TTS_SPEAKER.get(speaker_id, _TTS_SPEAKER_DEFAULT)


PcmCallback = Callable[[bytes], None]
StatusCallback = Callable[[str], None]


async def doubao_tts_stream(
    cfg: DoubaoTtsConfig,
    text: str,
    on_pcm: PcmCallback,
    on_status: Optional[StatusCallback] = None,
) -> None:
    if not cfg.api_key:
        raise RuntimeError("未配置豆包语音合成 API Key")
    connect_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    if on_status:
        try:
            chars = len(text or "")
            if chars > 0:
                evt = {
                    "response_meta": {
                        "SessionID": session_id,
                        "Billing": {
                            "DurationMsec": 0,
                            "Items": [{"Unit": "tts_chars", "Quantity": chars}],
                        },
                    }
                }
                on_status(f"[tts-usage] {evt}")
        except Exception:
            pass
    headers = {
        "X-Api-Key": cfg.api_key,
        "X-Api-Resource-Id": cfg.resource_id or _TTS_RESOURCE_ID_DEFAULT,
        "X-Api-Connect-Id": connect_id,
    }
    import inspect as _inspect

    kw = {"max_size": 16 * 1024 * 1024, "ping_interval": None}
    sig = _inspect.signature(websockets.connect)
    if "additional_headers" in sig.parameters:
        kw["additional_headers"] = headers
    else:
        kw["extra_headers"] = headers
    try:
        ws_cm = websockets.connect(_TTS_WS_URL, **kw)
        ws = await ws_cm
    except InvalidStatusCode as exc:
        raise RuntimeError(
            f"豆包语音合成连接失败：HTTP {exc.status_code}。"
            f"请确认当前 API Key 已开通 TTS Resource ID {cfg.resource_id or _TTS_RESOURCE_ID_DEFAULT}。"
        ) from exc
    try:
        await ws.send(_pack_frame(
            _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_JSON, _COMPRESSION_NONE,
            _EVENT_START_CONNECTION, None, b"{}",
        ))
        start_payload = {
            "user": {"uid": "sayhey_typed"},
            "event": _EVENT_START_SESSION,
            "namespace": "BidirectionalTTS",
            "req_params": {
                "speaker": cfg.speaker_id,
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": cfg.sample_rate,
                    "speech_rate": cfg.speech_rate,
                },
            },
        }
        await ws.send(_pack_frame(
            _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_JSON, _COMPRESSION_NONE,
            _EVENT_START_SESSION, session_id, json.dumps(start_payload).encode("utf-8"),
        ))
        task_payload = {"event": _EVENT_TASK_REQUEST, "req_params": {"text": text, "speaker": cfg.speaker_id}}
        await ws.send(_pack_frame(
            _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_JSON, _COMPRESSION_NONE,
            _EVENT_TASK_REQUEST, session_id, json.dumps(task_payload).encode("utf-8"),
        ))
        await ws.send(_pack_frame(
            _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_NONE, _COMPRESSION_NONE,
            _EVENT_FINISH_SESSION, session_id, b"{}",
        ))
        received_audio = False
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
            except asyncio.TimeoutError:
                if on_status and not received_audio:
                    on_status("[typed-tts] timeout")
                break
            if isinstance(raw, str):
                continue
            frame = _parse_frame(raw)
            mt = frame.get("msg_type")
            ev = frame.get("event")
            if on_status and mt != _MSG_AUDIO_ONLY_SERVER:
                try:
                    on_status(f"[typed-tts-raw] msg_type={mt} event={ev} sid={frame.get('session_id')} flags={frame.get('flags')} payload={frame.get('payload')}")
                except Exception:
                    pass
            elif on_status and mt == _MSG_AUDIO_ONLY_SERVER:
                try:
                    on_status(f"[typed-tts-raw] msg_type={mt} event={ev} audio_bytes={len(frame.get('payload') or b'')}")
                except Exception:
                    pass
            if mt == _MSG_AUDIO_ONLY_SERVER and frame.get("payload"):
                received_audio = True
                on_pcm(frame["payload"])
            elif mt == _MSG_ERROR_SERVER:
                msg = frame.get("payload", b"")
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="ignore")
                raise RuntimeError(f"TTS 错误：{msg}")
            elif ev in {_EVENT_SESSION_FINISHED, _EVENT_TTS_ENDED}:
                break
        try:
            await ws.send(_pack_frame(
                _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_NONE, _COMPRESSION_NONE,
                _EVENT_FINISH_CONNECTION, None, b"{}",
            ))
        except Exception:
            pass
    finally:
        await ws.close()
