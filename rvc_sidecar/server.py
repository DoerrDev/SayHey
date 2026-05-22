"""RVC sidecar HTTP server.

Endpoints consumed by RvcClient in app_core/rvc_client.py:
  GET  /health       -> {"ok": bool, "device": str, "rvc_available": bool}
  POST /load_model   -> JSON {model_path, index_path, pitch, index_rate}
  POST /set_params   -> JSON {pitch?, index_rate?}
  POST /infer        -> raw PCM bytes body + X-Sample-Rate header -> raw PCM bytes
"""

from __future__ import annotations

import argparse
import os
import struct
import tempfile

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI()

_rvc = None          # RVCInference instance, created lazily on first load
_device = "cpu:0"
_pitch = 0
_index_rate = 0.5


def _resolve_device(raw: str) -> str:
    """Map user-friendly device string to rvc_python format."""
    if raw == "auto":
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu:0"
        except Exception:
            return "cpu:0"
    if raw in ("cpu", "cpu:0"):
        return "cpu:0"
    if raw.startswith("cuda"):
        return raw if ":" in raw else f"{raw}:0"
    return raw


def _rvc_available() -> bool:
    try:
        import rvc_python.infer  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "device": _device, "rvc_available": _rvc_available()}


@app.post("/load_model")
async def load_model(request: Request):
    global _rvc, _pitch, _index_rate

    body = await request.json()
    model_path: str = body.get("model_path", "")
    index_path: str = body.get("index_path", "")
    pitch: int = int(body.get("pitch", 0))
    index_rate: float = float(body.get("index_rate", 0.5))

    if not model_path or not os.path.isfile(model_path):
        return JSONResponse({"ok": False, "error": f"model not found: {model_path}"}, status_code=400)

    try:
        from rvc_python.infer import RVCInference
        if _rvc is None:
            _rvc = RVCInference(device=_device)
        _rvc.load_model(model_path, index_path=index_path if index_path else "")
        _rvc.set_params(f0up_key=pitch, index_rate=index_rate)
        _pitch = pitch
        _index_rate = index_rate
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    return {"ok": True}


@app.post("/set_params")
async def set_params(request: Request):
    global _rvc, _pitch, _index_rate

    body = await request.json()
    if "pitch" in body:
        _pitch = int(body["pitch"])
    if "index_rate" in body:
        _index_rate = float(body["index_rate"])

    if _rvc is not None:
        _rvc.set_params(f0up_key=_pitch, index_rate=_index_rate)

    return {"ok": True}


@app.post("/infer")
async def infer(request: Request):
    if _rvc is None or not _rvc.current_model:
        # Pass through if no model loaded
        data = await request.body()
        return Response(content=data, media_type="application/octet-stream")

    sample_rate_str = request.headers.get("X-Sample-Rate", "16000")
    try:
        sample_rate = int(sample_rate_str)
    except ValueError:
        sample_rate = 16000

    pcm_bytes = await request.body()

    # Wrap raw PCM (int16, mono) in a minimal WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in:
        input_path = f_in.name
        _write_wav(f_in, pcm_bytes, sample_rate, channels=1, sampwidth=2)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_out:
        output_path = f_out.name

    try:
        _rvc.infer_file(input_path, output_path)
        out_pcm = _read_wav_pcm_resampled(output_path, sample_rate)
    except Exception:
        out_pcm = pcm_bytes
    finally:
        _safe_remove(input_path)
        _safe_remove(output_path)

    return Response(content=out_pcm, media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# WAV helpers (no scipy dependency required for basic use)
# ---------------------------------------------------------------------------

def _write_wav(f, pcm_bytes: bytes, sample_rate: int, channels: int, sampwidth: int) -> None:
    """Write a minimal RIFF WAV header + raw PCM data."""
    data_len = len(pcm_bytes)
    byte_rate = sample_rate * channels * sampwidth
    block_align = channels * sampwidth
    # RIFF header
    f.write(b"RIFF")
    f.write(struct.pack("<I", 36 + data_len))
    f.write(b"WAVE")
    # fmt chunk
    f.write(b"fmt ")
    f.write(struct.pack("<I", 16))          # chunk size
    f.write(struct.pack("<H", 1))           # PCM
    f.write(struct.pack("<H", channels))
    f.write(struct.pack("<I", sample_rate))
    f.write(struct.pack("<I", byte_rate))
    f.write(struct.pack("<H", block_align))
    f.write(struct.pack("<H", sampwidth * 8))
    # data chunk
    f.write(b"data")
    f.write(struct.pack("<I", data_len))
    f.write(pcm_bytes)


def _read_wav_pcm_resampled(path: str, target_sr: int) -> bytes:
    """Read WAV, resample to target_sr if needed, return int16 PCM bytes."""
    import numpy as np
    import soundfile as sf

    data, file_sr = sf.read(path, dtype="int16", always_2d=False)
    if file_sr != target_sr:
        # Linear interpolation resample (good enough for voice, no extra deps)
        n_out = int(round(len(data) * target_sr / file_sr))
        data = np.interp(
            np.linspace(0, len(data) - 1, n_out),
            np.arange(len(data)),
            data.astype(np.float32),
        ).astype(np.int16)
    return data.tobytes()


def _safe_remove(path: str) -> None:
    try:
        os.unlink(path)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _device

    parser = argparse.ArgumentParser(description="RVC sidecar server")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    _device = _resolve_device(args.device)

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
