# Zone Editor Parser Creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF 위에서 컬럼/행/영역 경계를 시각적으로 지정해 동적 파서를 생성하는 단일 창 3-패널 UI를 구현한다.

**Architecture:** FieldMapping의 `x` 단일 좌표를 `x_min/x_max` 범위로 교체하고, ZoneSpec 데이터클래스와 extract_fields() 함수를 새로 만들어 Zone 에디터 데이터를 DynamicParserConfig로 변환한다. ParserBuilderDialog를 3-패널 단일 창으로 전면 재작성한다 (FormPanel + ZoneEditorWidget + FieldListPanel).

**Tech Stack:** Python 3.11+, PyQt6, PyMuPDF (fitz), pytest, dataclasses

---

## File Map

| 파일 | 작업 |
|------|------|
| `core/parser_registry.py` | 수정 — FieldMapping x→x_min/x_max, build_class 매칭, load() 하위호환 |
| `tests/test_parser_registry.py` | 수정 — x→x_min/x_max 반영, 하위호환 테스트 업데이트 |
| `core/zone_spec.py` | 신규 — ZoneSpec, extract_fields(), zone_spec_to_config() |
| `tests/test_zone_spec.py` | 신규 |
| `ui/zone_editor_widget.py` | 신규 — PDF 렌더링 + 4종 드래그 가능 선 |
| `ui/parser_builder_dialog.py` | 전면 재작성 — 3-패널 단일 창 |

---

### Task 1: FieldMapping x → x_min/x_max

**배경:** 현재 `FieldMapping.x: float`는 컬럼 중심 x좌표이고, `build_class()`에서 `abs(cell_x - fm.x) <= X_TOLERANCE(50.0)` 로 셀을 매칭한다. 이를 `x_min/x_max` 범위 매칭으로 변경해 컬럼 경계를 직접 사용한다.

**Files:**
- Modify: `core/parser_registry.py`
- Modify: `tests/test_parser_registry.py`

---

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_parser_registry.py` 파일 상단 기존 `test_field_mapping_roundtrip` 함수를 아래로 교체하고, 하위 호환 테스트도 업데이트한다.

```python
def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", row_offset=0, x_min=10.0, x_max=90.0)
    assert fm.standard_field == "date"
    assert fm.row_offset == 0
    assert fm.x_min == 10.0
    assert fm.x_max == 90.0
```

기존 `test_dynamic_parser_config_roundtrip` 내 `FieldMapping` 생성 코드를 교체:
```python
# 기존
FieldMapping(standard_field="date", row_offset=0, x=50.0),
FieldMapping(standard_field="amount", row_offset=0, x=300.0),
# 변경 후
FieldMapping(standard_field="date", row_offset=0, x_min=0.0, x_max=100.0),
FieldMapping(standard_field="amount", row_offset=0, x_min=250.0, x_max=350.0),
```
그리고 assert 부분도:
```python
# 기존
assert loaded[0].field_mappings[1].x == 300.0
# 변경 후
assert loaded[0].field_mappings[1].x_min == 250.0
assert loaded[0].field_mappings[1].x_max == 350.0
```

기존 `test_load_ignores_unknown_fields_in_old_json` 내 assert를 교체:
```python
# 기존
assert loaded[0].field_mappings[0].x == 50.0
# 변경 후 — 구 JSON의 x=50.0은 x_min=0.0, x_max=100.0으로 변환돼야 함
assert loaded[0].field_mappings[0].x_min == 0.0
assert loaded[0].field_mappings[0].x_max == 100.0
```

`test_header_mapped_*` 4개 테스트의 `FieldMapping` 생성 코드를 모두 교체:
```python
# 기존 패턴
FieldMapping(standard_field="date",   row_offset=0, x=50.0),
FieldMapping(standard_field="name",   row_offset=0, x=200.0),
FieldMapping(standard_field="amount", row_offset=0, x=350.0),

# 변경 패턴 — mock_rows에서 cell_x가 x_min <= cell_x <= x_max 를 만족하도록 설정
FieldMapping(standard_field="date",   row_offset=0, x_min=0.0,   x_max=100.0),
FieldMapping(standard_field="name",   row_offset=0, x_min=150.0, x_max=250.0),
FieldMapping(standard_field="amount", row_offset=0, x_min=300.0, x_max=400.0),
```

`test_header_mapped_two_header_rows_separate_fields` 는 같은 x에 row_offset만 다른 구조이므로:
```python
FieldMapping(standard_field="date", row_offset=0, x_min=0.0, x_max=100.0),
FieldMapping(standard_field="type", row_offset=0, x_min=100.0, x_max=200.0),
FieldMapping(standard_field="name",   row_offset=1, x_min=0.0, x_max=100.0),
FieldMapping(standard_field="amount", row_offset=1, x_min=100.0, x_max=200.0),
```

`test_build_class_returns_base_parser_subclass` 도 교체:
```python
FieldMapping(standard_field="date", row_offset=0, x_min=0.0, x_max=100.0),
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_parser_registry.py -x -q 2>&1 | head -30
```
Expected: `AttributeError: FieldMapping has no field 'x_min'` 또는 `TypeError` 류

- [ ] **Step 3: FieldMapping 수정**

`core/parser_registry.py`의 `FieldMapping` 클래스를 아래로 교체:

```python
@dataclass
class FieldMapping:
    standard_field: str
    row_offset: int = 0
    x_min: float = 0.0   # 컬럼 스트립 왼쪽 경계 (PDF 좌표)
    x_max: float = 0.0   # 컬럼 스트립 오른쪽 경계 (PDF 좌표)
    y_min: float = 0.0
    y_max: float = 0.0
