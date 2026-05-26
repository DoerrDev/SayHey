import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from app_core.qwen_engine import QwenTtsConfig
from app_core.typed_engine import (
    DoubaoTranslateConfig,
    doubao_translate_text,
    resolve_doubao_tts_speaker,
    _EVENT_SESSION_FINISHED,
)


class _FakeResponse:
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps({
            "code": 20000000,
            "message": "ok",
            "data": {"translation_list": [{"translation": "hello"}]},
        }).encode("utf-8")


class TypedEngineTests(unittest.TestCase):
    def test_doubao_machine_translation_request_uses_openspeech_api(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse()

        cfg = DoubaoTranslateConfig(api_key="api-key", resource_id="volc.speech.mt")
        with patch("app_core.typed_engine.request.urlopen", fake_urlopen):
            translated = doubao_translate_text(cfg, "ni hao", "zh", "en")

        self.assertEqual(translated, "hello")
        self.assertEqual(
            captured["url"],
            "https://openspeech.bytedance.com/api/v3/machine_translation/matx_translate",
        )
        self.assertEqual(captured["headers"]["X-api-key"], "api-key")
        self.assertEqual(captured["headers"]["X-api-resource-id"], "volc.speech.mt")
        self.assertEqual(captured["body"], {
            "text_list": ["ni hao"],
            "target_language": "en",
            "source_language": "zh",
        })

    def test_doubao_machine_translation_http_error_includes_response_body(self) -> None:
        def fake_urlopen(req, timeout):
            body = json.dumps({
                "code": 45000001,
                "message": "target_language is required",
            }).encode("utf-8")
            raise HTTPError(req.full_url, 500, "Internal Server Error", hdrs=None, fp=BytesIO(body))

        cfg = DoubaoTranslateConfig(api_key="api-key", resource_id="volc.speech.mt")
        with patch("app_core.typed_engine.request.urlopen", fake_urlopen):
            with self.assertRaisesRegex(RuntimeError, "target_language is required"):
                doubao_translate_text(cfg, "hello", "en", "zh")

    def test_tts_speaker_maps_s2s_jupiter_voice_to_tts_uranus_voice(self) -> None:
        self.assertEqual(
            resolve_doubao_tts_speaker("zh_female_xiaohe_jupiter_bigtts"),
            "zh_female_xiaohe_uranus_bigtts",
        )

    def test_tts_speaker_falls_back_for_saturn_s2s_voice(self) -> None:
        self.assertEqual(
            resolve_doubao_tts_speaker("saturn_zh_male_fengfashaonian_tob"),
            "zh_female_xiaohe_uranus_bigtts",
        )

    def test_tts_session_finished_event_is_known(self) -> None:
        self.assertEqual(_EVENT_SESSION_FINISHED, 152)

    def test_qwen_tts_defaults_to_qwen3_flash_model(self) -> None:
        cfg = QwenTtsConfig(api_key="key", voice="Katerina")

        self.assertEqual(cfg.model, "qwen3-tts-flash-realtime")


if __name__ == "__main__":
    unittest.main()
