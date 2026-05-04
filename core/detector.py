import fitz
from parsers import PARSERS
from parsers.base import BaseParser

def detect_parser(pages: list[fitz.Page]) -> type[BaseParser] | None:
    """
    Detect the broker parser by keyword matching on the first page's text.
    Returns None if no parser matches.
    """
    sample_text = " ".join(pages[0].get_text().split())

    for parser_class in PARSERS:
        if any(kw in sample_text for kw in parser_class.DETECTION_KEYWORDS):
            return parser_class

    return None
