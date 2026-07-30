import unittest

from app_core.game_subtitle_controller import (
    GameSubtitleConfig,
    GameSubtitleController,
    is_mostly_chinese,
)
from app_core.translator import TranslatorEvent


class GameSubtitleControllerTests(unittest.TestCase):
    def _filtered_controller(self, subtitles, statuses=None) -> GameSubtitleController:
        return GameSubtitleController(
            GameSubtitleConfig(
                ws_url="ws://example.test",
                api_key="key",
                resource_id="resource",
                source_language="en",
                filter_chinese=True,
            ),
            on_status=(statuses.append if statuses is not None else None),
            on_subtitle=lambda kind, text: subtitles.append((kind, text)),
        )

    def test_forwards_source_and_translation_subtitle_events(self) -> None:
        subtitles = []
        controller = GameSubtitleController(
            GameSubtitleConfig(
                ws_url="ws://example.test",
                api_key="key",
                resource_id="resource",
                source_language="en",
            ),
            on_subtitle=lambda kind, text: subtitles.append((kind, text)),
        )

        controller._handle_engine_event(TranslatorEvent(type="source_text", text="hello"))
        controller._handle_engine_event(TranslatorEvent(type="translated_text", text="translated"))

        self.assertEqual(subtitles, [("source", "hello"), ("translation", "translated")])

    def test_filter_hides_chinese_source_and_translation(self) -> None:
        subtitles = []
        statuses = []
        controller = self._filtered_controller(subtitles, statuses)

        controller._handle_engine_event(TranslatorEvent(type="source_text", text="正在部署护盾"))
        controller._handle_engine_event(TranslatorEvent(type="translated_text", text="正在部署护盾"))
        controller._handle_engine_event(TranslatorEvent(type="source_text_final", text="正在部署护盾"))
        controller._handle_engine_event(TranslatorEvent(type="translated_text_final", text="正在部署护盾"))

        self.assertEqual(subtitles, [])
        self.assertTrue(any("dropped Chinese subtitle" in status for status in statuses))

    def test_filter_shows_english_sentence_after_final_events(self) -> None:
        subtitles = []
        controller = self._filtered_controller(subtitles)

        controller._handle_engine_event(TranslatorEvent(type="translated_text_final", text="敌人在左边"))
        controller._handle_engine_event(TranslatorEvent(type="source_text_final", text="Enemy on the left"))

        self.assertEqual(subtitles, [("source", "Enemy on the left"), ("translation", "敌人在左边")])

    def test_chinese_ratio_threshold(self) -> None:
        self.assertTrue(is_mostly_chinese("Apex角色正在部署护盾"))
        self.assertFalse(is_mostly_chinese("Use R-301 now"))
        self.assertFalse(is_mostly_chinese("好"))


if __name__ == "__main__":
    unittest.main()
