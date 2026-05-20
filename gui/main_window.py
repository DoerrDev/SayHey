from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app_core.controller import build_app_config
from app_core.game_subtitle_controller import build_game_subtitle_config
from core.bridge import ControllerThread, GameSubtitleThread
from core.settings_store import AppSettings, SettingsStore
from core.usage_tracker import UsageTracker
from gui.device_checklist import DeviceChecklistPanel
from gui.feedback_dialog import FeedbackDialog
from gui.game_panel import GameSubtitlePanel
from gui.header_bar import HeaderBar
from gui.log_panel import RuntimeLogPanel
from gui.mic_panel import MicTranslatePanel
from gui.overlay_window import SubtitleOverlay
from gui.settings_dialog import SettingsDialog
from gui.usage_dialog import UsageDialog
from gui.voice_selector_dialog import VoiceSelectorDialog

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class MainWindow(QMainWindow):
    sig_status = Signal(str)
    sig_mic_source = Signal(str)
    sig_mic_translation = Signal(str)
    sig_game_subtitle = Signal(str, str)
    sig_mic_stopped = Signal()
    sig_mic_error = Signal(str)
    sig_game_stopped = Signal()
    sig_game_error = Signal(str)
    sig_usage_updated = Signal(float, float)

    def __init__(self, store: SettingsStore) -> None:
        super().__init__()
        self._store = store
        self._mic_thread: Optional[ControllerThread] = None
        self._game_thread: Optional[GameSubtitleThread] = None
        self._overlay_visible = False

        usage_path = _ENV_PATH.parent / "usage_data.json"
        self._usage_tracker = UsageTracker(
            usage_path,
            on_update=lambda state: self.sig_usage_updated.emit(state.session_cost, state.total_cost),
        )

        self.setWindowTitle("SayHey")
        self.setMinimumSize(1080, 740)
        self.resize(1220, 820)

        self._build_layout()
        self._connect_signals()
        self._apply_settings(store.get())
        self._sync_overlay_state(False)

        from core.update_checker import start_check

        self._update_thread = start_check(self._on_update_check)

        from core.message_poller import MessagePoller

        self._msg_poller = MessagePoller(store.get().volc_trial_api_base, interval_sec=10, parent=self)
        self._msg_poller.sig_unread_count.connect(self._on_unread_count)
        self._msg_poller.start()

    def _on_update_check(self, info) -> None:
        if info and info.has_update:
            self._header.set_update_available(info)

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = HeaderBar()
        root.addWidget(self._header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: rgba(163,207,255,0.08);")
        root.addWidget(separator)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background: rgba(163,207,255,0.08); }")

        self._game_panel = GameSubtitlePanel()
        self._mic_panel = MicTranslatePanel()
        splitter.addWidget(self._game_panel)
        splitter.addWidget(self._mic_panel)
        splitter.setSizes([500, 620])
        content_layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self._checklist = DeviceChecklistPanel(self._store.get().cable_test_state)
        self._checklist.setMaximumWidth(360)
        self._checklist.setMinimumHeight(180)
        bottom.addWidget(self._checklist)

        self._log_panel = RuntimeLogPanel()
        self._log_panel.setMinimumHeight(180)
        bottom.addWidget(self._log_panel, 1)
        content_layout.addLayout(bottom)
        root.addWidget(content, 1)

        self._overlay = SubtitleOverlay()
        self._overlay._on_pos_saved = self._on_overlay_pos_saved

    def _connect_signals(self) -> None:
        self._header.sig_start_all.connect(self._start_all)
        self._header.sig_toggle_overlay.connect(self._toggle_overlay)
        self._header.sig_adjust_overlay.connect(self._overlay.set_drag_mode)
        self._header.sig_open_settings.connect(self._open_settings)
        self._header.sig_open_usage.connect(self._open_usage)
        self._header.sig_open_feedback.connect(self._open_feedback)
        self.sig_usage_updated.connect(self._on_usage_updated)

        self._game_panel.sig_start_requested.connect(self._start_game)
        self._game_panel.sig_stop_requested.connect(self._stop_game)

        self._mic_panel.sig_start_requested.connect(self._start_mic)
        self._mic_panel.sig_stop_requested.connect(self._stop_mic)
        self._mic_panel.sig_select_voice.connect(self._open_voice_selector)

        self._checklist.sig_status.connect(self._on_status)
        self._checklist.sig_test_state_changed.connect(self._on_cable_test_state_changed)
        self.sig_status.connect(self._on_status)
        self.sig_mic_source.connect(self._mic_panel.update_source)
        self.sig_mic_translation.connect(self._mic_panel.update_translation)
        self.sig_game_subtitle.connect(self._game_panel.append_subtitle_token)
        self._game_panel.sig_subtitle_flushed.connect(self._overlay.update_text)
        self.sig_mic_stopped.connect(self._on_mic_stopped)
        self.sig_mic_error.connect(self._on_mic_error)
        self.sig_game_stopped.connect(self._on_game_stopped)
        self.sig_game_error.connect(self._on_game_error)

    def _apply_settings(self, settings: AppSettings) -> None:
        self._header.set_usage_visible(settings.usage_tracking_enabled)
        self._header.set_usage_mode(settings.usage_chip_show_token)
        if settings.usage_tracking_enabled:
            state = self._usage_tracker.state
            self._header.set_usage(state.session_cost, state.total_cost, state.session_tokens, state.total_tokens)

        self._mic_panel.set_mic_by_index(settings.mic_input_index)
        self._mic_panel.set_engine(settings.translator_engine)
        self._mic_panel.set_source_language(settings.s2s_source_language)
        self._mic_panel.set_target_language(settings.s2s_target_language)
        self._mic_panel.set_speaker_id(settings.s2s_speaker_id)

        self._game_panel.set_source_language(settings.game_subtitle_source_language)
        self._game_panel.set_target_language(settings.game_subtitle_target_language)
        self._game_panel.set_max_lines(settings.overlay_max_lines)

        self._overlay.set_font_size(settings.overlay_font_size)
        self._overlay.set_opacity(settings.overlay_opacity)
        self._overlay.set_text_color(settings.overlay_text_color)
        self._overlay.set_overlay_width(settings.overlay_width)
        self._overlay.set_click_through(settings.overlay_click_through)
        if settings.overlay_x is not None and settings.overlay_y is not None:
            self._overlay.move(settings.overlay_x, settings.overlay_y)

    def _sync_overlay_state(self, visible: bool) -> None:
        self._overlay_visible = visible
        self._header.set_overlay_visible(visible)
        self._game_panel.set_overlay_visible(visible)
        self._mic_panel.set_overlay_visible(visible)
        self._checklist.set_overlay_visible(visible)

    @Slot()
    def _start_all(self) -> None:
        self._usage_tracker.reset_session()
        self._start_mic()
        self._start_game()

    @Slot()
    def _start_mic(self) -> None:
        if self._mic_thread is not None and self._mic_thread.isRunning():
            return

        device = self._mic_panel.selected_mic_device()
        if device is None:
            QMessageBox.warning(self, "麦克风", "请先选择一个可用的麦克风设备。")
            return

        engine = self._mic_panel.selected_engine()
        src_lang = self._mic_panel.selected_source_language()
        tgt_lang = self._mic_panel.selected_target_language()
        speaker_id = self._mic_panel.selected_speaker_id()

        if src_lang == tgt_lang and src_lang != "auto":
            QMessageBox.warning(self, "语言设置", "源语言和目标语言不能相同。")
            return

        try:
            config = build_app_config(_ENV_PATH)
            if engine == "huoshan" and not config.api_key:
                raise RuntimeError("未检测到火山引擎 App Key。\n\n请在设置页填写后再重试。")
            if engine == "openai" and not config.openai_api_key:
                raise RuntimeError("未检测到 OpenAI API Key。\n\n请在设置页填写后再重试。")

            config.audio_route = replace(
                config.audio_route,
                input_device_index=device.index,
                input_device_name=None,
            )
            config.engine_name = engine
            config.source_language = src_lang
            config.target_language = tgt_lang
            config.speaker_id = speaker_id if engine == "huoshan" else None

            self._store.save(
                replace(
                    self._store.get(),
                    mic_input_index=device.index,
                    translator_engine=engine,
                    s2s_source_language=src_lang,
                    s2s_target_language=tgt_lang,
                    s2s_speaker_id=speaker_id,
                )
            )
            if engine == "openai":
                config.sample_rate = 24000
                config.chunk_ms = 40
        except Exception as exc:
            QMessageBox.critical(self, "配置错误", str(exc))
            return

        self._mic_panel.set_running(True)
        self._header.set_status("麦克风翻译启动中...", "warn")

        self._mic_thread = ControllerThread(config, parent=self)
        self._mic_thread.sig_status.connect(self.sig_status)
        self._mic_thread.sig_source.connect(self.sig_mic_source)
        self._mic_thread.sig_translation.connect(self.sig_mic_translation)
        self._mic_thread.sig_stopped.connect(self.sig_mic_stopped)
        self._mic_thread.sig_error.connect(self.sig_mic_error)
        self._mic_thread.start()

    @Slot()
    def _stop_mic(self) -> None:
        if self._mic_thread and self._mic_thread.isRunning():
            self._header.set_status("正在停止麦克风翻译...", "warn")
            self._mic_thread.request_stop()

    @Slot()
    def _on_mic_stopped(self) -> None:
        self._mic_panel.set_running(False)
        self._mic_thread = None
        self._header.set_status("就绪")
        self._log_panel.append("麦克风翻译已停止。")

    @Slot(str)
    def _on_mic_error(self, message: str) -> None:
        self._mic_panel.set_running(False)
        self._mic_thread = None
        self._header.set_status("运行错误", "error")
        QMessageBox.critical(self, "运行错误", message)

    @Slot()
    def _start_game(self) -> None:
        if self._game_thread is not None and self._game_thread.isRunning():
            return

        try:
            config = build_game_subtitle_config(_ENV_PATH)
            if not config.api_key:
                raise RuntimeError("未检测到火山引擎 App Key。\n\n请在设置页填写后再重试。")
            src = self._game_panel.selected_source_language()
            tgt = self._game_panel.selected_target_language()
            config.source_language = src
            config.target_language = tgt
            self._store.save(
                replace(
                    self._store.get(),
                    game_subtitle_source_language=src,
                    game_subtitle_target_language=tgt,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "游戏字幕配置错误", str(exc))
            return

        self._game_panel.set_running(True)
        self._header.set_status("游戏字幕启动中...", "warn")

        self._game_thread = GameSubtitleThread(config, parent=self)
        self._game_thread.sig_status.connect(self.sig_status)
        self._game_thread.sig_subtitle.connect(self.sig_game_subtitle)
        self._game_thread.sig_stopped.connect(self.sig_game_stopped)
        self._game_thread.sig_error.connect(self.sig_game_error)
        self._game_thread.start()

    @Slot()
    def _stop_game(self) -> None:
        if self._game_thread and self._game_thread.isRunning():
            self._header.set_status("正在停止游戏字幕...", "warn")
            self._game_thread.request_stop()

    @Slot()
    def _on_game_stopped(self) -> None:
        self._game_panel.set_running(False)
        self._game_thread = None
        self._log_panel.append("游戏字幕已停止。")

    @Slot(str)
    def _on_game_error(self, message: str) -> None:
        self._game_panel.set_running(False)
        self._game_thread = None
        self._header.set_status("运行错误", "error")
        QMessageBox.critical(self, "游戏字幕错误", message)

    @Slot(str)
    def _on_status(self, message: str) -> None:
        lowered = message.lower()
        kind = "error" if any(token in lowered for token in ("error", "failed")) or any(
            token in message for token in ("错误", "失败", "异常")
        ) else "normal"
        self._header.set_status(message, kind)
        self._log_panel.append(message)
        if self._store.get().usage_tracking_enabled and "[usage]" in lowered:
            self._usage_tracker.feed_log_line(message)

    @Slot(float, float)
    def _on_usage_updated(self, session_cost: float, total_cost: float) -> None:
        if self._store.get().usage_tracking_enabled:
            state = self._usage_tracker.state
            self._header.set_usage(state.session_cost, state.total_cost, state.session_tokens, state.total_tokens)

    @Slot()
    def _open_usage(self) -> None:
        UsageDialog(self._usage_tracker, parent=self).exec()

    @Slot()
    def _open_feedback(self) -> None:
        FeedbackDialog(self._store, parent=self).exec()
        if getattr(self, "_msg_poller", None):
            self._msg_poller.trigger_now()

    @Slot(int)
    def _on_unread_count(self, count: int) -> None:
        self._header.set_feedback_unread(count)
        if count > 0:
            self._log_panel.append(f"有 {count} 条来自开发者的新消息，点击“提需求”查看。")

    @Slot()
    def _toggle_overlay(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            if not self._overlay_visible:
                screen = self.screen()
                if screen:
                    geometry = screen.geometry()
                    self._overlay.move(
                        geometry.x() + (geometry.width() - self._overlay.width()) // 2,
                        geometry.y() + geometry.height() - 200,
                    )
            self._overlay.show()
        self._sync_overlay_state(self._overlay.isVisible())

    @Slot()
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._store, parent=self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    @Slot()
    def _open_voice_selector(self) -> None:
        dialog = VoiceSelectorDialog(self._mic_panel.selected_speaker_id(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        speaker_id = dialog.selected_voice
        self._mic_panel.set_speaker_id(speaker_id)
        self._store.save(replace(self._store.get(), s2s_speaker_id=speaker_id))
        self._log_panel.append(f"火山音色已选择：{speaker_id or '服务默认音色'}")

    @Slot(object)
    def _on_settings_saved(self, payload: object) -> None:
        if not isinstance(payload, AppSettings):
            return
        self._apply_settings(payload)
        self._header.set_status("设置已保存")
        self._log_panel.append("设置已保存。")

    @Slot(str)
    def _on_cable_test_state_changed(self, state: str) -> None:
        if state not in {"idle", "ok", "warn", "error"}:
            return
        self._store.save(replace(self._store.get(), cable_test_state=state))

    def _on_overlay_pos_saved(self, x: int, y: int) -> None:
        self._store.save(replace(self._store.get(), overlay_x=x, overlay_y=y))

    def closeEvent(self, event) -> None:
        if self._mic_thread and self._mic_thread.isRunning():
            self._mic_thread.request_stop()
            self._mic_thread.wait(3000)
        if self._game_thread and self._game_thread.isRunning():
            self._game_thread.request_stop()
            self._game_thread.wait(3000)
        if getattr(self, "_msg_poller", None) and self._msg_poller.isRunning():
            self._msg_poller.request_stop()
            self._msg_poller.wait(2000)
        self._overlay.close()
        super().closeEvent(event)
