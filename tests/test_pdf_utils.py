from unittest.mock import MagicMock, patch
from core.pdf_utils import get_page_rows


def _make_mock_page(words):
    """words: list of (x0, y0, x1, y1, text, block, line, word) tuples"""
    mock = MagicMock()
    mock.get_text.return_value = words
    return mock


def test_get_page_rows_returns_rows():
    words = [
        (10.0, 20.0, 50.0, 30.0, "거래일자", 0, 0, 0),
        (60.0, 20.0, 120.0, 30.0, "거래명", 0, 0, 1),
        (10.0, 40.0, 50.0, 50.0, "2024/01/01", 0, 1, 0),
    ]
    mock_page = _make_mock_page(words)
    with patch("core.pdf_utils.is_scanned_page", return_value=False):
        rows = get_page_rows(mock_page)
    assert len(rows) == 2
    assert isinstance(rows[0], list)
    assert isinstance(rows[0][0], tuple)
    assert len(rows[0][0]) == 2  # (x0, text)


def test_get_page_rows_sorted_by_x():
    words = [
        (60.0, 20.0, 120.0, 30.0, "거래명", 0, 0, 1),
        (10.0, 20.0, 50.0, 30.0, "거래일자", 0, 0, 0),
    ]
    mock_page = _make_mock_page(words)
    with patch("core.pdf_utils.is_scanned_page", return_value=False):
        rows = get_page_rows(mock_page)
    for row in rows:
        xs = [cell[0] for cell in row]
        assert xs == sorted(xs)
