import pytest
from parsers.citi import CitiParser, _carry_forward


# ─── helpers ────────────────────────────────────────────────────────────────

def _row(
    처리일자="", 기산일자="", 처리시간="", 거래구분="",
    자원="", 지금="", 입금="", 잔액="", 처리점="", 텔러="", 적요="",
) -> dict:
    return {
        "처리일자": 처리일자, "기산일자": 기산일자, "처리시간": 처리시간,
        "거래구분": 거래구분, "자원": 자원, "지금": 지금, "입금": 입금,
        "잔액": 잔액, "처리점": 처리점, "텔러": 텔러, "입금의뢰인/적요": 적요,
    }


# ─── carry-forward unit tests ────────────────────────────────────────────────

def test_carry_forward_fills_missing_date_fields():
    rows = [
        _row(처리일자="2025.01.15", 기산일자="2025.01.15", 처리시간="10:30", 거래구분="이체", 잔액="500,000"),
        _row(잔액="450,000"),  # 앞 4개 전부 없음 → carry-forward
    ]
    result = _carry_forward(rows)
    assert result[1]["처리일자"] == "2025.01.15"
    assert result[1]["기산일자"] == "2025.01.15"
    assert result[1]["처리시간"] == "10:30"
    assert result[1]["거래구분"] == "이체"
    assert result[1]["잔액"] == "450,000"   # carry-forward 대상이 아님


def test_carry_forward_first_row_with_no_previous_uses_empty():
    rows = [_row(잔액="100,000")]
    result = _carry_forward(rows)
    assert result[0]["처리일자"] == ""
    assert result[0]["거래구분"] == ""
    assert result[0]["잔액"] == "100,000"


def test_carry_forward_does_not_modify_rows_with_dates():
    rows = [
        _row(처리일자="2025.01.15", 기산일자="2025.01.15", 처리시간="10:30", 거래구분="이체"),
        _row(처리일자="2025.01.16", 기산일자="2025.01.16", 처리시간="11:00", 거래구분="입금"),
    ]
    result = _carry_forward(rows)
    assert result[1]["처리일자"] == "2025.01.16"
    assert result[1]["거래구분"] == "입금"


def test_carry_forward_chains_multiple_consecutive_empty_rows():
    rows = [
        _row(처리일자="2025.02.01", 기산일자="2025.02.01", 처리시간="09:00", 거래구분="출금"),
        _row(잔액="200,000"),
        _row(잔액="100,000"),
    ]
    result = _carry_forward(rows)
    assert result[1]["처리일자"] == "2025.02.01"
    assert result[2]["처리일자"] == "2025.02.01"
    assert result[2]["거래구분"] == "출금"


def test_carry_forward_resets_when_new_date_appears():
    rows = [
        _row(처리일자="2025.02.01", 기산일자="2025.02.01", 처리시간="09:00", 거래구분="출금"),
        _row(잔액="200,000"),
        _row(처리일자="2025.02.02", 기산일자="2025.02.02", 처리시간="10:00", 거래구분="입금"),
        _row(잔액="300,000"),
    ]
    result = _carry_forward(rows)
    assert result[3]["처리일자"] == "2025.02.02"
    assert result[3]["거래구분"] == "입금"


# ─── class-level unit tests ──────────────────────────────────────────────────

def test_broker_name():
    assert CitiParser.BROKER_NAME == "씨티은행"


def test_detection_keywords_has_citi():
    assert any("씨티" in kw or "citi" in kw.lower() for kw in CitiParser.DETECTION_KEYWORDS)


def test_detection_keywords_has_at_least_two():
    assert len(CitiParser.DETECTION_KEYWORDS) >= 2


# ─── integration tests (skipped if PDF not found) ────────────────────────────

def test_citi_parser_detects_broker(citi_pdf, pdf_password):
    from core.loader import load_pdf
    pages = load_pdf(str(citi_pdf), pdf_password)
    full_text = " ".join(p.get_text() for p in pages)
    assert any(kw in full_text for kw in CitiParser.DETECTION_KEYWORDS)


def test_citi_parser_returns_transactions(citi_pdf, pdf_password):
    from core.loader import load_pdf
    pages = load_pdf(str(citi_pdf), pdf_password)
    parser = CitiParser()
    transactions, raw_rows = parser.parse(pages)
    assert len(transactions) > 0
    assert len(raw_rows) == len(transactions)


def test_citi_raw_rows_have_original_columns(citi_pdf, pdf_password):
    from core.loader import load_pdf
    pages = load_pdf(str(citi_pdf), pdf_password)
    parser = CitiParser()
    _, raw_rows = parser.parse(pages)
    for key in ("처리일자", "거래구분", "잔액"):
        assert key in raw_rows[0], f"raw_rows missing key: {key}"


def test_citi_all_transactions_have_date_after_carry_forward(citi_pdf, pdf_password):
    from core.loader import load_pdf
    pages = load_pdf(str(citi_pdf), pdf_password)
    parser = CitiParser()
    transactions, _ = parser.parse(pages)
    # 첫 행이 날짜 없이 시작할 수 있으므로 두 번째 이후만 검사
    for tx in transactions[1:]:
        assert tx.date != "", f"carry-forward failed: date is empty for a non-first transaction"
