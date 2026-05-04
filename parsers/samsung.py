"""
Samsung Securities (삼성증권) PDF parser.

The Samsung PDF has the following per-transaction structure across multiple rows:

  [Optional] TXTYPE row:  only 거래명 text at x~73
  DATE row:               거래일자 at x~27, optional inline 거래명 at x~73, then
                          거래수량, 거래금액, 제세금, 현금잔액, 변제금액, 통화코드,
                          외화정산금액, 처리점
  [Optional] CONT row:    종목명 (part 1) and/or 처리시간 at far right
  SUBNUM row:             거래번호 at x~42, 종목명 (part 1 or 2) at x~73,
                          거래단가, 정산금액, 수수료/Fee, 잔고수량/펀드평가금액
  [Optional] CONT row:    종목명 (continuation) at x~73

Column x-position thresholds (mid-point between adjacent headers):
  DATE row columns:
    거래일자       x < 80
    거래명 (inline) 60 < x < 120   (only when no date at start)
    거래수량       120 < x < 220
    거래금액       220 < x < 290
    제세금/대출이자 290 < x < 350
    현금잔액       350 < x < 460
    상대계좌명     460 < x < 540
    변제금액       540 < x < 600
    통화코드       590 < x < 660
    외화정산금액   650 < x < 720
    처리점         700 < x < 770
    처리(시간)     770 < x

  SUBNUM row columns:
    거래번호       x < 60
    종목명         60 < x < 170
    거래단가       160 < x < 230
    정산금액       220 < x < 295
    수수료/Fee     285 < x < 360
    잔고수량/펀드평가금액  360 < x < 440
    신용/대출금    490 < x < 575
    외화거래금액   565 < x < 650
    외화예수금액   640 < x < 715
    처리자         710 < x < 780
    처리시간       775 < x
"""

import re
from dataclasses import dataclass, field

import fitz

from core.models import Transaction
from core.pdf_utils import get_page_rows
from parsers.base import BaseParser

DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# Keywords that appear only in Samsung Securities PDFs
SKIP_FRAGMENTS = {
    "거래일자", "거래명", "거래수량", "거래금액", "거래단가", "거래번호",
    "정산금액", "수수료/Fee", "제세금/", "대출이자", "잔고수량/", "현금잔액",
    "상대계좌명", "상대계좌번호", "변제금액", "통화코드", "외화정산금액",
    "외화거래금액외화예수금액", "신용/대출금", "처리점", "처리자", "시간",
    "입금액합계", "출금액합계", "증감", "삼성증권", "출력", "끝",
    "계좌거래내역", "계좌번호", "조회구분", "조회일자", "고", "객", "명",
    "펀드평가금액",
}

# Page markers e.g. "1/3", "2/3", "3/3"
PAGE_MARKER_RE = re.compile(r"^\d+/\d+$")


def _is_skip_row(texts: list[str]) -> bool:
    """Return True if this row should be skipped (header, footer, etc.)."""
    if not texts:
        return True
    # Skip page markers
    if len(texts) == 1 and PAGE_MARKER_RE.match(texts[0]):
        return True
    # Skip rows where every token is a known header/skip word
    non_skip = [t for t in texts if t not in SKIP_FRAGMENTS and not PAGE_MARKER_RE.match(t)]
    if not non_skip:
        return True
    # Skip rows that contain obvious header keywords
    joined = " ".join(texts)
    for kw in ("입금액합계", "출금액합계", "출력", "계좌거래내역", "계좌번호", "조회구분"):
        if kw in joined:
            return True
    return False


def _get_cell_value(row: list[tuple], x_min: float, x_max: float) -> str:
    """Extract and concatenate all cell values in the given x range."""
    parts = [text for (x, text) in row if x_min <= x < x_max]
    return " ".join(parts)


def _parse_row_by_x(row: list[tuple]) -> dict:
    """
    Parse a DATE row into a dict using x-position thresholds.
    The first cell must be the date (x < 80).
    """
    result: dict = {}
    # Collect cells by column
    for x, text in row:
        if x < 55:
            result["거래일자"] = result.get("거래일자", "") + text
        elif x < 120:
            # Either inline 거래명, or processing office label
            result["거래명"] = result.get("거래명", "") + (" " if "거래명" in result else "") + text
        elif x < 225:
            result["거래수량"] = result.get("거래수량", "") + text
        elif x < 295:
            result["거래금액"] = result.get("거래금액", "") + text
        elif x < 355:
            result["제세금/대출이자"] = result.get("제세금/대출이자", "") + text
        elif x < 465:
            result["현금잔액"] = result.get("현금잔액", "") + text
        elif x < 545:
            result["상대계좌명"] = result.get("상대계좌명", "") + text
        elif x < 600:
            result["변제금액"] = result.get("변제금액", "") + text
        elif x < 660:
            result["통화코드"] = result.get("통화코드", "") + text
        elif x < 720:
            result["외화정산금액"] = result.get("외화정산금액", "") + text
        elif x < 775:
            result["처리점"] = result.get("처리점", "") + (" " if "처리점" in result else "") + text
        else:
            # 처리시간
            result["처리시간"] = result.get("처리시간", "") + text
    return result


