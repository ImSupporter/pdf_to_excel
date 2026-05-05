# Template Parser Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans when implementing or continuing this plan. Keep checkbox state current as work progresses.

**Goal:** 파서 추가 기능을 화면 내 그리드 매핑 방식에서 엑셀 포맷 다운로드/업로드 방식으로 전환한다. 사용자가 노란색으로 표시한 셀명은 변환 결과 컬럼명으로 그대로 사용하고, 회색으로 표시한 셀은 무시 키워드로 저장한다.

**Architecture:** `core/parser_template.py`가 엑셀 포맷 생성과 업로드 파싱을 담당한다. `ui/parser_builder_dialog.py`는 다운로드/업로드 중심 UI로 단순화한다. `core/parser_registry.py`는 `template` layout과 위치 metadata를 저장하고, 런타임 파서가 노란색 셀명을 `raw` 컬럼명으로 사용하게 한다.

**Tech Stack:** PyQt6, PyMuPDF(fitz), openpyxl, Python dataclasses, pytest

---

## File Map

| 파일 | 상태 | 역할 |
|---|---|---|
| `core/parser_template.py` | 신규 | PDF -> 엑셀 포맷 다운로드, 노란색/회색 셀 업로드 파싱 |
| `ui/parser_builder_dialog.py` | 수정 | PDF 그리드 제거, 포맷 파일 다운로드/업로드 UI 제공 |
| `core/parser_registry.py` | 수정 | `FieldMapping` 위치 metadata 추가, `template` layout 지원 |
| `tests/test_parser_template.py` | 신규 | 색상 기반 업로드 파싱 테스트 |

---

## Task 1: `core/parser_template.py` 추가

**Files:**
- Create: `core/parser_template.py`
- Create: `tests/test_parser_template.py`

- [x] **Step 1: 템플릿 데이터 모델 정의**

```python
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
```

- [x] **Step 2: 셀 색상 판별 함수 구현**

```python
def is_yellow(cell) -> bool:
    ...

def is_gray(cell) -> bool:
    ...
```

Acceptance:

- `FFFF00`, `FFF2CC`, `FFD966`은 노란색으로 인식한다.
- `BFBFBF`, `C0C0C0`, `D9D9D9`, `808080`, `A6A6A6`은 회색으로 인식한다.

- [x] **Step 3: `export_parser_template()` 구현**

Requirements:

- 현재 PDF의 최대 5페이지를 읽는다.
- 기본 시트명은 `PDF`로 한다.
- `_metadata` 숨김 시트를 생성한다.
- 각 PDF 텍스트 셀마다 `page_index`, `row_index`, `column_index`, `x`, `y`, `text`를 metadata에 저장한다.
- `필드목록` 시트에 표준 필드 참고표를 추가한다.
- 스캔 PDF 등 `page.get_text("words")`가 비어 있으면 `get_page_rows()` fallback을 사용한다.

- [x] **Step 4: `read_parser_template()` 구현**

Requirements:

- `_metadata` 시트가 없으면 `ValueError`를 발생시킨다.
- 노란색 셀은 `TemplateAnnotations.field_cells`에 추가한다.
- 회색 셀은 `TemplateAnnotations.skip_keywords`에 추가한다.
- 노란색 셀 텍스트가 표준 필드명이 아니어도 버리지 않는다.
- `skip_keywords`는 중복 제거하되 순서를 유지한다.

- [x] **Step 5: 테스트 추가**

Tests:

- `test_read_parser_template_extracts_yellow_fields_and_gray_keywords`
- `test_read_parser_template_keeps_arbitrary_yellow_cell_names`
- `test_infer_standard_field_accepts_common_labels`

Verification:

```bash
python3 -m pytest tests/test_parser_template.py -q
```

---

## Task 2: `ParserBuilderDialog`를 다운로드/업로드 방식으로 변경

**Files:**
- Modify: `ui/parser_builder_dialog.py`

- [x] **Step 1: 기존 화면 내 PDF 그리드 제거**

Remove:

- `QSplitter`
- `QTableWidget` 미리보기
- 페이지 이전/다음 버튼
- 레이아웃 콤보박스
- 필드 매핑 콤보박스
- 회전 레이아웃 y 범위 입력 테이블

- [x] **Step 2: 새 입력 필드 유지/추가**

Keep:

- 증권사명
- 감지 키워드
- 날짜 정규식
- 시작 페이지
- 행/거래