```

- [ ] **Step 4: load() 하위 호환 추가**

`load()` 함수 내 FieldMapping 생성 부분을 아래로 교체:

```python
valid_fm = {f.name for f in dataclasses.fields(FieldMapping)}
configs = []
for item in data:
    raw_mappings = item.pop("field_mappings", [])
    mappings = []
    for m in raw_mappings:
        fm_data = {k: v for k, v in m.items() if k in valid_fm}
        # 구 JSON: x 필드만 있고 x_min/x_max 없음 → 변환
        if "x" in m and "x_min" not in m and "x_max" not in m:
            fm_data["x_min"] = m["x"] - 50.0
            fm_data["x_max"] = m["x"] + 50.0
        mappings.append(FieldMapping(**fm_data))
    cfg_kwargs = {k: v for k, v in item.items() if k in valid_cfg}
    configs.append(DynamicParserConfig(**cfg_kwargs, field_mappings=mappings))
return configs
```

- [ ] **Step 5: build_class() 매칭 로직 수정**

`build_class()` 내 `header_mapped` 분기를 찾아 아래 두 부분을 수정한다.

**5a. `_date_x` 변수 교체** (함수 상단, `def parse(self, pages):` 바로 아래):

```python
# 기존
_date_fm = next(
    (fm for fm in _cfg.field_mappings if fm.standard_field == "date"), None
)
_date_x = _date_fm.x if _date_fm else None
_date_compiled = _re_mod.compile(_cfg.date_re)
X_TOLERANCE = 50.0

# 변경 후
_date_fm = next(
    (fm for fm in _cfg.field_mappings if fm.standard_field == "date"), None
)
_date_x_min = _date_fm.x_min if _date_fm else None
_date_x_max = _date_fm.x_max if _date_fm else None
_date_compiled = _re_mod.compile(_cfg.date_re)
```

**5b. anchor 탐지 로직 교체** (is_anchor 블록):

```python
# 기존
is_anchor = False
if _date_x is not None:
    closest = min(row_cells, key=lambda c: abs(c[0] - _date_x))
    if _date_compiled.match(closest[1]):
        is_anchor = True
if not is_anchor and any(_date_compiled.match(t) for _, t in row_cells):
    is_anchor = True

# 변경 후
is_anchor = False
if _date_x_min is not None:
    date_cells = [c for c in row_cells if _date_x_min <= c[0] <= _date_x_max]
    if date_cells and _date_compiled.match(date_cells[0][1]):
        is_anchor = True
if not is_anchor and any(_date_compiled.match(t) for _, t in row_cells):
    is_anchor = True
```

**5c. 셀 매칭 로직 교체** (for cell_x, cell_text 루프):

```python
# 기존
for cell_x, cell_text in row_cells:
    best = min(candidates, key=lambda fm: abs(fm.x - cell_x))
    if abs(best.x - cell_x) > X_TOLERANCE:
        continue
    field = best.standard_field
    raw[field] = (
        raw[field] + " " + cell_text if raw.get(field) else cell_text
    )

# 변경 후
for cell_x, cell_text in row_cells:
    matching = [fm for fm in candidates if fm.x_min <= cell_x <= fm.x_max]
    if not matching:
        continue
    field = matching[0].standard_field
    raw[field] = (
        raw[field] + " " + cell_text if raw.get(field) else cell_text
    )
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_parser_registry.py -v 2>&1 | tail -20
```
Expected: 전체 PASSED

- [ ] **Step 7: 전체 테스트 확인**

```bash
python3 -m pytest tests/ -q --ignore=tests/test_integration.py 2>&1 | tail -10
```
Expected: 기존 테스트 모두 통과 (integration 제외)

- [ ] **Step 8: 커밋**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "refactor: replace FieldMapping.x with x_min/x_max range matching"
```

---

### Task 2: core/zone_spec.py

**배경:** ZoneSpec 데이터클래스와 두 함수를 담는 새 파일. `extract_fields()`는 ZoneSpec의 좌표로 PDF 헤더 셀을 읽어 FieldMapping 리스트를 만든다. `zone_spec_to_config()`는 FieldMapping 리스트를 받아 DynamicParserConfig를 반환한다.

**Files:**
- Create: `core/zone_spec.py`
- Create: `tests/test_zone_spec.py`

---

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_zone_spec.py` 생성:

```python
from unittest.mock import MagicMock


def test_split_by_ys_no_splits():
    from core.zone_spec import _split_by_ys
    result = _split_by_ys(10.0, 50.0, [])
    assert result == [(10.0, 50.0)]


def test_split_by_ys_one_split():
    from core.zone_spec import _split_by_ys
    result = _split_by_ys(10.0, 50.0, [30.0])
    assert result == [(10.0, 30.0), (30.0, 50.0)]


