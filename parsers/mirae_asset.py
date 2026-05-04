"""
Mirae Asset Securities (미래에셋증권) PDF parser.

The Mirae Asset PDF uses a TRANSPOSED (rotated 90°) table layout:
  - The page contains narrow vertical text blocks (~8px wide), each holding one transaction column
  - Text within each block is rotated 90° and reads bottom-to-top
  - Each transaction occupies a PRIMARY block plus one or two SECONDARY/TERTIARY blocks

BLOCK STRUCTURE PER TRANSACTION:
  Primary block (x = col_x, x-offset from slot = 0–8):
    y=773-816 : 거래일자 (YYYY/MM/DD)
    y=660-770 : 거래종류 (e.g. 주식매수입고, 이체입금, 분배금입금, ...)
    y=560-600 : 종목번호 (ticker, e.g. A379810)
    y=403-422 : 수수료 (fee, combined with 제세금합)
    y=340-385 : 거래금액 (transaction amount)
    y=276-322 : 예수금잔액 (cash balance — present only for cash-based transactions)

  Secondary block (x ≈ col_x + 10–25, x-offset = 9–35):
    y=768-778 : 거래번호 (sub-sequence number within the same date)
    y=718-730 : 거래수량 (quantity = 0 for non-stock transactions)
    y=658-682 : 거래수량 (actual share quantity for stock purchases)
    y=596-632 : 단가 (unit price)
    y=468-600 : 종목명 (stock name — spans a wide y range)
    y=340-385 : 입출금액 (net amount)
    y=276-296 : 유가잔고 (share balance — NOT cash balance)

COLUMN SLOT DETECTION:
  Primary blocks are identified by the presence of a YYYY/MM/DD date at y=768–820.
  Typically 5 transactions per page with primary x ≈ [198, 257, 317, 376, 436].
  Slot boundaries are computed as midpoints between adjacent primary x-values.

  For each slot, items at x within [primary_x - 5, primary_x + 8] are PRIMARY items.
  Items at x within [primary_x + 9, primary_x + 45] are SECONDARY/TERTIARY items.
"""

import re

import fitz

from core.models import Transaction
from parsers.base import BaseParser

# Matches YYYY/MM/DD
DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# Y-range for PRIMARY block fields: (y_top_min, y_top_max)
_PRI_FIELD_Y = {
    "거래일자":   (768, 820),
    "거래종류":   (655, 770),
    "종목번호":   (558, 602),
    "수수료":     (403, 422),
    "거래금액":   (340, 386),
    "예수금잔액": (276, 325),
}

# Y-range for SECONDARY/TERTIARY block fields: (y_top_min, y_top_max)
_SEC_FIELD_Y = {
    "거래번호":   (768, 780),
    "거래수량":   (656, 685),   # both 0-value (y~724) and actual (y~666) fall here
    "단가":       (596, 633),
    "종목명":     (465, 560),   # main name text (y=471–548); exclude ticker range (560-600)
    "종목명_하":  (535, 600),   # tertiary block name continuation (overlaps with 종목명 slightly)
    "입출금액":   (340, 386),
    "유가잔고":   (276, 298),
}

# X-offset from primary_x for secondary/tertiary block detection
_SEC_X_MIN = 9
_SEC_X_MAX = 45


def _get_from(items: list[dict], y_min: int, y_max: int) -> list[str]:
    """Return texts of items whose y_top falls in [y_min, y_max]."""
    return [item["text"] for item in items if y_min <= item["y_top"] <= y_max]


def _first(items: list[dict], y_min: int, y_max: int) -> str:
    """Return the first matching text for the given y-range, or empty string."""
    parts = _get_from(items, y_min, y_max)
    return parts[0] if parts else ""


def _joined(items: list[dict], y_min: int, y_max: int) -> str:
    """Return space-joined text of all items whose y_top falls in [y_min, y_max]."""
    return " ".join(_get_from(items, y_min, y_max))


