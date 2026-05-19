from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


@dataclass
class TranslatorConfig:
    source_language: str
    target_language: str
    sample_rate: int = 16000
    speaker_id: Optional[str] = None
    speech_rate: int = 0
    provider_options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TranslatorEvent:
    type: str
    data: bytes = b""
    text: str = ""
    message: str = ""
    segment_id: int = 0


TranslatorEventCallback = Callable[[TranslatorEvent], None]


class SpeechTranslatorEngine(Protocol):
    async def start(self, config: TranslatorConfig, on_event: TranslatorEventCallback) -> None:
        ...

    async def send_audio(self, pcm_bytes: bytes) -> None:
        ...

    async def stop(self) -> None:
        ...
