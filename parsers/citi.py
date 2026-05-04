"""
Citibank Korea (씨티은행) PDF parser.

Each transaction is a single row. When 처리일자/기산일자/처리시간/거래구분 are
all absent (blank), those fields are carried forward from the previous row.

Column layout (calibrated from actual PDF x-coordinates):
  처리일자       x < 126
  기산일자      126 <= x < 170
  처리시간      170 <= x < 215
  거래구분      215 <= x < 270
  자원          270 <= x < 355
  지급          355 <= x < 430
  입금          430 <= x < 520
  잔액          520 <= x < 550
  처리점        550 <= x < 600
  텔러          600 <= x < 630
  입금의뢰인/적요  x >= 630
"""

import re
import fitz

from core.models import Transaction
from core.pdf_utils import get_page_rows
from parsers.base import BaseParser

DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")

CITI_COLUMNS = [
    "처리일자", "기산일자", "처리시간", "거래구분",
    "자원", "지급", "입금", "잔액", "처리점", "텔러", "입금의뢰인/적요",
]

CARRY_FORWARD_KEYS = ["처리일자", "기산일자", "처리시간", "거래구분"]

# x-coordinate upper bounds for each column (last column has no upper bound)
# Calibrated from actual PDF: 처리일자≈104, 기산일자≈148, 처리시간≈193,
# 거래구분≈230, 자원≈310, 지급≈376-402, 입금≈451-479, 잔액≈528-544,
# 처리점≈555-582, 텔러≈608, 적요≈639
_X_BOUNDS = [126, 170, 215, 270, 355, 430, 520, 550, 600, 630]

SKIP_KEYWORDS = [
    "처리일자", "기산일자", "처리시간", "거래구분", "합계", "페이지",
    "출력일자", "계좌번호", "씨티은행", "CITIBANK",
]


def _map_row(row: list[tuple]) -> dict:
    """Map a PDF row (list of (x, text) tuples) to a Citi column dict."""
    raw = {col: "" for col in CITI_COLUMNS}
    for x, text in row:
        col = _col_for_x(x)
        if col:
            if raw[col]:
                raw[col] += " " + text
            else:
                raw[col] = text
    return raw


def _col_for_x(x: float) -> str | None:
    for i, bound in enumerate(_X_BOUNDS):
        if x < bound:
            return CITI_COLUMNS[i]
    return CITI_COLUMNS[-1]  # 입금의뢰인/적요


def _carry_forward(raw_rows: list[dict]) -> list[dict]:
    """Fill missing carry-forward fields from the previous row."""
    prev: dict = {k: "" for k in CARRY_FORWARD_KEYS}
    result = []
    for row in raw_rows:
        all_empty = all(not row.get(k) for k in CARRY_FORWARD_KEYS)
        if all_empty:
            for k in CARRY_FORWARD_KEYS:
                row[k] = prev[k]
        else:
            for k in CARRY_FORWARD_KEYS:
                prev[k] = row.get(k, "")
        result.append(row)
    return result


def _is_skip_row(texts: list[str]) -> bool:
    if not texts:
        return True
    joined = " ".join(texts)
    return any(kw in joined for kw in SKIP_KEYWORDS)


def _parse_num(s: str) -> float:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _to_transaction(raw: dict, broker: str) -> Transaction:
    return Transaction(
        date=raw.get("처리일자", ""),
        type=raw.get("거래구분", ""),
        ticker="",
        name=raw.get("입금의뢰인/적요", ""),
        quantity=0.0,
        price=0.0,
        amount=_parse_num(raw.get("입금", "") or raw.get("지금", "")),
        fee=0.0,
        tax=0.0,
        balance=_parse_num(raw.get("잔액", "")),
        broker=broker,
        raw=raw,
    )


class CitiParser(BaseParser):
    BROKER_NAME = "씨티은행"
    DETECTION_KEYWORDS = ["씨티은행 신세계", "씨티은행신세거"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        all_rows: list[list[tuple]] = []
        for page in pages:
            all_rows.extend(get_page_rows(page, y_tolerance=4.0))

        raw_rows: list[dict] = []
        for row in all_rows:
            texts = [t for _, t in row]
            if _is_skip_row(texts):
                continue
            # Skip supplementary annotation rows (발생이자, 원전잔수 etc.)
            # that only contain text in 자원 column or later (no date columns)
            if not any(x < 270 for x, _ in row):
                continue
            raw = _map_row(row)
            # Only keep rows that have at least one meaningful value
            if any(raw.values()):
                raw_rows.append(raw)

        raw_rows = _carry_forward(raw_rows)

        transactions = [_to_transaction(r, self.BROKER_NAME) for r in raw_rows]
        return transactions, raw_rows
