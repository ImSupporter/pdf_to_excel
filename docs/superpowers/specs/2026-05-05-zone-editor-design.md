# Zone Editor — Parser Creator Design

## Goal

Samsung PDF처럼 헤더 텍스트가 여러 줄로 wrapping되어 자동 컬럼 탐지가 실패하는 경우를 해결하기 위해, 사용자가 PDF 위에서 직접 컬럼 x 경계·행 y 경계·헤더/데이터 영역을 시각적으로 지정하고 파서를 생성하는 기능.

---

## 전체 플로우

```
메인 창에서 PDF 로드 완료
  → ParserBuilderDialog(pages, parent) 오픈
    ① 폼 입력 (증권사명, 키워드, 날짜형식, 헤더 시작 키워드, 시작 페이지)
    → "영역 지정" 클릭
      ② ZoneEditorWidget 활성화 — PDF pixmap 렌더링 + 선 편집
    → "필드 추출" 클릭
      extract_fields(zone_spec, page) → list[FieldMapping]
      ③ FieldListWidget 활성화 — 필드 카드 목록 표시
    → "확인" 클릭
      zone_spec_to_config(zone_spec, field_mappings) → DynamicParserConfig
      parsers.json 저장 → dialog 닫힘
```

Excel 템플릿(export_parser_template / read_parser_template) 플로우는 별도로 유지되며 이 기능과 관계없음.

---

## 파일 구조

### 신규

**`core/zone_spec.py`**
- `ZoneSpec` 데이터클래스
- `extract_fields(zone_spec, page)` → `list[FieldMapping]`
- `zone_spec_to_config(zone_spec, field_mappings)` → `DynamicParserConfig`

### 수정

**`core/parser_registry.py`**
- `FieldMapping`: `x: float` → `x_min: float, x_max: float`
- `build_class()` 매칭 로직: `abs(cell_x - fm.x) <= X_TOLERANCE` → `fm.x_min <= cell_x <= fm.x_max`
- `X_TOLERANCE` 상수 제거
- `load()` 하위 호환: 구 JSON에 `x` 필드만 있으면 `x_min = x - 50.0, x_max = x + 50.0`으로 변환

**`ui/parser_builder_dialog.py`**
- 전면 재작성 (아래 상세 참조)

### 변경 없음

`core/parser_template.py`, `DynamicParserConfig` 구조(필드 추가/제거 없음), `parsers/` 내장 파서

---

## ZoneSpec 데이터 구조

```python
@dataclass
class ZoneSpec:
    # 폼 입력값
    broker_name: str
    detection_keywords: list[str]
    date_format: str                    # "yyyy/mm/dd"
    header_start_keyword: str
    start_page: int

    # 빨간 세로선 — 컬럼 x 경계
    column_xs: list[float]              # 정렬된 x값. 스트립 = [0,xs[0]], [xs[0],xs[1]], ..., [xs[-1], page_width]

    # 파란 가로선 — 컬럼별 행 y 경계
    row_ys_per_col: dict[int, list[float]]  # 컬럼 인덱스 → 정렬된 y 리스트

    # 영역 마커 4개
    header_start_y: float
    header_end_y: float
    data_start_y: float
    data_end_y: float
```

---

## FieldMapping 변경

```python
@dataclass
class FieldMapping:
    standard_field: str
    row_offset: int = 0
    x_min: float = 0.0      # 컬럼 스트립 왼쪽 경계
    x_max: float = 0.0      # 컬럼 스트립 오른쪽 경계
    y_min: float = 0.0      # 데이터 시작 y
    y_max: float = 0.0      # 데이터 끝 y
```

**col_offset 불필요 이유:** 컬럼은 x_min/x_max 절대 좌표로 직접 명시. row_offset은 트랜잭션 그룹 내 상대 순서가 필요해 존재하지만, 컬럼은 좌표 범위 자체가 식별자 역할.

---

## ParserBuilderDialog 변경 상세

### 생성자

```python
# 기존
ParserBuilderDialog(parent)

# 변경 후 — 메인 창에서 이미 로드된 pages 전달
ParserBuilderDialog(pages: list[fitz.Page], parent)
```

호출 지점: `ui/parser_select_dialog.py`의 "새 파서 추가" 버튼.
main_window → parser_select_dialog → ParserBuilderDialog 순으로 pages 전달.

### 제거 항목

- PDF 파일 선택 위젯 (내부 filedialog)
- 좌측 PDF 미리보기 테이블
- "포맷 파일 다운로드" 버튼
- "파서 파일 업로드" 버튼
- `rows_per_tx` 스핀박스
- `layout_type` 선택 (가로/세로)
- `data_start_keyword` 입력

### 추가 항목

- `header_start_keyword` 입력
- "영역 지정" 버튼
- `ZoneEditorWidget` (PDF pixmap + 4종 선)
- "필드 추출" 버튼
- `FieldListWidget` (추출 필드 카드 목록)
- "확인" 버튼

