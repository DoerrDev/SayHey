from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PY_VERSION = "3.11.9"
ROOT = Path(__file__).resolve().parent.parent
EMBED_DIR = ROOT / "resource" / "python_embed"
EMBED_ZIP_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
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


def main() -> int:
    if EMBED_DIR.exists() and (EMBED_DIR / "python.exe").exists() and (EMBED_DIR / "Scripts" / "pip.exe").exists():
        print(f"[skip] embed Python already at {EMBED_DIR}")
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

    print(f"[done] embed Python ready at {EMBED_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