def test_split_by_ys_ignores_out_of_range():
    from core.zone_spec import _split_by_ys
    # y=5 < header_start=10, y=60 > header_end=50 → 무시
    result = _split_by_ys(10.0, 50.0, [5.0, 30.0, 60.0])
    assert result == [(10.0, 30.0), (30.0, 50.0)]


def test_collect_text_picks_cells_in_range():
    from core.zone_spec import _collect_text
    # words: (x0, y0, x1, y1, text, block_no, line_no, word_no)
    words = [
        (5.0,  10.0, 55.0, 20.0, "거래일자", 0, 0, 0),
        (60.0, 10.0, 110.0, 20.0, "거래명",  0, 0, 1),
        (200.0, 10.0, 250.0, 20.0, "outside", 0, 0, 2),
    ]
    result = _collect_text(words, 0.0, 120.0, 5.0, 25.0)
    assert "거래일자" in result
    assert "거래명" in result
    assert "outside" not in result


def test_collect_text_empty_when_no_match():
    from core.zone_spec import _collect_text
    words = [(200.0, 10.0, 250.0, 20.0, "outside", 0, 0, 0)]
    result = _collect_text(words, 0.0, 100.0, 5.0, 25.0)
    assert result == ""


def test_extract_fields_two_columns_no_hlines():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 300.0
    mock_page.rect.height = 400.0
    mock_page.get_text.return_value = [
        # col 0: 0~100, header y: 10~40
        (10.0, 15.0, 80.0, 25.0, "거래일자", 0, 0, 0),
        # col 1: 100~300, header y: 10~40
        (110.0, 15.0, 200.0, 25.0, "거래명", 0, 0, 1),
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[100.0],
        row_ys_per_col={},
        header_start_y=10.0,
        header_end_y=40.0,
        data_start_y=45.0,
        data_end_y=380.0,
    )
    fields = extract_fields(spec, mock_page)

    assert len(fields) == 2
    assert fields[0].x_min == 0.0
    assert fields[0].x_max == 100.0
    assert fields[0].y_min == 45.0
    assert fields[0].y_max == 380.0
    assert fields[0].row_offset == 0
    assert fields[1].x_min == 100.0
    assert fields[1].x_max == 300.0


def test_extract_fields_skips_empty_slots():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 200.0
    mock_page.rect.height = 300.0
    # col 1 (100~200) has no text in header → should be skipped
    mock_page.get_text.return_value = [
        (10.0, 15.0, 80.0, 25.0, "거래일자", 0, 0, 0),
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[100.0],
        row_ys_per_col={},
        header_start_y=10.0,
        header_end_y=40.0,
        data_start_y=45.0,
        data_end_y=280.0,
    )
    fields = extract_fields(spec, mock_page)
    assert len(fields) == 1  # col 1 empty → skipped


def test_extract_fields_two_row_offsets():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 200.0
    mock_page.rect.height = 300.0
    mock_page.get_text.return_value = [
        (10.0, 12.0, 80.0, 22.0, "거래일자", 0, 0, 0),  # row_offset=0
        (10.0, 32.0, 80.0, 42.0, "거래번호", 0, 0, 1),  # row_offset=1
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[],
        row_ys_per_col={0: [27.0]},  # split at y=27 → slots (10,27) and (27,50)
        header_start_y=10.0,
        header_end_y=50.0,
        data_start_y=55.0,
        data_end_y=280.0,
    )
    fields = extract_fields(spec, mock_page)
    assert len(fields) == 2
    assert fields[0].row_offset == 0
    assert fields[1].row_offset == 1


