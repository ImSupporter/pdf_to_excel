import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from core.models import Transaction, STANDARD_FIELDS
from core.normalizer import transactions_to_rows

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9E1F2")

def _write_sheet(ws, headers: list[str], rows: list[dict]):
    for col, header in enumerate(headers, 1):
        cell = ws.cell(1, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for row_idx, row in enumerate(rows, 2):
        for col, header in enumerate(headers, 1):
            ws.cell(row_idx, col, row.get(header, ""))

def export_to_excel(
    transactions: list[Transaction],
    broker_raw: dict[str, list[dict]],
    selected_fields: list[str],
    output_path: str,
) -> None:
    """
    transactions: all normalized transactions
    broker_raw: {"broker_name": [original_row_dict, ...]}
    selected_fields: STANDARD_FIELDS keys for unified sheet
    output_path: output .xlsx path
    """
    wb = openpyxl.Workbook()

    # Sheet 1: 통합
    ws_unified = wb.active
    ws_unified.title = "통합"
    unified_rows = transactions_to_rows(transactions, selected_fields)
    headers = [STANDARD_FIELDS[f] for f in selected_fields]
    _write_sheet(ws_unified, headers, unified_rows)

    # Sheet 2+: per-broker original
    for broker_name, raw_rows in broker_raw.items():
        ws = wb.create_sheet(title=broker_name)
        if raw_rows:
            broker_headers = list(raw_rows[0].keys())
            _write_sheet(ws, broker_headers, raw_rows)

    wb.save(output_path)
