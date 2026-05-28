from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app_core.audio_io import AudioRouteVerifier
from app_core.controller import build_app_config
from app_core.game_subtitle_controller import build_game_subtitle_config
from core import hotword_store
from core.bridge import ControllerThread, GameSubtitleThread
from core.settings_store import AppSettings, SettingsStore
from gui.device_checklist import DeviceChecklistPanel
from gui.game_panel import GameSubtitlePanel
from gui.header_bar import HeaderBar
from gui.log_panel import RuntimeLogPanel
from gui.mic_panel import MicTranslatePanel
from gui.mic_area import MicAreaPanel
from gui.float_input import FloatingInputWindow
from gui.overlay_window import SubtitleOverlay
from core.hotkey import HotkeyManager, format_hotkey
from gui.toast import show_toast
from app_core.typed_engine import DoubaoTranslateConfig, DoubaoTtsConfig, resolve_doubao_tts_speaker
from app_core.typed_controller import TypedTranslateController, TypedConfig
from app_core.qwen_engine import QwenMtConfig, QwenTtsConfig
from core.bridge import TypedTranslateThread
from gui.feedback_dialog import FeedbackDialog
from gui.settings_dialog import SettingsDialog
from gui.usage_dialog import UsageDialog
from gui.voice_selector_dialog import VoiceSelectorDialog, voice_is_s2s
from core.usage_tracker import UsageTracker

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _list_speaker_names() -> list[str]:
    try:
        import soundcard as sc
        return [s.name for s in sc.all_speakers()]
    except Exception:
        return []


