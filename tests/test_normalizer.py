from core.models import Transaction, STANDARD_FIELDS
from core.normalizer import transactions_to_rows

def _make_tx(**kwargs):
    defaults = dict(
        date="2025/11/06", type="매수",
        amount=113775.0, balance=500000.0,
        broker="삼성증권", raw={}
    )
    defaults.update(kwargs)
    return Transaction(**defaults)

def test_normalizer_returns_list_of_dicts():
    txs = [_make_tx(), _make_tx(broker="미래에셋증권")]
    rows = transactions_to_rows(txs, selected_fields=list(STANDARD_FIELDS.keys()))
    assert len(rows) == 2
    assert isinstance(rows[0], dict)

def test_normalizer_uses_korean_column_names():
    txs = [_make_tx()]
    rows = transactions_to_rows(txs, selected_fields=["date", "type", "amount"])
    assert "거래일자" in rows[0]
    assert "거래종류" in rows[0]
    assert "거래금액" in rows[0]

def test_normalizer_respects_field_selection():
    txs = [_make_tx()]
    rows = transactions_to_rows(txs, selected_fields=["date", "amount"])
    assert len(rows[0]) == 2
    assert "거래일자" in rows[0]
    assert "거래금액" in rows[0]
