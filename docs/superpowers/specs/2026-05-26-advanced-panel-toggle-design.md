# Advanced Panel Toggle — Design Spec

**Date:** 2026-05-26  
**Status:** Approved

## Problem

Users were confused by device selectors (虚拟麦克风 in 同声传译, 音频源 in 翻译字幕) that are only relevant when using VB-Audio CABLE routing. Most users only need to pick their own microphone; everything else should work automatically.

## Goal

Add a global "高级" toggle in the main header. Off by default (simplified mode). When off, hide the two advanced device selectors; when on, show them. No logic changes — only UI visibility.

## Decisions

- **Simplified mode default:** `show_advanced_panel = False`
- **Mic output in simplified mode:** `_out_combo` hidden but still populated; backend uses whatever is saved (defaults to CABLE Input via `resolve_cable_input()`). No behavior change.
- **Audio source in simplified mode:** `_audio_combo` hidden; `selected_audio_device()` returns `""` → system default speaker. No behavior change.
- **Toggle placement:** Header bar, left of the settings gear button.
- **Toggle effect:** Immediate (no restart).

## Changes

### `core/settings_store.py`
Add to `AppSettings`:
```python
show_advanced_panel: bool = False
```

### `gui/header_bar.py`
- Add `sig_advanced_toggled = Signal(bool)`
- Add checkable `QPushButton("高级")` with `objectName="secondary"`, placed before the settings gear
- Connect `toggled` → emit `sig_advanced_toggled`
- Add `set_advanced(show: bool)` to sync button checked state from saved setting

### `gui/mic_panel.py`
- Wrap the 虚拟麦克风 row (`out_label` + `_out_combo`) in `self._out_row_widget = QWidget()` with a zero-margin `QHBoxLayout`
- Replace `layout.addLayout(out_row)` with `layout.addWidget(self._out_row_widget)`
- Add `set_advanced(show: bool) -> None` that calls `self._out_row_widget.setVisible(show)`

### `gui/game_panel.py`
- Wrap the 音频源 row (`audio_label` + `_audio_combo`) in `self._audio_row_widget = QWidget()` with a zero-margin `QHBoxLayout`
- Replace `layout.addLayout(audio_row)` with `layout.addWidget(self._audio_row_widget)`
- Add `set_advanced(show: bool) -> None` that calls `self._audio_row_widget.setVisible(show)`

### `gui/main_window.py`
- On startup: read `store.get().show_advanced_panel`, call `_header.set_advanced(v)`, `_mic_panel.set_advanced(v)`, `_game_panel.set_advanced(v)`
- Connect `_header.sig_advanced_toggled` to a slot that saves to store and calls both panels' `set_advanced()`

## Out of Scope
- No changes to backend audio routing logic
- No changes to settings dialog
- No per-panel independent toggles
