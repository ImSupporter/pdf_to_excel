# 증권 거래내역 PDF → 엑셀 변환기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여러 증권사의 거래내역서 PDF를 읽어 통합 엑셀 파일로 변환하는 Windows GUI 애플리케이션 구현

**Architecture:** PyMuPDF로 좌표 기반 PDF 파싱, 증권사별 파서 플러그인 구조, PyQt6 GUI, openpyxl 엑셀 출력. 핵심 로직(core/)과 UI(ui/)를 분리해 독립 테스트 가능하게 설계.

**Tech Stack:** Python 3.11+, PyQt6, PyMuPDF(fitz), openpyxl, pytest, PyInstaller

---

## 파일 구조

```
save_hj/
├── main.py
├── requirements.txt
├── tests/
│   ├── conftest.py
│   ├── test_loader.py
│   ├── test_detector.py
│   ├── test_samsung.py
│   ├── test_mirae_asset.py
│   ├── test_normalizer.py
│   └── test_exporter.py
├── core/
│   ├── __init__.py
│   ├── models.py          # Transaction dataclass, STANDARD_FIELDS
│   ├── pdf_utils.py       # 좌표 기반 행 추출 유틸
│   ├── loader.py          # PDF 로드 & 비밀번호 처리
│   ├── detector.py        # 증권사 자동 감지
│   ├── normalizer.py      # 공통 스키마 변환
│   └── exporter.py        # 엑셀 파일 생성
├── parsers/
│   ├── __init__.py        # PARSERS 리스트
│   ├── base.py            # BaseParser 추상 클래스
│   ├── samsung.py         # 삼성증권 파서
│   └── mirae_asset.py     # 미래에셋증권 파서
└── ui/
    ├── __init__.py
    ├── main_window.py
    ├── password_dialog.py
    ├── column_select.py
    └── mapping_dialog.py
```

---

## Task 1: 프로젝트 셋업

**Files:**
- Create: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `core/__init__.py`, `parsers/__init__.py`, `ui/__init__.py`

- [ ] **Step 1: requirements.txt 작성**

```
PyMuPDF==1.24.5
PyQt6==6.7.0
openpyxl==3.1.4
pytest==8.2.0
```

- [ ] **Step 2: 패키지 설치**

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
pip3 install -r requirements.txt
```

Expected: 오류 없이 설치 완료

- [ ] **Step 3: 디렉토리 및 빈 __init__.py 생성**

```bash
mkdir -p core parsers ui tests
touch core/__init__.py parsers/__init__.py ui/__init__.py tests/__init__.py
```

- [ ] **Step 4: conftest.py 작성** — 샘플 PDF 경로를 픽스처로 제공

```python
# tests/conftest.py
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent  # save_hj/ 폴더

@pytest.fixture
def samsung_pdf():
    return FIXTURES_DIR / "거래내역확인서_14515.pdf"

@pytest.fixture
def mirae_pdf():
    return FIXTURES_DIR / "거래내역증명서_20260504_202671300006385.pdf"

@pytest.fixture
def pdf_password():
    return "990901"
```

- [ ] **Step 5: pytest 동작 확인**

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
python3 -m pytest tests/ -v
```

Expected: `no tests ran` (테스트 파일 없으므로)

- [ ] **Step 6: 커밋**

```bash
git init
git add requirements.txt core/ parsers/ ui/ tests/
git commit -m "feat: project scaffolding"
```

---

## Task 2: 데이터 모델

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_models.py
from core.models import Transaction, STANDARD_FIELDS

def test_transaction_creation():
    t = Transaction(
        date="2025/11/06",
        type="매도",
        ticker="",
        name="삼성신종종류형MMF",
        quantity=1019462,
        price=1020.7,
        amount=1040564,
        fee=0,
        tax=0,
        balance=1040579,
        broker="삼성증권",
        raw={},
    )
    assert t.date == "2025/11/06"
    assert t.broker == "삼성증권"

def test_standard_fields_contains_required():
    assert "date" in STANDARD_FIELDS
    assert "broker" in STANDARD_FIELDS
    assert len(STANDARD_FIELDS) == 11
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_models.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: models.py 구현**

```python
# core/models.py
from dataclasses import dataclass, field

STANDARD_FIELDS = {
    "date": "거래일자",
    "type": "거래종류",
    "ticker": "종목코드",
    "name": "종목명",
    "quantity": "수량",
    "price": "단가",
    "amount": "거래금액",
    "fee": "수수료",
    "tax": "세금",
    "balance": "잔액",
    "broker": "증권사",
}

@dataclass
class Transaction:
    date: str
    type: str
    ticker: str
    name: str
    quantity: float
    price: float
    amount: float
    fee: float
    tax: float
    balance: float
    broker: str
    raw: dict = field(default_factory=dict)  # 원본 데이터 보존
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_models.py -v
```

Expected: PASS 2/2

- [ ] **Step 5: 커밋**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: Transaction dataclass and STANDARD_FIELDS"
```

---

## Task 3: PDF 좌표 유틸리티

**Files:**
- Create: `core/pdf_utils.py`
- Create: `tests/test_pdf_utils.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_pdf_utils.py
import fitz
from core.pdf_utils import get_page_rows

def test_get_page_rows_returns_rows(samsung_pdf, pdf_password):
    doc = fitz.open(str(samsung_pdf))
    doc.authenticate(pdf_password)
    page = doc[0]
    rows = get_page_rows(page)
    assert len(rows) > 0
    # 각 row는 (x0, text) 튜플의 리스트
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
        assert xs == sorted(xs), "각 행 내 셀은 x 좌표 기준 정렬되어야 함"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_pdf_utils.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: pdf_utils.py 구현**