### 레이아웃

```
QHBoxLayout (또는 QSplitter)
├── Panel 1 — FormWidget        (고정 너비 ~220px, 항상 표시)
├── Panel 2 — ZoneEditorWidget  (flex, "영역 지정" 클릭 후 활성화)
└── Panel 3 — FieldListWidget   (고정 너비 ~190px, "필드 추출" 후 활성화)
```

### 패널 상태 전환

```python
# 초기 상태
zone_editor.setEnabled(False)
field_list.setEnabled(False)
confirm_btn.setEnabled(False)

# "영역 지정" 클릭
def _on_open_zone_editor():
    zone_editor.load_page(pages[start_page - 1])
    zone_editor.setEnabled(True)

# "필드 추출" 클릭
def _on_extract_fields():
    zone_spec = _build_zone_spec()
    fields = extract_fields(zone_spec, pages[start_page - 1])
    field_list.populate(fields)
    field_list.setEnabled(True)
    confirm_btn.setEnabled(True)

# "확인" 클릭
def _on_confirm():
    config = zone_spec_to_config(zone_spec, fields)
    save_parser(config)   # parsers.json에 추가
    self.accept()
```

---

## ZoneEditorWidget 선 동작

| 선 종류 | 추가 | 이동 | 삭제 |
|---------|------|------|------|
| 빨간 세로선 (컬럼 x) | 툴바 "＋세로선" 클릭 후 캔버스 클릭 | ↔ 드래그 | 우클릭 |
| 파란 가로선 (컬럼별 행 y) | 툴바 "＋가로선" 클릭 후 컬럼 스트립 내 클릭 (해당 컬럼에만 생성) | ↕ 드래그 | 우클릭 |
| 주황 가로선 (헤더 시작/끝) | 초기부터 2개 고정, 추가 불가 | ↕ 드래그 (헤더 끝 > 헤더 시작 강제) | 삭제 불가 |
| 초록 가로선 (데이터 시작/끝) | 초기부터 2개 고정, 추가 불가 | ↕ 드래그 (데이터 끝 > 데이터 시작 강제) | 삭제 불가 |

**초기값:** `header_start_keyword`로 첫 번째 매칭 행을 찾아 `header_start_y` 자동 설정. 나머지 3개 마커는 페이지 비율 기준으로 초기 배치.

---

## extract_fields() 로직

```python
def extract_fields(zone_spec: ZoneSpec, page: fitz.Page) -> list[FieldMapping]:
    page_width = page.rect.width
    # 컬럼 스트립 계산
    xs = sorted(zone_spec.column_xs)
    boundaries = [0.0] + xs + [page_width]
    column_strips = [(boundaries[i], boundaries[i+1]) for i in range(len(boundaries)-1)]

    words = page.get_text("words")  # (x0, y0, x1, y1, text, ...)
    field_mappings = []

    for col_idx, (x0, x1) in enumerate(column_strips):
        row_ys = sorted(zone_spec.row_ys_per_col.get(col_idx, []))
        y_slots = _split_by_ys(zone_spec.header_start_y, zone_spec.header_end_y, row_ys)

        for row_offset, (y0, y1) in enumerate(y_slots):
            text = _collect_text(words, x0, x1, y0, y1)
            if not text.strip():
                continue
            std_field = infer_standard_field(text)
            field_mappings.append(FieldMapping(
                standard_field=std_field,
                row_offset=row_offset,
                x_min=x0,
                x_max=x1,
                y_min=zone_spec.data_start_y,
                y_max=zone_spec.data_end_y,
            ))

    return field_mappings
```

`_split_by_ys(y_start, y_end, ys)`: `[y_start] + ys + [y_end]`로 구간 리스트 생성.  
`_collect_text(words, x0, x1, y0, y1)`: words에서 셀 중심이 해당 범위 내인 텍스트 공백 결합.

---

## zone_spec_to_config() 로직

```python
def zone_spec_to_config(
    zone_spec: ZoneSpec,
    field_mappings: list[FieldMapping],
) -> DynamicParserConfig:
    return DynamicParserConfig(
        broker_name=zone_spec.broker_name,
        detection_keywords=zone_spec.detection_keywords,
        date_re=date_format_to_re(zone_spec.date_format),
        layout_type="header_mapped",
        start_page=zone_spec.start_page,
        skip_keywords=[],
        field_mappings=field_mappings,
    )
```

---

## 테스트 전략

- `test_zone_spec.py`:
  - `extract_fields()` — 가상 page words로 FieldMapping 생성 검증
  - `zone_spec_to_config()` — DynamicParserConfig 필드값 검증
  - `_split_by_ys()` — 경계 분할 검증
- `test_parser_registry.py`:
  - `x_min`/`x_max` 매칭 검증
  - 구 JSON (`x` 필드) 하위 호환 로드 검증