def test_zone_spec_to_config():
    from core.zone_spec import ZoneSpec, zone_spec_to_config
    from core.parser_registry import FieldMapping

    spec = ZoneSpec(
        broker_name="삼성증권",
        detection_keywords=["삼성"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[],
        row_ys_per_col={},
        header_start_y=0.0,
        header_end_y=50.0,
        data_start_y=55.0,
        data_end_y=500.0,
    )
    fms = [
        FieldMapping(standard_field="date", row_offset=0,
                     x_min=0.0, x_max=100.0, y_min=55.0, y_max=500.0)
    ]
    config = zone_spec_to_config(spec, fms)

    assert config.broker_name == "삼성증권"
    assert config.layout_type == "header_mapped"
    assert config.date_re == r"\d{4}/\d{2}/\d{2}"
    assert config.start_page == 0
    assert config.skip_keywords == []
    assert config.field_mappings[0].x_min == 0.0
    assert config.field_mappings[0].x_max == 100.0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_zone_spec.py -x -q 2>&1 | head -10
```
Expected: `ModuleNotFoundError: No module named 'core.zone_spec'`

- [ ] **Step 3: core/zone_spec.py 구현**

`core/zone_spec.py` 생성:

```python
from dataclasses import dataclass
import fitz
from core.parser_registry import FieldMapping, DynamicParserConfig
from core.parser_template import date_format_to_re, infer_standard_field


@dataclass
class ZoneSpec:
    broker_name: str
    detection_keywords: list[str]
    date_format: str                      # "yyyy/mm/dd" 형식
    header_start_keyword: str
    start_page: int

    column_xs: list[float]                # 빨간 세로선 x좌표 (PDF 좌표, 정렬 불필요)
    row_ys_per_col: dict[int, list[float]]  # 컬럼 인덱스 → 파란선 y 리스트

    header_start_y: float
    header_end_y: float
    data_start_y: float
    data_end_y: float


def _split_by_ys(
    y_start: float, y_end: float, ys: list[float]
) -> list[tuple[float, float]]:
    """header_start~header_end 구간을 ys로 분할해 (y0, y1) 슬롯 리스트 반환."""
    interior = sorted(y for y in ys if y_start < y < y_end)
    points = [y_start] + interior + [y_end]
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _collect_text(
    words: list, x0: float, x1: float, y0: float, y1: float
) -> str:
    """page.get_text('words') 결과에서 (x0,y0,x1,y1) 범위 내 텍스트를 공백 결합."""
    result = []
    for w in words:
        cx = (w[0] + w[2]) / 2
        cy = (w[1] + w[3]) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            result.append(w[4])
    return " ".join(result)


def extract_fields(zone_spec: ZoneSpec, page: fitz.Page) -> list[FieldMapping]:
    """ZoneSpec의 선 좌표로 헤더 셀을 읽어 FieldMapping 리스트를 반환."""
    page_width = page.rect.width
    xs = sorted(zone_spec.column_xs)
    boundaries = [0.0] + xs + [page_width]
    column_strips = [
        (boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)
    ]

    words = page.get_text("words")
    field_mappings: list[FieldMapping] = []

    for col_idx, (x0, x1) in enumerate(column_strips):
        row_ys = sorted(zone_spec.row_ys_per_col.get(col_idx, []))
        y_slots = _split_by_ys(
            zone_spec.header_start_y, zone_spec.header_end_y, row_ys
        )

        for row_offset, (y0, y1) in enumerate(y_slots):
            text = _collect_text(words, x0, x1, y0, y1)
            if not text.strip():
                continue
            std_field = infer_standard_field(text) or text.strip()
            field_mappings.append(
                FieldMapping(
                    standard_field=std_field,
                    row_offset=row_offset,
                    x_min=x0,
                    x_max=x1,
                    y_min=zone_spec.data_start_y,
                    y_max=zone_spec.data_end_y,
                )
            )

    return field_mappings


def zone_spec_to_config(
    zone_spec: ZoneSpec,
    field_mappings: list[FieldMapping],
) -> DynamicParserConfig:
    """ZoneSpec + FieldMapping 리스트 → DynamicParserConfig."""
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

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_zone_spec.py -v 2>&1 | tail -20
```
Expected: 전체 PASSED

- [ ] **Step 5: 전체 테스트 확인**

```bash
python3 -m pytest tests/ -q --ignore=tests/test_integration.py 2>&1 | tail -10
```
Expected: 기존 테스트 모두 통과

- [ ] **Step 6: 커밋**

```bash
git add core/zone_spec.py tests/test_zone_spec.py
git commit -m "feat: add ZoneSpec dataclass, extract_fields, zone_spec_to_config"
```

---

### Task 3: ui/zone_editor_widget.py

**배경:** PDF 페이지를 배경으로 렌더링하고, 4종의 드래그 가능한 선을 오버레이하는 커스텀 QWidget. PyQt6 위젯은 표시 장치 없이 단위 테스트가 불가능하므로 이 태스크에는 단위 테스트를 작성하지 않는다.

**Files:**
- Create: `ui/zone_editor_widget.py`

---

- [ ] **Step 1: ui/zone_editor_widget.py 생성**

```python
import fitz
from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage

_RENDER_SCALE = 1.5   # PDF → pixmap 배율
_HIT_PX = 8           # 선 클릭 인식 반경 (픽셀)


class ZoneEditorWidget(QWidget):
    """PDF 페이지 위에 컬럼/행/영역 경계선을 그리는 위젯.

    좌표계: 내부적으로 PDF 좌표(fitz 단위)로 저장. 렌더링 시 * _RENDER_SCALE.
    """

    MODE_NONE = 0
    MODE_ADD_V = 1   # 빨간 세로선 추가 대기
    MODE_ADD_H = 2   # 파란 가로선 추가 대기

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._page_w = 0.0
        self._page_h = 0.0
        self._mode = self.MODE_NONE

        self._vlines: list[float] = []             # 빨간 세로선 x (PDF 좌표)
        self._hlines: dict[int, list[float]] = {}  # col_idx → [y] (PDF 좌표)
        self._header_start = 0.0
        self._header_end = 0.0
        self._data_start = 0.0
        self._data_end = 0.0

        # 드래그 상태: None 또는 ("v", idx) | ("h", col, idx) | ("hs",) | ("he",) | ("ds",) | ("de",)
        self._drag: tuple | None = None

        self.setMouseTracking(True)

    # ── 공개 메서드 ──────────────────────────────────────────────────

    def load_page(self, page: fitz.Page, header_start_keyword: str = "") -> None:
        """페이지를 pixmap으로 렌더링하고 초기 영역 마커를 설정한다."""
        mat = fitz.Matrix(_RENDER_SCALE, _RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat)
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride,
            QImage.Format.Format_RGB888,
        )
        self._pixmap = QPixmap.fromImage(img)
        self._page_w = page.rect.width
        self._page_h = page.rect.height
        self.setFixedSize(pix.width, pix.height)

        h = self._page_h
        self._header_start = 0.0
        self._header_end = h * 0.25
        self._data_start = h * 0.28
        self._data_end = h * 0.95

        if header_start_keyword:
            for w in page.get_text("words"):
                if header_start_keyword in w[4]:
                    self._header_start = max(0.0, w[1] - 3.0)
                    self._header_end = min(h, w[1] + h * 0.20)
                    self._data_start = min(h, self._header_end + 5.0)
                    break

        self._vlines.clear()
        self._hlines.clear()
        self._drag = None
        self.update()

    def set_mode(self, mode: int) -> None:
        self._mode = mode

    def reset(self) -> None:
        h = self._page_h
        self._vlines.clear()
        self._hlines.clear()
        self._header_start = 0.0
        self._header_end = h * 0.25
        self._data_start = h * 0.28
        self._data_end = h * 0.95
        self.update()

    def get_zone_data(self) -> dict:
        """현재 선 상태를 PDF 좌표 딕셔너리로 반환 (ZoneSpec 생성에 사용)."""
        return {
            "column_xs": sorted(self._vlines),
            "row_ys_per_col": {k: sorted(v) for k, v in self._hlines.items()},
            "header_start_y": self._header_start,
            "header_end_y": self._header_end,
            "data_start_y": self._data_start,
            "data_end_y": self._data_end,
        }

    # ── 좌표 변환 ────────────────────────────────────────────────────

    def _s(self, pdf_val: float) -> int:
        return round(pdf_val * _RENDER_SCALE)

    def _p(self, screen_val: float) -> float:
        return screen_val / _RENDER_SCALE

    def _col_at(self, pdf_x: float) -> int:
        """pdf_x가 속하는 컬럼 인덱스 반환."""
        for i, x in enumerate(sorted(self._vlines)):
            if pdf_x < x:
                return i
        return len(self._vlines)

    # ── 렌더링 ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._pixmap is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)

        w = self._pixmap.width()
        h = self._pixmap.height()

        # 헤더/데이터 영역 반투명 배경
        hs = self._s(self._header_start)
        he = self._s(self._header_end)
        ds = self._s(self._data_start)
        de = self._s(self._data_end)
        p.fillRect(0, hs, w, max(1, he - hs), QColor(251, 146, 60, 40))
        p.fillRect(0, ds, w, max(1, de - ds), QColor(22, 163, 74, 20))

        # 빨간 세로선
        p.setPen(QPen(QColor("#ef4444"), 2))
        for vx in self._vlines:
            sx = self._s(vx)
            p.drawLine(sx, 0, sx, h)

        # 파란 가로선 (컬럼별)
        p.setPen(QPen(QColor("#3b82f6"), 2))
        sorted_v = sorted(self._vlines)
        bx = [0] + [self._s(x) for x in sorted_v] + [w]
        for col_idx, ys in self._hlines.items():
            if col_idx >= len(bx) - 1:
                continue
            for vy in ys:
                sy = self._s(vy)
                p.drawLine(bx[col_idx], sy, bx[col_idx + 1], sy)

        # 주황 영역 마커 (헤더 시작/끝)
        pen_orange = QPen(QColor("#f97316"), 2)
        for yval, label, above in [
            (self._header_start, "헤더 시작 ↕", False),
            (self._header_end,   "헤더 끝 ↕",   True),
        ]:
            sy = self._s(yval)
            p.setPen(pen_orange)
            p.drawLine(0, sy, w, sy)
            lx, ly = 2, (sy - 16 if above else sy + 2)
            p.fillRect(lx, ly, 68, 14, QColor("#f97316"))
            p.setPen(Qt.GlobalColor.white)
            p.drawText(lx, ly, 68, 14, Qt.AlignmentFlag.AlignCenter, label)

        # 초록 영역 마커 (데이터 시작/끝)
        pen_green = QPen(QColor("#16a34a"), 2)
        for yval, label, above in [
            (self._data_start, "↕ 데이터 시작", True),
            (self._data_end,   "↕ 데이터 끝",   True),
        ]:
            sy = self._s(yval)
            p.setPen(pen_green)
            p.drawLine(0, sy, w, sy)
            lx, ly = w - 80, sy - 16
            p.fillRect(lx, ly, 78, 14, QColor("#16a34a"))
            p.setPen(Qt.GlobalColor.white)
            p.drawText(lx, ly, 78, 14, Qt.AlignmentFlag.AlignCenter, label)

        p.end()

    # ── 마우스 이벤트 ────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._pixmap is None:
            return
        sx = event.position().x()
        sy = event.position().y()
        px, py = self._p(sx), self._p(sy)

        if event.button() == Qt.MouseButton.RightButton:
            return  # contextMenuEvent 에서 처리

        if self._mode == self.MODE_ADD_V:
            self._vlines.append(max(0.0, min(self._page_w, px)))
            # 모드 유지 — 버튼 토글로 해제 (연속 추가 가능)
            self.update()
            return

        if self._mode == self.MODE_ADD_H:
            col = self._col_at(px)
            self._hlines.setdefault(col, []).append(
                max(0.0, min(self._page_h, py))
            )
            # 모드 유지 — 버튼 토글로 해제
            self.update()
            return

        self._drag = self._find_target(sx, sy)

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        sx = event.position().x()
        sy = event.position().y()
        px, py = self._p(sx), self._p(sy)
        tag = self._drag[0]

        if tag == "v":
            self._vlines[self._drag[1]] = max(0.0, min(self._page_w, px))
        elif tag == "hs":
            self._header_start = max(0.0, min(self._header_end - 1, py))
        elif tag == "he":
            self._header_end = max(self._header_start + 1,
                                   min(self._data_start - 1, py))
        elif tag == "ds":
            self._data_start = max(self._header_end + 1,
                                   min(self._data_end - 1, py))
        elif tag == "de":
            self._data_end = max(self._data_start + 1, min(self._page_h, py))
        elif tag == "h":
            _, col, idx = self._drag
            self._hlines[col][idx] = max(0.0, min(self._page_h, py))

        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None

    def contextMenuEvent(self, event):
        sx = event.pos().x()
        sy = event.pos().y()
        target = self._find_target(float(sx), float(sy))
        if target is None:
            return
        tag = target[0]
        menu = QMenu(self)
        if tag == "v":
            idx = target[1]
            menu.addAction("삭제", lambda: self._delete_vline(idx))
        elif tag == "h":
            _, col, idx = target
            menu.addAction("삭제", lambda: self._delete_hline(col, idx))
        # 영역 마커(hs/he/ds/de)는 삭제 불가
        if menu.actions():
            menu.exec(event.globalPosition().toPoint())

    # ── 내부 헬퍼 ────────────────────────────────────────────────────

    def _find_target(self, sx: float, sy: float) -> tuple | None:
        """마우스 위치(스크린 좌표)에서 가장 가까운 드래그 대상을 반환."""
        hit = _HIT_PX

        # 영역 마커 우선
        for tag, yval in [
            ("hs", self._header_start),
            ("he", self._header_end),
            ("ds", self._data_start),
            ("de", self._data_end),
        ]:
            if abs(sy - self._s(yval)) <= hit:
                return (tag,)

        # 빨간 세로선
        for i, vx in enumerate(self._vlines):
            if abs(sx - self._s(vx)) <= hit:
                return ("v", i)

        # 파란 가로선
        for col_idx, ys in self._hlines.items():
            for j, vy in enumerate(ys):
                if abs(sy - self._s(vy)) <= hit:
                    return ("h", col_idx, j)

        return None

    def _delete_vline(self, idx: int) -> None:
        """세로선 삭제. 가로선의 컬럼 인덱스를 재매핑한다."""
        # _find_target은 _vlines의 원본 인덱스를 반환하므로 그대로 사용
        sorted_v = sorted(self._vlines)
        del_x = self._vlines[idx]
        sorted_idx = sorted_v.index(del_x)

        new_hlines: dict[int, list[float]] = {}
        for old_col, ys in self._hlines.items():
            if old_col < sorted_idx:
                new_col = old_col
            elif old_col in (sorted_idx, sorted_idx + 1):
                new_col = sorted_idx
            else:
                new_col = old_col - 1
            new_hlines.setdefault(new_col, []).extend(ys)

        del self._vlines[idx]
        self._hlines = new_hlines
        self.update()

    def _delete_hline(self, col_idx: int, line_idx: int) -> None:
        del self._hlines[col_idx][line_idx]
        if not self._hlines[col_idx]:
            del self._hlines[col_idx]
        self.update()
