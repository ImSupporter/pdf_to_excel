from core.models import Transaction, STANDARD_FIELDS

def test_transaction_creation():
    t = Transaction(
        date="2025/11/06",
        type="매도",
        ticker="",
        name="삼성신종종류형MMF",
        quantity=1019462,
        price=1020.7,
        amount=1040564,
        fee=0,
        tax=0,
        balance=1040579,
        broker="삼성증권",
        raw={},
    )
    assert t.date == "2025/11/06"
    assert t.broker == "삼성증권"

def test_standard_fields_contains_required():
    assert "date" in STANDARD_FIELDS
    assert "broker" in STANDARD_FIELDS
    assert len(STANDARD_FIELDS) == 11
