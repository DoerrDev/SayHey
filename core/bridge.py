from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app_core.controller import VoiceTranslatorController, AppConfig, build_app_config
from app_core.game_subtitle_controller import GameSubtitleController, GameSubtitleConfig, build_game_subtitle_config
from app_core.typed_controller import TypedTranslateController, TypedConfig

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class ControllerThread(QThread):
    sig_status = Signal(str)
    sig_source = Signal(str)
    sig_translation = Signal(str)
    sig_stopped = Signal()
    sig_error = Signal(str)

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._controller: Optional[VoiceTranslatorController] = None
        self._translation_held = False

    def run(self) -> None:
        try:
            self._controller = VoiceTranslatorController(
                self._config,
                on_status=self.sig_status.emit,
                on_source=self.sig_source.emit,
                on_translation=self.sig_translation.emit,
            )
            self._controller.set_translation_held(self._translation_held)
            asyncio.run(self._controller.run())
        except asyncio.CancelledError:
            self.sig_status.emit("Stopped")
        except Exception as exc:
            self.sig_error.emit(str(exc))
            self.sig_status.emit(f"Error: {exc}")
            traceback.print_exc()
        finally:
            self._controller = None
            self.sig_stopped.emit()

    def request_stop(self) -> None:
        if self._controller is not None:
            self._controller.request_stop()

    def set_translation_held(self, held: bool) -> None:
        self._translation_held = bool(held)
        if self._controller is not None:
            self._controller.set_translation_held(held)


class GameSubtitleThread(QThread):
    sig_status = Signal(str)
    sig_subtitle = Signal(str, str)
    sig_stopped = Signal()
    sig_error = Signal(str)

    def __init__(self, config: GameSubtitleConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._controller: Optional[GameSubtitleController] = None

    def run(self) -> None:
        try:
            self._controller = GameSubtitleController(
                self._config,
                on_status=self.sig_status.emit,
                on_subtitle=self.sig_subtitle.emit,
            )
            asyncio.run(self._controller.run())
        except asyncio.CancelledError:
            self.sig_status.emit("Game subtitles stopped")
        except Exception as exc:
            self.sig_error.emit(str(exc))
            self.sig_status.emit(f"Game subtitles error: {exc}")
            traceback.print_exc()
        finally:
            self._controller = None
            self.sig_stopped.emit()

    def request_stop(self) -> None:
        if self._controller is not None:
            self._controller.request_stop()


class TypedTranslateThread(QThread):
    sig_status = Signal(str)
    sig_result = Signal(str, str)   # source, translated
    sig_done = Signal()
    sig_error = Signal(str)

    def __init__(self, controller: TypedTranslateController, text: str, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._text = text

    def run(self) -> None:
        try:
            self._controller.on_status = self.sig_status.emit
            self._controller.on_result = lambda s, t: self.sig_result.emit(s, t)
            self._controller.translate_and_send(self._text)
        except Exception as exc:
            self.sig_error.emit(str(exc))
            traceback.print_exc()
        finally:
            self.sig_done.emit()


def build_mic_config(env_path: Path = _ENV_PATH) -> AppConfig:
    return build_app_config(env_path)


def build_game_config(env_path: Path = _ENV_PATH) -> GameSubtitleConfig:
    return build_game_subtitle_config(env_path)