```

- [ ] **Step 2: import 확인**

```bash
python3 -c "from ui.zone_editor_widget import ZoneEditorWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add ui/zone_editor_widget.py
git commit -m "feat: add ZoneEditorWidget with draggable column/region lines"
```

---

### Task 4: Rewrite ui/parser_builder_dialog.py

**배경:** 기존 다이얼로그(다운로드/업로드 방식)를 3-패널 단일 창으로 전면 교체한다.  
- Panel 1 (좌, FormWidget): 파서 정보 입력 + "영역 지정" 버튼  
- Panel 2 (중, ZonePanel): ZoneEditorWidget + 툴바 + "필드 추출" 버튼  
- Panel 3 (우, FieldPanel): 추출된 필드 카드 목록 + "확인" 버튼  

파서 저장은 기존 `parser_registry.save(configs + [config])` 패턴 그대로 사용한다.

**Files:**
- Modify: `ui/parser_builder_dialog.py` (전면 재작성)

---

- [ ] **Step 1: parser_builder_dialog.py 전면 교체**

`ui/parser_builder_dialog.py`를 아래 내용으로 완전히 교체한다:

```python
import fitz
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QPushButton,
    QLineEdit, QSpinBox, QFormLayout, QLabel,
    QScrollArea, QWidget, QMessageBox, QSplitter,
    QSizePolicy,
)
from PyQt6.QtCore import Qt


