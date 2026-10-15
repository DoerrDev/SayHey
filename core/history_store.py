from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

if getattr(sys, "frozen", False):
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _APP_DIR = Path(__file__).resolve().parent.parent
HISTORY_DIR = _APP_DIR / "history"

MODE_LABELS = {"mic": "麦克风", "game": "游戏字幕", "typed": "打字翻译"}


@dataclass
class HistoryRecord:
    ts: datetime
    mode: str
    source: str
    translation: str


def ensure_dir() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def _path_for(day: date) -> Path:
    return ensure_dir() / f"{day.isoformat()}.jsonl"


def append(mode: str, source: str, translation: str) -> None:
    source = (source or "").strip()
    translation = (translation or "").strip()
    if not source and not translation:
        return
    now = datetime.now()
    line = json.dumps(
        {"ts": now.isoformat(timespec="seconds"), "mode": mode, "source": source, "translation": translation},
        ensure_ascii=False,
    )
    with _path_for(now.date()).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def available_days() -> list[date]:
    ensure_dir()
    days: list[date] = []
    for p in HISTORY_DIR.glob("*.jsonl"):
        try:
            days.append(date.fromisoformat(p.stem))
        except ValueError:
            continue
    return sorted(days)


def load_range(start: date, end: date) -> list[HistoryRecord]:
    if end < start:
        start, end = end, start
    records: list[HistoryRecord] = []
    day = start
    while day <= end:
        path = _path_for(day)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    records.append(
                        HistoryRecord(
                            ts=datetime.fromisoformat(raw["ts"]),
                            mode=raw.get("mode", ""),
                            source=raw.get("source", ""),
                            translation=raw.get("translation", ""),
                        )
                    )
                except Exception:
                    continue
        day += timedelta(days=1)
    records.sort(key=lambda r: r.ts)
    return records


def format_text(records: list[HistoryRecord]) -> str:
    lines: list[str] = []
    for r in records:
        label = MODE_LABELS.get(r.mode, r.mode or "-")
        lines.append(f"[{r.ts.strftime('%Y-%m-%d %H:%M:%S')}] ({label})")
        lines.append(f"原文: {r.source}")
        lines.append(f"译文: {r.translation}")
        lines.append("")
    return "\n".join(lines)


def clear_range(start: date, end: date) -> int:
    if end < start:
        start, end = end, start
    removed = 0
    day = start
    while day <= end:
        path = _path_for(day)
        if path.exists():
            path.unlink()
            removed += 1
        day += timedelta(days=1)
    return removed
