import fitz
from core.ocr import is_scanned_page, ocr_page_to_rows
from core.text_cleaning import remove_ignored_chars

def get_page_rows(page: fitz.Page, y_tolerance: float = 4.0) -> list[list[tuple]]:
    """
    Extract words and group into rows by y-coordinate proximity.
    Scanned (image-only) pages automatically fall back to OCR.
    Returns: [[(x0, text), ...], ...] — rows sorted by y, cells sorted by x within each row
    """
    if is_scanned_page(page):
        return ocr_page_to_rows(page)

    words = page.get_text("words")
    # words format: (x0, y0, x1, y1, "text", block_no, line_no, word_no)
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: w[1])

    rows: list[list[tuple]] = []
    current_row: list[tuple] = []
    current_y: float = words_sorted[0][1]

    for w in words_sorted:
        if abs(w[1] - current_y) <= y_tolerance:
            text = remove_ignored_chars(w[4])
            if text:
                current_row.append((w[0], text))
        else:
            if current_row:
                rows.append(sorted(current_row, key=lambda c: c[0]))
            text = remove_ignored_chars(w[4])
            current_row = [(w[0], text)] if text else []
            current_y = w[1]

    if current_row:
        rows.append(sorted(current_row, key=lambda c: c[0]))

    return rows


def get_page_rows_with_y(page: fitz.Page, y_tolerance: float = 4.0) -> list[tuple[float, list[tuple[float, str]]]]:
    """Like get_page_rows but returns (row_y, [(x, text), ...]) for each row."""
    if is_scanned_page(page):
        rows = ocr_page_to_rows(page)
        return [(float(i) * 15.0, row) for i, row in enumerate(rows)]

    words = page.get_text("words")
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: w[1])
    result: list[tuple[float, list[tuple[float, str]]]] = []
    current_row: list[tuple[float, str]] = []
    current_y: float = words_sorted[0][1]

    for w in words_sorted:
        if abs(w[1] - current_y) <= y_tolerance:
            text = remove_ignored_chars(w[4])
            if text:
                current_row.append((w[0], text))
        else:
            if current_row:
                result.append((current_y, sorted(current_row, key=lambda c: c[0])))
            text = remove_ignored_chars(w[4])
            current_row = [(w[0], text)] if text else []
            current_y = w[1]

    if current_row:
        result.append((current_y, sorted(current_row, key=lambda c: c[0])))

    return result


def merge_row_cells(row: list[tuple], x_gap: float = 8.0) -> list[str]:
    """
    Merge adjacent cells in a row that are within x_gap of each other.
    Returns: list of merged text values
    """
    if not row:
        return []

    merged: list[str] = []
    current_text = row[0][1]
    current_x1 = row[0][0] + len(row[0][1]) * 4  # approximate x1

    for i in range(1, len(row)):
        x0, text = row[i]
        if x0 - current_x1 <= x_gap:
            current_text += " " + text
        else:
            merged.append(current_text)
            current_text = text
        current_x1 = x0 + len(text) * 4

    merged.append(current_text)
    return merged
