from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

_APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = _APP_DIR / "settings.json"
_ENV_PATH = _APP_DIR / ".env"
_OPENAI_ENV_PATH = _APP_DIR / "openapi.env"


@dataclass
class AppSettings:
    volc_api_key: str = ""
    volc_resource_id: str = "volc.service_type.10053"
    volc_ws_url: str = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
    openai_api_key: str = ""
    openai_ws_url: str = "wss://translate.doerr.work/v1/realtime/translations"
    vb_cable_input_name: str = "CABLE Input"
    vb_cable_output_name: str = "CABLE Output"
    translator_engine: str = "huoshan"
    s2s_source_language: str = "en"
    s2s_target_language: str = "zh"
    s2s_speaker_id: str = "zh_female_xiaohe_jupiter_bigtts"
    s2s_speech_rate: int = 0
    game_subtitle_source_language: str = "en"
    game_subtitle_target_language: str = "zh"
    mic_input_index: Optional[int] = None
    game_audio_device_name: str = ""
    overlay_font_size: int = 32
    overlay_opacity: float = 0.85
    overlay_x: Optional[int] = None
    overlay_y: Optional[int] = None
    overlay_click_through: bool = True
    overlay_max_lines: int = 2
    overlay_text_color: str = "#ffffff"
    overlay_width: int = 800
    usage_tracking_enabled: bool = False
    usage_chip_show_token: bool = True
    auto_switch_default_mic: bool = False
    auto_switch_mic_keyword: str = "CABLE Output"


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
        else:
            s = self._bootstrap_from_env()
            self._path.write_text(
                json.dumps(asdict(s), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        self._sync_to_environ(s)
        return s

    def _bootstrap_from_env(self) -> AppSettings:
        env: dict[str, str] = {}
        for env_path in (_ENV_PATH, _OPENAI_ENV_PATH):
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
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
            openai_api_key=get("OPENAI_API_KEY"),
            openai_ws_url=get("OPENAI_REALTIME_WS_URL", "wss://translate.doerr.work/v1/realtime/translations"),
            vb_cable_input_name=get("VB_CABLE_INPUT_NAME", "CABLE Input"),
            vb_cable_output_name=get("VB_CABLE_OUTPUT_NAME", "CABLE Output"),
            translator_engine=get("TRANSLATOR_ENGINE", "huoshan"),
            s2s_source_language=get("S2S_SOURCE_LANGUAGE") or get("SOURCE_LANGUAGE", "en"),
            s2s_target_language=get("S2S_TARGET_LANGUAGE") or get("TARGET_LANGUAGE", "zh"),
            s2s_speaker_id=get("S2S_SPEAKER_ID", "zh_female_xiaohe_jupiter_bigtts"),
            s2s_speech_rate=int(get("S2S_SPEECH_RATE", "0") or "0"),
            game_subtitle_source_language=get("GAME_SUBTITLE_SOURCE_LANGUAGE", "en"),
            game_subtitle_target_language=get("GAME_SUBTITLE_TARGET_LANGUAGE", "zh"),
            mic_input_index=mic_idx,
            game_audio_device_name=get("GAME_AUDIO_DEVICE_NAME"),
        )

    def _sync_to_environ(self, s: AppSettings) -> None:
        overrides: dict[str, str] = {
            "VOLC_APP_KEY": s.volc_api_key,
            "VOLC_API_KEY": s.volc_api_key,
            "VOLC_RESOURCE_ID": s.volc_resource_id,
            "VOLC_WS_URL": s.volc_ws_url,
            "OPENAI_API_KEY": s.openai_api_key,
            "OPENAI_REALTIME_WS_URL": s.openai_ws_url,
            "VB_CABLE_INPUT_NAME": s.vb_cable_input_name,
            "VB_CABLE_OUTPUT_NAME": s.vb_cable_output_name,
            "TRANSLATOR_ENGINE": s.translator_engine,
            "S2S_SOURCE_LANGUAGE": s.s2s_source_language,
            "S2S_TARGET_LANGUAGE": s.s2s_target_language,
            "S2S_SPEAKER_ID": s.s2s_speaker_id,
            "S2S_SPEECH_RATE": str(s.s2s_speech_rate),
            "GAME_SUBTITLE_SOURCE_LANGUAGE": s.game_subtitle_source_language,
            "GAME_SUBTITLE_TARGET_LANGUAGE": s.game_subtitle_target_language,
            "GAME_AUDIO_DEVICE_NAME": s.game_audio_device_name,
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