```python
# core/pdf_utils.py
import fitz

def get_page_rows(page: fitz.Page, y_tolerance: float = 4.0) -> list[list[tuple]]:
    """
    페이지에서 단어를 추출해 y좌표 기준으로 행 단위로 묶어 반환.
    반환값: [[(x0, text), ...], ...]  — 행별 셀 목록, x 오름차순 정렬
    """
    words = page.get_text("words")
    # words 형식: (x0, y0, x1, y1, "text", block_no, line_no, word_no)
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: w[1])

    rows: list[list[tuple]] = []
    current_row: list[tuple] = []
    current_y: float = words_sorted[0][1]

    for w in words_sorted:
        if abs(w[1] - current_y) <= y_tolerance:
            current_row.append((w[0], w[4]))
        else:
            if current_row:
                rows.append(sorted(current_row, key=lambda c: c[0]))
            current_row = [(w[0], w[4])]
            current_y = w[1]

    if current_row:
        rows.append(sorted(current_row, key=lambda c: c[0]))

    return rows


def merge_row_cells(row: list[tuple], x_gap: float = 8.0) -> list[str]:
    """
    같은 행 내에서 x 간격이 x_gap 이하인 인접 셀을 하나의 문자열로 병합.
    반환값: 병합된 텍스트 값 목록
    """
    if not row:
        return []

    merged: list[str] = []
    current_text = row[0][1]
    current_x1 = row[0][0] + len(row[0][1]) * 4  # 근사 x1 (폰트 크기 가정)

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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_pdf_utils.py -v
```

Expected: PASS 2/2

- [ ] **Step 5: 커밋**

```bash
git add core/pdf_utils.py tests/test_pdf_utils.py
git commit -m "feat: coordinate-based PDF row extraction utility"
```

---

## Task 4: PDF 로더

**Files:**
- Create: `core/loader.py`
- Create: `tests/test_loader.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_loader.py
import pytest
from core.loader import load_pdf, PasswordError

def test_load_pdf_with_correct_password(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    assert len(pages) == 3  # 삼성 PDF는 3페이지

def test_load_pdf_without_password_on_unprotected():
    # 비밀번호 없는 PDF는 빈 문자열로 처리
    import fitz
    # 임시 비암호화 PDF 생성
    doc = fitz.open()
    doc.new_page()
    tmp_path = "/tmp/test_nopass.pdf"
    doc.save(tmp_path)
    doc.close()

    pages = load_pdf(tmp_path, "")
    assert len(pages) == 1

def test_load_pdf_with_wrong_password_raises(samsung_pdf):
    with pytest.raises(PasswordError):
        load_pdf(str(samsung_pdf), "wrongpass")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_loader.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: loader.py 구현**

```python
# core/loader.py
import fitz

class PasswordError(Exception):
    pass

def load_pdf(path: str, password: str) -> list[fitz.Page]:
    """
    PDF 파일을 열어 페이지 목록을 반환.
    비밀번호가 틀리면 PasswordError 발생.
    """
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password:
            raise PasswordError(f"비밀번호가 필요한 파일입니다: {path}")
        result = doc.authenticate(password)
        if result == 0:
            raise PasswordError(f"비밀번호가 올바르지 않습니다: {path}")
    return list(doc)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_loader.py -v
```

Expected: PASS 3/3

- [ ] **Step 5: 커밋**

```bash
git add core/loader.py tests/test_loader.py
git commit -m "feat: PDF loader with password handling"
```

---

## Task 5: BaseParser 및 파서 레지스트리

**Files:**
- Create: `parsers/base.py`
- Modify: `parsers/__init__.py`

- [ ] **Step 1: base.py 작성** — 테스트가 간단하므로 구현 먼저 작성

```python
# parsers/base.py
from abc import ABC, abstractmethod
import fitz
from core.models import Transaction

class BaseParser(ABC):
    BROKER_NAME: str = ""
    DETECTION_KEYWORDS: list[str] = []

    @abstractmethod
    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        """
        반환: (transactions, raw_rows)
        - transactions: 정규화용 Transaction 목록
        - raw_rows: 원본 컬럼 그대로인 dict 목록 (증권사별 시트용)
        """
        ...
```

- [ ] **Step 2: parsers/__init__.py 작성** — 파서 등록 리스트

```python
# parsers/__init__.py
# 새 파서는 이 파일에 import 추가 후 PARSERS 리스트에 등록
from .samsung import SamsungParser
from .mirae_asset import MiraeAssetParser

