from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QwenVoice:
    voice_id: str
    display_name: str
    gender: str
    language: str
    preview_url: str = ""


QWEN_VOICES: list[QwenVoice] = [
    QwenVoice("Cherry", "Cherry 知性女声", "female", "zh/en"),
    QwenVoice("Serena", "Serena 温柔女声", "female", "zh/en"),
    QwenVoice("Chelsie", "Chelsie 元气女声", "female", "zh/en"),
    QwenVoice("Ethan", "Ethan 阳光男声", "male", "zh/en"),
    QwenVoice("Dylan", "Dylan 沉稳男声", "male", "zh/en"),
    QwenVoice("Jada", "Jada 知性女声", "female", "zh/en"),
    QwenVoice("Sunny", "Sunny 活力女声", "female", "zh/en"),
]

QWEN_VOICE_BY_ID: dict[str, QwenVoice] = {v.voice_id: v for v in QWEN_VOICES}
QWEN_DEFAULT_VOICE_ID = "Cherry"


QWEN_LANGUAGES_S2S: list[tuple[str, str]] = [
    ("auto", "自动识别"),
    ("zh", "中文"),
    ("en", "英语"),
    ("ja", "日语"),
    ("ko", "韩语"),
    ("fr", "法语"),
    ("de", "德语"),
    ("es", "西班牙语"),
    ("ru", "俄语"),
    ("it", "意大利语"),
    ("pt", "葡萄牙语"),
    ("ar", "阿拉伯语"),
    ("th", "泰语"),
    ("vi", "越南语"),
    ("id", "印尼语"),
]

QWEN_LANGUAGES_TARGET: list[tuple[str, str]] = [
    (code, name) for code, name in QWEN_LANGUAGES_S2S if code != "auto"
]
