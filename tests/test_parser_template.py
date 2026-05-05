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


def test_compute_x_zones_groups_nearby_x_coordinates():
    from core.parser_template import _compute_x_zones, TemplateCell

    cells = [
        TemplateCell(0, 0, 0, x=50.0, y=10, text="거래일자"),
        TemplateCell(0, 0, 1, x=200.0, y=10, text="종목명"),
        TemplateCell(0, 0, 2, x=350.0, y=10, text="수량"),
        TemplateCell(0, 1, 0, x=52.0, y=20, text="2024/01/01"),   # same zone as 50
        TemplateCell(0, 1, 1, x=200.0, y=20, text="삼성"),         # same zone as 200
        TemplateCell(0, 1, 2, x=222.0, y=20, text="전자"),         # extra word: new zone
        TemplateCell(0, 1, 3, x=350.0, y=20, text="100"),          # same zone as 350
    ]
    zones = _compute_x_zones(cells)

    assert len(zones) == 4  # ~50, ~200, ~222, ~350


def test_find_zone_index_returns_nearest_zone_index():
    from core.parser_template import _find_zone_index

    zones = [50.0, 200.0, 350.0]
    assert _find_zone_index(49.0, zones) == 0
    assert _find_zone_index(201.0, zones) == 1
    assert _find_zone_index(340.0, zones) == 2


def test_date_format_to_re_slash():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy/mm/dd") == r"\d{4}/\d{2}/\d{2}"


def test_date_format_to_re_dash():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy-mm-dd") == r"\d{4}-\d{2}-\d{2}"


def test_date_format_to_re_dot():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy.mm.dd") == r"\d{4}\.\d{2}\.\d{2}"


def test_date_format_to_re_two_digit_year():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yy/mm/dd") == r"\d{2}/\d{2}/\d{2}"


def test_detect_date_format_slash():
    from core.parser_template import _detect_date_format
    result = _detect_date_format(["계좌번호", "1234", "2025/11/06", "매도"])
    assert result is not None
    assert result[0] == r"\d{4}/\d{2}/\d{2}"
    assert result[1] == "yyyy/mm/dd"


def test_detect_date_format_returns_none():
    from core.parser_template import _detect_date_format
    assert _detect_date_format(["계좌번호", "ABC", "테스트"]) is None
