from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from core import history_store  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402
from gui import settings_dialog as sd  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dlg(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(history_store, "HISTORY_DIR", tmp_path / "history")
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    store = SettingsStore(tmp_path / "settings.json")
    return sd.SettingsDialog(store)


def _seed(day: date, rows: list[tuple[str, str, str, str]]) -> None:
    history_store.ensure_dir()
    path = history_store.HISTORY_DIR / f"{day.isoformat()}.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"ts": ts, "mode": m, "source": s, "translation": t}, ensure_ascii=False)
            for ts, m, s, t in rows
        )
        + "\n",
        encoding="utf-8",
    )


def _set_range(dlg, start: date, end: date) -> None:
    dlg._history_start.setDate(QDate(start.year, start.month, start.day))
    dlg._history_end.setDate(QDate(end.year, end.month, end.day))


def test_history_tab_exists_in_sidebar(dlg):
    labels = [dlg._tabs._nav.item(i).text() for i in range(dlg._tabs._nav.count())]
    assert "翻译历史" in labels


def test_count_respects_date_filter(dlg):
    _seed(date(2026, 8, 1), [("2026-08-01T10:00:00", "mic", "a", "A")])
    _seed(date(2026, 8, 5), [
        ("2026-08-05T10:00:00", "game", "b", "B"),
        ("2026-08-05T11:00:00", "typed", "c", "C"),
    ])
    _set_range(dlg, date(2026, 8, 5), date(2026, 8, 5))
    dlg._count_history()
    assert "共 2 条记录" in dlg._history_hint.text()

    _set_range(dlg, date(2026, 8, 1), date(2026, 8, 5))
    dlg._count_history()
    assert "共 3 条记录" in dlg._history_hint.text()


def test_export_writes_plain_text_of_selected_range(dlg, tmp_path, monkeypatch):
    _seed(date(2026, 8, 1), [("2026-08-01T09:00:00", "mic", "old", "旧")])
    _seed(date(2026, 8, 5), [("2026-08-05T10:20:30", "typed", "hello", "你好")])
    out = tmp_path / "out.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))

    _set_range(dlg, date(2026, 8, 5), date(2026, 8, 5))
    dlg._export_history()

    text = out.read_text(encoding="utf-8")
    assert "[2026-08-05 10:20:30] (打字翻译)" in text
    assert "原文: hello" in text
    assert "译文: 你好" in text
    assert "old" not in text
    assert "已导出 1 条" in dlg._history_hint.text()


def test_export_empty_range_does_not_write_file(dlg, tmp_path, monkeypatch):
    out = tmp_path / "never.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    _set_range(dlg, date(2026, 7, 1), date(2026, 7, 2))
    dlg._export_history()
    assert not out.exists()


def test_export_cancelled_dialog_is_noop(dlg, monkeypatch):
    _seed(date(2026, 8, 5), [("2026-08-05T10:00:00", "mic", "x", "X")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    _set_range(dlg, date(2026, 8, 5), date(2026, 8, 5))
    dlg._history_hint.setText("")
    dlg._export_history()
    assert dlg._history_hint.text() == ""


def test_clear_history_requires_confirmation(dlg, monkeypatch):
    _seed(date(2026, 8, 5), [("2026-08-05T10:00:00", "mic", "x", "X")])
    _set_range(dlg, date(2026, 8, 5), date(2026, 8, 5))

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel)
    )
    dlg._clear_history()
    assert len(history_store.load_range(date(2026, 8, 5), date(2026, 8, 5))) == 1

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    dlg._clear_history()
    assert history_store.load_range(date(2026, 8, 5), date(2026, 8, 5)) == []


def test_toggle_persists_to_settings(dlg, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save))
    assert dlg._history_enabled.isChecked() is True
    dlg._history_enabled.setChecked(False)
    dlg._store.save(dlg._collect())
    assert dlg._store.get().history_enabled is False

    reloaded = SettingsStore(dlg._store._path)
    assert reloaded.get().history_enabled is False
