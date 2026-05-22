from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PY_VERSION = "3.10.11"
ROOT = Path(__file__).resolve().parent.parent
EMBED_DIR = ROOT / "resource" / "python_embed"
EMBED_ZIP_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
NUGET_URL = f"https://www.nuget.org/api/v2/package/python/{PY_VERSION}"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def _download(url: str, dest: Path) -> None:
    print(f"[fetch] {url}")
    with urllib.request.urlopen(url) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _patch_pth(embed_dir: Path) -> None:
    for pth in embed_dir.glob("python*._pth"):
        text = pth.read_text(encoding="utf-8")
        new_text = text.replace("#import site", "import site")
        if "import site" not in new_text:
            new_text += "\nimport site\n"
        pth.write_text(new_text, encoding="utf-8")
        print(f"[patch] enabled site in {pth.name}")
        return


def _ensure_dev_files(embed_dir: Path) -> None:
    if (embed_dir / "include" / "Python.h").exists() and (embed_dir / "libs" / "python310.lib").exists():
        return

    pkg_path = embed_dir / "_python.nupkg"
    _download(NUGET_URL, pkg_path)
    print("[unzip] Python headers/libs")
    with zipfile.ZipFile(pkg_path) as zf:
        for info in zf.infolist():
            parts = Path(info.filename).parts
            if len(parts) < 3 or parts[0] != "tools" or parts[1] not in {"include", "libs"}:
                continue
            target = embed_dir.joinpath(*parts[1:])
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    pkg_path.unlink()


def main() -> int:
    if EMBED_DIR.exists() and (EMBED_DIR / "python.exe").exists() and (EMBED_DIR / "Scripts" / "pip.exe").exists():
        _ensure_dev_files(EMBED_DIR)
        print(f"[skip] embed Python already at {EMBED_DIR}")
        _install_rvc_deps(EMBED_DIR)
        return 0
    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = EMBED_DIR / "_embed.zip"
    _download(EMBED_ZIP_URL, zip_path)
    print(f"[unzip] -> {EMBED_DIR}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(EMBED_DIR)
    zip_path.unlink()

    _patch_pth(EMBED_DIR)

    get_pip = EMBED_DIR / "get-pip.py"
    _download(GET_PIP_URL, get_pip)
    py = EMBED_DIR / "python.exe"
    import subprocess
    print("[pip] installing via get-pip.py")
    subprocess.check_call([str(py), str(get_pip)])
    get_pip.unlink()

    _ensure_dev_files(EMBED_DIR)

    print(f"[done] embed Python ready at {EMBED_DIR}")
    _install_rvc_deps(EMBED_DIR)
    return 0


def _install_rvc_deps(embed_dir: Path) -> None:
    """Install rvc_python + deps and pre-download base models into python_embed."""
    marker = embed_dir / ".rvc_installed"
    if marker.exists():
        print("[skip] rvc deps already installed in python_embed")
        return

    py = embed_dir / "python.exe"
    if not py.exists():
        print("[skip] python.exe not found, skipping rvc install")
        return

    import subprocess

    def run(args: list) -> None:
        print(f"[rvc-install] {' '.join(str(a) for a in args)}")
        subprocess.check_call(args)

    run([str(py), "-m", "pip", "install", "--upgrade", "pip<24.1", "wheel", "setuptools"])
    run([str(py), "-m", "pip", "install", "numpy==1.23.5", "Cython<3"])

    import shutil
    if shutil.which("nvidia-smi"):
        run([str(py), "-m", "pip", "install", "torch", "torchaudio",
             "--index-url", "https://download.pytorch.org/whl/cu121"])
    else:
        run([str(py), "-m", "pip", "install", "torch", "torchaudio",
             "--index-url", "https://download.pytorch.org/whl/cpu"])

    env = {"READTHEDOCS": "1", **__import__("os").environ}
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "--no-build-isolation", "fairseq==0.12.2"],
        env=env,
    )
    run([str(py), "-m", "pip", "install",
         "av", "faiss-cpu==1.7.3", "fastapi", "ffmpeg-python", "loguru",
         "omegaconf==2.0.6", "praat-parselmouth", "pydantic",
         "python-multipart", "pyworld", "requests", "soundfile",
         "torchcrepe", "uvicorn"])
    run([str(py), "-m", "pip", "install", "--no-deps", "rvc-python==0.1.5"])

    # Pre-download base models
    lib_dir = embed_dir / "Lib" / "site-packages" / "rvc_python"
    dl_script = (
        "from rvc_python.download_model import download_rvc_models; "
        f"download_rvc_models(r'{lib_dir}')"
    )
    run([str(py), "-c", dl_script])

    marker.touch()
    print("[done] rvc deps installed and models ready")


if __name__ == "__main__":
    sys.exit(main())
