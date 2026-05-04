# 새 증권사 파서 추가 가이드

## 전체 흐름

```
1. PDF 구조 파악  →  2. 파서 클래스 작성  →  3. 레지스트리 등록  →  4. 동작 확인
```

---

## 1단계: PDF 구조 파악

새 PDF의 행/컬럼 레이아웃을 먼저 확인합니다.

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
python3 -c "
import fitz, sys
sys.path.insert(0, '.')
from core.pdf_utils import get_page_rows

doc = fitz.open('새증권사_거래내역.pdf')
doc.authenticate('비밀번호')  # 비밀번호 없으면 생략

page = doc[0]
rows = get_page_rows(page, y_tolerance=4.0)
for i, row in enumerate(rows[:40]):
    texts = [cell[1] for cell in row]
    xs    = [round(cell[0]) for cell in row]
    print(f'Row {i:2d}  x={xs}')
    print(f'         {texts}')
"
```

출력 결과에서 확인할 것:
- 거래 행이 날짜(`2025/11/06`)로 시작하는지
- 컬럼이 몇 개이고 순서가 어떻게 되는지
- 헤더/푸터 행에 공통으로 들어있는 키워드

---

## 2단계: `parsers/새증권사.py` 작성

`parsers/samsung.py`를 참고합니다. 아래는 키움증권 예시입니다.

```python
# parsers/kiwoom.py
import re
import fitz
from parsers.base import BaseParser
from core.models import Transaction
from core.pdf_utils import get_page_rows

DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

# 1단계 출력에서 확인한 원본 컬럼명 (순서 중요)
KIWOOM_COLUMNS = [
    "거래일자", "거래구분", "종목코드", "종목명",
    "거래수량", "거래단가", "거래금액", "수수료",
    "세금", "잔고", "정산금액",
]

# 헤더/푸터에 포함된 키워드 → 이 키워드가 있는 행은 스킵
SKIP_KEYWORDS = ["거래일자", "거래구분", "합계", "페이지"]


class KiwoomParser(BaseParser):
    BROKER_NAME = "키움증권"

    # PDF 첫 페이지에서 찾을 고유 키워드 (2개 이상 권장)
    DETECTION_KEYWORDS = ["키움증권", "거래내역확인"]

    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        transactions: list[Transaction] = []
        raw_rows:     list[dict]        = []

        for page in pages:
            rows = get_page_rows(page, y_tolerance=4.0)
            for row in rows:
                texts = [cell[1] for cell in row]
                if not texts:
                    continue
                # 헤더/푸터 스킵
                if any(kw in " ".join(texts) for kw in SKIP_KEYWORDS):
                    continue
                # 날짜로 시작하는 행 = 거래 데이터
                if DATE_PATTERN.match(texts[0]):
                    raw = _map_row(texts)
                    raw_rows.append(raw)
                    transactions.append(_to_transaction(raw, self.BROKER_NAME))

        return transactions, raw_rows


def _map_row(values: list[str]) -> dict:
    raw = {}
    for idx, col in enumerate(KIWOOM_COLUMNS):
        raw[col] = values[idx] if idx < len(values) else ""
    return raw


def _parse_num(s: str) -> float:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _to_transaction(raw: dict, broker: str) -> Transaction:
    return Transaction(
        date=raw.get("거래일자", ""),
        type=raw.get("거래구분", ""),
        ticker=raw.get("종목코드", ""),
        name=raw.get("종목명", ""),
        quantity=_parse_num(raw.get("거래수량", "0")),
        price=_parse_num(raw.get("거래단가", "0")),
        amount=_parse_num(raw.get("거래금액", "0")),
        fee=_parse_num(raw.get("수수료", "0")),
        tax=_parse_num(raw.get("세금", "0")),
        balance=_parse_num(raw.get("잔고", "0")),
        broker=broker,
        raw=raw,
    )
```

---

## 3단계: `parsers/__init__.py`에 등록

```python
# parsers/__init__.py
from .samsung     import SamsungParser
from .mirae_asset import MiraeAssetParser
from .kiwoom      import KiwoomParser       # ← 추가

PARSERS: list = [SamsungParser, MiraeAssetParser, KiwoomParser]  # ← 추가
```

등록하면 앱 실행 시 키움 PDF를 자동으로 감지합니다.

---

## 4단계: 동작 확인

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from core.loader import load_pdf
from core.detector import detect_parser

pages = load_pdf('새증권사_거래내역.pdf', '비밀번호')
parser_class = detect_parser(pages)
print('감지된 증권사:', parser_class.BROKER_NAME if parser_class else '인식 실패')

parser = parser_class()
txs, raws = parser.parse(pages)
print(f'파싱된 거래 수: {len(txs)}')
for t in txs[:3]:
    print(f'  {t.date} | {t.type} | {t.name} | {t.amount:,.0f}원')
"
```

---

## PDF 레이아웃 유형별 팁

