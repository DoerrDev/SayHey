from __future__ import annotations

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) or "__compiled__" in globals()


def app_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = Path(__file__).resolve().parent.parent
SIDECAR_DIR = ROOT / "rvc_sidecar"
SIDECAR_SCRIPT = SIDECAR_DIR / "server.py"
DEFAULT_MODELS_DIR = Path.home() / ".sayhey" / "rvc_models"


def sidecar_script_path() -> Path:
    candidates = [
        app_root() / "rvc_sidecar" / "server.py",
        SIDECAR_SCRIPT,
    ]
    for p in candidates:
        if p.exists():
            return p
    return SIDECAR_SCRIPT


def embed_python_path() -> Optional[Path]:
    if os.name != "nt":
        return None
    for base in (app_root(), ROOT):
        p = base / "resource" / "python_embed" / "python.exe"
        if p.exists():
            return p
    return None


def _sidecar_python() -> str:
    p = embed_python_path()
    if p is not None:
        return str(p)
    if not _is_frozen():
        return sys.executable
    return ""


def sidecar_installed() -> bool:
    py = embed_python_path()
    if py is None:
        if _is_frozen():
            return False
        py_str = sys.executable
    else:
        py_str = str(py)
    try:
        r = subprocess.run(
            [py_str, "-c", "import rvc_python"],
            capture_output=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return r.returncode == 0
    except Exception:
        return False


def embed_python_available() -> bool:
    return embed_python_path() is not None


def _has_cuda() -> bool:
    import shutil as _sh
    return _sh.which("nvidia-smi") is not None


def install_sidecar(on_line: Optional[Callable[[str], None]] = None, cancel_check: Optional[Callable[[], bool]] = None) -> bool:
    def emit(msg: str) -> None:
        if on_line:
            on_line(msg)

    py = embed_python_path()
    if py is None:
        if _is_frozen():
            emit("ERROR: embedded Python not found. Re-install SayHey (resource/python_embed missing).")
            return False
        emit("WARN: embedded Python not found; using current interpreter (dev mode).")
        py_str = sys.executable
    else:
        py_str = str(py)
        emit(f"using embedded python: {py_str}")

    def run(args: list[str], env: Optional[dict[str, str]] = None) -> bool:
        if cancel_check and cancel_check():
            return False
        emit(f"$ {' '.join(args)}")
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        proc = subprocess.Popen(
            args,
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel_check and cancel_check():
                try:
                    proc.terminate()
                except Exception:
                    pass
                return False
            emit(line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            emit(f"command failed with code {proc.returncode}")
            return False
        return True

    if not run([py_str, "-m", "pip", "install", "--upgrade", "pip<24.1", "wheel", "setuptools"]):
        return False

    if not run([py_str, "-m", "pip", "install", "numpy==1.23.5", "Cython<3"]):
        return False

    if _has_cuda():
        emit("detected nvidia-smi -> installing torch CUDA build")
        ok = run([py_str, "-m", "pip", "install", "torch", "torchaudio",
                  "--index-url", "https://download.pytorch.org/whl/cu121"])
    else:
        emit("no nvidia-smi -> installing torch CPU build")
        ok = run([py_str, "-m", "pip", "install", "torch", "torchaudio",
                  "--index-url", "https://download.pytorch.org/whl/cpu"])
    if not ok:
        return False

    if not run([py_str, "-m", "pip", "install", "--no-build-isolation", "fairseq==0.12.2"], env={"READTHEDOCS": "1"}):
        return False

    if not run([py_str, "-m", "pip", "install",
                "av", "faiss-cpu==1.7.3", "fastapi", "ffmpeg-python", "loguru",
                "omegaconf==2.0.6", "praat-parselmouth", "pydantic",
                "python-multipart", "pyworld", "requests", "soundfile",
                "torchcrepe", "uvicorn"]):
        return False

    if not run([py_str, "-m", "pip", "install", "--no-deps", "rvc-python==0.1.5"]):
        return False

    emit("Pre-downloading RVC base models (hubert_base.pt, rmvpe.pt)...")
    download_script = textwrap.dedent("""
        from rvc_python.download_model import download_rvc_models
        import os, sys
        lib_dir = os.path.join(
            os.path.dirname(sys.executable),
            "Lib", "site-packages", "rvc_python"
        )
        download_rvc_models(lib_dir)
        print("models ready.")
    """)
    if not run([py_str, "-c", download_script]):
        emit("WARN: model pre-download failed; will retry on first use.")

    emit("install complete.")
    return True


def find_free_port(preferred: int = 7861) -> int:
    for port in [preferred] + list(range(7862, 7900)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


@dataclass
class RvcModel:
    name: str
    pth_path: Path
    index_path: Optional[Path] = None

    @staticmethod
    def scan(root: Path = DEFAULT_MODELS_DIR) -> list["RvcModel"]:
        if not root.exists():
            return []
        models: list[RvcModel] = []
        for sub in sorted(root.iterdir()):
            if not sub.is_dir():
                continue
            pth = next(iter(sub.glob("*.pth")), None)
            idx = next(iter(sub.glob("*.index")), None)
            if pth:
                models.append(RvcModel(name=sub.name, pth_path=pth, index_path=idx))
        for pth in sorted(root.glob("*.pth")):
            idx = pth.with_suffix(".index")
            models.append(RvcModel(
                name=pth.stem,
                pth_path=pth,
                index_path=idx if idx.exists() else None,
            ))
        return models


@dataclass
class RvcConfig:
    enabled: bool = False
    model_name: str = ""
    pitch: int = 0
    index_rate: float = 0.5
    port: int = 7861
    device: str = "auto"
    models_dir: Path = field(default_factory=lambda: DEFAULT_MODELS_DIR)


class RvcClient:
    def __init__(
        self,
        port: int,
        on_status: Optional[Callable[[str], None]] = None,
        timeout: float = 5.0,
    ) -> None:
        self.port = port
        self.on_status = on_status
        self.timeout = timeout
        self._base = f"http://127.0.0.1:{port}"
        self._lock = threading.Lock()

    def _emit(self, msg: str) -> None:
        if self.on_status:
            self.on_status(f"[rvc] {msg}")

    def health(self) -> Optional[dict]:
        try:
            with urllib.request.urlopen(f"{self._base}/health", timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def wait_ready(self, total_timeout: float = 60.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < total_timeout:
            info = self.health()
            if info and info.get("ok"):
                return True
            time.sleep(0.5)
        return False

    def load_model(self, model: RvcModel, pitch: int, index_rate: float) -> bool:
        payload = {
            "model_path": str(model.pth_path),
            "index_path": str(model.index_path) if model.index_path else "",
            "pitch": int(pitch),
            "index_rate": float(index_rate),
        }
        try:
            req = urllib.request.Request(
                f"{self._base}/load_model",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120.0) as resp:
                resp.read()
            self._emit(f"loaded {model.name}")
            return True
        except Exception as exc:
            self._emit(f"load_model failed: {exc}")
            return False

    def set_params(self, pitch: Optional[int] = None, index_rate: Optional[float] = None) -> bool:
        payload: dict = {}
        if pitch is not None:
            payload["pitch"] = int(pitch)
        if index_rate is not None:
            payload["index_rate"] = float(index_rate)
        try:
            req = urllib.request.Request(
                f"{self._base}/set_params",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
            return True
        except Exception as exc:
            self._emit(f"set_params failed: {exc}")
            return False

    def infer(self, pcm_bytes: bytes, sample_rate: int) -> bytes:
        try:
            req = urllib.request.Request(
                f"{self._base}/infer",
                data=pcm_bytes,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Sample-Rate": str(sample_rate),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                return resp.read()
        except Exception as exc:
            self._emit(f"infer failed: {exc}")
            return pcm_bytes


class RvcSidecarManager:
    def __init__(
        self,
        config: RvcConfig,
        on_status: Optional[Callable[[str], None]] = None,
        on_output: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        self.config = config
        self.on_status = on_status
        self.on_output = on_output
        self.process: Optional[subprocess.Popen] = None
        self.client: Optional[RvcClient] = None
        self._buf_lock = threading.Lock()
        self._pcm_buf = bytearray()
        self._chunk_target = 0
        # worker thread for async inference; no maxsize — drop silence not words
        self._infer_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_running = False

    def _emit(self, msg: str) -> None:
        if self.on_status:
            self.on_status(f"[rvc] {msg}")

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> bool:
        if self.is_running():
            return True
        port = find_free_port(self.config.port)
        self.config.port = port
        py = _sidecar_python()
        if not py:
            self._emit("no Python interpreter available for sidecar (embedded missing)")
            return False
        args = [
            py, str(sidecar_script_path()), "--port", str(port),
            "--device", self.config.device, "--f0-method", "rmvpe",
        ]
        try:
            self.process = subprocess.Popen(
                args,
                cwd=str(SIDECAR_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError as exc:
            self._emit(f"failed to start sidecar: {exc}")
            return False
        threading.Thread(target=self._drain_output, daemon=True).start()
        self.client = RvcClient(port, on_status=self.on_status)
        self._emit(f"sidecar starting on port {port} (device={self.config.device})")
        if not self.client.wait_ready(total_timeout=90.0):
            self._emit("sidecar did not become ready in time")
            return False
        info = self.client.health()
        if info:
            self._emit(f"ready device={info.get('device')} rvc_available={info.get('rvc_available')}")
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()
        return True

    def stop(self) -> None:
        self._worker_running = False
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None
        if self.process is not None:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception:
                pass
            self.process = None
        self.client = None
        with self._buf_lock:
            self._pcm_buf.clear()

    def _drain_output(self) -> None:
        proc = self.process
        if proc is None or proc.stdout is None:
            return
        try:
            for line in iter(proc.stdout.readline, b""):
                if not line:
                    break
                self._emit(line.decode("utf-8", errors="replace").rstrip())
        except Exception:
            pass

    def _run_worker(self) -> None:
        while self._worker_running:
            try:
                chunk, sample_rate = self._infer_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self.client is None:
                continue
            out = self.client.infer(chunk, sample_rate)
            if out and self.on_output:
                self.on_output(out)

    def apply_model(self, model: Optional[RvcModel]) -> bool:
        if not self.is_running() or self.client is None or model is None:
            return False
        return self.client.load_model(model, self.config.pitch, self.config.index_rate)

    def apply_params(self) -> None:
        if self.client is not None:
            self.client.set_params(pitch=self.config.pitch, index_rate=self.config.index_rate)

    def process_pcm(self, pcm_bytes: bytes, sample_rate: int, min_chunk_bytes: int = 0) -> None:
        if not self.config.enabled or self.client is None or not self.is_running():
            if self.on_output:
                self.on_output(pcm_bytes)
            return
        with self._buf_lock:
            self._pcm_buf.extend(pcm_bytes)
            if len(self._pcm_buf) < max(min_chunk_bytes, 1):
                return
            chunk = bytes(self._pcm_buf)
            self._pcm_buf.clear()
        self._infer_queue.put((chunk, sample_rate))
