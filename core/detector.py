import fitz
from parsers.base import BaseParser
from core.text_cleaning import remove_ignored_chars


def detect_parser(pages: list[fitz.Page]) -> type[BaseParser] | None:
    """
    Detect the broker parser by keyword matching on the first page's text.
    Returns None if no parser matches.
    """
    from core.parser_registry import get_all_parsers
    sample_text = " ".join(remove_ignored_chars(pages[0].get_text()).split())
    if not sample_text:
        from core.ocr import ocr_page_to_words

        sample_text = " ".join(word[4] for word in ocr_page_to_words(pages[0]))

    for parser_class in get_all_parsers():
        keywords = [remove_ignored_chars(kw) for kw in parser_class.DETECTION_KEYWORDS]
        if any(kw and kw in sample_text for kw in keywords):
            return parser_class

    return None
