import tempfile, os
import openpyxl
from core.models import Transaction, STANDARD_FIELDS
from core.exporter import export_to_excel

def _make_tx(broker="삼성증권", date="2025/11/06"):
    return Transaction(
        date=date, type="매수", ticker="", name="KODEX S&P500",
        quantity=5, price=22755.0, amount=113775, fee=1,
        tax=0, balance=500000, broker=broker,
        raw={"거래일자": date, "거래명": "매수", "종목명": "KODEX S&P500",
             "거래수량": "5", "거래금액": "113,775"}
    )

def test_export_creates_file():
    txs = [_make_tx("삼성증권"), _make_tx("미래에셋증권")]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(
            transactions=txs,
            broker_raw={"삼성증권": [txs[0].raw], "미래에셋증권": [txs[1].raw]},
            selected_fields=list(STANDARD_FIELDS.keys()),
            output_path=path,
        )
        assert os.path.exists(path)
        wb = openpyxl.load_workbook(path)
        assert "통합" in wb.sheetnames
        assert "삼성증권" in wb.sheetnames
        assert "미래에셋증권" in wb.sheetnames
    finally:
        os.unlink(path)

def test_export_unified_sheet_has_correct_columns():
    txs = [_make_tx()]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(
            transactions=txs,
            broker_raw={"삼성증권": [txs[0].raw]},
            selected_fields=["date", "type", "amount"],
            output_path=path,
        )
        wb = openpyxl.load_workbook(path)
        ws = wb["통합"]
        headers = [ws.cell(1, c).value for c in range(1, 4)]
        assert "거래일자" in headers
        assert "거래종류" in headers
        assert "거래금액" in headers
    finally:
        os.unlink(path)