Add:

- `포맷 파일 다운로드` 버튼
- `업로드` 버튼
- 업로드 결과 요약 `QTextEdit`

- [x] **Step 3: 다운로드 버튼 연결**

```python
def _download_template(self):
    path, _ = QFileDialog.getSaveFileName(...)
    export_parser_template(self._pages, path, max_pages=5)
```

Acceptance:

- 저장 경로가 비어 있으면 아무 작업도 하지 않는다.
- `.xlsx` 확장자가 없으면 자동으로 붙인다.
- 실패 시 `QMessageBox.critical`로 오류를 표시한다.

- [x] **Step 4: 업로드 버튼 연결**

```python
def _upload_template(self):
    path, _ = QFileDialog.getOpenFileName(...)
    annotations = read_parser_template(path)
```

Acceptance:

- 업로드 결과에 필드 셀 수, 각 필드 셀 위치, 무시 키워드 목록을 표시한다.
- 노란색 셀명은 표준 필드 변환 없이 그대로 표시한다.

- [x] **Step 5: 저장 로직 변경**

Requirements:

- 업로드된 `TemplateAnnotations`가 없으면 저장 불가.
- 노란색 필드 셀이 없으면 저장 불가.
- `DynamicParserConfig.layout_type`은 `"template"`로 저장한다.
- `FieldMapping.standard_field`에는 노란색 셀 텍스트를 그대로 저장한다.
- `source_text`에도 노란색 셀 텍스트를 저장한다.
- 회색 셀 텍스트는 `skip_keywords`로 저장한다.
- `date`로 추론 가능한 노란색 셀이 있으면 이를 기준으로 `row_offset`을 계산한다.

---

## Task 3: `parser_registry` template layout 지원

**Files:**
- Modify: `core/parser_registry.py`

- [x] **Step 1: `FieldMapping` 확장**

Add:

```python
page_index: int = 0
row_index: int = 0
x: float = 0.0
y: float = 0.0
source_text: str = ""
```

- [x] **Step 2: `template` layout 파싱 경로 추가**

Implementation:

```python
if _cfg.layout_type in {"table", "template"}:
    ...
```

- [x] **Step 3: 출력 컬럼명 정책 변경**

Requirement:

- `raw` dict key는 `FieldMapping.standard_field`를 그대로 사용한다.
- `standard_field` 값이 `입금금액`, `내가 원하는 컬럼`이면 변환 결과 컬럼도 그대로 사용된다.
- `Transaction` 생성용 표준 필드 값은 `infer_standard_field()`로 보조 추론한다.
- `Transaction.raw`에는 원본 `raw` dict를 그대로 넣는다.

---

## Task 4: 검증

- [x] **Step 1: 문법 검사**

```bash
python3 -m py_compile core/parser_template.py core/parser_registry.py ui/parser_builder_dialog.py
```

- [x] **Step 2: 관련 테스트 실행**

```bash
python3 -m pytest tests/test_parser_template.py tests/test_parser_registry.py -q
```

Expected:

```text
9 passed
```

- [x] **Step 3: 전체 테스트 실행**

```bash
python3 -m pytest tests/ -q
```

Expected/current:

```text
46 passed, 4 skipped
```

---

## Manual QA

- [ ] 앱 실행

```bash
python3 main.py
```

- [ ] PDF 추가 후 `파서 추가` 클릭
- [ ] `포맷 파일 다운로드`로 `.xlsx` 저장
- [ ] 엑셀에서 변환 결과 컬럼으로 쓸 셀을 노란색으로 표시
- [ ] 엑셀에서 무시할 키워드를 회색으로 표시
- [ ] 저장한 `.xlsx` 업로드
- [ ] 업로드 결과에 노란색 셀명이 그대로 표시되는지 확인
- [ ] 파서 저장 후 변환 실행
- [ ] 결과 엑셀 컬럼명이 노란색 셀명 그대로인지 확인

---

## Known Constraints

- 현재 template layout 런타임 파싱은 기존 table layout과 같은 행/컬럼 그룹 방식을 사용한다.
- PDF의 행/열 추출 구조가 다운로드 당시와 크게 달라지면 위치 기반 매핑이 어긋날 수 있다.
- 노란색 셀명은 중복될 경우 첫 번째 항목만 저장한다.
- 스캔 PDF는 `get_page_rows()` OCR fallback 품질에 의존한다.
