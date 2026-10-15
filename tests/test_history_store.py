from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from core import history_store


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_DIR", tmp_path / "history")
    return tmp_path / "history"


def _write(day: date, rows: list[tuple[str, str, str, str]]) -> None:
    history_store.ensure_dir()
    path = history_store.HISTORY_DIR / f"{day.isoformat()}.jsonl"
    lines = [
        json.dumps({"ts": ts, "mode": mode, "source": src, "translation": tgt}, ensure_ascii=False)
        for ts, mode, src, tgt in rows
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_append_creates_daily_file_and_roundtrip():
    history_store.append("mic", " hello ", " 你好 ")
    today = date.today()
    path = history_store.HISTORY_DIR / f"{today.isoformat()}.jsonl"
    assert path.exists()
    records = history_store.load_range(today, today)
    assert len(records) == 1
    assert records[0].source == "hello"
    assert records[0].translation == "你好"
    assert records[0].mode == "mic"
    assert isinstance(records[0].ts, datetime)


def test_append_skips_empty():
    history_store.append("mic", "", "   ")
    assert history_store.load_range(date.today(), date.today()) == []


def test_load_range_filters_by_date_and_sorts():
    d1 = date(2026, 8, 1)
    d2 = date(2026, 8, 2)
    d3 = date(2026, 8, 3)
    _write(d1, [("2026-08-01T10:00:00", "mic", "a", "A")])
    _write(d2, [
        ("2026-08-02T12:00:00", "game", "c", "C"),
        ("2026-08-02T09:00:00", "typed", "b", "B"),
    ])
    _write(d3, [("2026-08-03T10:00:00", "mic", "d", "D")])

    records = history_store.load_range(d1, d2)
    assert [r.source for r in records] == ["a", "b", "c"]

    # 单日
    assert [r.source for r in history_store.load_range(d3, d3)] == ["d"]
    # 起止颠倒也能取到
    assert len(history_store.load_range(d3, d1)) == 4
    # 空区间
    assert history_store.load_range(date(2026, 7, 1), date(2026, 7, 5)) == []


def test_load_range_skips_corrupted_lines():
    day = date(2026, 8, 5)
    history_store.ensure_dir()
    path = history_store.HISTORY_DIR / f"{day.isoformat()}.jsonl"
    path.write_text(
        '{"ts": "2026-08-05T10:00:00", "mode": "mic", "source": "ok", "translation": "好"}\n'
        "not-json\n"
        "\n"
        '{"ts": "bad-ts", "mode": "mic", "source": "x", "translation": "y"}\n',
        encoding="utf-8",
    )
    records = history_store.load_range(day, day)
    assert [r.source for r in records] == ["ok"]


def test_available_days_ignores_non_date_files():
    history_store.ensure_dir()
    (history_store.HISTORY_DIR / "2026-08-01.jsonl").write_text("", encoding="utf-8")
    (history_store.HISTORY_DIR / "notes.jsonl").write_text("", encoding="utf-8")
    assert history_store.available_days() == [date(2026, 8, 1)]


def test_format_text_layout():
    _write(date(2026, 8, 1), [("2026-08-01T10:20:30", "typed", "hello", "你好")])
    text = history_store.format_text(history_store.load_range(date(2026, 8, 1), date(2026, 8, 1)))
    assert text.splitlines()[:3] == [
        "[2026-08-01 10:20:30] (打字翻译)",
        "原文: hello",
        "译文: 你好",
    ]


def test_clear_range_only_removes_selected_days():
    d1 = date(2026, 8, 1)
    d2 = date(2026, 8, 2)
    _write(d1, [("2026-08-01T10:00:00", "mic", "a", "A")])
    _write(d2, [("2026-08-02T10:00:00", "mic", "b", "B")])
    assert history_store.clear_range(d1, d1) == 1
    assert history_store.load_range(d1, d1) == []
    assert len(history_store.load_range(d2, d2)) == 1
    assert history_store.clear_range(d1 - timedelta(days=5), d1) == 0
