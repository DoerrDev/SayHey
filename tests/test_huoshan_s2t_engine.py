import unittest

from app_core.huoshan_s2t_engine import HuoshanS2TSubtitleEngine
from python_protogen.common.events_pb2 import Type
from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateResponse


def _response_bytes(event: int, text: str = "") -> bytes:
    response = TranslateResponse()
    response.event = event
    response.text = text
    return response.SerializeToString()


class HuoshanS2TSubtitleEngineTests(unittest.TestCase):
    def test_source_subtitle_response_emits_source_text(self) -> None:
        events = []
        engine = HuoshanS2TSubtitleEngine("ws://example.test", "key", "resource")
        engine.on_event = events.append

        engine._handle_response(_response_bytes(Type.SourceSubtitleResponse, "hello world"))

        self.assertEqual([(event.type, event.text) for event in events], [("source_text", "hello world")])

    def test_source_subtitle_end_emits_final_source_text(self) -> None:
        events = []
        engine = HuoshanS2TSubtitleEngine("ws://example.test", "key", "resource")
        engine.on_event = events.append

        engine._handle_response(_response_bytes(Type.SourceSubtitleEnd, "final source"))

        self.assertEqual(
            [(event.type, event.text) for event in events],
            [("source_text", "final source"), ("source_text_final", "final source")],
        )

    def test_repeated_source_text_can_start_next_sentence_after_end(self) -> None:
        events = []
        engine = HuoshanS2TSubtitleEngine("ws://example.test", "key", "resource")
        engine.on_event = events.append

        engine._handle_response(_response_bytes(Type.SourceSubtitleResponse, "hello"))
        engine._handle_response(_response_bytes(Type.SourceSubtitleEnd, "hello"))
        engine._handle_response(_response_bytes(Type.SourceSubtitleResponse, "hello"))

        self.assertEqual(
            [(event.type, event.text) for event in events],
            [
                ("source_text", "hello"),
                ("source_text_final", "hello"),
                ("source_text", "hello"),
            ],
        )

    def test_translation_end_emits_last_snapshot_as_final_text(self) -> None:
        events = []
        engine = HuoshanS2TSubtitleEngine("ws://example.test", "key", "resource")
        engine.on_event = events.append

        engine._handle_response(_response_bytes(Type.TranslationSubtitleResponse, "敌人在左边"))
        engine._handle_response(_response_bytes(Type.TranslationSubtitleEnd))

        self.assertEqual(
            [(event.type, event.text) for event in events if event.type != "status"],
            [
                ("translated_text", "敌人在左边"),
                ("translated_text_final", "敌人在左边"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
