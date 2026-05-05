from dataclasses import dataclass
from pathlib import Path

import fitz
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from core.models import STANDARD_FIELDS

YELLOW_FILL = "FFFF00"
GRAY_FILL = "BFBFBF"
META_SHEET = "_metadata"
FIELDS_SHEET = "필드목록"

_AUTO_DATE_PATTERNS: list[tuple[str, str]] = [
    (r"\d{4}/\d{2}/\d{2}", "yyyy/mm/dd"),
    (r"\d{4}-\d{2}-\d{2}", "yyyy-mm-dd"),
    (r"\d{4}\.\d{2}\.\d{2}", "yyyy.mm.dd"),
    (r"\d{2}/\d{2}/\d{4}", "dd/mm/yyyy"),
]


def date_format_to_re(fmt: str) -> str:
    r"""Convert user-friendly date format string to regex. e.g. 'yyyy/mm/dd' → r'\d{4}/\d{2}/\d{2}'"""
    result = fmt
    result = result.replace("yyyy", r"\d{4}")
    result = result.replace("yy", r"\d{2}")
    result = result.replace("mm", r"\d{2}")
    result = result.replace("dd", r"\d{2}")
    result = result.replace(".", r"\.")
    return result


def _detect_date_format(texts: list[str]) -> tuple[str, str] | None:
    """Scan texts for a known date pattern. Returns (regex, format_str) or None."""
    import re
    for pattern, fmt in _AUTO_DATE_PATTERNS:
        compiled = re.compile(pattern)
        if any(compiled.match(t) for t in texts):
            return pattern, fmt
    return None


@dataclass
class TemplateCell:
    page_index: int
    row_index: int
    column_index: int
    x: float
    y: float
    text: str


@dataclass
class TemplateAnnotations:
    field_cells: list[TemplateCell]
    skip_keywords: list[str]


def _cell_fill_rgb(cell) -> str:
    fill = cell.fill
    if fill.fill_type != "solid":
        return ""
    color = fill.fgColor
    if color.type == "rgb" and color.rgb:
        return color.rgb[-6:].upper()
    if color.type == "indexed":
        indexed = {
            5: "FFFF00",
            22: "C0C0C0",
            23: "808080",
        }
        return indexed.get(color.indexed, "")
    return ""


def is_yellow(cell) -> bool:
    rgb = _cell_fill_rgb(cell)
    return rgb in {"FFFF00", "FFF2CC", "FFD966"}


def is_gray(cell) -> bool:
    rgb = _cell_fill_rgb(cell)
    return rgb in {"BFBFBF", "C0C0C0", "D9D9D9", "808080", "A6A6A6"}