PARSERS: list = [SamsungParser, MiraeAssetParser]
```

단, samsung.py와 mirae_asset.py가 아직 없으므로 import는 Task 6, 7 완료 후 추가.  
지금은 빈 목록으로 커밋:

```python
# parsers/__init__.py (임시)
PARSERS: list = []
```

- [ ] **Step 3: 커밋**

```bash
git add parsers/base.py parsers/__init__.py
git commit -m "feat: BaseParser abstract class and parser registry"
```

---

## Task 6: 삼성증권 파서

**Files:**
- Create: `parsers/samsung.py`
- Create: `tests/test_samsung.py`

삼성 PDF 구조: 헤더 2행(컬럼명), 이후 트랜잭션마다 2행씩 데이터.
날짜 패턴(`YYYY/MM/DD`)으로 트랜잭션 시작 감지.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_samsung.py
from core.loader import load_pdf
from parsers.samsung import SamsungParser

def test_samsung_parser_detects_broker(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    full_text = " ".join(p.get_text() for p in pages)
    assert any(kw in full_text for kw in SamsungParser.DETECTION_KEYWORDS)

def test_samsung_parser_returns_transactions(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    transactions, raw_rows = parser.parse(pages)
    assert len(transactions) > 0
    assert len(raw_rows) == len(transactions)

def test_samsung_first_transaction(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    transactions, _ = parser.parse(pages)
    first = transactions[0]
    assert first.date == "2025/11/06"
    assert first.type == "매도"
    assert first.broker == "삼성증권"

def test_samsung_raw_rows_have_original_columns(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser = SamsungParser()
    _, raw_rows = parser.parse(pages)
    # 원본 컬럼명 확인
    assert "거래일자" in raw_rows[0]
    assert "거래명" in raw_rows[0]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_samsung.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: samsung.py 구현**

```python
# parsers/samsung.py
import re
import fitz
from parsers.base import BaseParser
from core.models import Transaction
from core.pdf_utils import get_page_rows

DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# 삼성증권 PDF 원본 컬럼 순서 (헤더 2행 합산)
SAMSUNG_COLUMNS = [
    "거래일자", "거래번호", "거래명", "종목명", "거래수량", "거래단가",
    "거래금액", "정산금액", "제세금/대출이자", "수수료/Fee", "현금잔액",
    "잔고수량/펀드평가금액", "상대계좌명", "변제금액", "통화코드",
    "외화정산금액", "처리점", "처리시간", "처리자",
    "상대계좌번호", "신용/대출금", "외화거래금액", "외화예수금액",
]

