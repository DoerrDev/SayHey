from __future__ import annotations

import asyncio
import datetime
import gzip
import hashlib
import hmac
import json
import struct
import uuid
from dataclasses import dataclass
from typing import Callable, Optional
from urllib import parse, request

import websockets


# ---------- Volc Machine Translation (REST, sign v4) ----------

_VOLC_MT_HOST = "translate.volcengineapi.com"
_VOLC_MT_SERVICE = "translate"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signed_headers_v4(
    method: str,
    host: str,
    region: str,
    service: str,
    query: dict,
    body: bytes,
    ak: str,
    sk: str,
) -> dict:
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    canonical_uri = "/"
    sorted_q = sorted(query.items())
    canonical_query = "&".join(f"{parse.quote(k, safe='-_.~')}={parse.quote(v, safe='-_.~')}" for k, v in sorted_q)
    payload_hash = _sha256_hex(body)
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{host}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = (
        f"{method}\n{canonical_uri}\n{canonical_query}\n"
        f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    credential_scope = f"{date_stamp}/{region}/{service}/request"
    string_to_sign = (
        f"HMAC-SHA256\n{amz_date}\n{credential_scope}\n{_sha256_hex(canonical_request.encode())}"
    )
    k_date = _hmac_sha256(sk.encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": amz_date,
        "X-Content-Sha256": payload_hash,
        "Authorization": authorization,
    }


@dataclass
class VolcTranslateConfig:
    ak: str
    sk: str
    region: str = "cn-north-1"
    timeout: float = 8.0


def volc_translate_text(cfg: VolcTranslateConfig, text: str, source_lang: str, target_lang: str) -> str:
    if not cfg.ak or not cfg.sk:
        raise RuntimeError("未配置 Volc 翻译 AK/SK，请在设置中填写")
    body_obj: dict = {"TextList": [text], "TargetLanguage": target_lang}
    if source_lang and source_lang != "auto":
        body_obj["SourceLanguage"] = source_lang
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
    query = {"Action": "TranslateText", "Version": "2020-06-01"}
    headers = _signed_headers_v4("POST", _VOLC_MT_HOST, cfg.region, _VOLC_MT_SERVICE, query, body, cfg.ak, cfg.sk)
    url = f"https://{_VOLC_MT_HOST}/?" + parse.urlencode(query)
    req = request.Request(url, data=body, method="POST", headers=headers)
    try:
        with request.urlopen(req, timeout=cfg.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"翻译请求失败：{exc}")
    err = payload.get("ResponseMetadata", {}).get("Error")
    if err:
        raise RuntimeError(f"翻译 API 错误：{err.get('Message') or err}")
    lst = payload.get("TranslationList") or []
    if not lst:
        raise RuntimeError("翻译响应为空")
    return lst[0].get("Translation") or ""


# ---------- Volc BigTTS WebSocket V3 streaming ----------

_TTS_WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
_TTS_RESOURCE_ID_DEFAULT = "volc.service_type.10029"

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
_EVENT_TTS_RESPONSE = 352
_EVENT_TTS_SENTENCE_START = 350
_EVENT_TTS_SENTENCE_END = 351
_EVENT_TTS_ENDED = 359


def _pack_frame(msg_type: int, flags: int, serialization: int, compression: int, event: Optional[int], session_id: Optional[str], payload: bytes) -> bytes:
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
        return {"msg_type": msg_type, "event": event, "session_id": session_id, "error_code": err_code, "payload": payload}
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
class VolcTtsConfig:
    app_key: str
    access_key: str
    speaker_id: str = "zh_female_xiaohe_jupiter_bigtts"
    sample_rate: int = 24000
    speech_rate: int = 0
    resource_id: str = _TTS_RESOURCE_ID_DEFAULT


PcmCallback = Callable[[bytes], None]
StatusCallback = Callable[[str], None]


async def volc_tts_stream(
    cfg: VolcTtsConfig,
    text: str,
    on_pcm: PcmCallback,
    on_status: Optional[StatusCallback] = None,
) -> None:
    if not cfg.app_key or not cfg.access_key:
        raise RuntimeError("未配置 Volc TTS app_key/access_key")
    connect_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    headers = {
        "X-Api-App-Key": cfg.app_key,
        "X-Api-Access-Key": cfg.access_key,
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
    async with websockets.connect(_TTS_WS_URL, **kw) as ws:
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
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
            except asyncio.TimeoutError:
                if on_status:
                    on_status("[typed-tts] timeout")
                break
            if isinstance(raw, str):
                continue
            frame = _parse_frame(raw)
            mt = frame.get("msg_type")
            ev = frame.get("event")
            if mt == _MSG_AUDIO_ONLY_SERVER and frame.get("payload"):
                on_pcm(frame["payload"])
            elif mt == _MSG_ERROR_SERVER:
                msg = frame.get("payload", b"")
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="ignore")
                raise RuntimeError(f"TTS 错误：{msg}")
            elif ev == _EVENT_TTS_ENDED:
                break
            elif mt == _MSG_FULL_SERVER and ev == _EVENT_TTS_ENDED:
                break
        try:
            await ws.send(_pack_frame(
                _MSG_FULL_CLIENT, _FLAGS_EVENT, _SERIALIZATION_NONE, _COMPRESSION_NONE,
                _EVENT_FINISH_CONNECTION, None, b"{}",
            ))
        except Exception:
            pass
