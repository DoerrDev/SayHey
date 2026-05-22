from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app_core.rvc_client import embed_python_available, install_sidecar


def main() -> int:
    if not embed_python_available():
        print("[warn] resource/python_embed/python.exe not found.")
        print("       run 'python scripts/fetch_python_embed.py' first to bundle embedded Python.")
        print("       proceeding with current interpreter (dev only)...")
    ok = install_sidecar(on_line=lambda s: print(s, flush=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
