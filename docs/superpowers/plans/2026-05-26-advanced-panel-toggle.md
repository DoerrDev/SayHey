# Advanced Panel Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "高级" toggle in the main header that shows/hides the 虚拟麦克风 selector in MicTranslatePanel and the 音频源 selector in GameSubtitlePanel, defaulting to hidden (simplified mode).

**Architecture:** Single boolean setting `show_advanced_panel` stored in AppSettings. HeaderBar emits a signal on toggle; MainWindow propagates it to both panels via `set_advanced(bool)`. The hidden controls still hold their values — backend behavior is unchanged.

**Tech Stack:** PySide6, Python dataclasses, existing `SettingsStore` JSON persistence.

---

## File Map

| File | Change |
|------|--------|
| `core/settings_store.py` | Add `show_advanced_panel: bool = False` to `AppSettings` |
| `gui/mic_panel.py` | Wrap 虚拟麦克风 row in `QWidget`; add `set_advanced()` |
| `gui/game_panel.py` | Wrap 音频源 row in `QWidget`; add `set_advanced()` |
| `gui/header_bar.py` | Add `sig_advanced_toggled` signal + checkable button + `set_advanced()` |
| `gui/main_window.py` | Wire signal; apply initial state in `_apply_settings` |

---

## Task 1: Add `show_advanced_panel` to AppSettings

**Files:**
- Modify: `core/settings_store.py`
- Test: `tests/test_settings_store.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings_store.py`:

```python
import json
import unittest
from core.settings_store import AppSettings, SettingsStore
import tempfile, pathlib


class AdvancedPanelSettingTests(unittest.TestCase):
    def test_defaults_to_false(self):
        s = AppSettings()
        self.assertFalse(s.show_advanced_panel)

    def test_round_trips_through_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "settings.json"
            store = SettingsStore(path)
            from dataclasses import replace
            store.save(replace(store.get(), show_advanced_panel=True))
            store2 = SettingsStore(path)
            self.assertTrue(store2.get().show_advanced_panel)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /d/Users/user/PycharmProjects/SayHey && python -m pytest tests/test_settings_store.py -v
```

Expected: `AttributeError: 'AppSettings' object has no attribute 'show_advanced_panel'`

- [ ] **Step 3: Add the field to AppSettings**

In `core/settings_store.py`, find the last field before the closing of the dataclass (currently `hotkey_typed_tts_toggle: str = ""`). Add after it:

```python
    show_advanced_panel: bool = False
```

- [ ] **Step 4: Check that SettingsStore supports unknown keys gracefully**

Open `core/settings_store.py` and find the `load` / `__init__` of `SettingsStore`. Confirm it uses something like `dataclasses.fields()` or `**json_data` filtered by known keys. If it does a direct `AppSettings(**data)` without filtering, unknown keys from old JSON will crash. Look for a pattern like:

```python
known = {f.name for f in dataclasses.fields(AppSettings)}
filtered = {k: v for k, v in data.items() if k in known}
return AppSettings(**filtered)
```

If this filter is already present, skip to Step 5. If not, add it.

- [ ] **Step 5: Run test to confirm it passes**

```bash
python -m pytest tests/test_settings_store.py -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "feat: add show_advanced_panel setting (default False)"
```

---

## Task 2: Wrap 虚拟麦克风 row in MicTranslatePanel

**Files:**
- Modify: `gui/mic_panel.py:93-104`

Currently the code does:
```python
out_row = QHBoxLayout()
out_row.setSpacing(12)
out_label = QLabel("虚拟麦克风")
...
layout.addLayout(out_row)
```

We need a `QWidget` container so we can call `setVisible()` on the whole row.

- [ ] **Step 1: Add `QWidget` import (already present — verify)**

Check line 1–20 of `gui/mic_panel.py`. `QWidget` must be in the `from PySide6.QtWidgets import (...)` block. If missing, add it.

- [ ] **Step 2: Replace the out_row layout block**

In `gui/mic_panel.py`, replace lines 93–104:

```python
        # Virtual mic output row
        out_row = QHBoxLayout()
        out_row.setSpacing(12)
        out_label = QLabel("虚拟麦克风")
        out_label.setObjectName("sectionTitle")
        out_label.setToolTip("翻译后的音频将输出到该设备（一般选 CABLE Input）")
        out_row.addWidget(out_label)
        self._out_combo = QComboBox()
        self._out_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._out_combo.currentIndexChanged.connect(self._on_output_changed)
        out_row.addWidget(self._out_combo, 1)
        layout.addLayout(out_row)
```

with:

```python
        # Virtual mic output row (hidden in simplified mode)
        self._out_row_widget = QWidget()
        out_row = QHBoxLayout(self._out_row_widget)
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(12)
        out_label = QLabel("虚拟麦克风")
        out_label.setObjectName("sectionTitle")
        out_label.setToolTip("翻译后的音频将输出到该设备（一般选 CABLE Input）")
        out_row.addWidget(out_label)
        self._out_combo = QComboBox()
        self._out_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._out_combo.currentIndexChanged.connect(self._on_output_changed)
        out_row.addWidget(self._out_combo, 1)
        layout.addWidget(self._out_row_widget)
```

- [ ] **Step 3: Add `set_advanced()` method**

In `gui/mic_panel.py`, find a public method like `set_mic_by_index` or `set_speech_rate` and add `set_advanced` near the other setters:

```python
    def set_advanced(self, show: bool) -> None:
        self._out_row_widget.setVisible(show)
```

- [ ] **Step 4: Verify the app still starts**

```bash
python main.py
```