class MainWindow(QMainWindow):
    # Cross-thread signals (connected to main-thread slots)
    sig_status = Signal(str)
    sig_mic_source = Signal(str)
    sig_mic_translation = Signal(str)
    sig_game_subtitle = Signal(str, str)
    sig_mic_stopped = Signal()
    sig_mic_error = Signal(str)
    sig_game_stopped = Signal()
    sig_game_error = Signal(str)
    sig_usage_updated = Signal(float, float)  # session_cost, total_cost

    def __init__(self, store: SettingsStore) -> None:
        super().__init__()
        self._store = store
        self._mic_thread: Optional[ControllerThread] = None
        self._restart_mic_after_stop: bool = False
        self._game_thread: Optional[GameSubtitleThread] = None
        self._last_engine: str = store.get().translator_engine
        self._overlay_visible = False
        usage_path = _ENV_PATH.parent / "usage_data.json"
        self._usage_tracker = UsageTracker(
            usage_path,
            on_update=lambda st: self.sig_usage_updated.emit(st.session_cost, st.total_cost),
        )

        self.setWindowTitle("SayHey")
        self.setMinimumSize(1060, 720)
        self.resize(1700, 900)

        self._build_layout()
        self._connect_signals()
        self._apply_settings(store.get())

        from core.update_checker import start_check
        self._update_thread = start_check(self._on_update_check)

        # Start message poller (server → client push via polling)
        from core.message_poller import MessagePoller
        api_base = store.get().volc_trial_api_base
        self._msg_poller = MessagePoller(api_base, interval_sec=10, parent=self)
        self._msg_poller.sig_unread_count.connect(self._on_unread_count)
        self._msg_poller.start()

    def _on_update_check(self, info) -> None:
        if info and info.has_update:
            self._header.set_update_available(info)

    @Slot()
    def _on_zh_to_zh_selected(self) -> None:
        if self._store.get().zh_to_zh_info_shown:
            return
        from gui.zh_to_zh_info_dialog import ZhToZhInfoDialog
        dlg = ZhToZhInfoDialog(self)
        dlg.exec()
        if dlg.dont_show_again():
            self._store.save(replace(self._store.get(), zh_to_zh_info_shown=True))

    @Slot(bool)
    def _on_advanced_toggled(self, show: bool) -> None:
        if show and not self._store.get().advanced_audio_warning_shown:
            from gui.advanced_audio_dialog import AdvancedAudioWarningDialog
            dlg = AdvancedAudioWarningDialog(self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                self._header.set_advanced(False)
                return
            if dlg.dont_show_again():
                self._store.save(replace(self._store.get(), advanced_audio_warning_shown=True))
        self._mic_panel.set_advanced(show)
        self._game_panel.set_advanced(show)
        self._store.save(replace(self._store.get(), show_advanced_panel=show))

    def _show_si_hotword_info_once(self) -> None:
        if self._store.get().si_hotword_info_shown:
            return
        from gui.hotword_usage_dialog import HotwordUsageDialog
        dlg = HotwordUsageDialog(self)
        dlg.exec()
        if dlg.dont_show_again():
            self._store.save(replace(self._store.get(), si_hotword_info_shown=True))

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = HeaderBar()
        root.addWidget(self._header)

        # Thin separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(163,207,255,0.08);")
        root.addWidget(sep)

        # Main content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(10)

        # Top: two panels side by side
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setHandleWidth(0)

        self._game_panel = GameSubtitlePanel()
        top_splitter.addWidget(self._game_panel)

        self._mic_area = MicAreaPanel()
        self._mic_panel = self._mic_area.voice
        self._typed_panel = self._mic_area.typed
        top_splitter.addWidget(self._mic_area)

        top_splitter.setSizes([480, 600])
        content_layout.addWidget(top_splitter, 1)

        # Bottom: device checklist + log
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._checklist = DeviceChecklistPanel()
        self._checklist.setMaximumWidth(340)
        self._checklist.setMinimumHeight(140)
        bottom.addWidget(self._checklist)

        self._log_panel = RuntimeLogPanel()
        self._log_panel.setMinimumHeight(140)
        bottom.addWidget(self._log_panel, 1)

        content_layout.addLayout(bottom)
        root.addWidget(content, 1)

        # Overlay (hidden by default)
        self._overlay = SubtitleOverlay()
        self._overlay._on_pos_saved = self._on_overlay_pos_saved

        # Floating input window for typed translate
        self._float_input = FloatingInputWindow()
        self._float_input.sig_submit.connect(self._on_typed_submit_from_float)

        # Typed translate state
        self._typed_controller: Optional[TypedTranslateController] = None
        self._typed_thread: Optional[TypedTranslateThread] = None
        self._typed_busy = False

        # Global hotkeys
        self._hotkeys = HotkeyManager()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installNativeEventFilter(self._hotkeys)

    def _connect_signals(self) -> None:
        # Header actions
        self._header.sig_toggle_overlay.connect(self._toggle_overlay)
        self._header.sig_adjust_overlay.connect(self._overlay.set_drag_mode)
        self._header.sig_open_settings.connect(self._open_settings)
        self._header.sig_open_usage.connect(self._open_usage)
        self._header.sig_open_feedback.connect(self._open_feedback)
        self._header.sig_advanced_toggled.connect(self._on_advanced_toggled)
        self.sig_usage_updated.connect(self._on_usage_updated)

        # Game panel
        self._game_panel.sig_start_requested.connect(self._start_game)
        self._game_panel.sig_stop_requested.connect(self._stop_game)
        self._game_panel.sig_overlay_toggle.connect(self._toggle_overlay)
        self._game_panel.sig_audio_device_changed.connect(self._on_game_audio_changed)
        self._game_audio_accepted = ""

        # Mic panel
        self._mic_panel.sig_start_requested.connect(self._start_mic)
        self._mic_panel.sig_stop_requested.connect(self._stop_mic)
        self._mic_panel.sig_test_cable.connect(self._test_cable)
        self._mic_panel.sig_select_voice.connect(self._open_voice_selector)
        self._mic_panel.sig_voice_warning.connect(lambda msg: (self._header.set_status(msg, "warn"), self._log_panel.append(msg)))

        # Typed panel
        self._typed_panel.sig_translate_requested.connect(self._on_typed_submit)
        self._typed_panel.sig_settings_changed.connect(self._on_typed_settings_changed)

        self._mic_panel.sig_zh_to_zh_selected.connect(self._on_zh_to_zh_selected)
        self._game_panel.sig_zh_to_zh_selected.connect(self._on_zh_to_zh_selected)
        self._typed_panel.sig_zh_to_zh_selected.connect(self._on_zh_to_zh_selected)

        self._mic_panel.sig_hotword_changed.connect(self._on_mic_hotword_changed)
        self._typed_panel.sig_hotword_changed.connect(self._on_typed_hotword_changed)
        self._game_panel.sig_hotword_changed.connect(self._on_game_hotword_changed)

        # Checklist
        self._checklist.sig_status.connect(self._on_status)

        # Cross-thread signals → main-thread slots
        self.sig_status.connect(self._on_status)
        self.sig_mic_source.connect(self._mic_panel.update_source)
        self.sig_mic_translation.connect(self._mic_panel.update_translation)
        self._game_panel.sig_subtitle_flushed.connect(self._overlay.update_text)
        self.sig_game_subtitle.connect(self._game_panel.append_subtitle_token)
        self.sig_mic_stopped.connect(self._on_mic_stopped)
        self.sig_mic_error.connect(self._on_mic_error)
        self.sig_game_stopped.connect(self._on_game_stopped)
        self.sig_game_error.connect(self._on_game_error)

    def _hotkey_display(self, raw: str) -> str:
        return format_hotkey(raw)

    @Slot(str)
    def _on_mic_hotword_changed(self, title: str) -> None:
        self._store.save(replace(self._store.get(), mic_hotword_set=title))

    @Slot(str)
    def _on_typed_hotword_changed(self, title: str) -> None:
        self._store.save(replace(self._store.get(), typed_hotword_set=title))

    @Slot(str)
    def _on_game_hotword_changed(self, title: str) -> None:
        self._store.save(replace(self._store.get(), game_hotword_set=title))

    def _load_hotwords(self, title: str) -> dict[str, str]:
        if not title:
            return {}
        try:
            return dict(hotword_store.load(title).entries)
        except Exception:
            return {}

    def _on_typed_settings_changed(self) -> None:
        s = self._store.get()
        self._store.save(replace(
            s,
            typed_source_language=self._typed_panel.selected_source(),
            typed_target_language=self._typed_panel.selected_target(),
            typed_auto_tts=self._typed_panel.auto_tts(),
        ))
        self._refresh_float_chips()

    def _refresh_float_chips(self) -> None:
        s = self._store.get()
        route = f"{s.typed_source_language} → {s.typed_target_language}"
        self._float_input.update_chips(self._hotkey_display(s.typed_hotkey), route, s.typed_auto_tts)

    def _build_typed_controller(self) -> TypedTranslateController:
        s = self._store.get()
        cfg = TypedConfig(
            translate=DoubaoTranslateConfig(api_key=s.volc_api_key),
            tts=DoubaoTtsConfig(
                api_key=s.volc_api_key,
                speaker_id=resolve_doubao_tts_speaker(s.s2s_speaker_id),
            ),
            source_language=self._typed_panel.selected_source(),
            target_language=self._typed_panel.selected_target(),
            auto_tts=self._typed_panel.auto_tts(),
            cable_input_name=s.vb_cable_input_name,
            engine_name=s.translator_engine,
            qwen_mt=QwenMtConfig(api_key=s.qwen_api_key, base_url=s.qwen_base_url),
            qwen_tts=QwenTtsConfig(
                api_key=s.qwen_api_key,
                voice=s.qwen_s2s_speaker_id or "Cherry",
                realtime_url=s.qwen_ws_url,
            ),
            hotwords=self._load_hotwords(self._typed_panel.selected_hotword_set()),
        )
        if self._typed_controller is None:
            self._typed_controller = TypedTranslateController(cfg)
        else:
            self._typed_controller.cfg = cfg
        return self._typed_controller

    @Slot(str)
    def _validate_voice_for_mode(self, engine: str, speaker_id: str, expects_s2s: bool) -> bool:
        is_s2s = voice_is_s2s(engine, speaker_id)
        if is_s2s is None:
            return True
        if expects_s2s and not is_s2s:
            QMessageBox.warning(self, "音色不匹配", "当前为同声传译模式，请选择标有「同传可用」的同声传译音色。")
            return False
        if not expects_s2s and is_s2s:
            QMessageBox.warning(self, "音色不匹配", "当前模式不支持同声传译音色，请选择普通 TTS 音色。")
            return False
        return True

    def _on_typed_submit(self, text: str) -> None:
        self._run_typed(text, from_float=False)

    @Slot(str)
    def _on_typed_submit_from_float(self, text: str) -> None:
        self._run_typed(text, from_float=True)

    def _run_typed(self, text: str, from_float: bool) -> None:
        if self._typed_busy:
            return
        if self._typed_panel.auto_tts():
            s = self._store.get()
            engine = s.translator_engine
            speaker_id = s.qwen_s2s_speaker_id if engine == "qwen" else s.s2s_speaker_id
            if not self._validate_voice_for_mode(engine, speaker_id, expects_s2s=False):
                return
        try:
            controller = self._build_typed_controller()
        except Exception as exc:
            QMessageBox.critical(self, "打字翻译", str(exc))
            return
        self._typed_busy = True
        self._typed_panel.set_busy(True)
        thread = TypedTranslateThread(controller, text, parent=self)
        thread.sig_status.connect(self.sig_status)
        thread.sig_result.connect(self._on_typed_result)
        thread.sig_done.connect(self._on_typed_done)
        thread.sig_error.connect(self._on_typed_error)
        self._typed_thread = thread
        thread.start()

    @Slot(str, str)
    def _on_typed_result(self, source: str, translated: str) -> None:
        self._typed_panel.show_result(source, translated)
        self._float_input.show_result(source, translated)

    @Slot()
    def _on_typed_done(self) -> None:
        self._typed_busy = False
        self._typed_panel.set_busy(False)
        self._typed_thread = None

    @Slot(str)
    def _on_typed_error(self, msg: str) -> None:
        self._typed_busy = False
        self._typed_panel.set_busy(False)
        self._log_panel.append(f"[typed-error] {msg}")
        QMessageBox.warning(self, "打字翻译失败", msg)

    def _apply_hotkeys(self, s: AppSettings) -> None:
        self._hotkeys.unregister_all()
        bindings = [
            ("typed_panel", s.typed_hotkey, self._hk_toggle_typed_panel),
            ("subtitle", s.hotkey_subtitle_toggle, self._hk_toggle_subtitle),
            ("si", s.hotkey_si_toggle, self._hk_toggle_si),
            ("sim_checkbox", s.hotkey_sim_checkbox, self._hk_toggle_sim_checkbox),
            ("subtitle_drag", s.hotkey_subtitle_drag_toggle, self._hk_toggle_subtitle_drag),
            ("typed_tts", s.hotkey_typed_tts_toggle, self._hk_toggle_typed_tts),
        ]
        for action, combo, cb in bindings:
            if not combo:
                continue
            if self._hotkeys.register_action(action, combo, cb):
                self._log_panel.append(f"热键已绑定 [{action}]：{combo}")
            else:
                self._log_panel.append(f"热键绑定失败 [{action}]：{combo}")
        self._refresh_float_chips()

    def _hk_toggle_typed_panel(self) -> None:
        if self._float_input.isVisible():
            self._float_input.hide()
        else:
            self._float_input.show_centered(self.screen())

    def _hk_toggle_subtitle(self) -> None:
        running = self._game_thread is not None and self._game_thread.isRunning()
        if running:
            self._stop_game()
            show_toast("字幕已关闭")
        else:
            self._start_game()
            started = self._game_thread is not None and self._game_thread.isRunning()
            if started:
                show_toast("字幕已开启")

    def _hk_toggle_si(self) -> None:
        running = self._mic_thread is not None and self._mic_thread.isRunning()
        if running:
            self._stop_mic()
            show_toast("麦克风已关闭")
        else:
            self._start_mic()
            if self._mic_thread is not None:
                show_toast("麦克风已开启")

    def _hk_toggle_sim_checkbox(self) -> None:
        cb = self._mic_panel._simultaneous_checkbox
        new_state = not cb.isChecked()
        cb.setChecked(new_state)
        running = self._mic_thread is not None and self._mic_thread.isRunning()
        if running:
            self._restart_mic_after_stop = True
            self._stop_mic()
        show_toast("同声传译已开启" if new_state else "麦克风直连已开启")

    def _hk_toggle_subtitle_drag(self) -> None:
        new_state = not self._header._adjust_btn.isChecked()
        self._header._adjust_btn.setChecked(new_state)
        show_toast("字幕可拖动" if new_state else "字幕已锁定")

    def _hk_toggle_typed_tts(self) -> None:
        new_state = not self._typed_panel.auto_tts()
        self._typed_panel.set_auto_tts(new_state)
        show_toast("打字翻译语音合成已开启" if new_state else "打字翻译语音合成已关闭")

    def _apply_settings(self, s: AppSettings) -> None:
        is_qwen = s.translator_engine == "qwen"
        self._header.set_usage_visible(s.usage_tracking_enabled)
        self._header.set_usage_mode(s.usage_chip_show_token)
        if s.usage_tracking_enabled:
            st = self._usage_tracker.state
            self._header.set_usage(st.session_cost, st.total_cost, st.session_tokens, st.total_tokens)
        self._mic_panel.set_mic_by_index(s.mic_input_index)
        self._mic_panel.set_output_by_index(s.mic_output_index)
        self._mic_panel.set_engine(s.translator_engine)
        self._game_panel.set_engine(s.translator_engine)
        self._typed_panel.set_engine(s.translator_engine)
        self._mic_panel.set_source_language(s.s2s_source_language)
        self._mic_panel.set_target_language(s.s2s_target_language)
        self._mic_panel.set_speaker_id(s.qwen_s2s_speaker_id if is_qwen else s.s2s_speaker_id)
        self._mic_panel.set_simultaneous_interpretation_enabled(s.mic_simultaneous_interpretation_enabled)
        self._mic_panel.set_speech_rate(s.s2s_speech_rate)
        self._game_panel.set_source_language(s.game_subtitle_source_language)
        self._game_panel.set_target_language(s.game_subtitle_target_language)
        self._game_panel.set_audio_devices(_list_speaker_names(), s.game_audio_device_name)
        self._game_audio_accepted = s.game_audio_device_name or ""
        self._apply_mic_conflict_state(self._game_audio_accepted)
        self._game_panel.set_max_lines(s.overlay_max_lines)
        self._game_panel.set_show_source(s.overlay_show_source)
        # Overlay appearance
        self._overlay.set_font_size(s.overlay_font_size)
        self._overlay.set_opacity(s.overlay_opacity)
        self._overlay.set_text_color(s.overlay_text_color)
        self._overlay.set_overlay_width(s.overlay_width)
        self._overlay.set_click_through(s.overlay_click_through)
        if s.overlay_x is not None and s.overlay_y is not None:
            self._overlay.move(s.overlay_x, s.overlay_y)
        # Typed panel settings
        self._typed_panel.set_source(s.typed_source_language)
        self._typed_panel.set_target(s.typed_target_language)
        self._typed_panel.set_auto_tts(s.typed_auto_tts)
        self._mic_panel.set_hotword_set(s.mic_hotword_set)
        self._typed_panel.set_hotword_set(s.typed_hotword_set)
        self._game_panel.set_hotword_set(s.game_hotword_set)
        self._apply_hotkeys(s)
        self._header.set_advanced(s.show_advanced_panel)
        self._mic_panel.set_advanced(s.show_advanced_panel)
        self._game_panel.set_advanced(s.show_advanced_panel)

    @Slot()
    def _start_mic(self) -> None:
        if self._mic_thread is not None and self._mic_thread.isRunning():
            return

        device = self._mic_panel.selected_mic_device()
        if device is None:
            QMessageBox.warning(self, "麦克风", "请选择麦克风设备")
            return

        engine = self._mic_panel.selected_engine()
        src_lang = self._mic_panel.selected_source_language()
        tgt_lang = self._mic_panel.selected_target_language()
        speaker_id = self._mic_panel.selected_speaker_id()
        simultaneous_enabled = self._mic_panel.simultaneous_interpretation_enabled()
        speech_rate = self._mic_panel.selected_speech_rate()

        if simultaneous_enabled and src_lang == tgt_lang and src_lang != "auto" and src_lang != "zh":
            QMessageBox.warning(self, "语言设置", "源语言和目标语言不能相同")
            return

        if simultaneous_enabled:
            zh_to_zh = src_lang == "zh" and tgt_lang == "zh"
            if not self._validate_voice_for_mode(engine, speaker_id, expects_s2s=not zh_to_zh):
                return

        try:
            config = build_app_config(_ENV_PATH)
            if simultaneous_enabled and engine == "huoshan" and not config.api_key:
                raise RuntimeError(
                    "未检测到火山引擎 App Key。\n\n"
                    "请点击右上角齿轮图标 → 火山引擎选项卡，填写 App Key 后保存。"
                )
            out_device = self._mic_panel.selected_output_device()
            config.audio_route = replace(
                config.audio_route,
                input_device_index=device.index,
                input_device_name=None,
                output_device_index=out_device.index if out_device else None,
                output_device_name=out_device.name if out_device else config.audio_route.output_device_name,
            )
            config.engine_name = engine
            config.source_language = src_lang
            config.target_language = tgt_lang
            config.speaker_id = speaker_id
            config.simultaneous_interpretation_enabled = simultaneous_enabled
            config.speech_rate = speech_rate
            config.hotwords = self._load_hotwords(self._mic_panel.selected_hotword_set())
            self._store.save(
                replace(
                    self._store.get(),
                    mic_input_index=device.index,
                    mic_output_index=(out_device.index if out_device else None),
                    translator_engine=engine,
                    s2s_source_language=src_lang,
                    s2s_target_language=tgt_lang,
                    s2s_speaker_id=speaker_id,
                    mic_simultaneous_interpretation_enabled=simultaneous_enabled,
                    s2s_speech_rate=speech_rate,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "配置错误", str(exc))
            return

        if simultaneous_enabled:
            self._show_si_hotword_info_once()

        self._mic_panel.set_running(True)
        self._header.set_status("翻译启动中...", "warn")

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
            self._header.set_status("正在停止...", "warn")
            self._mic_thread.request_stop()

    @Slot()
    def _on_mic_stopped(self) -> None:
        self._mic_panel.set_running(False)
        self._mic_thread = None
        self._header.set_status("就绪")
        self._log_panel.append("麦克风翻译已停止")
        if self._restart_mic_after_stop:
            self._restart_mic_after_stop = False
            self._start_mic()

    @Slot(str)
    def _on_mic_error(self, msg: str) -> None:
        self._mic_panel.set_running(False)
        self._mic_thread = None
        self._header.set_status("错误", "error")
        QMessageBox.critical(self, "运行错误", msg)

    def _is_cable_input_device(self, name: str) -> bool:
        if not name:
            return False
        cable = (self._store.get().vb_cable_input_name or "CABLE Input").strip().lower()
        return cable and cable in name.lower()

    def _apply_mic_conflict_state(self, device_name: str) -> None:
        conflict = self._is_cable_input_device(device_name)
        self._mic_area.voice.setEnabled(not conflict)
        if conflict:
            self._mic_area.voice.setToolTip("游戏字幕音频源占用了同一根虚拟线，同声传译已禁用")
        else:
            self._mic_area.voice.setToolTip("")

    @Slot(str)
    def _on_game_audio_changed(self, name: str) -> None:
        if not self._is_cable_input_device(name):
            self._game_audio_accepted = name
            self._apply_mic_conflict_state(name)
            return
        if self._mic_thread is not None and self._mic_thread.isRunning():
            QMessageBox.warning(
                self,
                "冲突",
                "同声传译正在运行，无法选择该虚拟线。请先停止同声传译。",
            )
            self._game_panel.set_audio_device(self._game_audio_accepted)
            return
        resp = QMessageBox.question(
            self,
            "确认",
            "该设备与同声传译使用同一根虚拟线。\n"
            "选中后将自动禁用同声传译功能，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            self._game_panel.set_audio_device(self._game_audio_accepted)
            return
        self._game_audio_accepted = name
        self._apply_mic_conflict_state(name)

    @Slot()
    def _start_game(self) -> None:
        if self._game_thread is not None and self._game_thread.isRunning():
            return

        try:
            config = build_game_subtitle_config(_ENV_PATH)
            if not config.api_key:
                raise RuntimeError(
                    "未检测到火山引擎 App Key。\n\n"
                    "请点击右上角齿轮图标 → 火山引擎选项卡，填写 App Key 后保存。"
                )
            src = self._game_panel.selected_source_language()
            tgt = self._game_panel.selected_target_language()
            audio_device = self._game_panel.selected_audio_device()
            config.source_language = src
            config.target_language = tgt
            config.audio_device_name = audio_device or None
            config.hotwords = self._load_hotwords(self._game_panel.selected_hotword_set())
            self._store.save(replace(
                self._store.get(),
                game_subtitle_source_language=src,
                game_subtitle_target_language=tgt,
                game_audio_device_name=audio_device,
            ))
        except Exception as exc:
            QMessageBox.critical(self, "游戏字幕配置错误", str(exc))
            return

        self._show_si_hotword_info_once()

        self._game_panel.set_running(True)
        self._header.set_status("游戏字幕启动中...", "warn")
        if not self._overlay.isVisible():
            self._toggle_overlay()

        self._game_thread = GameSubtitleThread(config, parent=self)
        self._game_thread.sig_status.connect(self.sig_status)
        self._game_thread.sig_subtitle.connect(self.sig_game_subtitle)
        self._game_thread.sig_stopped.connect(self.sig_game_stopped)
        self._game_thread.sig_error.connect(self.sig_game_error)
        self._game_thread.start()

    @Slot()
    def _stop_game(self) -> None:
        if self._game_thread and self._game_thread.isRunning():
            self._game_thread.request_stop()

    @Slot()
    def _on_game_stopped(self) -> None:
        self._game_panel.set_running(False)
        self._game_thread = None
        self._log_panel.append("游戏字幕已停止")
        if self._overlay.isVisible():
            self._overlay.hide()
            self._overlay_visible = False

    @Slot(str)
    def _on_game_error(self, msg: str) -> None:
        self._game_panel.set_running(False)
        self._game_thread = None
        QMessageBox.critical(self, "游戏字幕错误", msg)

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        kind = "error" if "error" in msg.lower() else "normal"
        self._header.set_status(msg, kind)
        self._log_panel.append(msg)
        if self._store.get().usage_tracking_enabled and ("usage]" in msg):
            self._usage_tracker.feed_log_line(msg)

    @Slot(float, float)
    def _on_usage_updated(self, session_cost: float, total_cost: float) -> None:
        if self._store.get().usage_tracking_enabled:
            st = self._usage_tracker.state
            self._header.set_usage(st.session_cost, st.total_cost, st.session_tokens, st.total_tokens)

    @Slot()
    def _open_usage(self) -> None:
        dlg = UsageDialog(self._usage_tracker, parent=self)
        dlg.exec()

    @Slot()
    def _open_feedback(self) -> None:
        dlg = FeedbackDialog(self._store, parent=self)
        dlg.exec()
        # After closing, dialog has acked unread messages → refresh badge
        if getattr(self, "_msg_poller", None):
            self._msg_poller.trigger_now()

    @Slot(int)
    def _on_unread_count(self, n: int) -> None:
        self._header.set_feedback_unread(n)
        if n > 0:
            self._log_panel.append(f"📩 有 {n} 条来自开发者的新消息，点击「提需求」查看")

    @Slot()
    def _toggle_overlay(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            if not self._overlay_visible:
                # First show: position bottom-center of screen
                screen = self.screen()
                if screen:
                    sg = screen.geometry()
                    self._overlay.move(
                        sg.x() + (sg.width() - self._overlay.width()) // 2,
                        sg.y() + sg.height() - 200,
                    )
            self._overlay.show()
        self._overlay_visible = self._overlay.isVisible()

    @Slot()
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._store, parent=self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    @Slot()
    def _open_voice_selector(self) -> None:
        engine = self._store.get().translator_engine
        dlg = getattr(self, "_voice_dlg", None)
        if dlg is not None and getattr(dlg, "_engine", "huoshan") != engine:
            try:
                dlg.close()
            except Exception:
                pass
            dlg = None
            self._voice_dlg = None
        if dlg is None:
            dlg = VoiceSelectorDialog(
                self._mic_panel.selected_speaker_id(),
                parent=self,
                engine=engine,
                qwen_api_key=self._store.get().qwen_api_key,
            )
            dlg.voice_selected.connect(self._on_voice_selected)
            self._voice_dlg = dlg
        else:
            dlg._current_voice = self._mic_panel.selected_speaker_id()
            dlg._refresh_rows()
            dlg._update_selected_label()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    @Slot(str)
    def _on_voice_selected(self, speaker_id: str) -> None:
        self._mic_panel.set_speaker_id(speaker_id)
        cur = self._store.get()
        if cur.translator_engine == "qwen":
            self._store.save(replace(cur, qwen_s2s_speaker_id=speaker_id or "Cherry"))
            self._log_panel.append(f"Qwen 音色已选择: {speaker_id or 'Cherry'}")
        else:
            self._store.save(replace(cur, s2s_speaker_id=speaker_id))
            self._log_panel.append(f"火山音色已选择: {speaker_id or '服务默认音色'}")

    @Slot(object)
    def _on_settings_saved(self, s: object) -> None:
        from core.settings_store import AppSettings
        if not isinstance(s, AppSettings):
            return
        prev_engine = getattr(self, "_last_engine", "huoshan")
        if prev_engine != s.translator_engine:
            if self._mic_thread and self._mic_thread.isRunning():
                self._mic_thread.request_stop()
                self._log_panel.append(f"引擎切换 {prev_engine}→{s.translator_engine}：已停止同传")
            if self._game_thread and self._game_thread.isRunning():
                self._game_thread.request_stop()
                self._log_panel.append(f"引擎切换 {prev_engine}→{s.translator_engine}：已停止游戏字幕")
        self._last_engine = s.translator_engine
        self._apply_settings(s)
        self._header.set_status("设置已保存", "normal")
        self._log_panel.append("设置已保存")

    @Slot()
    def _test_cable(self) -> None:
        self._checklist.test_cable()

    def _on_overlay_pos_saved(self, x: int, y: int) -> None:
        s = self._store.get()
        from dataclasses import replace
        self._store.save(replace(s, overlay_x=x, overlay_y=y))

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
        self._float_input.close()
        self._hotkeys.unregister_all()
        if self._typed_controller is not None:
            self._typed_controller.close()
            self._typed_controller = None
        super().closeEvent(event)
