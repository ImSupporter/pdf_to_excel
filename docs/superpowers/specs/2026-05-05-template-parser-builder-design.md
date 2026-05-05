# 엑셀 포맷 기반 파서 생성 기능 설계 문서

**날짜:** 2026-05-05  
**상태:** 구현됨

---

## 1. 개요

기존 `ParserBuilderDialog`의 화면 내 PDF 그리드/콤보박스 매핑 방식을 제거하고, 사용자가 엑셀 파일에서 직접 셀을 색으로 표시해 파서를 생성하는 방식으로 변경한다.

목표는 다음과 같다.

- 프로그램이 현재 PDF의 최대 5페이지를 원본 배치에 가까운 엑셀 포맷 파일로 내보낸다.
- 사용자는 엑셀에서 변환 결과 컬럼으로 사용할 셀을 노란색으로 표시한다.
- 사용자는 파싱 시 무시할 키워드를 회색으로 표시한다.
- 업로드 시 프로그램은 색상, 셀 위치, 원본 텍스트를 읽어 동적 파서 설정으로 저장한다.
- 변환 결과는 표준 필드로 통합하지 않고, 노란색으로 표시한 셀명을 그대로 컬럼명으로 사용한다.

---

## 2. UX 흐름

```text
ParserSelectDialog
  -> [파서 추가]
  -> ParserBuilderDialog
       - 증권사명 입력
       - 감지 키워드 입력
       - 날짜 정규식 입력
       - 시작 페이지 / 행당 거래 수 입력
       - [포맷 파일 다운로드]
           -> 현재 PDF 최대 5페이지를 parser_format.xlsx로 저장
       - 사용자가 엑셀 편집
           -> 필드 셀: 노란색
           -> 무시 키워드: 회색
       - [업로드]
           -> 노란색 셀/회색 셀 추출
           -> 업로드 결과 요약 표시
       - [저장]
           -> DynamicParserConfig(layout_type="template") 저장
```

---

## 3. 색상 규칙

| 색상 | 의미 | 저장 위치 |
|---|---|---|
| 노란색 | 변환 결과에 포함할 필드 | `field_mappings` |
| 회색 | 파싱 시 무시할 키워드 | `skip_keywords` |

지원하는 노란색 RGB:

- `FFFF00`
- `FFF2CC`
- `FFD966`

지원하는 회색 RGB:

- `BFBFBF`
- `C0C0C0`
- `D9D9D9`
- `808080`
- `A6A6A6`

---

## 4. 포맷 파일 구조

### `PDF` 시트

사용자가 보는 편집 시트다.

- `A1`: 제목
- `A2`: 사용 안내
- `A4` 이후: PDF 페이지별 텍스트 셀
- 페이지 구분 행: `Page 1`, `Page 2`, ...
- 각 셀 값: PDF에서 추출한 원본 텍스트

### `_metadata` 시트

숨김 시트다. 사용자가 색칠한 엑셀 셀을 PDF 위치정보로 되돌리기 위해 사용한다.

컬럼:

| 컬럼 | 의미 |
|---|---|
| `sheet` | 표시 시트명 |
| `excel_row` | 엑셀 행 |
| `excel_col` | 엑셀 열 |
| `page_index` | PDF 페이지 인덱스 |
| `row_index` | PDF 행 인덱스 |
| `column_index` | PDF 행 내부 컬럼 인덱스 |
| `x` | PDF x 좌표 |
| `y` | PDF y 좌표 |
| `text` | 원본 셀 텍스트 |

### `필드목록` 시트

참고용 표준 필드 목록이다. 현재 저장 로직은 이 목록으로 필드명을 강제하지 않는다.

---

## 5. 데이터 모델

### `core/parser_template.py`

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

주요 함수:

| 함수 | 역할 |
|---|---|
| `export_parser_template(pages, output_path, max_pages=5)` | PDF 텍스트를 엑셀 포맷 파일로 내보낸다. |
| `read_parser_template(path)` | 노란색/회색 셀을 읽어 `TemplateAnnotations`를 반환한다. |
| `is_yellow(cell)` | 엑셀 셀이 필드 표시 색상인지 판단한다. |
| `is_gray(cell)` | 엑셀 셀이 무시 키워드 색상인지 판단한다. |
| `infer_standard_field(text)` | 내부 `Transaction` 보조값 계산을 위한 표준 필드 추론 함수다. |

### `core/parser_registry.py`

`FieldMapping`은 템플릿 기반 위치정보를 저장할 수 있도록 확장된다.

```python
@dataclass
class FieldMapping:
    standard_field: str
    column_index: int = 0
    row_offset: int = 0
    y_min: int = 0
    y_max: int = 0
    page_index: int = 0
    row_index: int = 0
    x: float = 0.0
    y: float = 0.0
    source_text: str = ""
```

템플릿 기반 파서는 `DynamicParserConfig.layout_type == "template"`로 저장된다. 런타임 파싱은 기존 table 파싱과 같은 행/컬럼 그룹 방식을 사용하되, 컬럼명은 노란색 셀의 `text`를 그대로 사용한다.

---

## 6. 변환 출력 정책

템플릿 기반 파서의 `raw` dict는 다음처럼 생성된다.

```python
raw[노란색_셀명] = 추출된_값
```

예를 들어 사용자가 노란색 셀명을 `입금금액`, `내가 원하는 컬럼`으로 지정하면 변환 결과 엑셀 컬럼도 그대로 `입금금액`, `내가 원하는 컬럼`이 된다.

표준 필드 통합은 하지 않는다. 다만 `Transaction` 객체 생성 시 `거래일자`, `종목명`, `수량` 같은 알려진 이름은 내부 보조값으로 추론한다. 출력에는 영향을 주지 않는다.

---

## 7. 유효성 검사

`ParserBuilderDialog._save()`는 다음을 검사한다.

- 증권사명 필수
- 감지 키워드 1개 이상 필수
- 업로드된 포맷 파일 필수
- 노란색으로 표시된 필드 셀 1개 이상 필수

---

## 8. 테스트 범위

| 테스트 | 목적 |
|---|---|
| `test_read_parser_template_extracts_yellow_fields_and_gray_keywords` | 노란색 셀과 회색 셀을 구분해 읽는지 확인 |
| `test_read_parser_template_keeps_arbitrary_yellow_cell_names` | 임의 컬럼명이 표준 필드가 아니어도 유지되는지 확인 |
| `test_infer_standard_field_accepts_common_labels` | 내부 보조 추론 alias 확인 |

전체 회귀 확인:

```bash
python3 -m pytest tests/ -q
```

현재 결과:

```text
46 passed, 4 skipped
```