Expected: app opens, 虚拟麦克风 row still visible (we haven't wired the toggle yet). No crash.

- [ ] **Step 5: Commit**

```bash
git add gui/mic_panel.py
git commit -m "refactor: wrap 虚拟麦克风 row in QWidget for show/hide support"
```

---

## Task 3: Wrap 音频源 row in GameSubtitlePanel

**Files:**
- Modify: `gui/game_panel.py:115-131`

Currently:
```python
        audio_row = QHBoxLayout()
        audio_row.setSpacing(12)
        audio_label = QLabel("音频源")
        ...
        layout.addLayout(audio_row)
```

- [ ] **Step 1: Add `QWidget` import (verify)**

Check `gui/game_panel.py` imports. `QWidget` must be in the PySide6 import block. If missing, add it.

- [ ] **Step 2: Replace the audio_row layout block**

In `gui/game_panel.py`, replace the audio source row (lines ~115–131):

```python
        # Audio source row
        audio_row = QHBoxLayout()
        audio_row.setSpacing(12)
        audio_label = QLabel("音频源")
        audio_label.setObjectName("sectionTitle")
        audio_row.addWidget(audio_label)
        self._audio_combo = QComboBox()
        self._audio_combo.setToolTip(
            "选择要监听的扬声器设备（loopback 捕获）。\n"
            "把游戏音频输出到 CABLE Input 后选它，物理扬声器放音乐不影响翻译。"
        )
        self._audio_combo.setMinimumWidth(260)
        self._audio_combo.currentIndexChanged.connect(
            lambda _i: self.sig_audio_device_changed.emit(self.selected_audio_device())
        )
        audio_row.addWidget(self._audio_combo, 1)
        layout.addLayout(audio_row)
```

with:

```python
        # Audio source row (hidden in simplified mode)
        self._audio_row_widget = QWidget()
        audio_row = QHBoxLayout(self._audio_row_widget)
        audio_row.setContentsMargins(0, 0, 0, 0)
        audio_row.setSpacing(12)
        audio_label = QLabel("音频源")
        audio_label.setObjectName("sectionTitle")
        audio_row.addWidget(audio_label)
        self._audio_combo = QComboBox()
        self._audio_combo.setToolTip(
            "选择要监听的扬声器设备（loopback 捕获）。\n"
            "把游戏音频输出到 CABLE Input 后选它，物理扬声器放音乐不影响翻译。"
        )
        self._audio_combo.setMinimumWidth(260)
        self._audio_combo.currentIndexChanged.connect(
            lambda _i: self.sig_audio_device_changed.emit(self.selected_audio_device())
        )
        audio_row.addWidget(self._audio_combo, 1)
        layout.addWidget(self._audio_row_widget)
```

- [ ] **Step 3: Add `set_advanced()` method**

In `gui/game_panel.py`, add near the other setters (e.g. after `set_audio_device`):

```python
    def set_advanced(self, show: bool) -> None:
        self._audio_row_widget.setVisible(show)
```

- [ ] **Step 4: Verify the app still starts**

```bash
python main.py
```

Expected: 音频源 row still visible, no crash.

- [ ] **Step 5: Commit**

```bash
git add gui/game_panel.py
git commit -m "refactor: wrap 音频源 row in QWidget for show/hide support"
```

---

## Task 4: Add "高级" toggle button to HeaderBar

**Files:**
- Modify: `gui/header_bar.py`

- [ ] **Step 1: Add the signal declaration**

In `gui/header_bar.py`, in the `HeaderBar` class body, add the new signal alongside the existing ones:

```python
    sig_advanced_toggled = Signal(bool)
```

- [ ] **Step 2: Add the button in `_build_ui`**

In `gui/header_bar.py`, find the line that adds `settings_btn` (the gear icon). Insert the advanced toggle **before** `settings_btn`:

```python
        self._advanced_btn = QPushButton("高级")
        self._advanced_btn.setObjectName("secondary")
        self._advanced_btn.setCheckable(True)
        self._advanced_btn.setFixedWidth(60)
        self._advanced_btn.setToolTip("显示/隐藏高级音频设备选项")
        self._advanced_btn.toggled.connect(self.sig_advanced_toggled.emit)
        layout.addWidget(self._advanced_btn)
```

- [ ] **Step 3: Add `set_advanced()` to sync button state**

In `gui/header_bar.py`, add this method:

```python
    def set_advanced(self, show: bool) -> None:
        self._advanced_btn.blockSignals(True)
        self._advanced_btn.setChecked(show)
        self._advanced_btn.blockSignals(False)
```

- [ ] **Step 4: Verify the button appears**

```bash
python main.py
```

Expected: "高级" button visible in header, left of the gear icon. Clicking it toggles its checked state but panels don't change yet (not wired).

- [ ] **Step 5: Commit**

```bash
git add gui/header_bar.py
git commit -m "feat: add 高级 toggle button to header bar"
```

---

## Task 5: Wire toggle in MainWindow

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Connect the signal in `_connect_signals`**

In `gui/main_window.py`, inside `_connect_signals`, after the existing header signal connections (lines ~175–179), add:

```python
        self._header.sig_advanced_toggled.connect(self._on_advanced_toggled)
```

- [ ] **Step 2: Add the slot**

In `gui/main_window.py`, add a new method (place it near other `_on_*` header slots):

```python
    @Slot(bool)
    def _on_advanced_toggled(self, show: bool) -> None:
        self._mic_panel.set_advanced(show)
        self._game_panel.set_advanced(show)
        self._store.save(replace(self._store.get(), show_advanced_panel=show))
```

- [ ] **Step 3: Apply initial state in `_apply_settings`**

In `gui/main_window.py`, inside `_apply_settings(self, s: AppSettings)`, add at the end of the method (after the `_apply_hotkeys` call):

```python
        self._header.set_advanced(s.show_advanced_panel)
        self._mic_panel.set_advanced(s.show_advanced_panel)
        self._game_panel.set_advanced(s.show_advanced_panel)
```

- [ ] **Step 4: Verify full flow**

```bash
python main.py
```

Checklist:
- On first launch: 虚拟麦克风 and 音频源 rows are **hidden**; "高级" button is unchecked
- Click "高级": both rows appear immediately; button shows as checked
- Click "高级" again: both rows hide; button unchecked
- Close and reopen the app: state persists (check `settings.json` has `"show_advanced_panel": true/false`)

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: wire advanced panel toggle — hides 虚拟麦克风 and 音频源 rows by default"
```
