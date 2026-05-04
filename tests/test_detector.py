import fitz
from core.loader import load_pdf
from core.detector import detect_parser
from parsers.samsung import SamsungParser
from parsers.mirae_asset import MiraeAssetParser

def test_detects_samsung(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser_class = detect_parser(pages)
    assert parser_class is SamsungParser

def test_detects_mirae(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser_class = detect_parser(pages)
    assert parser_class is MiraeAssetParser

def test_returns_none_for_unknown():
    doc = fitz.open()
    doc.new_page()
    pages = list(doc)
    result = detect_parser(pages)
    assert result is None
