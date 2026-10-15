from __future__ import annotations

import os
import sys
from pathlib import Path

tag = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")).strip()
if not tag:
    sys.exit("usage: stamp_version.py <tag>  (or set GITHUB_REF_NAME)")

ver = tag.lstrip("v")
path = Path(__file__).resolve().parent.parent / "core" / "version.py"
path.write_text(f'__version__ = "{ver}"\n', encoding="utf-8")
print(f"stamped {path} -> {ver}")