def _parse_num(value: str) -> float:
    """Convert a Korean number string like '1,040,564' to float."""
    if not value:
        return 0.0
    cleaned = value.replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_page_transactions(page: fitz.Page) -> list[dict]:
    """
    Extract all transactions from a single rotated-layout page.
    Returns a list of raw field dicts, one per transaction.
    """
    # Collect all (x, y_top, text) from text spans on this page
    items: list[dict] = []
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        bx = block["bbox"][0]
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"].strip()
                if not text:
                    continue
                items.append(
                    {
                        "x": round(bx),
                        "y_top": round(span["bbox"][1]),
                        "text": text,
                    }
                )

    # Step 1: find primary x-positions by detecting date strings in the date y-range
    primary_xs: list[int] = []
    date_y_min, date_y_max = _PRI_FIELD_Y["거래일자"]
    for item in items:
        if date_y_min <= item["y_top"] <= date_y_max and DATE_RE.match(item["text"]):
            primary_xs.append(item["x"])
    primary_xs.sort()

    if not primary_xs:
        return []

    # Step 2: compute slot boundaries (midpoints between adjacent primaries)
    boundaries: list[float] = []
    for i in range(len(primary_xs) - 1):
        boundaries.append((primary_xs[i] + primary_xs[i + 1]) / 2.0)

    def slot_of(x: int) -> int:
        for i, b in enumerate(boundaries):
            if x < b:
                return i
        return len(primary_xs) - 1

    # Step 3: partition items into primary and secondary sub-lists per slot
    # Only consider items in the data area (x > 190)
    pri_items: dict[int, list[dict]] = {i: [] for i in range(len(primary_xs))}
    sec_items: dict[int, list[dict]] = {i: [] for i in range(len(primary_xs))}

    for item in items:
        if item["x"] <= 190:
            continue
        s = slot_of(item["x"])
        col_x = primary_xs[s]
        offset = item["x"] - col_x
        if -5 <= offset <= 8:
            pri_items[s].append(item)
        elif _SEC_X_MIN <= offset <= _SEC_X_MAX:
            sec_items[s].append(item)
        # else: outside this slot's range — skip

    # Step 4: build raw field dicts for each slot
    transactions: list[dict] = []
    for s in range(len(primary_xs)):
        pri = pri_items[s]
        sec = sec_items[s]

        # Extract date from primary items only
        date_val = _first(pri, *_PRI_FIELD_Y["거래일자"])
        if not DATE_RE.match(date_val):
            continue  # sanity check — should always pass

        # 거래종류: may span multiple items in primary block (e.g., 'ETF/상장클래스 분배금입금')
        tx_type = _joined(pri, *_PRI_FIELD_Y["거래종류"])

        # 종목번호: from primary block
        ticker = _first(pri, *_PRI_FIELD_Y["종목번호"])

        # 수수료: from primary block (this PDF stores combined fee+tax here)
        fee_str = _first(pri, *_PRI_FIELD_Y["수수료"])

        # 거래금액: from primary block (leftmost value in the amount row)
        amount_str = _first(pri, *_PRI_FIELD_Y["거래금액"])

        # 예수금잔액: from primary block (may not exist for stock-buying transactions)
        balance_str = _first(pri, *_PRI_FIELD_Y["예수금잔액"])

        # 거래수량: from secondary block — prefer non-zero value
        # Two possible y-positions: ~724 (zero) and ~666 (actual)
        # We take the actual quantity (y=658-685); if zero, we fall back to the zero value
        qty_items = _get_from(sec, *_SEC_FIELD_Y["거래수량"])
        # Filter out the '0' placeholder (at y~724) if a real quantity exists (at y~666)
        actual_qtys = [
            t for t, item in zip(qty_items, [i for i in sec if _SEC_FIELD_Y["거래수량"][0] <= i["y_top"] <= _SEC_FIELD_Y["거래수량"][1]])
            if 656 <= item["y_top"] <= 682
        ]
        # Rebuild: prefer items at y=656-682 (actual qty range)
        qty_actual_items = [i for i in sec if 656 <= i["y_top"] <= 682]
        qty_str = qty_actual_items[0]["text"] if qty_actual_items else ""

        # 단가: from secondary block
        price_str = _first(sec, *_SEC_FIELD_Y["단가"])

        # 종목명: combine text from secondary block's name y-range AND tertiary-style items
        # Both '종목명' and '종목명_하' ranges are in secondary items
        name_parts_a = _get_from(sec, *_SEC_FIELD_Y["종목명"])       # y=465-560
        name_parts_b = _get_from(sec, *_SEC_FIELD_Y["종목명_하"])    # y=535-600 (tertiary)
        # Merge and deduplicate (some parts may overlap at y=535-560)
        seen: set[str] = set()
        name_parts: list[str] = []
        for p in name_parts_a + name_parts_b:
            if p not in seen:
                seen.add(p)
                name_parts.append(p)
        name_str = " ".join(name_parts)

        raw: dict = {
            "거래일자": date_val,
            "거래종류": tx_type,
            "종목번호": ticker,
            "수수료": fee_str,
            "제세금합": "",   # not separately listed; fee field includes combined
            "거래금액": amount_str,
            "예수금잔액": balance_str,
            "거래번호": _first(sec, *_SEC_FIELD_Y["거래번호"]),
            "거래수량": qty_str,
            "단가": price_str,
            "종목명": name_str,
            "입출금액": _first(sec, *_SEC_FIELD_Y["입출금액"]),
            "유가잔고": _first(sec, *_SEC_FIELD_Y["유가잔고"]),
        }

        transactions.append(raw)

    return transactions


class MiraeAssetParser(BaseParser):
    BROKER_NAME = "미래에셋증권"
    DETECTION_KEYWORDS = ["미래에셋증권", "거래내역증명서"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        """
        Parse Mirae Asset Securities PDF pages into transactions.

        Page index 0 is the cover page and is skipped.
        Pages 1–N contain the rotated transaction table.
        """
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        for page_idx, page in enumerate(pages):
            if page_idx == 0:
                continue  # cover page

            page_raws = _extract_page_transactions(page)
            for raw in page_raws:
                balance = _parse_num(raw["예수금잔액"])
                tx_type = raw["거래종류"].strip()

                tx = Transaction(
                    date=raw["거래일자"],
                    type=tx_type,
                    ticker=raw["종목번호"],
                    name=raw["종목명"],
                    quantity=_parse_num(raw["거래수량"]),
                    price=_parse_num(raw["단가"]),
                    amount=_parse_num(raw["거래금액"]),
                    fee=_parse_num(raw["수수료"]),
                    tax=_parse_num(raw["제세금합"]),
                    balance=balance,
                    broker=self.BROKER_NAME,
                    raw=raw,
                )
                transactions.append(tx)
                raw_rows.append(raw)

        return transactions, raw_rows
