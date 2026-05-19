from __future__ import annotations

import ast
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# Volcengine pricing: CNY per 1,000,000 tokens
PRICE_PER_MTOKEN = {
    "input_audio_tokens": 80.0,
    "input_text_tokens": 10.0,
    "input_audio_cached_tokens": 5.0,
    "input_text_cached_tokens": 5.0,
    "output_audio_tokens": 300.0,
    "output_text_tokens": 30.0,
}

_USAGE_RE = re.compile(r"\[(?:game-s2t-usage|usage)\]\s*(\{.*\})\s*$")


@dataclass
class UsageEvent:
    ts: str
    source: str  # "game" or "mic"
    session_id: str
    duration_ms: int
    tokens: dict[str, float]
    cost: float


@dataclass
class UsageState:
    session_cost: float = 0.0
    session_events: int = 0
    session_tokens: int = 0
    total_cost: float = 0.0
    total_events: int = 0
    total_tokens: int = 0
    daily: dict[str, dict] = field(default_factory=dict)  # date -> {cost, events, tokens{}}
    events: list[UsageEvent] = field(default_factory=list)


def calc_cost(tokens: dict[str, float]) -> float:
    total = 0.0
    for unit, qty in tokens.items():
        price = PRICE_PER_MTOKEN.get(unit, 0.0)
        total += float(qty) * price / 1_000_000.0
    return total


def parse_usage_line(line: str) -> Optional[tuple[str, dict]]:
    """Return (source, parsed_dict) or None if not a usage line."""
    m = _USAGE_RE.search(line)
    if not m:
        return None
    payload = m.group(1)
    try:
        data = ast.literal_eval(payload)
    except Exception:
        try:
            data = json.loads(payload)
        except Exception:
            return None
    source = "game" if "game-s2t-usage" in line else "mic"
    return source, data


def extract_event(source: str, data: dict) -> Optional[UsageEvent]:
    meta = data.get("response_meta") or {}
    billing = meta.get("Billing") or {}
    items = billing.get("Items") or []
    tokens: dict[str, float] = {}
    for item in items:
        unit = item.get("Unit")
        qty = item.get("Quantity")
        if unit is None or qty is None:
            continue
        tokens[unit] = float(qty)
    if not tokens:
        return None
    duration = int(billing.get("DurationMsec") or 0)
    cost = calc_cost(tokens)
    return UsageEvent(
        ts=datetime.now().isoformat(timespec="seconds"),
        source=source,
        session_id=meta.get("SessionID", ""),
        duration_ms=duration,
        tokens=tokens,
        cost=cost,
    )


class UsageTracker:
    """Parses usage log lines, accumulates session + total cost, persists daily."""

    MAX_EVENTS = 5000

    def __init__(self, store_path: Path, on_update: Optional[Callable[[UsageState], None]] = None) -> None:
        self._path = store_path
        self._on_update = on_update
        self._lock = threading.Lock()
        self.state = UsageState()
        self._load()

    def set_callback(self, cb: Optional[Callable[[UsageState], None]]) -> None:
        self._on_update = cb

    def reset_session(self) -> None:
        with self._lock:
            self.state.session_cost = 0.0
            self.state.session_events = 0
            self.state.session_tokens = 0
        self._notify()

    def feed_log_line(self, line: str) -> None:
        parsed = parse_usage_line(line)
        if parsed is None:
            return
        source, data = parsed
        ev = extract_event(source, data)
        if ev is None:
            return
        self._record(ev)

    def _record(self, ev: UsageEvent) -> None:
        with self._lock:
            ev_tokens = int(sum(ev.tokens.values()))
            self.state.session_cost += ev.cost
            self.state.session_events += 1
            self.state.session_tokens += ev_tokens
            self.state.total_cost += ev.cost
            self.state.total_events += 1
            self.state.total_tokens += ev_tokens
            day = ev.ts[:10]
            bucket = self.state.daily.setdefault(day, {"cost": 0.0, "events": 0, "tokens": {}})
            bucket["cost"] += ev.cost
            bucket["events"] += 1
            for k, v in ev.tokens.items():
                bucket["tokens"][k] = bucket["tokens"].get(k, 0.0) + v
            self.state.events.append(ev)
            if len(self.state.events) > self.MAX_EVENTS:
                self.state.events = self.state.events[-self.MAX_EVENTS:]
            self._save_locked()
        self._notify()

    def _notify(self) -> None:
        if self._on_update:
            try:
                self._on_update(self.state)
            except Exception:
                pass

    def _save_locked(self) -> None:
        data = {
            "total_cost": self.state.total_cost,
            "total_events": self.state.total_events,
            "total_tokens": self.state.total_tokens,
            "daily": self.state.daily,
            "events": [
                {
                    "ts": e.ts,
                    "source": e.source,
                    "session_id": e.session_id,
                    "duration_ms": e.duration_ms,
                    "tokens": e.tokens,
                    "cost": e.cost,
                }
                for e in self.state.events
            ],
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.state.total_cost = float(data.get("total_cost", 0.0))
        self.state.total_events = int(data.get("total_events", 0))
        self.state.total_tokens = int(data.get("total_tokens", 0))
        self.state.daily = data.get("daily", {}) or {}
        evs = data.get("events", []) or []
        self.state.events = [
            UsageEvent(
                ts=e.get("ts", ""),
                source=e.get("source", ""),
                session_id=e.get("session_id", ""),
                duration_ms=int(e.get("duration_ms", 0)),
                tokens=e.get("tokens", {}) or {},
                cost=float(e.get("cost", 0.0)),
            )
            for e in evs
        ]

    def export_csv(self, out_path: Path) -> int:
        import csv
        with self._lock:
            events = list(self.state.events)
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["时间", "来源", "SessionID", "时长(ms)", "input_audio", "output_text", "output_audio", "费用(元)"])
            for e in events:
                w.writerow([
                    e.ts, e.source, e.session_id, e.duration_ms,
                    e.tokens.get("input_audio_tokens", 0),
                    e.tokens.get("output_text_tokens", 0),
                    e.tokens.get("output_audio_tokens", 0),
                    f"{e.cost:.6f}",
                ])
        return len(events)
