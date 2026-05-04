from core.loader import load_pdf
from parsers.samsung import SamsungParser


def test_samsung_parser_detects_broker(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    full_text = " ".join(p.get_text() for p in pages)
    assert any(kw in full_text for kw in SamsungParser.DETECTION_KEYWORDS)


def test_samsung_parser_returns_transactions(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    transactions, raw_rows = parser.parse(pages)
    assert len(transactions) > 0
    assert len(raw_rows) == len(transactions)


def test_samsung_first_transaction(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    transactions, _ = parser.parse(pages)
    first = transactions[0]
    assert first.date == "2025/11/06"
    assert first.type == "매도"
    assert first.broker == "삼성증권"


def test_samsung_raw_rows_have_original_columns(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    _, raw_rows = parser.parse(pages)
    assert "거래일자" in raw_rows[0]
    assert "거래명" in raw_rows[0]
