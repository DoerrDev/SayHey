from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = _APP_DIR / "settings.json"
_ENV_PATH = _APP_DIR / ".env"


@dataclass
class AppSettings:
    volc_api_key: str = ""
    volc_resource_id: str = "volc.service_type.10053"
    volc_ws_url: str = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
    vb_cable_input_name: str = "CABLE Input"
    vb_cable_output_name: str = "CABLE Output"
    translator_engine: str = "huoshan"
    s2s_source_language: str = "en"
    s2s_target_language: str = "zh"
    s2s_speaker_id: str = "zh_female_xiaohe_jupiter_bigtts"
    s2s_speech_rate: int = 0
    mic_simultaneous_interpretation_enabled: bool = True
    mic_push_to_translate_enabled: bool = False
    mic_noise_gate_threshold: float = 0.02
    game_subtitle_source_language: str = "en"
    game_subtitle_target_language: str = "zh"
    game_subtitle_filter_chinese: bool = False
    mic_input_index: Optional[int] = None
    mic_output_index: Optional[int] = None
    game_audio_device_name: str = ""
    overlay_font_size: int = 32
    overlay_opacity: float = 0.85
    overlay_x: Optional[int] = None
    overlay_y: Optional[int] = None
    overlay_click_through: bool = True
    overlay_max_lines: int = 2
    overlay_text_color: str = "#ffffff"
    overlay_width: int = 800
    overlay_show_source: bool = True
    usage_tracking_enabled: bool = False
    usage_chip_show_token: bool = True
    auto_switch_default_mic: bool = False
    auto_switch_mic_keyword: str = "CABLE Output"
    volc_trial_enabled: bool = False
    volc_trial_token: str = ""
    volc_trial_proxy_ws_url: str = "wss://trial.sayhey.top/api/v4/ast/v2/translate"
    volc_trial_api_base: str = "https://trial.sayhey.top"
    feedback_nickname: str = ""
    typed_source_language: str = "zh"
    typed_target_language: str = "en"
    typed_auto_tts: bool = True
    typed_hotkey: str = "ctrl+alt+t"
    hotkey_subtitle_toggle: str = ""
    hotkey_si_toggle: str = ""
    hotkey_sim_checkbox: str = ""
    hotkey_subtitle_drag_toggle: str = ""
    hotkey_typed_tts_toggle: str = ""
    hotkey_hold_translate: str = ""
    show_advanced_panel: bool = False
    advanced_audio_warning_shown: bool = False
    zh_to_zh_info_shown: bool = False
    si_hotword_info_shown: bool = False
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    qwen_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    qwen_trial_base_url: str = "https://trial.sayhey.top/api/qwen"
    qwen_trial_ws_url: str = "wss://trial.sayhey.top/api/qwen/realtime"
    qwen_s2s_speaker_id: str = ""
    monitor_enabled: bool = False
    monitor_device_name: str = ""
    monitor_gain: float = 1.0
    mic_hotword_set: str = ""
    typed_hotword_set: str = ""
    game_hotword_set: str = ""


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self._path = path
        self._settings: AppSettings = self._load()

    def get(self) -> AppSettings:
        return self._settings

    def save(self, settings: AppSettings) -> None:
        self._settings = settings
        self._path.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._sync_to_environ(settings)

    def _load(self) -> AppSettings:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                known = set(AppSettings.__dataclass_fields__.keys())
                filtered = {k: v for k, v in raw.items() if k in known}
                s = AppSettings(**filtered)
            except Exception:
                s = self._bootstrap_from_env()
            migrated = self._migrate_qwen_trial(s)
            if migrated is not None:
                s = migrated
                self._path.write_text(
                    json.dumps(asdict(s), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        else:
            s = self._bootstrap_from_env()
            self._path.write_text(
                json.dumps(asdict(s), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        self._sync_to_environ(s)
        return s

    @staticmethod
    def _migrate_qwen_trial(s: AppSettings) -> Optional[AppSettings]:
        """Recover configs polluted by the old Qwen-trial flow that wrote the trial
        token / proxy URLs directly into the user's own qwen_* fields. Move those
        values back into the dedicated trial fields and restore DashScope defaults.
        Returns a new AppSettings if migration happened, else None.
        """
        _TRIAL_HOST = "trial.sayhey.top"
        polluted = any(
            _TRIAL_HOST in (v or "")
            for v in (s.qwen_api_key, s.qwen_base_url, s.qwen_ws_url)
        )
        if not polluted:
            return None
        from dataclasses import replace

        changes: dict[str, object] = {}
        if _TRIAL_HOST in (s.qwen_ws_url or ""):
            changes["qwen_trial_ws_url"] = s.qwen_ws_url
            changes["qwen_ws_url"] = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
        if _TRIAL_HOST in (s.qwen_base_url or ""):
            changes["qwen_trial_base_url"] = s.qwen_base_url
            changes["qwen_base_url"] = "https://dashscope.aliyuncs.com/api/v1"
        # qwen_api_key was overwritten with the trial token (trial tokens are not
        # DashScope "sk-" keys). Move it into the shared trial token slot and clear
        # the user's own key field so they can re-enter their real key.
        if not (s.qwen_api_key or "").startswith("sk-"):
            token = s.qwen_api_key
            changes["qwen_api_key"] = ""
            if token and not s.volc_trial_token:
                changes["volc_trial_token"] = token
            if token:
                changes["volc_trial_enabled"] = True
        return replace(s, **changes)

    def _bootstrap_from_env(self) -> AppSettings:
        env: dict[str, str] = {}
        if _ENV_PATH.exists():
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                k, v = raw.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")

        def get(key: str, default: str = "") -> str:
            return env.get(key, default).strip()

        mic_idx: Optional[int] = None
        if get("MIC_INPUT_INDEX"):
            try:
                mic_idx = int(get("MIC_INPUT_INDEX"))
            except ValueError:
                pass

        return AppSettings(
            volc_api_key=get("VOLC_APP_KEY") or get("VOLC_API_KEY"),
            volc_resource_id=get("VOLC_RESOURCE_ID", "volc.service_type.10053"),
            volc_ws_url=get("VOLC_WS_URL", "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"),
            vb_cable_input_name=get("VB_CABLE_INPUT_NAME", "CABLE Input"),
            vb_cable_output_name=get("VB_CABLE_OUTPUT_NAME", "CABLE Output"),
            translator_engine=get("TRANSLATOR_ENGINE", "huoshan"),
            s2s_source_language=get("S2S_SOURCE_LANGUAGE") or get("SOURCE_LANGUAGE", "en"),
            s2s_target_language=get("S2S_TARGET_LANGUAGE") or get("TARGET_LANGUAGE", "zh"),
            s2s_speaker_id=get("S2S_SPEAKER_ID", "zh_female_xiaohe_jupiter_bigtts"),
            s2s_speech_rate=int(get("S2S_SPEECH_RATE", "0") or "0"),
            mic_simultaneous_interpretation_enabled=get("MIC_SIMULTANEOUS_INTERPRETATION", "1")
            not in {"0", "false", "False"},
            mic_push_to_translate_enabled=get("MIC_PUSH_TO_TRANSLATE", "0")
            not in {"0", "false", "False"},
            game_subtitle_source_language=get("GAME_SUBTITLE_SOURCE_LANGUAGE", "en"),
            game_subtitle_target_language=get("GAME_SUBTITLE_TARGET_LANGUAGE", "zh"),
            game_subtitle_filter_chinese=get("GAME_SUBTITLE_FILTER_CHINESE", "0")
            not in {"0", "false", "False"},
            mic_input_index=mic_idx,
            game_audio_device_name=get("GAME_AUDIO_DEVICE_NAME"),
            qwen_api_key=get("QWEN_API_KEY"),
            qwen_base_url=get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"),
            qwen_ws_url=get("QWEN_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"),
        )

    def _sync_to_environ(self, s: AppSettings) -> None:
        use_trial = bool(s.volc_trial_enabled and s.volc_trial_token) and s.translator_engine != "qwen"
        effective_api_key = s.volc_trial_token if use_trial else s.volc_api_key
        effective_ws_url = s.volc_trial_proxy_ws_url if use_trial else s.volc_ws_url
        qwen_trial = bool(s.volc_trial_enabled and s.volc_trial_token) and s.translator_engine == "qwen"
        qwen_api_key = s.volc_trial_token if qwen_trial else s.qwen_api_key
        qwen_base_url = s.qwen_trial_base_url if qwen_trial else s.qwen_base_url
        qwen_ws_url = s.qwen_trial_ws_url if qwen_trial else s.qwen_ws_url
        overrides: dict[str, str] = {
            "VOLC_APP_KEY": effective_api_key,
            "VOLC_API_KEY": effective_api_key,
            "VOLC_RESOURCE_ID": s.volc_resource_id,
            "VOLC_WS_URL": effective_ws_url,
            "VOLC_TRIAL_ENABLED": "1" if use_trial else "",
            "VOLC_TRIAL_API_BASE": s.volc_trial_api_base,
            "VB_CABLE_INPUT_NAME": s.vb_cable_input_name,
            "VB_CABLE_OUTPUT_NAME": s.vb_cable_output_name,
            "TRANSLATOR_ENGINE": s.translator_engine,
            "QWEN_API_KEY": qwen_api_key,
            "QWEN_BASE_URL": qwen_base_url,
            "QWEN_WS_URL": qwen_ws_url,
            "QWEN_S2S_SPEAKER_ID": s.qwen_s2s_speaker_id,
            "S2S_SOURCE_LANGUAGE": s.s2s_source_language,
            "S2S_TARGET_LANGUAGE": s.s2s_target_language,
            "S2S_SPEAKER_ID": s.s2s_speaker_id,
            "S2S_SPEECH_RATE": str(s.s2s_speech_rate),
            "MIC_SIMULTANEOUS_INTERPRETATION": "1" if s.mic_simultaneous_interpretation_enabled else "0",
            "MIC_PUSH_TO_TRANSLATE": "1" if s.mic_push_to_translate_enabled else "",
            "MIC_NOISE_GATE": f"{float(s.mic_noise_gate_threshold):.4f}",
            "GAME_SUBTITLE_SOURCE_LANGUAGE": s.game_subtitle_source_language,
            "GAME_SUBTITLE_TARGET_LANGUAGE": s.game_subtitle_target_language,
            "GAME_SUBTITLE_FILTER_CHINESE": "1" if s.game_subtitle_filter_chinese else "",
            "GAME_AUDIO_DEVICE_NAME": s.game_audio_device_name,
            "S2S_MONITOR_ENABLED": "1" if s.monitor_enabled else "",
            "S2S_MONITOR_DEVICE": s.monitor_device_name,
            "S2S_MONITOR_GAIN": f"{float(s.monitor_gain):.2f}",
        }
        if s.mic_input_index is not None:
            overrides["MIC_INPUT_INDEX"] = str(s.mic_input_index)
        elif "MIC_INPUT_INDEX" in os.environ:
            del os.environ["MIC_INPUT_INDEX"]

        for key, value in overrides.items():
            if value:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
