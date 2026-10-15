from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core import history_store  # noqa: E402
from gui import history_recorder  # noqa: E402
from gui.history_recorder import HistoryRecorder  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(history_store, "HISTORY_DIR", tmp_path / "history")


def _today():
    return history_store.load_range(date.today(), date.today())


def test_snapshot_pair_commits_once():
    rec = HistoryRecorder("mic")
    rec.update_source("Hello")
    rec.update_source("Hello world")
    rec.update_translation("你好")
    rec.update_translation("你好世界")
    rec.commit()
    records = _today()
    assert len(records) == 1
    assert (records[0].source, records[0].translation) == ("Hello world", "你好世界")
    assert records[0].mode == "mic"


def test_boundary_reset_splits_two_records():
    rec = HistoryRecorder("game")
    rec.update_source("first line")
    rec.update_translation("第一句")
    rec.update_source("second line")  # 非前缀延伸 → 上一句落盘
    rec.update_translation("第二句")
    rec.commit()
    records = _today()
    assert [(r.source, r.translation) for r in records] == [
        ("first line", "第一句"),
        ("second line", "第二句"),
    ]


def test_idle_timer_commits(qapp, monkeypatch):
    monkeypatch.setattr(history_recorder, "IDLE_MS", 30)
    rec = HistoryRecorder("mic")
    rec.update_source("idle text")
    rec.update_translation("空闲文本")
    assert _today() == []
    deadline = 2000
    while deadline > 0 and not _today():
        qapp.processEvents()
        QApplication.instance().thread().msleep(10)
        deadline -= 10
    records = _today()
    assert len(records) == 1
    assert records[0].source == "idle text"


def test_commit_is_idempotent_and_clears_state():
    rec = HistoryRecorder("mic")
    rec.update_source("once")
    rec.commit()
    rec.commit()
    assert len(_today()) == 1


def test_disabled_recorder_writes_nothing():
    rec = HistoryRecorder("mic", enabled=False)
    rec.update_source("nope")
    rec.update_translation("不记录")
    rec.record("nope", "不记录")
    rec.commit()
    assert _today() == []


def test_set_enabled_false_flushes_pending_then_stops():
    rec = HistoryRecorder("typed")
    rec.update_source("pending")
    rec.update_translation("待落盘")
    rec.set_enabled(False)
    assert len(_today()) == 1
    rec.update_source("after")
    rec.commit()
    assert len(_today()) == 1


def test_record_writes_direct_pair():
    rec = HistoryRecorder("typed")
    rec.record("hi", "嗨")
    records = _today()
    assert (records[0].source, records[0].translation, records[0].mode) == ("hi", "嗨", "typed")


def test_write_failure_is_swallowed(monkeypatch):
    rec = HistoryRecorder("mic")

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(history_store, "append", boom)
    rec.update_source("x")
    rec.commit()  # 不应抛异常
    rec.record("y", "z")