def _normalize_label(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def infer_standard_field(text: str) -> str | None:
    aliases = {
        "date": ["date", "거래일자", "일자", "거래일", "매매일자"],
        "type": ["type", "거래종류", "구분", "매매구분", "거래구분"],
        "ticker": ["ticker", "종목코드", "코드", "symbol"],
        "name": ["name", "종목명", "종목", "상품명"],
        "quantity": ["quantity", "수량", "거래수량", "잔고수량"],
        "price": ["price", "단가", "가격", "체결단가"],
        "amount": ["amount", "거래금액", "금액", "매매금액"],
        "fee": ["fee", "수수료", "수수료금액"],
        "tax": ["tax", "세금", "거래세", "제세금"],
        "balance": ["balance", "잔액", "잔고", "평가금액"],
        "broker": ["broker", "증권사"],
    }
    normalized = _normalize_label(text)
    for key, values in aliases.items():
        labels = values + [STANDARD_FIELDS.get(key, "")]
        if normalized in {_normalize_label(v) for v in labels if v}:
            return key
    return None


def _compute_x_zones(cells: list[TemplateCell], x_gap: float = 20.0) -> list[float]:
    """Cluster x-coordinates across all cells into distinct column zones."""
    xs = sorted({c.x for c in cells})
    if not xs:
        return [0.0]
    zones = [xs[0]]
    for x in xs[1:]:
        if x - zones[-1] > x_gap:
            zones.append(x)
    return zones


def _find_zone_index(x: float, zones: list[float]) -> int:
    """Return the index of the zone nearest to x."""
    return min(range(len(zones)), key=lambda i: abs(zones[i] - x))


def _extract_page_cells(page: fitz.Page, page_index: int, y_tolerance: float = 4.0) -> list[TemplateCell]:
    words = page.get_text("words")
    if not words:
        from core.pdf_utils import get_page_rows

        cells: list[TemplateCell] = []
        for row_index, row in enumerate(get_page_rows(page, y_tolerance=y_tolerance)):
            for column_index, (x, text) in enumerate(row):
                cells.append(TemplateCell(
                    page_index=page_index,
                    row_index=row_index,
                    column_index=column_index,
                    x=float(x),
                    y=float(row_index),
                    text=text,
                ))
        return cells

    rows: list[list[tuple[float, float, str]]] = []
    current: list[tuple[float, float, str]] = []
    current_y = sorted(words, key=lambda w: w[1])[0][1]

    for word in sorted(words, key=lambda w: w[1]):
        x0, y0, text = word[0], word[1], word[4]
        if abs(y0 - current_y) <= y_tolerance:
            current.append((x0, y0, text))
        else:
            rows.append(sorted(current, key=lambda item: item[0]))
            current = [(x0, y0, text)]
            current_y = y0

    if current:
        rows.append(sorted(current, key=lambda item: item[0]))

    cells: list[TemplateCell] = []
    for row_index, row in enumerate(rows):
        for column_index, (x, y, text) in enumerate(row):
            cells.append(TemplateCell(
                page_index=page_index,
                row_index=row_index,
                column_index=column_index,
                x=x,
                y=y,
                text=text,
            ))
    return cells


def export_parser_template(pages: list[fitz.Page], output_path: str | Path, max_pages: int = 5) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    fields = wb.create_sheet(FIELDS_SHEET)

    ws["A1"] = "PDF 원본 셀"
    ws["A1"].font = Font(bold=True)
    ws["A2"] = "필드로 지정할 셀은 노란색, 무시할 키워드는 회색으로 표시한 뒤 업로드하세요."
    ws["A2"].alignment = Alignment(wrap_text=True)

    meta.append(["sheet", "excel_row", "excel_col", "page_index", "row_index", "column_index", "x", "y", "text"])

    excel_row = 4
    max_col = 1
    for page_index, page in enumerate(pages[:max_pages]):
        ws.cell(excel_row, 1, f"Page {page_index + 1}")
        ws.cell(excel_row, 1).font = Font(bold=True)
        excel_row += 1

        page_cells = _extract_page_cells(page, page_index)
        zones = _compute_x_zones(page_cells)
        current_row = None
        for cell_info in page_cells:
            if current_row is None:
                current_row = cell_info.row_index
            if cell_info.row_index != current_row:
                excel_row += 1
                current_row = cell_info.row_index

            excel_col = _find_zone_index(cell_info.x, zones) + 1
            max_col = max(max_col, excel_col)
            ws.cell(excel_row, excel_col, cell_info.text)
            meta.append([
                ws.title,
                excel_row,
                excel_col,
                cell_info.page_index,
                cell_info.row_index,
                cell_info.column_index,
                cell_info.x,
                cell_info.y,
                cell_info.text,
            ])
        excel_row += 2

    for col in range(1, max_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14

    fields.append(["필드 키", "필드명"])
    fields["A1"].font = Font(bold=True)
    fields["B1"].font = Font(bold=True)
    for key, label in STANDARD_FIELDS.items():
        fields.append([key, label])
    fields.column_dimensions["A"].width = 16
    fields.column_dimensions["B"].width = 16

    meta.sheet_state = "hidden"
    wb.save(output_path)


def read_parser_template(path: str | Path) -> TemplateAnnotations:
    wb = openpyxl.load_workbook(path)
    if META_SHEET not in wb.sheetnames:
        raise ValueError("포맷 파일 metadata 시트를 찾을 수 없습니다.")

    meta_ws = wb[META_SHEET]
    metadata: dict[tuple[str, int, int], TemplateCell] = {}
    for row in meta_ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        sheet, excel_row, excel_col, page_index, row_index, column_index, x, y, text = row
        metadata[(str(sheet), int(excel_row), int(excel_col))] = TemplateCell(
            page_index=int(page_index),
            row_index=int(row_index),
            column_index=int(column_index),
            x=float(x),
            y=float(y),
            text=str(text or ""),
        )

    field_cells: list[TemplateCell] = []
    skip_keywords: list[str] = []

    for sheet_name in wb.sheetnames:
        if sheet_name in {META_SHEET, FIELDS_SHEET}:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                info = metadata.get((sheet_name, cell.row, cell.column))
                if info is None:
                    continue
                value = str(cell.value or info.text or "").strip()
                if not value:
                    continue
                if is_yellow(cell):
                    field_cells.append(TemplateCell(
                        page_index=info.page_index,
                        row_index=info.row_index,
                        column_index=info.column_index,
                        x=info.x,
                        y=info.y,
                        text=value,
                    ))
                elif is_gray(cell):
                    skip_keywords.append(value)

    unique_skips = list(dict.fromkeys(skip_keywords))
    return TemplateAnnotations(field_cells=field_cells, skip_keywords=unique_skips)