def _parse_subnum_row_by_x(row: list[tuple]) -> dict:
    """
    Parse a SUBNUM row (거래번호 row) using x-position thresholds.
    """
    result: dict = {}
    for x, text in row:
        if x < 60:
            result["거래번호"] = result.get("거래번호", "") + text
        elif x < 170:
            result["종목명"] = result.get("종목명", "") + (" " if "종목명" in result else "") + text
        elif x < 225:
            result["거래단가"] = result.get("거래단가", "") + text
        elif x < 290:
            result["정산금액"] = result.get("정산금액", "") + text
        elif x < 360:
            result["수수료/Fee"] = result.get("수수료/Fee", "") + text
        elif x < 465:
            result["잔고수량/펀드평가금액"] = result.get("잔고수량/펀드평가금액", "") + text
        elif x < 575:
            result["신용/대출금"] = result.get("신용/대출금", "") + text
        elif x < 645:
            result["외화거래금액"] = result.get("외화거래금액", "") + text
        elif x < 715:
            result["외화예수금액"] = result.get("외화예수금액", "") + text
        elif x < 775:
            result["처리자"] = result.get("처리자", "") + text
        else:
            result["처리시간"] = result.get("처리시간", "") + text
    return result


def _parse_num(value: str) -> float:
    """Convert Korean number string (e.g. '1,040,564') to float."""
    if not value:
        return 0.0
    try:
        return float(value.replace(",", "").replace(" ", ""))
    except ValueError:
        return 0.0