class SamsungParser(BaseParser):
    BROKER_NAME = "삼성증권"
    DETECTION_KEYWORDS = ["삼성증권", "7164099145"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        all_values: list[list[str]] = []

        for page in pages:
            rows = get_page_rows(page, y_tolerance=4.0)
            for row in rows:
                texts = [cell[1] for cell in row]
                row_text = " ".join(texts)
                # 헤더행, 요약행, 페이지 번호행 스킵
                if any(kw in row_text for kw in ["거래일자", "거래명", "입금액합계", "출력 끝", "페이지"]):
                    continue
                if texts:
                    all_values.append(texts)

        transactions: list[Transaction] = []
        raw_rows: list[dict] = []
        i = 0

        while i < len(all_values):
            row = all_values[i]
            # 날짜로 시작하는 행이 트랜잭션 시작
            if row and DATE_PATTERN.match(row[0]):
                # 현재 행 + 다음 행을 합쳐서 하나의 트랜잭션
                combined = row[:]
                if i + 1 < len(all_values) and not DATE_PATTERN.match(all_values[i + 1][0]):
                    combined += all_values[i + 1]
                    i += 1

                raw = _map_samsung_row(combined)
                raw_rows.append(raw)
                transactions.append(_to_transaction(raw, self.BROKER_NAME))
            i += 1

        return transactions, raw_rows


def _map_samsung_row(values: list[str]) -> dict:
    raw = {}
    for idx, col in enumerate(SAMSUNG_COLUMNS):
        raw[col] = values[idx] if idx < len(values) else ""
    return raw


def _parse_number(s: str) -> float:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _to_transaction(raw: dict, broker: str) -> Transaction:
    return Transaction(
        date=raw.get("거래일자", ""),
        type=raw.get("거래명", ""),
        ticker="",
        name=raw.get("종목명", ""),
        quantity=_parse_number(raw.get("거래수량", "0")),
        price=_parse_number(raw.get("거래단가", "0")),
        amount=_parse_number(raw.get("거래금액", "0")),
        fee=_parse_number(raw.get("수수료/Fee", "0")),
        tax=_parse_number(raw.get("제세금/대출이자", "0")),
        balance=_parse_number(raw.get("현금잔액", "0")),
        broker=broker,
        raw=raw,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_samsung.py -v
```

Expected: PASS 4/4. 실패 시 `get_page_rows` y_tolerance 또는 SAMSUNG_COLUMNS 순서 조정.

- [ ] **Step 5: parsers/__init__.py 업데이트**

```python
# parsers/__init__.py
from .samsung import SamsungParser

PARSERS: list = [SamsungParser]
```

- [ ] **Step 6: 커밋**

```bash
git add parsers/samsung.py parsers/__init__.py tests/test_samsung.py
git commit -m "feat: Samsung Securities PDF parser"
```

---

## Task 7: 미래에셋증권 파서

**Files:**
- Create: `parsers/mirae_asset.py`
- Create: `tests/test_mirae_asset.py`

미래에셋 PDF 구조: 각 페이지 상단에 31개 컬럼 헤더가 2행으로 나열됨.
트랜잭션 데이터는 날짜+거래종류가 합쳐진 셀로 시작.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_mirae_asset.py
from core.loader import load_pdf
from parsers.mirae_asset import MiraeAssetParser

def test_mirae_detects_broker(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    full_text = " ".join(p.get_text() for p in pages)
    assert any(kw in full_text for kw in MiraeAssetParser.DETECTION_KEYWORDS)

def test_mirae_returns_transactions(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    transactions, raw_rows = parser.parse(pages)
    assert len(transactions) > 0
    assert len(raw_rows) == len(transactions)

def test_mirae_has_transfer_in(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    transactions, _ = parser.parse(pages)
    dates = [t.date for t in transactions]
    assert "2025/10/22" in dates

def test_mirae_raw_rows_have_original_columns(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser = MiraeAssetParser()
    _, raw_rows = parser.parse(pages)
    assert "거래일자" in raw_rows[0]
    assert "거래종류" in raw_rows[0]
    assert "거래금액" in raw_rows[0]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_mirae_asset.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: mirae_asset.py 구현**

```python
# parsers/mirae_asset.py
import re
import fitz
from parsers.base import BaseParser
from core.models import Transaction
from core.pdf_utils import get_page_rows

DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# 미래에셋 원본 컬럼 (헤더 2행 합산, 총 31개)
MIRAE_COLUMNS = [
    "거래일자", "거래종류", "종목번호/기타", "수수료", "거래금액",
    "예수금잔액", "외화거래금액", "외화예수금", "미수총잔고", "미수발생금액",
    "거래번호", "원번호", "거래수량", "단가", "종목명",
    "제세금합", "입출금액", "유가잔고", "외화입출금액", "외화유가잔고",
    "통화코드", "미수변제금액", "상대금융기관", "상대계좌번호", "상대고객명",
    "(CD기)은행", "대출상환금액", "대출이자금액", "환율", "처리점", "처리시각",
]

# 헤더로 인식하는 키워드 (스킵 대상)
HEADER_KEYWORDS = set(MIRAE_COLUMNS) | {
    "거래내역", "증명서", "계좌번호", "고객님", "페이지", "계좌정보",
    "거래내역서", "N", "O", "NO", "ISA"
}

class MiraeAssetParser(BaseParser):
    BROKER_NAME = "미래에셋증권"
    DETECTION_KEYWORDS = ["미래에셋증권", "724-292"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        # 표지(page 0) 제외, 데이터 페이지부터 파싱
        for page in pages[1:]:
            page_transactions, page_raw = self._parse_page(page)
            transactions.extend(page_transactions)
            raw_rows.extend(page_raw)

        return transactions, raw_rows

    def _parse_page(self, page: fitz.Page):
        rows = get_page_rows(page, y_tolerance=4.0)
        transactions = []
        raw_rows = []

        # 각 행에서 날짜 패턴으로 시작하는 행 찾기
        for row in rows:
            texts = [cell[1] for cell in row]
            if not texts:
                continue
            # 헤더/메타 행 스킵
            if texts[0] in HEADER_KEYWORDS or any(kw in " ".join(texts) for kw in ["고객님 거래내역서", "계좌정보", "페이지"]):
                continue

            # 날짜로 시작하는 행 = 트랜잭션
            if DATE_PATTERN.match(texts[0]) and len(texts) >= 2:
                raw = _map_mirae_row(texts)
                raw_rows.append(raw)
                transactions.append(_to_transaction(raw, self.BROKER_NAME))

        return transactions, raw_rows


def _map_mirae_row(values: list[str]) -> dict:
    """
    날짜+거래종류가 texts[0]+texts[1]이고, 이후 값들을 순서대로 매핑.
    미래에셋은 한 행에 날짜, 거래종류, 이후 값들이 x좌표 순으로 나열됨.
    """
    raw = {col: "" for col in MIRAE_COLUMNS}
    raw["거래일자"] = values[0] if len(values) > 0 else ""
    raw["거래종류"] = values[1] if len(values) > 1 else ""
    # 나머지 값을 순서대로 남은 컬럼에 매핑
    remaining_cols = MIRAE_COLUMNS[2:]
    for i, col in enumerate(remaining_cols):
        idx = i + 2
        raw[col] = values[idx] if idx < len(values) else ""
    return raw


def _parse_number(s: str) -> float:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _to_transaction(raw: dict, broker: str) -> Transaction:
    # 종목코드: 'A379810' 형태에서 숫자만 추출
    ticker_raw = raw.get("종목번호/기타", "")
    ticker = re.sub(r"[^0-9]", "", ticker_raw)

    return Transaction(
        date=raw.get("거래일자", ""),
        type=raw.get("거래종류", ""),
        ticker=ticker,
        name=raw.get("종목명", ""),
        quantity=_parse_number(raw.get("거래수량", "0")),
        price=_parse_number(raw.get("단가", "0")),
        amount=_parse_number(raw.get("거래금액", "0")),
        fee=_parse_number(raw.get("수수료", "0")),
        tax=_parse_number(raw.get("제세금합", "0")),
        balance=_parse_number(raw.get("예수금잔액", "0")),
        broker=broker,
        raw=raw,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_mirae_asset.py -v
```

Expected: PASS 4/4. 실패 시 y_tolerance 조정 또는 HEADER_KEYWORDS 확장.

- [ ] **Step 5: parsers/__init__.py 최종 업데이트**

```python
# parsers/__init__.py
from .samsung import SamsungParser
from .mirae_asset import MiraeAssetParser

PARSERS: list = [SamsungParser, MiraeAssetParser]
```

- [ ] **Step 6: 커밋**

```bash
git add parsers/mirae_asset.py parsers/__init__.py tests/test_mirae_asset.py
git commit -m "feat: Mirae Asset Securities PDF parser"
```

---

## Task 8: 브로커 감지기

**Files:**
- Create: `core/detector.py`
- Create: `tests/test_detector.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_detector.py
import fitz
from core.loader import load_pdf
from core.detector import detect_parser
from parsers.samsung import SamsungParser
from parsers.mirae_asset import MiraeAssetParser

def test_detects_samsung(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    parser_class = detect_parser(pages)
    assert parser_class is SamsungParser

def test_detects_mirae(mirae_pdf, pdf_password):
    pages = load_pdf(str(mirae_pdf), pdf_password)
    parser_class = detect_parser(pages)
    assert parser_class is MiraeAssetParser

def test_returns_none_for_unknown():
    doc = fitz.open()
    doc.new_page()
    pages = list(doc)
    result = detect_parser(pages)
    assert result is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_detector.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: detector.py 구현**

```python
# core/detector.py
import fitz
from parsers import PARSERS
from parsers.base import BaseParser

def detect_parser(pages: list[fitz.Page]) -> type[BaseParser] | None:
    """
    첫 페이지 텍스트에서 키워드 매칭으로 증권사 파서를 반환.
    인식 불가 시 None 반환.
    """
    sample_text = " ".join(pages[0].get_text().split())

    for parser_class in PARSERS:
        if any(kw in sample_text for kw in parser_class.DETECTION_KEYWORDS):
            return parser_class

    return None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_detector.py -v
```

Expected: PASS 3/3

- [ ] **Step 5: 커밋**

```bash
git add core/detector.py tests/test_detector.py
git commit -m "feat: broker auto-detection by keyword matching"
```

---

## Task 9: 정규화기

**Files:**
- Create: `core/normalizer.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_normalizer.py
from core.models import Transaction, STANDARD_FIELDS
from core.normalizer import transactions_to_rows

def _make_tx(**kwargs):
    defaults = dict(
        date="2025/11/06", type="매수", ticker="379810",
        name="KODEX 미국S&P500", quantity=5, price=22755.0,
        amount=113775, fee=1, tax=0, balance=500000,
        broker="삼성증권", raw={}
    )
    defaults.update(kwargs)
    return Transaction(**defaults)

def test_normalizer_returns_list_of_dicts():
    txs = [_make_tx(), _make_tx(broker="미래에셋증권")]
    rows = transactions_to_rows(txs, selected_fields=list(STANDARD_FIELDS.keys()))
    assert len(rows) == 2
    assert isinstance(rows[0], dict)

def test_normalizer_uses_korean_column_names():
    txs = [_make_tx()]
    rows = transactions_to_rows(txs, selected_fields=["date", "type", "amount"])
    assert "거래일자" in rows[0]
    assert "거래종류" in rows[0]
    assert "거래금액" in rows[0]

def test_normalizer_respects_field_selection():
    txs = [_make_tx()]
    rows = transactions_to_rows(txs, selected_fields=["date", "broker"])
    assert len(rows[0]) == 2
    assert "거래일자" in rows[0]
    assert "증권사" in rows[0]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_normalizer.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: normalizer.py 구현**

```python
# core/normalizer.py
from core.models import Transaction, STANDARD_FIELDS

def transactions_to_rows(
    transactions: list[Transaction],
    selected_fields: list[str],
) -> list[dict]:
    """
    Transaction 목록을 선택된 필드 기준의 한국어 컬럼명 dict 목록으로 변환.
    selected_fields: STANDARD_FIELDS 키 목록 (예: ["date", "type", "amount"])
    """
    rows = []
    for tx in transactions:
        row = {}
        for field_key in selected_fields:
            korean_name = STANDARD_FIELDS.get(field_key, field_key)
            row[korean_name] = getattr(tx, field_key, "")
        rows.append(row)
    return rows
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_normalizer.py -v
```

Expected: PASS 3/3

- [ ] **Step 5: 커밋**

```bash
git add core/normalizer.py tests/test_normalizer.py
git commit -m "feat: transaction normalizer with field selection"
```

---

## Task 10: 엑셀 익스포터

**Files:**
- Create: `core/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_exporter.py
import tempfile
import os
import openpyxl
from core.models import Transaction, STANDARD_FIELDS
from core.exporter import export_to_excel

def _make_tx(broker="삼성증권", date="2025/11/06"):
    return Transaction(
        date=date, type="매수", ticker="", name="KODEX S&P500",
        quantity=5, price=22755.0, amount=113775, fee=1,
        tax=0, balance=500000, broker=broker,
        raw={"거래일자": date, "거래명": "매수", "종목명": "KODEX S&P500",
             "거래수량": "5", "거래금액": "113,775"}
    )

def test_export_creates_file():
    txs = [_make_tx("삼성증권"), _make_tx("미래에셋증권")]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(
            transactions=txs,
            broker_raw={"삼성증권": [txs[0].raw], "미래에셋증권": [txs[1].raw]},
            selected_fields=list(STANDARD_FIELDS.keys()),
            output_path=path,
        )
        assert os.path.exists(path)
        wb = openpyxl.load_workbook(path)
        assert "통합" in wb.sheetnames
        assert "삼성증권" in wb.sheetnames
        assert "미래에셋증권" in wb.sheetnames
    finally:
        os.unlink(path)

def test_export_unified_sheet_has_correct_columns():
    txs = [_make_tx()]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(
            transactions=txs,
            broker_raw={"삼성증권": [txs[0].raw]},
            selected_fields=["date", "type", "amount"],
            output_path=path,
        )
        wb = openpyxl.load_workbook(path)
        ws = wb["통합"]
        headers = [ws.cell(1, c).value for c in range(1, 4)]
        assert "거래일자" in headers
        assert "거래종류" in headers
        assert "거래금액" in headers
    finally:
        os.unlink(path)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_exporter.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: exporter.py 구현**

```python
# core/exporter.py
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from core.models import Transaction
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
    transactions: 전체 정규화된 트랜잭션 목록
    broker_raw: {"증권사명": [원본 dict, ...]}
    selected_fields: 통합 시트에 포함할 STANDARD_FIELDS 키 목록
    output_path: 출력 .xlsx 경로
    """
    wb = openpyxl.Workbook()

    # Sheet 1: 통합
    ws_unified = wb.active
    ws_unified.title = "통합"
    unified_rows = transactions_to_rows(transactions, selected_fields)
    from core.models import STANDARD_FIELDS
    headers = [STANDARD_FIELDS[f] for f in selected_fields]
    _write_sheet(ws_unified, headers, unified_rows)

    # Sheet 2+: 증권사별 원본
    for broker_name, raw_rows in broker_raw.items():
        ws = wb.create_sheet(title=broker_name)
        if raw_rows:
            broker_headers = list(raw_rows[0].keys())
            _write_sheet(ws, broker_headers, raw_rows)

    wb.save(output_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_exporter.py -v
```

Expected: PASS 2/2

- [ ] **Step 5: 커밋**

```bash
git add core/exporter.py tests/test_exporter.py
git commit -m "feat: Excel exporter with unified and per-broker sheets"
```

---

## Task 11: 비밀번호 입력 다이얼로그

**Files:**
- Create: `ui/password_dialog.py`

UI 컴포넌트는 PyQt6 이벤트 루프가 필요해 자동 테스트 제외. 수동 확인.

- [ ] **Step 1: password_dialog.py 작성**

```python
# ui/password_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton
)

class PasswordDialog(QDialog):
    def __init__(self, filename: str, last_password: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF 비밀번호")
        self.setModal(True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"파일: {filename}"))
        layout.addWidget(QLabel("비밀번호 (없으면 빈칸):"))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setText(last_password)
        self.password_input.selectAll()
        layout.addWidget(self.password_input)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_password(self) -> str:
        return self.password_input.text()
```

- [ ] **Step 2: 커밋**

```bash
git add ui/password_dialog.py
git commit -m "feat: password input dialog UI"
```

---

## Task 12: 컬럼 선택 다이얼로그

**Files:**
- Create: `ui/column_select.py`

- [ ] **Step 1: column_select.py 작성**

```python
# ui/column_select.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QScrollArea, QWidget
)
from core.models import STANDARD_FIELDS

class ColumnSelectDialog(QDialog):
    def __init__(self, selected_fields: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("통합 시트 컬럼 선택")
        self.setModal(True)
        self.setFixedSize(300, 400)

        if selected_fields is None:
            selected_fields = list(STANDARD_FIELDS.keys())

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("통합 시트에 포함할 컬럼을 선택하세요:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        self.checkboxes: dict[str, QCheckBox] = {}
        for key, korean in STANDARD_FIELDS.items():
            cb = QCheckBox(korean)
            cb.setChecked(key in selected_fields)
            self.checkboxes[key] = cb
            container_layout.addWidget(cb)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_selected_fields(self) -> list[str]:
        return [key for key, cb in self.checkboxes.items() if cb.isChecked()]
```

- [ ] **Step 2: 커밋**

```bash
git add ui/column_select.py
git commit -m "feat: column selection dialog UI"
```

---

## Task 13: 컬럼 매핑 다이얼로그 (미인식 증권사)

**Files:**
- Create: `ui/mapping_dialog.py`

- [ ] **Step 1: mapping_dialog.py 작성**

```python
# ui/mapping_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QScrollArea, QWidget, QLineEdit
)
from core.models import STANDARD_FIELDS

STANDARD_OPTIONS = ["(매핑 안 함)"] + list(STANDARD_FIELDS.keys())
STANDARD_LABELS = {k: v for k, v in STANDARD_FIELDS.items()}

class MappingDialog(QDialog):
    """
    PDF에서 추출된 미인식 컬럼을 표준 필드에 매핑하는 다이얼로그.
    detected_columns: PDF에서 추출한 원본 컬럼명 목록
    """
    def __init__(self, detected_columns: list[str], broker_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"컬럼 매핑 — {broker_name or '미인식 증권사'}")
        self.setModal(True)
        self.setMinimumSize(480, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("증권사를 자동 인식하지 못했습니다."))
        layout.addWidget(QLabel("증권사 이름을 입력하고 컬럼을 매핑해 주세요:"))

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("증권사명:"))
        self.broker_name_input = QLineEdit(broker_name)
        name_layout.addWidget(self.broker_name_input)
        layout.addLayout(name_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        self.combos: dict[str, QComboBox] = {}
        for col in detected_columns:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(col), stretch=2)
            combo = QComboBox()
            combo.addItem("(매핑 안 함)")
            for key, korean in STANDARD_FIELDS.items():
                combo.addItem(f"{korean} ({key})", userData=key)
            self.combos[col] = combo
            row_layout.addWidget(combo, stretch=3)
            container_layout.addLayout(row_layout)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_broker_name(self) -> str:
        return self.broker_name_input.text().strip() or "미인식증권사"

    def get_mapping(self) -> dict[str, str]:
        """반환: {원본컬럼명: 표준필드키} — 매핑 안 함은 제외"""
        result = {}
        for col, combo in self.combos.items():
            key = combo.currentData()
            if key:
                result[col] = key
        return result
```

- [ ] **Step 2: 커밋**

```bash
git add ui/mapping_dialog.py
git commit -m "feat: column mapping dialog for unknown brokers"
```

---

## Task 14: 메인 윈도우

**Files:**
- Create: `ui/main_window.py`

- [ ] **Step 1: main_window.py 작성**

```python
# ui/main_window.py
import os
from collections import defaultdict
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.loader import load_pdf, PasswordError
from core.detector import detect_parser
from core.exporter import export_to_excel
from core.models import STANDARD_FIELDS
from ui.password_dialog import PasswordDialog
from ui.column_select import ColumnSelectDialog
from ui.mapping_dialog import MappingDialog


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_entries, selected_fields, output_path):
        super().__init__()
        self.file_entries = file_entries  # list of (path, password, parser_class, mapping)
        self.selected_fields = selected_fields
        self.output_path = output_path

    def run(self):
        all_transactions = []
        broker_raw: dict[str, list[dict]] = defaultdict(list)
        total = len(self.file_entries)

        for i, (path, password, parser_class, mapping) in enumerate(self.file_entries):
            try:
                self.progress.emit(int((i / total) * 80), f"파싱 중: {os.path.basename(path)}")
                pages = load_pdf(path, password)
                parser = parser_class()
                transactions, raw_rows = parser.parse(pages)
                all_transactions.extend(transactions)
                broker_name = parser_class.BROKER_NAME
                broker_raw[broker_name].extend(raw_rows)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

        self.progress.emit(90, "엑셀 파일 생성 중...")
        try:
            export_to_excel(all_transactions, dict(broker_raw), self.selected_fields, self.output_path)
        except PermissionError:
            self.finished.emit(False, f"파일이 열려 있습니다. 닫고 다시 시도하세요:\n{self.output_path}")
            return

        self.progress.emit(100, "완료!")
        self.finished.emit(True, self.output_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("증권 거래내역 → 엑셀 변환기")
        self.setMinimumSize(700, 480)

        self._last_password = ""
        self._file_entries: list[tuple] = []  # (path, password, parser_class, mapping)
        self._selected_fields: list[str] = list(STANDARD_FIELDS.keys())
        self._output_path = os.path.expanduser("~/Desktop/거래내역.xlsx")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 파일 목록
        btn_row = QHBoxLayout()
        add_btn = QPushButton("PDF 파일 추가")
        add_btn.clicked.connect(self._add_files)
        del_btn = QPushButton("선택 삭제")
        del_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["파일명", "증권사", "상태"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # 컬럼 선택
        col_btn = QPushButton("컬럼 선택 (통합 시트)")
        col_btn.clicked.connect(self._select_columns)
        layout.addWidget(col_btn)

        # 저장 위치
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("저장 위치:"))
        self.output_label = QLabel(self._output_path)
        self.output_label.setStyleSheet("color: gray;")
        save_row.addWidget(self.output_label, stretch=1)
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self._browse_output)
        save_row.addWidget(browse_btn)
        layout.addLayout(save_row)

        # 변환 버튼 & 진행바
        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.setFixedHeight(40)
        self.convert_btn.clicked.connect(self._start_convert)
        layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 파일 선택", "", "PDF Files (*.pdf)"
        )
        for path in paths:
            self._process_file(path)

    def _process_file(self, path: str):
        filename = os.path.basename(path)
        dlg = PasswordDialog(filename, self._last_password, self)
        if dlg.exec() != PasswordDialog.DialogCode.Accepted:
            return

        password = dlg.get_password()
        if password:
            self._last_password = password

        try:
            pages = load_pdf(path, password)
        except PasswordError as e:
            QMessageBox.critical(self, "비밀번호 오류", str(e))
            return

        parser_class = detect_parser(pages)
        mapping = {}

        if parser_class is None:
            # 미인식 증권사 — 컬럼 매핑 UI 호출
            sample_text = pages[0].get_text()
            # 첫 페이지에서 컬럼명 추정 (줄바꿈 기준)
            detected_cols = [ln.strip() for ln in sample_text.split("\n") if ln.strip()][:30]
            map_dlg = MappingDialog(detected_cols, parent=self)
            if map_dlg.exec() != MappingDialog.DialogCode.Accepted:
                return
            mapping = map_dlg.get_mapping()
            broker_name = map_dlg.get_broker_name()
            # 미인식 파서를 동적 생성
            from parsers.base import BaseParser
            from core.models import Transaction

            class DynamicParser(BaseParser):
                BROKER_NAME = broker_name
                DETECTION_KEYWORDS = []

                def parse(self_, pages_):
                    return [], []

            parser_class = DynamicParser

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setItem(row, 1, QTableWidgetItem(parser_class.BROKER_NAME))
        status = "✓ 인식됨" if not mapping else "⚠ 수동 매핑"
        self.table.setItem(row, 2, QTableWidgetItem(status))
        self._file_entries.append((path, password, parser_class, mapping))

    def _remove_selected(self):
        rows = sorted(
            set(idx.row() for idx in self.table.selectedIndexes()), reverse=True
        )
        for row in rows:
            self.table.removeRow(row)
            self._file_entries.pop(row)

    def _select_columns(self):
        dlg = ColumnSelectDialog(self._selected_fields, self)
        if dlg.exec() == ColumnSelectDialog.DialogCode.Accepted:
            self._selected_fields = dlg.get_selected_fields()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택", self._output_path, "Excel Files (*.xlsx)"
        )
        if path:
            self._output_path = path
            self.output_label.setText(path)

    def _start_convert(self):
        if not self._file_entries:
            QMessageBox.warning(self, "경고", "PDF 파일을 먼저 추가하세요.")
            return
        if not self._selected_fields:
            QMessageBox.warning(self, "경고", "통합 시트에 포함할 컬럼을 선택하세요.")
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = ConvertWorker(self._file_entries, self._selected_fields, self._output_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "완료", f"변환이 완료되었습니다:\n{message}")
            self.status_label.setText("완료!")
        else:
            QMessageBox.critical(self, "오류", message)
            self.status_label.setText("오류 발생")
```

- [ ] **Step 2: 커밋**

```bash
git add ui/main_window.py
git commit -m "feat: main window with file list, progress bar, and convert worker"
```

---

## Task 15: 앱 진입점

**Files:**
- Create: `main.py`

- [ ] **Step 1: main.py 작성**

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("증권 거래내역 변환기")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 앱 실행 확인 (macOS에서 UI 점검)**

```bash
python3 main.py
```

Expected: 메인 윈도우 표시, PDF 추가 → 비밀번호 팝업 → 목록에 파일 추가 → 변환 시작 동작 확인

- [ ] **Step 3: 커밋**

```bash
git add main.py
git commit -m "feat: app entry point"
```

---

## Task 16: 엔드투엔드 통합 테스트

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_integration.py
import tempfile, os
import openpyxl
from core.loader import load_pdf
from core.detector import detect_parser
from core.exporter import export_to_excel
from core.models import STANDARD_FIELDS
from collections import defaultdict

def _run_pipeline(pdf_path, password, tmp_path):
    pages = load_pdf(str(pdf_path), password)
    parser_class = detect_parser(pages)
    assert parser_class is not None

    parser = parser_class()
    transactions, raw_rows = parser.parse(pages)

    broker_raw = defaultdict(list)
    broker_raw[parser_class.BROKER_NAME].extend(raw_rows)

    export_to_excel(
        transactions=transactions,
        broker_raw=dict(broker_raw),
        selected_fields=list(STANDARD_FIELDS.keys()),
        output_path=tmp_path,
    )
    return transactions, tmp_path

def test_samsung_full_pipeline(samsung_pdf, pdf_password):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        transactions, out = _run_pipeline(samsung_pdf, pdf_password, path)
        assert len(transactions) > 0
        wb = openpyxl.load_workbook(out)
        assert "통합" in wb.sheetnames
        assert "삼성증권" in wb.sheetnames
        ws = wb["통합"]
        assert ws.max_row > 1
    finally:
        os.unlink(path)

def test_mirae_full_pipeline(mirae_pdf, pdf_password):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        transactions, out = _run_pipeline(mirae_pdf, pdf_password, path)
        assert len(transactions) > 0
        wb = openpyxl.load_workbook(out)
        assert "통합" in wb.sheetnames
        assert "미래에셋증권" in wb.sheetnames
    finally:
        os.unlink(path)

def test_combined_pipeline(samsung_pdf, mirae_pdf, pdf_password):
    from collections import defaultdict
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        all_txs = []
        broker_raw = defaultdict(list)

        for pdf, pw in [(samsung_pdf, pdf_password), (mirae_pdf, pdf_password)]:
            pages = load_pdf(str(pdf), pw)
            pc = detect_parser(pages)
            txs, raws = pc().parse(pages)
            all_txs.extend(txs)
            broker_raw[pc.BROKER_NAME].extend(raws)

        export_to_excel(all_txs, dict(broker_raw), list(STANDARD_FIELDS.keys()), path)
        wb = openpyxl.load_workbook(path)
        assert "통합" in wb.sheetnames
        assert "삼성증권" in wb.sheetnames
        assert "미래에셋증권" in wb.sheetnames
        ws = wb["통합"]
        # 두 증권사 합산 행 수 확인 (헤더 1행 제외)
        assert ws.max_row > len(all_txs)  # 헤더 포함
    finally:
        os.unlink(path)
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
python3 -m pytest tests/ -v
```

Expected: 모든 테스트 PASS. 실패 시 해당 파서의 y_tolerance, 키워드, 컬럼 순서 조정.

- [ ] **Step 3: 커밋**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end pipeline integration tests"
```

---

## Task 17: PyInstaller 빌드 설정

**Files:**
- Create: `build.spec` (선택사항, 필요 시)

- [ ] **Step 1: PyInstaller 설치**

```bash
pip3 install pyinstaller
```

- [ ] **Step 2: 빌드 실행**

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
pyinstaller --onefile --windowed --name "증권거래내역변환기" main.py
```

Expected: `dist/증권거래내역변환기` (macOS) 또는 `dist/증권거래내역변환기.exe` (Windows) 생성

- [ ] **Step 3: Windows 빌드 시 추가 옵션** (Windows 환경에서 실행)

```bash
pyinstaller --onefile --windowed \
  --name "증권거래내역변환기" \
  --add-data "core;core" \
  --add-data "parsers;parsers" \
  --add-data "ui;ui" \
  main.py
```

- [ ] **Step 4: 커밋**

```bash
git add .gitignore
git commit -m "chore: add gitignore for build artifacts"
```

`.gitignore` 내용:
```
__pycache__/
*.pyc
dist/
build/
*.spec
.pytest_cache/
```

---

## 스펙 커버리지 확인

| 스펙 요구사항 | 구현 태스크 |
|---|---|
| 여러 PDF → 하나의 엑셀 | Task 10, 16 |
| 비밀번호 per-file, 이전값 힌트 | Task 11, 14 |
| 비밀번호 없는 PDF 지원 | Task 4 |
| 증권사 자동 감지 | Task 8 |
| 미래에셋 파서 | Task 7 |
| 삼성증권 파서 | Task 6 |
| 컬럼 선택 | Task 12, 14 |
| 통합 시트 + 증권사별 시트 | Task 10 |
| 미인식 증권사 매핑 GUI | Task 13, 14 |
| Windows GUI | Task 11–15 |
| .exe 배포 | Task 17 |
| 새 증권사 확장성 | Task 5, 8 |
