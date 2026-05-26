from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent
HOTWORDS_DIR = _APP_DIR / "hotwords"

_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|]')
MAX_ENTRIES = 500


@dataclass
class HotwordSet:
    title: str
    entries: dict[str, str] = field(default_factory=dict)


def ensure_dir() -> Path:
    HOTWORDS_DIR.mkdir(parents=True, exist_ok=True)
    return HOTWORDS_DIR


def sanitize_filename(title: str) -> str:
    s = _INVALID_FN_CHARS.sub("_", title).strip()
    return s or "untitled"


def _path_for(title: str) -> Path:
    return ensure_dir() / f"{sanitize_filename(title)}.txt"


def list_titles() -> list[str]:
    ensure_dir()
    return sorted(p.stem for p in HOTWORDS_DIR.glob("*.txt"))


def load(title: str) -> HotwordSet:
    path = _path_for(title)
    entries: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                entries[k] = v
    return HotwordSet(title=title, entries=entries)


def save(hw: HotwordSet) -> Path:
    if len(hw.entries) > MAX_ENTRIES:
        raise ValueError(f"热词条数超过上限 {MAX_ENTRIES}")
    path = _path_for(hw.title)
    lines = [f"# {hw.title}"]
    for k, v in hw.entries.items():
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def delete(title: str) -> bool:
    path = _path_for(title)
    if path.exists():
        path.unlink()
        return True
    return False