class SamsungParser(BaseParser):
    BROKER_NAME = "삼성증권"
    DETECTION_KEYWORDS = ["삼성증권", "계좌거래내역"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        """
        Parse Samsung Securities PDF pages into transactions.

        The PDF layout per transaction group:
          - [Optional] stand-alone 거래명 row (TXTYPE row, x~73)
          - DATE row starting with YYYY/MM/DD (may include inline 거래명)
          - [Optional] CONT row: partial 종목명 + 처리시간
          - SUBNUM row: 거래번호 + rest of data
          - [Optional] CONT row: 종목명 continuation

        We collect all raw rows across pages then group them into transactions.
        """
        all_rows: list[list[tuple]] = []
        for page in pages:
            page_rows = get_page_rows(page, y_tolerance=4.0)
            all_rows.extend(page_rows)

        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        # State machine: we walk through rows and build transaction records
        i = 0
        n = len(all_rows)

        # Pending 거래명 from standalone TXTYPE row
        pending_tx_type: str = ""

        while i < n:
            row = all_rows[i]
            texts = [c[1] for c in row]
            xs = [c[0] for c in row]

            if not texts:
                i += 1
                continue

            if _is_skip_row(texts):
                i += 1
                continue

            first_x = xs[0]
            first_text = texts[0]

            # ─── Detect row type ───────────────────────────────────────────

            is_date_row = DATE_RE.match(first_text) is not None

            # TXTYPE-only row: single or few tokens at x~73 (no date), not a digit
            is_txtype_only = (
                not is_date_row
                and 60 <= first_x <= 95
                and not first_text.isdigit()
                and (len(texts) == 1 or (len(texts) == 2 and xs[-1] > 700))
            )

            # SUBNUM row: first cell is a digit at x~42
            is_subnum_row = (
                not is_date_row
                and 35 <= first_x <= 55
                and first_text.isdigit()
            )

            if is_txtype_only:
                # This is a standalone 거래명 row preceding the date row
                pending_tx_type = " ".join(texts[t_i] for t_i in range(len(texts)) if xs[t_i] < 700)
                i += 1
                continue

            if is_date_row:
                # Parse the main DATE row
                date_data = _parse_row_by_x(row)

                # If 거래명 was in previous row, use that
                if pending_tx_type and not date_data.get("거래명"):
                    date_data["거래명"] = pending_tx_type
                pending_tx_type = ""

                # Look ahead for: optional CONT row (종목명 pt1 + 처리시간), SUBNUM row, optional CONT row
                j = i + 1

                # CONT row 1: may contain partial 종목명 at x~73 and/or 처리시간 at x>770
                cont_name_parts: list[str] = []
                processing_time: str = date_data.get("처리시간", "")

                if j < n:
                    nrow = all_rows[j]
                    ntexts = [c[1] for c in nrow]
                    nxs = [c[0] for c in nrow]
                    # CONT row: first cell x in [60,170], not a digit, not a date
                    if ntexts and not DATE_RE.match(ntexts[0]) and not ntexts[0].isdigit():
                        if 55 <= nxs[0] <= 170:
                            for ni, (nx, nt) in enumerate(zip(nxs, ntexts)):
                                if nx < 700:
                                    cont_name_parts.append(nt)
                                else:
                                    processing_time = nt
                            j += 1

                # SUBNUM row
                subnum_data: dict = {}
                if j < n:
                    srow = all_rows[j]
                    stexts = [c[1] for c in srow]
                    sxs = [c[0] for c in srow]
                    if stexts and 35 <= sxs[0] <= 55 and stexts[0].isdigit():
                        subnum_data = _parse_subnum_row_by_x(srow)
                        # Merge 처리시간 if found in subnum row
                        if not processing_time and "처리시간" in subnum_data:
                            processing_time = subnum_data["처리시간"]
                        j += 1

                        # CONT row 2: 종목명 continuation at x~73
                        if j < n:
                            crow = all_rows[j]
                            ctexts = [c[1] for c in crow]
                            cxs = [c[0] for c in crow]
                            if ctexts and not DATE_RE.match(ctexts[0]) and not ctexts[0].isdigit():
                                if 55 <= cxs[0] <= 170 and (len(ctexts) == 1 or (len(ctexts) <= 3 and all(cx < 200 for cx in cxs))):
                                    cont_name_parts.extend(ctexts)
                                    j += 1

                # Assemble 종목명
                name_from_subnum = subnum_data.get("종목명", "")
                name_from_cont = " ".join(cont_name_parts)
                if name_from_subnum and name_from_cont:
                    full_name = name_from_cont + " " + name_from_subnum
                elif name_from_subnum:
                    full_name = name_from_subnum
                else:
                    full_name = name_from_cont

                # Build raw_row dict with all original Samsung column names
                raw: dict = {
                    "거래일자": date_data.get("거래일자", ""),
                    "거래번호": subnum_data.get("거래번호", ""),
                    "거래명": date_data.get("거래명", ""),
                    "종목명": full_name,
                    "거래수량": date_data.get("거래수량", ""),
                    "거래단가": subnum_data.get("거래단가", ""),
                    "거래금액": date_data.get("거래금액", ""),
                    "정산금액": subnum_data.get("정산금액", ""),
                    "제세금/대출이자": date_data.get("제세금/대출이자", ""),
                    "수수료/Fee": subnum_data.get("수수료/Fee", ""),
                    "현금잔액": date_data.get("현금잔액", ""),
                    "잔고수량/펀드평가금액": subnum_data.get("잔고수량/펀드평가금액", ""),
                    "상대계좌명": date_data.get("상대계좌명", ""),
                    "변제금액": date_data.get("변제금액", ""),
                    "통화코드": date_data.get("통화코드", ""),
                    "외화정산금액": date_data.get("외화정산금액", ""),
                    "처리점": date_data.get("처리점", ""),
                    "처리시간": processing_time,
                    "신용/대출금": subnum_data.get("신용/대출금", ""),
                }

                # Build normalized Transaction
                tx = Transaction(
                    date=raw["거래일자"],
                    type=raw["거래명"],
                    ticker="",
                    name=raw["종목명"],
                    quantity=_parse_num(raw["거래수량"]),
                    price=_parse_num(raw["거래단가"]),
                    amount=_parse_num(raw["거래금액"]),
                    fee=_parse_num(raw["수수료/Fee"]),
                    tax=_parse_num(raw["제세금/대출이자"]),
                    balance=_parse_num(raw["현금잔액"]),
                    broker=self.BROKER_NAME,
                    raw=raw,
                )

                transactions.append(tx)
                raw_rows.append(raw)

                i = j
                continue

            # Anything else (stray continuation rows, etc.) — skip
            i += 1

        return transactions, raw_rows
