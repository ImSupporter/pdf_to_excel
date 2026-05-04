# 동적 파서 생성/선택 기능 설계 문서

**날짜:** 2026-05-05  
**상태:** 승인됨

---

## 1. 개요

사용자가 GUI에서 새 증권사 파서를 직접 만들고 관리할 수 있는 기능을 추가한다.
파서 설정은 JSON으로 `%APPDATA%`에 영구 저장되며, Windows EXE(PyInstaller) 배포 환경에서 동작한다.
출력 구조는 통합 시트를 제거하고 파서(증권사)별 개별 시트로 변경한다.

---

## 2. UX 흐름

```
메인 윈도우 → [PDF 파일 추가]
    ↓
비밀번호 입력 (PasswordDialog)
    ↓
PDF 로드 (load_pdf)
    ↓
ParserSelectDialog
  - detect_parser()로 추천 파서 계산 → ★ 표시 + 자동 선택
  - 내장 파서 목록 (삭제 불가)
  - 동적 파서 목록 (삭제 가능)
  - [파서 추가] 버튼 → ParserBuilderDialog (현재 PDF 전달)
    ↓
파서 선택 확인
    ↓
메인 윈도우 파일 목록에 추가
    ↓
[변환 시작] → 파서별 개별 시트 Excel 출력
```

---

## 3. 새로 추가되는 파일

### `core/parser_registry.py`

동적 파서의 로드/저장/팩토리를 담당한다.

```python
@dataclass
class FieldMapping:
    standard_field: str   # STANDARD_FIELDS 키 (예: "date", "amount")
    # layout_type == "table": column_index 사용, y_min/y_max 무시
    column_index: int
    # layout_type == "rotated": y_min/y_max 사용, column_index 무시
    y_min: int
    y_max: int

@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str                   # raw 정규식 문자열
    layout_type: str               # "table" | "rotated"
    start_page: int                # 파싱 시작 페이지 인덱스
    rows_per_tx: int               # 거래 1건당 행 수 (1~3), layout_type=="table"만 적용
    skip_keywords: list[str]       # 헤더/합계 행 건너뛰기 키워드, layout_type=="table"만 적용
    field_mappings: list[FieldMapping]
```

**레이아웃 타입별 파싱 전략:**

| layout_type | 미리보기 | 필드 매핑 방식 |
|---|---|---|
| `table` | `get_page_rows()` 결과 행/컬럼 테이블 | 컬럼 인덱스 선택 드롭다운 |
| `rotated` | `page.get_text("dict")` span 좌표 산점도 (x, y, text) | Y좌표 범위(y_min, y_max) 직접 입력 |

`ParserBuilderDialog`는 레이아웃 타입 드롭다운 변경 시 미리보기와 필드 매핑 UI를 전환한다.

**저장 위치 (`_get_data_dir`):**

```python
import sys, os
from pathlib import Path

def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "증권거래내역변환기"
    d.mkdir(parents=True, exist_ok=True)
    return d

PARSERS_JSON = _get_data_dir() / "parsers.json"
```

**주요 메서드:**

| 메서드 | 역할 |
|---|---|
| `load() -> list[DynamicParserConfig]` | JSON → config 목록 |
| `save(configs)` | config 목록 → JSON 덮어쓰기 |
| `build_class(config) -> type[BaseParser]` | config → `BaseParser` 서브클래스 동적 생성 |
| `get_all_parsers() -> list[type[BaseParser]]` | 내장 + 동적 파서 전체 목록 |

`build_class()`는 `type()` 또는 클래스 팩토리로 런타임에 `BaseParser` 서브클래스를 생성하여 `detect_parser()`와 동일한 인터페이스로 동작하게 한다.

---

### `ui/parser_select_dialog.py` — `ParserSelectDialog`

```
┌─────────────────────────────────────────────┐
│  파서 선택 — {파일명}                          │
├─────────────────────────────────────────────┤
│  ★ 키움증권     [내장] DETECTION_KEYWORDS 일치│  ← 자동 선택
│    삼성증권     [내장]                        │
│    미래에셋증권  [내장]                        │
│    시티은행     [내장]                        │
│  ─────────────────────────────────────────  │
│    나의증권사   [동적]              [삭제]     │
├─────────────────────────────────────────────┤
│  [파서 추가]              [취소]  [선택 확인] │
└─────────────────────────────────────────────┘
```

- 생성자: `__init__(pages, recommended_class, parent)`
- `get_selected_parser() -> type[BaseParser]`
- [삭제]: 동적 파서만 가능, 확인 팝업 후 `parser_registry.save()` 호출
- [파서 추가]: `ParserBuilderDialog(pages)` 열기, 저장 후 목록 즉시 갱신

---

### `ui/parser_builder_dialog.py` — `ParserBuilderDialog`

좌우 분할 레이아웃:

