import openpyxl
from openpyxl.styles import PatternFill


def test_read_parser_template_extracts_yellow_fields_and_gray_keywords(tmp_path):
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet", "excel_row", "excel_col", "page_index", "row_index", "column_index", "x", "y", "text"])

    ws["A1"] = "거래일자"
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 1, 0, 3, 0, 12.5, 48.0, "거래일자"])

    ws["B1"] = "합계"
    ws["B1"].fill = PatternFill(fill_type="solid", fgColor="BFBFBF")
    meta.append(["PDF", 1, 2, 0, 3, 1, 58.0, 48.0, "합계"])

    wb.save(path)

    annotations = read_parser_template(path)

    assert len(annotations.field_cells) == 1
    assert annotations.field_cells[0].text == "거래일자"
    assert annotations.field_cells[0].row_index == 3
    assert annotations.field_cells[0].column_index == 0
    assert annotations.skip_keywords == ["합계"]


def test_read_parser_template_keeps_arbitrary_yellow_cell_names(tmp_path):
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet", "excel_row", "excel_col", "page_index", "row_index", "column_index", "x", "y", "text"])

    ws["A1"] = "내가 원하는 컬럼"
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 1, 0, 3, 0, 12.5, 48.0, "내가 원하는 컬럼"])

    wb.save(path)

    annotations = read_parser_template(path)

    assert len(annotations.field_cells) == 1
    assert annotations.field_cells[0].text == "내가 원하는 컬럼"


def test_infer_standard_field_accepts_common_labels():
    from core.parser_template import infer_standard_field

    assert infer_standard_field("종목명") == "name"
    assert infer_standard_field("거래금액") == "amount"
    assert infer_standard_field("ticker") == "ticker"
    assert infer_standard_field("알수없음") is None
