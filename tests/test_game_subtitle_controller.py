import unittest

from app_core.game_subtitle_controller import GameSubtitleConfig, GameSubtitleController
from app_core.translator import TranslatorEvent


class GameSubtitleControllerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
