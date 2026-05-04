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


def test_detects_dynamic_parser(tmp_path, monkeypatch):
    import fitz
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, save
    from core.detector import detect_parser

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트다이나믹",
        detection_keywords=["UNIQUE_KEYWORD_XYZ"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "UNIQUE_KEYWORD_XYZ")
    pages = list(doc)

    result = detect_parser(pages)
    assert result is not None
    assert result.BROKER_NAME == "테스트다이나믹"
