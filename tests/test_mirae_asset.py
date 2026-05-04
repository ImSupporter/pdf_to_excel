from core.loader import load_pdf
from parsers.mirae_asset import MiraeAssetParser

def test_mirae_detects_broker(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    full_text = " ".join(p.get_text() for p in pages)
    assert any(kw in full_text for kw in MiraeAssetParser.DETECTION_KEYWORDS)

def test_mirae_returns_transactions(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    transactions, raw_rows = parser.parse(pages)
    assert len(transactions) > 0
    assert len(raw_rows) == len(transactions)

def test_mirae_has_transfer_in(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    transactions, _ = parser.parse(pages)
    dates = [t.date for t in transactions]
    assert "2025/10/22" in dates

def test_mirae_raw_rows_have_original_columns(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    _, raw_rows = parser.parse(pages)
    assert "거래일자" in raw_rows[0]
    assert "거래종류" in raw_rows[0]
    assert "거래금액" in raw_rows[0]