class ParserBuilderDialog(QDialog):
    """3-패널 단일 창 파서 생성 다이얼로그.

    pages: 이미 로드된 fitz.Page 리스트 (메인 창에서 전달).
    """

    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 생성")
        self.setMinimumSize(1000, 600)
        self._pages = pages
        self._fields: list = []  # extract_fields() 결과

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        splitter.addWidget(self._build_form_panel())
        splitter.addWidget(self._build_zone_panel())
        splitter.addWidget(self._build_field_panel())
        splitter.setSizes([230, 600, 210])

        # 초기 비활성화
        self._zone_panel.setEnabled(False)
        self._field_panel.setEnabled(False)
        self._confirm_btn.setEnabled(False)

    # ── 패널 빌더 ─────────────────────────────────────────────────────

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(260)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(10, 10, 10, 10)

        title = QLabel("① 파서 정보")
        title.setStyleSheet("font-weight:bold;font-size:11px;color:#555;")
        vbox.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._broker_edit = QLineEdit()
        form.addRow("증권사명 *:", self._broker_edit)

        self._kw_edit = QLineEdit()
        self._kw_edit.setPlaceholderText("쉼표 구분 (예: 키움증권, 거래내역)")
        form.addRow("감지 키워드 *:", self._kw_edit)

        self._date_fmt_edit = QLineEdit()
        self._date_fmt_edit.setPlaceholderText("예: yyyy/mm/dd")
        form.addRow("날짜 형식 *:", self._date_fmt_edit)

        self._header_kw_edit = QLineEdit()
        self._header_kw_edit.setPlaceholderText("예: 거래일자")
        form.addRow("헤더 시작 키워드 *:", self._header_kw_edit)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 99)
        form.addRow("시작 페이지:", self._start_spin)

        vbox.addLayout(form)
        vbox.addStretch()

        self._open_zone_btn = QPushButton("영역 지정 →")
        self._open_zone_btn.setStyleSheet(
            "background:#8b5cf6;color:white;padding:8px;font-weight:bold;"
        )
        self._open_zone_btn.clicked.connect(self._on_open_zone_editor)
        vbox.addWidget(self._open_zone_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        vbox.addWidget(cancel_btn)

        return panel

    def _build_zone_panel(self) -> QWidget:
        from ui.zone_editor_widget import ZoneEditorWidget

        self._zone_panel = QWidget()
        vbox = QVBoxLayout(self._zone_panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 툴바
        toolbar = QWidget()
        toolbar.setStyleSheet("background:#f0f0f0;border-bottom:1px solid #ccc;")
        tbar = QHBoxLayout(toolbar)
        tbar.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel("② 존 에디터")
        lbl.setStyleSheet("font-weight:bold;color:#555;font-size:11px;")
        tbar.addWidget(lbl)

        self._add_v_btn = QPushButton("＋세로선")
        self._add_v_btn.setStyleSheet(
            "background:#ef4444;color:white;padding:2px 8px;border-radius:3px;"
        )
        self._add_v_btn.setCheckable(True)
        self._add_v_btn.clicked.connect(self._on_toggle_add_v)
        tbar.addWidget(self._add_v_btn)

        self._add_h_btn = QPushButton("＋가로선")
        self._add_h_btn.setStyleSheet(
            "background:#3b82f6;color:white;padding:2px 8px;border-radius:3px;"
        )
        self._add_h_btn.setCheckable(True)
        self._add_h_btn.clicked.connect(self._on_toggle_add_h)
        tbar.addWidget(self._add_h_btn)
        tbar.addStretch()
        vbox.addWidget(toolbar)

        # PDF 캔버스 (스크롤 가능)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        self._zone_editor = ZoneEditorWidget()
        scroll.setWidget(self._zone_editor)
        vbox.addWidget(scroll, 1)

        # 하단 버튼 바
        bottom = QWidget()
        bottom.setStyleSheet("background:#f0f0f0;border-top:1px solid #ccc;")
        bbar = QHBoxLayout(bottom)
        bbar.setContentsMargins(8, 6, 8, 6)

        reset_btn = QPushButton("초기화")
        reset_btn.clicked.connect(self._zone_editor.reset)
        bbar.addWidget(reset_btn)
        bbar.addStretch()

        extract_btn = QPushButton("필드 추출 →")
        extract_btn.setStyleSheet(
            "background:#2563eb;color:white;padding:4px 14px;font-weight:bold;"
        )
        extract_btn.clicked.connect(self._on_extract_fields)
        bbar.addWidget(extract_btn)
        vbox.addWidget(bottom)

        return self._zone_panel

    def _build_field_panel(self) -> QWidget:
        self._field_panel = QWidget()
        self._field_panel.setMaximumWidth(240)
        vbox = QVBoxLayout(self._field_panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        title = QLabel("③ 추출된 필드")
        title.setStyleSheet(
            "font-weight:bold;font-size:11px;color:#555;"
            "padding:6px 10px;background:#f0f0f0;border-bottom:1px solid #ccc;"
        )
        vbox.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._field_list_widget = QWidget()
        self._field_list_layout = QVBoxLayout(self._field_list_widget)
        self._field_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._field_list_layout.setSpacing(4)
        self._field_list_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self._field_list_widget)
        vbox.addWidget(scroll, 1)

        bottom = QWidget()
        bottom.setStyleSheet("border-top:1px solid #ddd;")
        bbar = QVBoxLayout(bottom)
        bbar.setContentsMargins(7, 7, 7, 7)
        self._confirm_btn = QPushButton("✓ 확인 (파서 생성)")
        self._confirm_btn.setStyleSheet(
            "background:#16a34a;color:white;padding:7px;font-weight:bold;"
        )
        self._confirm_btn.clicked.connect(self._on_confirm)
        bbar.addWidget(self._confirm_btn)
        vbox.addWidget(bottom)

        return self._field_panel

    # ── 이벤트 핸들러 ────────────────────────────────────────────────

    def _on_toggle_add_v(self, checked: bool) -> None:
        from ui.zone_editor_widget import ZoneEditorWidget
        if checked:
            self._add_h_btn.setChecked(False)
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_ADD_V)
        else:
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_NONE)

    def _on_toggle_add_h(self, checked: bool) -> None:
        from ui.zone_editor_widget import ZoneEditorWidget
        if checked:
            self._add_v_btn.setChecked(False)
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_ADD_H)
        else:
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_NONE)

    def _on_open_zone_editor(self) -> None:
        date_fmt = self._date_fmt_edit.text().strip()
        if not self._broker_edit.text().strip():
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return
        if not date_fmt:
            QMessageBox.warning(self, "입력 오류", "날짜 형식을 입력하세요 (예: yyyy/mm/dd).")
            return

        start = self._start_spin.value()
        if start >= len(self._pages):
            QMessageBox.warning(self, "입력 오류", f"시작 페이지({start})가 범위를 벗어납니다.")
            return

        self._zone_editor.load_page(
            self._pages[start],
            header_start_keyword=self._header_kw_edit.text().strip(),
        )
        self._zone_panel.setEnabled(True)

    def _on_extract_fields(self) -> None:
        from core.zone_spec import ZoneSpec, extract_fields

        kw_text = self._kw_edit.text().strip()
        keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
        zone_data = self._zone_editor.get_zone_data()

        self._zone_spec = ZoneSpec(
            broker_name=self._broker_edit.text().strip(),
            detection_keywords=keywords,
            date_format=self._date_fmt_edit.text().strip(),
            header_start_keyword=self._header_kw_edit.text().strip(),
            start_page=self._start_spin.value(),
            column_xs=zone_data["column_xs"],
            row_ys_per_col=zone_data["row_ys_per_col"],
            header_start_y=zone_data["header_start_y"],
            header_end_y=zone_data["header_end_y"],
            data_start_y=zone_data["data_start_y"],
            data_end_y=zone_data["data_end_y"],
        )

        try:
            self._fields = extract_fields(
                self._zone_spec, self._pages[self._start_spin.value()]
            )
        except Exception as exc:
            QMessageBox.critical(self, "필드 추출 실패", str(exc))
            return

        self._populate_field_list()
        self._field_panel.setEnabled(True)
        self._confirm_btn.setEnabled(True)

    def _populate_field_list(self) -> None:
        # 기존 카드 제거
        while self._field_list_layout.count():
            item = self._field_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for fm in self._fields:
            card = QWidget()
            card.setStyleSheet(
                "background:#eff6ff;border:1px solid #bfdbfe;"
                "border-radius:3px;padding:2px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(2)

            lbl_field = QLabel(fm.standard_field)
            lbl_field.setStyleSheet("font-weight:bold;font-size:10px;color:#1d4ed8;")
            lbl_meta = QLabel(
                f"row_offset={fm.row_offset}  "
                f"x=[{fm.x_min:.0f},{fm.x_max:.0f}]"
            )
            lbl_meta.setStyleSheet("font-size:9px;color:#555;")
            cl.addWidget(lbl_field)
            cl.addWidget(lbl_meta)
            self._field_list_layout.addWidget(card)

    def _on_confirm(self) -> None:
        from core import parser_registry
        from core.zone_spec import zone_spec_to_config

        if not self._fields:
            QMessageBox.warning(self, "오류", "추출된 필드가 없습니다.")
            return

        config = zone_spec_to_config(self._zone_spec, self._fields)
        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
```

- [ ] **Step 2: import 확인**

```bash
python3 -c "from ui.parser_builder_dialog import ParserBuilderDialog; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 전체 테스트 확인 (UI 제외)**

```bash
python3 -m pytest tests/ -q --ignore=tests/test_integration.py 2>&1 | tail -10
```
Expected: 모두 PASSED

- [ ] **Step 4: 커밋**

```bash
git add ui/parser_builder_dialog.py
git commit -m "feat: rewrite ParserBuilderDialog as 3-panel zone editor UI"
```

---

## 완료 후 검증

앱을 실제 실행해 파서 생성 흐름을 확인한다:

```bash
python3 main.py
```

1. PDF 파일 추가 → 파서 선택 다이얼로그 오픈
2. "파서 추가" 버튼 클릭 → ParserBuilderDialog 오픈
3. 폼 입력 → "영역 지정" 클릭 → PDF가 Zone Editor에 표시됨 확인
4. "＋세로선" → 클릭으로 빨간 세로선 추가, 드래그 이동, 우클릭 삭제 확인
5. "＋가로선" → 컬럼 내 클릭으로 파란 가로선 추가 확인
6. 주황/초록 마커 드래그 확인
7. "필드 추출" → 우측 패널에 필드 카드 표시 확인
8. "확인" → parsers.json에 저장 확인 (`python3 -c "from core import parser_registry; print(parser_registry.load())"`)
