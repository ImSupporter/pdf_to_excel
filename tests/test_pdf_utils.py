import fitz
from core.pdf_utils import get_page_rows

def test_get_page_rows_returns_rows(samsung_pdf, pdf_password):
    doc = fitz.open(str(samsung_pdf))
    doc.authenticate(pdf_password)
    page = doc[0]
    rows = get_page_rows(page)
    assert len(rows) > 0
    assert isinstance(rows[0], list)
    assert isinstance(rows[0][0], tuple)
    assert len(rows[0][0]) == 2  # (x0, text)

def test_get_page_rows_sorted_by_x(samsung_pdf, pdf_password):
    doc = fitz.open(str(samsung_pdf))
    doc.authenticate(pdf_password)
    page = doc[0]
    rows = get_page_rows(page)
    for row in rows:
        xs = [cell[0] for cell in row]
        assert xs == sorted(xs)