```
┌──────────────────────────┬──────────────────────────────────────┐
│  PDF 미리보기 (QTableWidget)│  파서 설정 (QFormLayout)             │
│                          │                                      │
│  Col0   Col1   Col2 ...  │  증권사명:    [                    ]  │
│  ...                     │  감지 키워드: [                    ]  │
│                          │  날짜 정규식: [^\d{4}/\d{2}/\d{2}$]  │
│  [← 이전] [다음 →]        │  레이아웃:   [일반 테이블       ▼]   │
│                          │  시작 페이지: [0                  ]  │
│                          │  건너뛸 키워드:[                   ]  │
│                          │  행/거래:    [1                  ]   │
│                          │                                      │
│                          │  ── 필드 매핑 ──────────────────────  │
│                          │  거래일자 → [Col0: 2024/01/15 ▼]    │
│                          │  거래종류 → [Col1: 매수       ▼]    │
│                          │  종목명   → [Col2: 삼성전자   ▼]    │
│                          │  거래수량 → [미사용           ▼]    │
│                          │  거래금액 → [Col4: 50,000     ▼]    │
│                          │  수수료   → [미사용           ▼]    │
│                          │  세금     → [미사용           ▼]    │
│                          │  잔액     → [미사용           ▼]    │
├──────────────────────────┴──────────────────────────────────────┤
│                                          [취소]  [저장]          │
└─────────────────────────────────────────────────────────────────┘
```

- 미리보기 테이블: `get_page_rows(page)`로 추출한 행/컬럼 표시, 컬럼 헤더는 `Col0, Col1, ...`
- 페이지 이동: start_page 설정에 맞춰 기본 페이지 표시, 좌우 버튼으로 이동
- 필드 매핑 드롭다운: `["미사용", "Col0: {샘플1}, {샘플2}", "Col1: ...", ...]` 형태
- [저장]: 유효성 검사(증권사명 필수, 감지 키워드 1개 이상) → `parser_registry.save()` → `ParserSelectDialog` 목록 갱신

---

## 4. 수정되는 기존 파일

### `ui/main_window.py`

`_process_file()` 내부 변경:

```python
# 변경 전
parser_class = detect_parser(pages)
if parser_class is None:
    # MappingDialog ...

# 변경 후
from ui.parser_select_dialog import ParserSelectDialog
recommended = detect_parser(pages)
dlg = ParserSelectDialog(pages, recommended, parent=self)
if dlg.exec() != QDialog.DialogCode.Accepted:
    return
parser_class = dlg.get_selected_parser()
```

`_file_entries` 튜플에서 `mapping` 항목 제거: `(path, password, parser_class)`.

### `core/exporter.py`

통합 시트 제거, 파서별 시트만 출력:

```python
# 변경 전: export_to_excel(transactions, broker_raw, selected_fields, output_path)
# 변경 후: export_to_excel(broker_raw, output_path)
# broker_raw: dict[str, list[dict]] — 증권사명 → 원본 행 목록
```

각 증권사별로 시트 1개, 컬럼은 해당 파서의 원본 필드명 그대로 사용.

### `core/detector.py`

`detect_parser()`가 내장 파서뿐 아니라 동적 파서도 포함해서 검색:

```python
from core.parser_registry import get_all_parsers

def detect_parser(pages):
    sample_text = " ".join(pages[0].get_text().split())
    for parser_class in get_all_parsers():
        if any(kw in sample_text for kw in parser_class.DETECTION_KEYWORDS):
            return parser_class
    return None
```

---

## 5. 제거되는 기존 코드

| 파일 | 이유 |
|---|---|
| `ui/column_select.py` | 통합 시트 제거로 불필요 |
| `ui/mapping_dialog.py` | `ParserBuilderDialog`로 대체 |
| `main_window.py` 내 `DynamicParser` 임시 클래스 | `parser_registry.build_class()`로 대체 |
| `ConvertWorker`의 `mapping` 파라미터 및 처리 로직 | 매핑 개념 제거 |

---

## 6. JSON 저장 형식

```json
[
  {
    "broker_name": "키움증권",
    "detection_keywords": ["키움증권", "거래내역확인"],
    "date_re": "^\\d{4}/\\d{2}/\\d{2}$",
    "layout_type": "table",
    "start_page": 0,
    "rows_per_tx": 2,
    "skip_keywords": ["거래일자", "합계", "페이지"],
    "field_mappings": [
      {"standard_field": "date", "column_index": 0},
      {"standard_field": "type", "column_index": 1},
      {"standard_field": "name", "column_index": 3},
      {"standard_field": "quantity", "column_index": 4},
      {"standard_field": "amount", "column_index": 6},
      {"standard_field": "fee", "column_index": 7}
    ]
  }
]
```

---

## 7. 배포 고려사항 (Windows PyInstaller)

- `%APPDATA%\증권거래내역변환기\parsers.json`은 번들 외부에 위치하므로 런타임에 읽기/쓰기 가능
- `sys.frozen` 여부와 무관하게 `_get_data_dir()`이 올바른 경로 반환
- PyInstaller `.spec`에 `core/parser_registry.py` 추가 불필요 (Python 소스이므로 자동 포함)

---

## 8. 테스트 전략

| 테스트 | 방법 |
|---|---|
| `DynamicParserConfig` 직렬화/역직렬화 | JSON 왕복 단위 테스트 |
| `build_class()` 동적 생성 | 내장 파서와 동일 인터페이스 확인 |
| `detect_parser()` 동적 파서 포함 감지 | 키워드 매칭 단위 테스트 |
| `ParserSelectDialog` 추천 표시 | 수동 UI 테스트 |
| `ParserBuilderDialog` 저장→목록 갱신 | 수동 UI 테스트 |
| `export_to_excel()` 파서별 시트 | 단위 테스트 |