| 레이아웃 유형 | 참고 파서 | 핵심 전략 |
|---|---|---|
| 일반 테이블 (행 = 거래 1건) | `samsung.py` | 날짜 패턴으로 행 시작 감지, x좌표로 컬럼 매핑 |
| 다중행 거래 (2~3행/건) | `samsung.py` | 서브번호 행(1, 2, 3…) 감지 후 그룹핑 |
| 세로 방향 레이아웃 | `mirae_asset.py` | `page.get_text("dict")`로 스팬 좌표 직접 추출 |
| 스캔 이미지 PDF | 자동 처리 | `get_page_rows()` 호출 시 OCR 자동 적용 |

---

## 다중행 거래 파싱 패턴

거래 1건이 PDF에서 여러 행에 걸쳐 있는 경우 두 가지 패턴 중 하나를 선택합니다.

### 패턴 1: 앵커 행 + 룩어헤드 (삼성증권 방식)

날짜나 번호처럼 "첫 행"을 구분할 수 있는 앵커가 있고, 뒤에 서브 행들이 따라오는 구조입니다.

```
Row 0: [2025/01/15] [매수] [100] [50,000]    ← 앵커(DATE) 행
Row 1: [거래번호001] [삼성전자] [500] [200]   ← 서브(SUBNUM) 행
Row 2: [삼성전자우선주 계속...]               ← 선택적 CONT 행
Row 3: [2025/01/16] ...                      ← 다음 거래
```

`while` 루프에서 `i`를 직접 조작해 소비한 행을 건너뜁니다.

```python
i = 0
while i < len(all_rows):
    row = all_rows[i]
    texts = [c[1] for c in row]

    if DATE_RE.match(texts[0]):        # 앵커 행 감지
        date_data = _parse_date_row(row)
        j = i + 1                      # 룩어헤드 포인터

        # 서브 행
        sub_data: dict = {}
        if j < len(all_rows) and _is_subnum_row(all_rows[j]):
            sub_data = _parse_subnum_row(all_rows[j])
            j += 1

        # 선택적 CONT 행
        cont_data: dict = {}
        if j < len(all_rows) and _is_cont_row(all_rows[j]):
            cont_data = _parse_cont_row(all_rows[j])
            j += 1

        transactions.append(_build_tx(date_data, sub_data, cont_data))
        i = j                          # 소비한 행 전부 건너뜀
    else:
        i += 1
```

`_is_subnum_row`, `_is_cont_row`는 x좌표나 텍스트 패턴으로 행 유형을 구분하는 헬퍼입니다.

---

### 패턴 2: 구분자 방식

빈 행, 소계 행 등 명확한 경계가 있어 거래 그룹을 분리할 수 있는 구조입니다.

```
Row 0: [삼성전자]                ← 그룹 시작
Row 1: [2025/01/15] [매수]
Row 2: [거래수량: 100]
Row 3: (빈 행 또는 소계)         ← 구분자
Row 4: [카카오]                  ← 다음 그룹
```

먼저 그룹으로 묶은 뒤 각 그룹을 파싱합니다.

```python
groups: list[list] = []
current: list = []

for row in all_rows:
    if _is_separator(row):    # 빈 행, 소계 행, 합계 행 등
        if current:
            groups.append(current)
            current = []
    else:
        current.append(row)

if current:
    groups.append(current)

for group in groups:
    raw = _build_raw_from_group(group)
    transactions.append(_to_transaction(raw, self.BROKER_NAME))
```

---

### 패턴 3: 고정 행 수

거래마다 항상 N행이 고정인 경우 가장 단순합니다.

```python
N = 3  # 거래 1건 = 3행
data_rows = [r for r in all_rows if not _is_skip_row(r)]

for i in range(0, len(data_rows), N):
    group = data_rows[i:i + N]
    if len(group) < N:
        break
    transactions.append(_build_tx_from_fixed_group(group))
```

---

### 패턴 선택 기준

| 상황 | 권장 패턴 |
|---|---|
| 날짜/번호 등 앵커 행이 명확하고, 뒤에 오는 서브 행 수가 가변 | 패턴 1 (룩어헤드) |
| 빈 행이나 소계 행으로 그룹 경계가 확실함 | 패턴 2 (구분자) |
| 거래당 행 수가 항상 동일 | 패턴 3 (고정 행 수) |

---

## 자주 겪는 문제

**컬럼 값이 밀려서 매핑됨**
→ `KIWOOM_COLUMNS` 순서를 1단계 출력 결과와 다시 비교해서 맞춤

**증권사 자동 감지 실패**
→ `DETECTION_KEYWORDS`에 PDF 첫 페이지에서 확실히 등장하는 고유 문자열 추가
→ `"계좌번호"` 같은 공통 단어 말고 증권사명이나 고유 계좌 포맷 사용

**헤더 행이 거래 데이터로 파싱됨**
→ `SKIP_KEYWORDS`에 헤더 행에서 보이는 키워드 추가

**날짜 형식이 다름** (예: `2025.11.06`, `20251106`)
→ `DATE_PATTERN` 정규식 수정
```python
DATE_PATTERN = re.compile(r"^\d{4}[./\-]\d{2}[./\-]\d{2}$")  # 구분자 유연하게
DATE_PATTERN = re.compile(r"^\d{8}$")  # 20251106 형식
```
