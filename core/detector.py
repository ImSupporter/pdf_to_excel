import fitz
from parsers.base import BaseParser


def detect_parser(pages: list[fitz.Page]) -> type[BaseParser] | None:
    """
    Detect the broker parser by keyword matching on the first page's text.
    Returns None if no parser matches.
    """
    from core.parser_registry import get_all_parsers
    sample_text = " ".join(pages[0].get_text().split())

    for parser_class in get_all_parsers():
        if any(kw in sample_text for kw in parser_class.DETECTION_KEYWORDS):
            return parser_class

    return None
