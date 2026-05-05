def test_standard_fields_are_coordinate_template_core_fields_only():
    from core.models import STANDARD_FIELDS

    assert STANDARD_FIELDS == {
        "date": "거래일자",
        "type": "거래종류",
        "amount": "거래금액",
        "balance": "잔액",
    }


def test_transaction_has_four_standard_values_and_raw_custom_fields():
    from core.models import Transaction

    tx = Transaction(
        date="2026/05/05",
        type="매수",
        amount=12345.0,
        balance=99999.0,
        broker="테스트증권",
        raw={"사용자종목명": "삼성전자", "사용자수량": "10"},
    )

    assert tx.date == "2026/05/05"
    assert tx.type == "매수"
    assert tx.amount == 12345.0
    assert tx.balance == 99999.0
    assert tx.broker == "테스트증권"
    assert tx.raw["사용자종목명"] == "삼성전자"
    assert not hasattr(tx, "ticker")
    assert not hasattr(tx, "quantity")
