from unittest.mock import MagicMock, patch


def test_detect_parser_falls_back_to_ocr_words_when_page_text_is_empty(monkeypatch):
    from core import detector, parser_registry

    class TestParser:
        BROKER_NAME = "테스트증권"
        DETECTION_KEYWORDS = ["거래내역"]

    page = MagicMock()
    page.get_text.return_value = ""
    monkeypatch.setattr(parser_registry, "get_all_parsers", lambda: [TestParser])

    with patch(
        "core.ocr.ocr_page_to_words",
        return_value=[(10.0, 20.0, 60.0, 30.0, "거래내역")],
    ):
        detected = detector.detect_parser([page])

    assert detected is TestParser


def test_detect_parser_ignores_greater_than_and_equals_chars(monkeypatch):
    from core import detector, parser_registry

    class TestParser:
        BROKER_NAME = "test"
        DETECTION_KEYWORDS = ["ABC"]

    page = MagicMock()
    page.get_text.return_value = "A>B=C"
    monkeypatch.setattr(parser_registry, "get_all_parsers", lambda: [TestParser])

    detected = detector.detect_parser([page])

    assert detected is TestParser
