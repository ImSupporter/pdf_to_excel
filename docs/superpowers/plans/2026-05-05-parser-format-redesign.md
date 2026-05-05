# Parser Format Redesign (header_mapped) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing `table`/`template` dynamic parser layouts with `header_mapped`, which uses PDF column header x-coordinates to map cells correctly across multi-row transactions.

**Architecture:** The 제목행(column header row group) defines canonical column x-positions. All data cells — including continuation rows and secondary header rows — are mapped to the nearest header x. Transaction groups are delimited by date-anchor detection rather than a fixed `rows_per_tx` count. The Excel template is generated from the data section only, skipping pre-data content.

**Tech Stack:** Python 3.11+, PyMuPDF (fitz), openpyxl, PyQt6, dataclasses, re

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `core/parser_registry.py` | Modify | Slim `FieldMapping`, drop `rows_per_tx`, add `header_mapped` branch in `build_class`, backward-compat `load()` |
| `core/parser_template.py` | Modify | `date_format_to_re`, `_detect_date_format`, full rewrite of `export_parser_template` and `read_parser_template`, new `AnnotatedField` / `TemplateAnnotations` |
| `ui/parser_builder_dialog.py` | Modify | Add `data_start_keyword` field, replace regex input with format input, wire new export/read API |
| `tests/test_parser_registry.py` | Modify | Update old tests to new model, add `header_mapped` parse tests |
| `tests/test_parser_template.py` | Modify | Replace `field_cells`-based tests, add date-format util tests, add new `read_parser_template` tests |

---

## Task 1: Data model simplification

**Files:**
- Modify: `core/parser_registry.py`
- Modify: `tests/test_parser_registry.py`

- [ ] **Step 1: Write failing tests for the new model**

Replace the content of `tests/test_parser_registry.py` with:

```python
import json
import tempfile
from pathlib import Path
import pytest


def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", row_offset=0, x=50.0)
    assert fm.standard_field == "date"
    assert fm.row_offset == 0
    assert fm.x == 50.0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
            FieldMapping(standard_field="amount", row_offset=0, x=300.0),
        ],
    )
    parser_registry.save([cfg])

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].detection_keywords == ["테스트", "거래내역"]
    assert len(loaded[0].field_mappings) == 2
    assert loaded[0].field_mappings[1].x == 300.0


def test_load_returns_empty_when_no_file(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    result = parser_registry.load()
    assert result == []


def test_load_ignores_unknown_fields_in_old_json(tmp_path, monkeypatch):
    """Old parsers.json with column_index/rows_per_tx must load without error."""
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    old_format = [{
        "broker_name": "구버전증권",
        "detection_keywords": ["구버전"],
        "date_re": r"\d{4}/\d{2}/\d{2}",
        "layout_type": "table",
        "start_page": 0,
        "rows_per_tx": 2,
        "skip_keywords": [],
        "field_mappings": [{
            "standard_field": "date",
            "column_index": 0,
            "row_offset": 0,
            "y_min": 0,
            "y_max": 0,
            "x": 50.0,
        }]
    }]
    (tmp_path / "parsers.json").write_text(json.dumps(old_format), encoding="utf-8")

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "구버전증권"
    assert loaded[0].field_mappings[0].x == 50.0


def test_build_class_returns_base_parser_subclass():
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class
    from parsers.base import BaseParser

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
        ],
    )
    cls = build_class(cfg)
    assert issubclass(cls, BaseParser)
    assert cls.BROKER_NAME == "테스트증권"
    assert cls.DETECTION_KEYWORDS == ["테스트"]
    assert hasattr(cls(), "parse")


def test_get_all_parsers_includes_builtins(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    from core.parser_registry import get_all_parsers

    all_parsers = get_all_parsers()
    names = [p.BROKER_NAME for p in all_parsers]
    assert "삼성증권" in names
    assert "미래에셋증권" in names


def test_get_all_parsers_includes_dynamic(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, get_all_parsers, save

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="다이나믹증권",
        detection_keywords=["다이나믹"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])
    names = [p.BROKER_NAME for p in get_all_parsers()]
    assert "다이나믹증권" in names
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_parser_registry.py -q
```

Expected: multiple failures (FieldMapping missing x, DynamicParserConfig has rows_per_tx, etc.)

- [ ] **Step 3: Update `core/parser_registry.py` — slim FieldMapping and DynamicParserConfig**

Replace the `FieldMapping` and `DynamicParserConfig` dataclasses (lines 9–32) with:

```python
@dataclass
class FieldMapping:
    standard_field: str
    row_offset: int = 0
    x: float = 0.0
    y_min: float = 0.0   # rotated layout only
    y_max: float = 0.0   # rotated layout only


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str
    layout_type: str           # "header_mapped" | "rotated"
    start_page: int
    skip_keywords: list[str]
    field_mappings: list[FieldMapping] = field(default_factory=list)
```

> `y_min` / `y_max`는 `rotated` 레이아웃이 여전히 사용하므로 유지한다.
> `column_index`, `page_index`, `row_index`, `y`, `source_text`만 제거.

- [ ] **Step 4: Update `load()` for backward compatibility**

Replace the `load()` function body with:

```python
def load() -> list[DynamicParserConfig]:
    path = _get_data_dir() / "parsers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    import dataclasses as _dc
    valid_fm = {f.name for f in _dc.fields(FieldMapping)}
    valid_cfg = {f.name for f in _dc.fields(DynamicParserConfig)}

    configs = []
    for item in data:
        raw_mappings = item.pop("field_mappings", [])
        mappings = [
            FieldMapping(**{k: v for k, v in m.items() if k in valid_fm})
            for m in raw_mappings
        ]
        cfg_kwargs = {k: v for k, v in item.items() if k in valid_cfg}
        configs.append(DynamicParserConfig(**cfg_kwargs, field_mappings=mappings))
    return configs
```

- [ ] **Step 5: Run tests — expect all to pass except `build_class`-related ones (parser logic not yet updated)**

```bash
python3 -m pytest tests/test_parser_registry.py -q
```

Expected: `test_field_mapping_roundtrip`, `test_dynamic_parser_config_roundtrip`, `test_load_*`, `test_get_all_parsers_*` pass. `test_build_class_returns_base_parser_subclass` may still pass (just checks subclass). Any parse-logic tests skip for now.

- [ ] **Step 6: Commit**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "refactor: slim FieldMapping/DynamicParserConfig, backward-compat load()"
```

---

## Task 2: Date format utilities

**Files:**
- Modify: `core/parser_template.py`
- Modify: `tests/test_parser_template.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_parser_template.py`:

```python
def test_date_format_to_re_slash():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy/mm/dd") == r"\d{4}/\d{2}/\d{2}"


def test_date_format_to_re_dash():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy-mm-dd") == r"\d{4}-\d{2}-\d{2}"


def test_date_format_to_re_dot():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yyyy.mm.dd") == r"\d{4}\.\d{2}\.\d{2}"


def test_date_format_to_re_two_digit_year():
    from core.parser_template import date_format_to_re
    assert date_format_to_re("yy/mm/dd") == r"\d{2}/\d{2}/\d{2}"


def test_detect_date_format_slash():
    from core.parser_template import _detect_date_format
    result = _detect_date_format(["계좌번호", "1234", "2025/11/06", "매도"])
    assert result is not None
    assert result[0] == r"\d{4}/\d{2}/\d{2}"
    assert result[1] == "yyyy/mm/dd"


def test_detect_date_format_returns_none():
    from core.parser_template import _detect_date_format
    assert _detect_date_format(["계좌번호", "ABC", "테스트"]) is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_parser_template.py::test_date_format_to_re_slash tests/test_parser_template.py::test_detect_date_format_slash -q
```

Expected: ImportError or AttributeError (functions not yet defined)

- [ ] **Step 3: Add utilities to `core/parser_template.py`**

Add after the existing imports at the top of `core/parser_template.py`:

```python
_AUTO_DATE_PATTERNS: list[tuple[str, str]] = [
    (r"\d{4}/\d{2}/\d{2}", "yyyy/mm/dd"),
    (r"\d{4}-\d{2}-\d{2}", "yyyy-mm-dd"),
    (r"\d{4}\.\d{2}\.\d{2}", "yyyy.mm.dd"),
    (r"\d{2}/\d{2}/\d{4}", "dd/mm/yyyy"),
]


def date_format_to_re(fmt: str) -> str:
    """Convert user-friendly date format string to regex. e.g. 'yyyy/mm/dd' → r'\d{4}/\d{2}/\d{2}'"""
    result = fmt
    result = result.replace("yyyy", r"\d{4}")
    result = result.replace("yy", r"\d{2}")
    result = result.replace("mm", r"\d{2}")
    result = result.replace("dd", r"\d{2}")
    result = result.replace(".", r"\.")
    return result


def _detect_date_format(texts: list[str]) -> tuple[str, str] | None:
    """Scan texts for a known date pattern. Returns (regex, format_str) or None."""
    import re
    for pattern, fmt in _AUTO_DATE_PATTERNS:
        compiled = re.compile(pattern)
        if any(compiled.match(t) for t in texts):
            return pattern, fmt
    return None
```

- [ ] **Step 4: Run tests — all new util tests should pass**

```bash
python3 -m pytest tests/test_parser_template.py -q
```

Expected: all pass (existing tests still pass since we only added functions)

- [ ] **Step 5: Commit**

```bash
git add core/parser_template.py tests/test_parser_template.py
git commit -m "feat: add date_format_to_re and _detect_date_format utilities"
```

---

## Task 3: Template generation rewrite

**Files:**
- Modify: `core/parser_template.py` (replace `export_parser_template`)
- Modify: `tests/test_parser_template.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_parser_template.py`:

```python
def test_export_parser_template_creates_header_rows_with_is_header_flag(tmp_path):
    """Header group cells must have is_header_row=True in metadata."""
    import fitz
    import openpyxl
    from unittest.mock import MagicMock, patch
    from core.parser_template import META_SHEET, export_parser_template, TemplateCell

    # Fake PDF: 3 rows
    # row 0: 거래일자 x=50, 종목명 x=200  ← header
    # row 1: 2024/01/01 x=50, 삼성전자 x=200  ← first data row
    # row 2: 2024/01/02 x=50, 카카오 x=200
    fake_cells = [
        TemplateCell(0, 0, 0, x=50.0,  y=10.0, text="거래일자"),
        TemplateCell(0, 0, 1, x=200.0, y=10.0, text="종목명"),
        TemplateCell(0, 1, 0, x=50.0,  y=20.0, text="2024/01/01"),
        TemplateCell(0, 1, 1, x=200.0, y=20.0, text="삼성전자"),
        TemplateCell(0, 2, 0, x=50.0,  y=30.0, text="2024/01/02"),
        TemplateCell(0, 2, 1, x=200.0, y=30.0, text="카카오"),
    ]

    mock_page = MagicMock(spec=fitz.Page)
    out = tmp_path / "out.xlsx"

    with patch("core.parser_template._extract_page_cells", return_value=fake_cells):
        result = export_parser_template(
            [mock_page], out,
            data_start_keyword="거래일자",
            date_re=r"\d{4}/\d{2}/\d{2}",
        )

    wb = openpyxl.load_workbook(out)
    meta = wb[META_SHEET]
    rows = list(meta.iter_rows(min_row=2, values_only=True))

    header_rows = [r for r in rows if r[9] is True]   # is_header_row=True
    data_rows   = [r for r in rows if r[9] is False]

    assert len(header_rows) == 2   # 거래일자, 종목명
    assert len(data_rows)   >= 2   # sample data rows

    header_texts = {r[8] for r in header_rows}
    assert "거래일자" in header_texts
    assert "종목명" in header_texts


def test_export_parser_template_excludes_pre_header_rows(tmp_path):
    """Rows before data_start_keyword (e.g. account number) must not appear in Excel."""
    import fitz
    import openpyxl
    from unittest.mock import MagicMock, patch
    from core.parser_template import META_SHEET, export_parser_template, TemplateCell

    fake_cells = [
        TemplateCell(0, 0, 0, x=50.0, y=5.0,  text="계좌번호: 1234-5678"),  # pre-header
        TemplateCell(0, 1, 0, x=50.0, y=15.0, text="거래일자"),              # header start
        TemplateCell(0, 1, 1, x=200.0,y=15.0, text="종목명"),
        TemplateCell(0, 2, 0, x=50.0, y=25.0, text="2024/01/01"),
        TemplateCell(0, 2, 1, x=200.0,y=25.0, text="삼성전자"),
    ]
    mock_page = MagicMock(spec=fitz.Page)
    out = tmp_path / "out.xlsx"

    with patch("core.parser_template._extract_page_cells", return_value=fake_cells):
        export_parser_template(
            [mock_page], out,
            data_start_keyword="거래일자",
            date_re=r"\d{4}/\d{2}/\d{2}",
        )

    wb = openpyxl.load_workbook(out)
    meta = wb[META_SHEET]
    all_texts = {r[8] for r in meta.iter_rows(min_row=2, values_only=True) if r[8]}
    assert "계좌번호: 1234-5678" not in all_texts


def test_export_parser_template_writes_config_sheet(tmp_path):
    """_config sheet must store date_format and data_start_keyword."""
    import fitz
    import openpyxl
    from unittest.mock import MagicMock, patch
    from core.parser_template import export_parser_template, TemplateCell

    fake_cells = [
        TemplateCell(0, 0, 0, x=50.0, y=10.0, text="거래일자"),
        TemplateCell(0, 0, 1, x=200.0,y=10.0, text="종목명"),
        TemplateCell(0, 1, 0, x=50.0, y=20.0, text="2024/01/01"),
        TemplateCell(0, 1, 1, x=200.0,y=20.0, text="삼성전자"),
    ]
    mock_page = MagicMock(spec=fitz.Page)
    out = tmp_path / "out.xlsx"

    with patch("core.parser_template._extract_page_cells", return_value=fake_cells):
        export_parser_template(
            [mock_page], out,
            data_start_keyword="거래일자",
            date_re=r"\d{4}/\d{2}/\d{2}",
        )

    wb = openpyxl.load_workbook(out)
    assert "_config" in wb.sheetnames
    config = {r[0]: r[1] for r in wb["_config"].iter_rows(values_only=True) if r[0]}
    assert config["data_start_keyword"] == "거래일자"


def test_export_parser_template_autodetects_date_format(tmp_path):
    """When date_re is None, auto-detection must succeed and return format string."""
    import fitz
    from unittest.mock import MagicMock, patch
    from core.parser_template import export_parser_template, TemplateCell

    fake_cells = [
        TemplateCell(0, 0, 0, x=50.0, y=10.0, text="거래일자"),
        TemplateCell(0, 1, 0, x=50.0, y=20.0, text="2024-01-01"),
        TemplateCell(0, 1, 1, x=200.0,y=20.0, text="삼성전자"),
    ]
    mock_page = MagicMock(spec=fitz.Page)
    out = tmp_path / "out.xlsx"

    with patch("core.parser_template._extract_page_cells", return_value=fake_cells):
        fmt = export_parser_template([mock_page], out, data_start_keyword="거래일자")

    assert fmt == "yyyy-mm-dd"


def test_export_parser_template_raises_when_keyword_not_found(tmp_path):
    import fitz
    from unittest.mock import MagicMock, patch
    from core.parser_template import export_parser_template, TemplateCell

    fake_cells = [TemplateCell(0, 0, 0, x=50.0, y=10.0, text="전혀다른내용")]
    mock_page = MagicMock(spec=fitz.Page)
    out = tmp_path / "out.xlsx"

    with patch("core.parser_template._extract_page_cells", return_value=fake_cells):
        with pytest.raises(ValueError, match="거래일자"):
            export_parser_template([mock_page], out, data_start_keyword="거래일자",
                                   date_re=r"\d{4}/\d{2}/\d{2}")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_parser_template.py::test_export_parser_template_creates_header_rows_with_is_header_flag -q
```

Expected: FAIL — `export_parser_template` has wrong signature

- [ ] **Step 3: Replace `export_parser_template` in `core/parser_template.py`**

Replace the entire `export_parser_template` function (lines 151–210 in current file) with:

```python
def export_parser_template(
    pages: list[fitz.Page],
    output_path: str | Path,
    data_start_keyword: str,
    date_re: str | None = None,
    max_pages: int = 3,
) -> str | None:
    """Generate Excel template for header_mapped parser creation.

    Returns detected date format string (e.g. "yyyy/mm/dd") or None when
    date_re was provided without a matching _AUTO_DATE_PATTERNS entry.
    Raises ValueError if data_start_keyword is not found or date detection fails.
    """
    import re as _re
    from collections import defaultdict

    all_page_cells: list[list[TemplateCell]] = [
        _extract_page_cells(page, pi) for pi, page in enumerate(pages[:max_pages])
    ]

    # Find header group start
    header_start_page: int | None = None
    header_start_row_idx: int | None = None
    for pi, cells in enumerate(all_page_cells):
        for c in cells:
            if data_start_keyword in c.text:
                header_start_page = pi
                header_start_row_idx = c.row_index
                break
        if header_start_page is not None:
            break

    if header_start_page is None:
        raise ValueError(f"'{data_start_keyword}'를 PDF에서 찾을 수 없습니다.")

    # Resolve date_re
    detected_format: str | None = None
    if date_re is None:
        candidate_texts = [
            c.text for c in all_page_cells[header_start_page]
            if c.row_index > header_start_row_idx
        ]
        result = _detect_date_format(candidate_texts)
        if result is None:
            raise ValueError(
                "날짜 패턴을 자동으로 감지할 수 없습니다. 날짜 형식을 직접 입력하세요 (예: yyyy/mm/dd)."
            )
        date_re, detected_format = result
    else:
        for pattern, fmt in _AUTO_DATE_PATTERNS:
            if date_re == pattern:
                detected_format = fmt
                break

    compiled_re = _re.compile(date_re)

    # Group cells by row on the header page
    page_cells = all_page_cells[header_start_page]
    cells_by_row: dict[int, list[TemplateCell]] = defaultdict(list)
    for c in page_cells:
        cells_by_row[c.row_index].append(c)

    # Identify header group rows
    header_row_indices: list[int] = []
    first_data_row_idx: int | None = None
    for row_idx in sorted(cells_by_row.keys()):
        if row_idx < header_start_row_idx:
            continue
        row_texts = [c.text for c in cells_by_row[row_idx]]
        if any(compiled_re.match(t) for t in row_texts):
            first_data_row_idx = row_idx
            break
        header_row_indices.append(row_idx)

    if not header_row_indices:
        raise ValueError("제목행 그룹을 찾을 수 없습니다.")
    if first_data_row_idx is None:
        raise ValueError("첫 번째 데이터 행을 찾을 수 없습니다.")

    # Column zones from header cells only
    header_cells = [c for c in page_cells if c.row_index in header_row_indices]
    zones = _compute_x_zones(header_cells, x_gap=20.0)

    # Find date column x for anchor detection
    date_header_x: float | None = next(
        (c.x for c in header_cells if data_start_keyword in c.text), None
    )

    # Collect sample transaction groups
    sample_groups: list[list[list[TemplateCell]]] = []
    current_group: list[list[TemplateCell]] = []

    for pi, p_cells in enumerate(all_page_cells):
        rc: dict[int, list[TemplateCell]] = defaultdict(list)
        for c in p_cells:
            rc[c.row_index].append(c)

        for row_idx in sorted(rc.keys()):
            if pi == header_start_page and row_idx < first_data_row_idx:
                continue
            row = sorted(rc[row_idx], key=lambda c: c.x)
            row_texts = [c.text for c in row]

            is_anchor = False
            if date_header_x is not None:
                closest = min(row, key=lambda c: abs(c.x - date_header_x), default=None)
                if closest and compiled_re.match(closest.text):
                    is_anchor = True
            if not is_anchor and any(compiled_re.match(t) for t in row_texts):
                is_anchor = True

            if is_anchor:
                if current_group:
                    sample_groups.append(current_group)
                if len(sample_groups) >= 5:
                    break
                current_group = [row]
            elif current_group:
                current_group.append(row)

        if len(sample_groups) >= 5:
            break

    if current_group:
        sample_groups.append(current_group)

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    fields_ws = wb.create_sheet(FIELDS_SHEET)
    config_ws = wb.create_sheet("_config")

    ws["A1"] = "제목행(회색) 셀을 노란색으로 칠해 필드를 지정하세요. 무시할 키워드는 회색으로 칠하세요."
    ws["A1"].alignment = Alignment(wrap_text=True)

    meta.append([
        "sheet", "excel_row", "excel_col",
        "page_index", "row_index", "column_index",
        "x", "y", "text", "is_header_row",
    ])

    config_ws.append(["date_format", detected_format or ""])
    config_ws.append(["data_start_keyword", data_start_keyword])
    config_ws.sheet_state = "hidden"

    HEADER_BG = "D9D9D9"
    SAMPLE_FILLS = ["FFFFFF", "EBF3FB"]

    excel_row = 3
    max_col = 1

    for row_idx in header_row_indices:
        for c in sorted(cells_by_row[row_idx], key=lambda cell: cell.x):
            excel_col = _find_zone_index(c.x, zones) + 1
            max_col = max(max_col, excel_col)
            cell = ws.cell(excel_row, excel_col, c.text)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(fill_type="solid", fgColor=HEADER_BG)
            meta.append([
                ws.title, excel_row, excel_col,
                c.page_index, c.row_index, c.column_index,
                c.x, c.y, c.text, True,
            ])
        excel_row += 1

    for group_idx, group in enumerate(sample_groups):
        bg = SAMPLE_FILLS[group_idx % 2]
        fill = PatternFill(fill_type="solid", fgColor=bg)
        for row in group:
            for c in row:
                excel_col = _find_zone_index(c.x, zones) + 1
                max_col = max(max_col, excel_col)
                ws.cell(excel_row, excel_col, c.text).fill = fill
                meta.append([
                    ws.title, excel_row, excel_col,
                    c.page_index, c.row_index, c.column_index,
                    c.x, c.y, c.text, False,
                ])
            excel_row += 1
        excel_row += 1

    for col in range(1, max_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14

    fields_ws.append(["필드 키", "필드명"])
    fields_ws["A1"].font = Font(bold=True)
    fields_ws["B1"].font = Font(bold=True)
    for key, label in STANDARD_FIELDS.items():
        fields_ws.append([key, label])
    fields_ws.column_dimensions["A"].width = 16
    fields_ws.column_dimensions["B"].width = 16

    meta.sheet_state = "hidden"
    wb.save(output_path)
    return detected_format
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_parser_template.py -q
```

Expected: all new `test_export_*` tests pass; pre-existing tests may fail (they use old `read_parser_template` — handled in Task 4)

- [ ] **Step 5: Commit**

```bash
git add core/parser_template.py tests/test_parser_template.py
git commit -m "feat: rewrite export_parser_template for header_mapped layout"
```

---

## Task 4: Template reading rewrite

**Files:**
- Modify: `core/parser_template.py` (add `AnnotatedField`, update `TemplateAnnotations`, replace `read_parser_template`)
- Modify: `tests/test_parser_template.py`

- [ ] **Step 1: Write failing tests**

Replace the two old `test_read_parser_template_*` tests with:

```python
def test_read_parser_template_extracts_yellow_header_fields(tmp_path):
    import openpyxl
    from openpyxl.styles import PatternFill
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet","excel_row","excel_col","page_index","row_index","column_index","x","y","text","is_header_row"])

    ws["A1"] = "거래일자"
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 1, 0, 3, 0, 50.0, 48.0, "거래일자", True])

    ws["B1"] = "종목명"
    ws["B1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 2, 0, 3, 1, 200.0, 48.0, "종목명", True])

    ws["C1"] = "합계"
    ws["C1"].fill = PatternFill(fill_type="solid", fgColor="BFBFBF")
    meta.append(["PDF", 1, 3, 0, 3, 2, 300.0, 48.0, "합계", True])

    # Yellow on data row → must be IGNORED
    ws["A2"] = "2024/01/01"
    ws["A2"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 2, 1, 0, 4, 0, 50.0, 60.0, "2024/01/01", False])

    wb.save(path)
    annotations = read_parser_template(path)

    assert len(annotations.field_mappings) == 2
    date_fm = next(fm for fm in annotations.field_mappings if fm.standard_field == "date")
    name_fm = next(fm for fm in annotations.field_mappings if fm.standard_field == "name")
    assert date_fm.x == 50.0
    assert date_fm.row_offset == 0
    assert name_fm.x == 200.0
    assert annotations.skip_keywords == ["합계"]


def test_read_parser_template_multi_header_row_offsets(tmp_path):
    import openpyxl
    from openpyxl.styles import PatternFill
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet","excel_row","excel_col","page_index","row_index","column_index","x","y","text","is_header_row"])

    # excel_row=1: 거래일자 → row_offset=0
    ws["A1"] = "거래일자"
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 1, 0, 3, 0, 50.0, 48.0, "거래일자", True])

    # excel_row=2: 종목명 → row_offset=1
    ws["B2"] = "종목명"
    ws["B2"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 2, 2, 0, 4, 1, 150.0, 60.0, "종목명", True])

    wb.save(path)
    annotations = read_parser_template(path)

    date_fm = next(fm for fm in annotations.field_mappings if fm.standard_field == "date")
    name_fm = next(fm for fm in annotations.field_mappings if fm.standard_field == "name")
    assert date_fm.row_offset == 0
    assert name_fm.row_offset == 1


def test_read_parser_template_reads_config_sheet(tmp_path):
    import openpyxl
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet","excel_row","excel_col","page_index","row_index","column_index","x","y","text","is_header_row"])
    cfg = wb.create_sheet("_config")
    cfg.append(["date_format", "yyyy/mm/dd"])
    cfg.append(["data_start_keyword", "거래일자"])
    wb.save(path)

    annotations = read_parser_template(path)
    assert annotations.detected_date_format == "yyyy/mm/dd"


def test_read_parser_template_custom_field_name(tmp_path):
    """Unknown header text is kept as-is (custom field key)."""
    import openpyxl
    from openpyxl.styles import PatternFill
    from core.parser_template import META_SHEET, read_parser_template

    path = tmp_path / "format.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PDF"
    meta = wb.create_sheet(META_SHEET)
    meta.append(["sheet","excel_row","excel_col","page_index","row_index","column_index","x","y","text","is_header_row"])

    ws["A1"] = "특수컬럼명XYZ"
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    meta.append(["PDF", 1, 1, 0, 3, 0, 50.0, 48.0, "특수컬럼명XYZ", True])

    wb.save(path)
    annotations = read_parser_template(path)
    assert annotations.field_mappings[0].standard_field == "특수컬럼명XYZ"
```

- [ ] **Step 2: Run failing tests**

```bash
python3 -m pytest tests/test_parser_template.py::test_read_parser_template_extracts_yellow_header_fields -q
```

Expected: FAIL — `TemplateAnnotations` still has `field_cells`, not `field_mappings`

- [ ] **Step 3: Add `AnnotatedField`, update `TemplateAnnotations` in `core/parser_template.py`**

Replace the existing `TemplateAnnotations` dataclass with:

```python
@dataclass
class AnnotatedField:
    standard_field: str
    row_offset: int
    x: float


@dataclass
class TemplateAnnotations:
    field_mappings: list[AnnotatedField]
    skip_keywords: list[str]
    detected_date_format: str | None = None
```

- [ ] **Step 4: Replace `read_parser_template` in `core/parser_template.py`**

Replace the entire `read_parser_template` function with:

```python
def read_parser_template(path: str | Path) -> TemplateAnnotations:
    wb = openpyxl.load_workbook(path)
    if META_SHEET not in wb.sheetnames:
        raise ValueError("포맷 파일 metadata 시트를 찾을 수 없습니다.")

    detected_date_format: str | None = None
    if "_config" in wb.sheetnames:
        for row in wb["_config"].iter_rows(values_only=True):
            if row and row[0] == "date_format" and row[1]:
                detected_date_format = str(row[1])

    meta_ws = wb[META_SHEET]
    metadata: dict[tuple[str, int, int], tuple[TemplateCell, bool]] = {}
    for row in meta_ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        sheet, excel_row, excel_col, page_index, row_index, column_index, x, y, text, is_header = row
        tc = TemplateCell(
            page_index=int(page_index),
            row_index=int(row_index),
            column_index=int(column_index),
            x=float(x),
            y=float(y),
            text=str(text or ""),
        )
        metadata[(str(sheet), int(excel_row), int(excel_col))] = (tc, bool(is_header))

    header_excel_rows = [
        er for (sh, er, _ec), (_tc, is_hdr) in metadata.items()
        if is_hdr and sh != META_SHEET
    ]
    header_start_excel_row = min(header_excel_rows) if header_excel_rows else None

    field_mappings: list[AnnotatedField] = []
    skip_keywords: list[str] = []
    seen_fields: set[str] = set()

    for sheet_name in wb.sheetnames:
        if sheet_name in {META_SHEET, FIELDS_SHEET, "_config"}:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                key = (sheet_name, cell.row, cell.column)
                if key not in metadata:
                    continue
                tc, is_header_row = metadata[key]
                value = str(cell.value or tc.text or "").strip()
                if not value:
                    continue
                if is_yellow(cell):
                    if not is_header_row:
                        continue
                    standard_field = infer_standard_field(value) or value
                    if standard_field in seen_fields:
                        continue
                    seen_fields.add(standard_field)
                    row_offset = (cell.row - header_start_excel_row) if header_start_excel_row else 0
                    field_mappings.append(AnnotatedField(
                        standard_field=standard_field,
                        row_offset=row_offset,
                        x=tc.x,
                    ))
                elif is_gray(cell):
                    skip_keywords.append(value)

    return TemplateAnnotations(
        field_mappings=field_mappings,
        skip_keywords=list(dict.fromkeys(skip_keywords)),
        detected_date_format=detected_date_format,
    )
```

- [ ] **Step 5: Remove the now-deleted `TemplateCell.column_index` / old `TemplateAnnotations` fields from the file**

Also remove the old `TemplateAnnotations` class definition if it still references `field_cells`.

- [ ] **Step 6: Run all template tests**

```bash
python3 -m pytest tests/test_parser_template.py -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add core/parser_template.py tests/test_parser_template.py
git commit -m "feat: rewrite read_parser_template, add AnnotatedField/TemplateAnnotations"
```

---

## Task 5: Parser execution — header_mapped branch

**Files:**
- Modify: `core/parser_registry.py` (`build_class`)
- Modify: `tests/test_parser_registry.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_parser_registry.py`:

```python
def test_header_mapped_single_header_parses_two_transactions():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date",   row_offset=0, x=50.0),
            FieldMapping(standard_field="name",   row_offset=0, x=200.0),
            FieldMapping(standard_field="amount", row_offset=0, x=350.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (200.0, "삼성전자"), (350.0, "1000000")]),
        (20.0, [(50.0, "2024/01/02"), (200.0, "카카오"),   (350.0, "500000")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, raws = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 2
    assert txns[0].date == "2024/01/01"
    assert txns[0].name == "삼성전자"
    assert txns[0].amount == 1000000.0
    assert txns[1].date == "2024/01/02"


def test_header_mapped_continuation_row_concatenates():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
            FieldMapping(standard_field="name", row_offset=0, x=200.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (200.0, "1Q미국S&P500")]),
        (20.0, [(200.0, "채혼합50액티브")]),  # continuation
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].name == "1Q미국S&P500 채혼합50액티브"


def test_header_mapped_two_header_rows_separate_fields():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            # Header row 0: date@50, type@150
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
            FieldMapping(standard_field="type", row_offset=0, x=150.0),
            # Header row 1: name@50, amount@150 (same x — different field by row_offset)
            FieldMapping(standard_field="name",   row_offset=1, x=50.0),
            FieldMapping(standard_field="amount", row_offset=1, x=150.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (150.0, "매도")]),
        (20.0, [(50.0, "삼성전자"),   (150.0, "1000000")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].type == "매도"
    assert txns[0].name == "삼성전자"
    assert txns[0].amount == 1000000.0


def test_header_mapped_skip_keywords_filter_rows():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date",   row_offset=0, x=50.0),
            FieldMapping(standard_field="amount", row_offset=0, x=150.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (150.0, "1000000")]),
        (20.0, [(50.0, "합계"),       (150.0, "9999999")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].amount == 1000000.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_parser_registry.py::test_header_mapped_single_header_parses_two_transactions -q
```

Expected: FAIL — `build_class` has no `header_mapped` branch

- [ ] **Step 3: Add `header_mapped` branch to `build_class` in `core/parser_registry.py`**

Inside `build_class`, replace the entire inner `parse` function with:

```python
    def parse(self, pages):
        import re as _re_mod
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        _header_group_size = max(
            (fm.row_offset for fm in _cfg.field_mappings), default=0
        ) + 1
        _date_fm = next(
            (fm for fm in _cfg.field_mappings if fm.standard_field == "date"), None
        )
        _date_x = _date_fm.x if _date_fm else None
        _date_compiled = _re_mod.compile(_cfg.date_re)
        X_TOLERANCE = 50.0

        def _contains_skip(row_cells):
            joined = " ".join(t for _, t in row_cells)
            return any(kw in joined for kw in _cfg.skip_keywords)

        from core.pdf_utils import get_page_rows_with_y as _get_rows_with_y

        if _cfg.layout_type == "header_mapped":
            for page_idx, page in enumerate(pages):
                if page_idx < _cfg.start_page:
                    continue

                rows_with_y = [
                    (ry, rc)
                    for ry, rc in _get_rows_with_y(page, y_tolerance=4.0)
                    if rc and not _contains_skip(rc)
                ]

                groups: list[list[tuple]] = []
                current: list[tuple] = []
                for row_y, row_cells in rows_with_y:
                    is_anchor = False
                    if _date_x is not None:
                        closest = min(row_cells, key=lambda c: abs(c[0] - _date_x))
                        if _date_compiled.match(closest[1]):
                            is_anchor = True
                    if not is_anchor and any(_date_compiled.match(t) for _, t in row_cells):
                        is_anchor = True

                    if is_anchor:
                        if current:
                            groups.append(current)
                        current = [(row_y, row_cells)]
                    elif current:
                        current.append((row_y, row_cells))
                if current:
                    groups.append(current)

                for group in groups:
                    raw: dict = {}
                    for row_offset, (row_y, row_cells) in enumerate(group):
                        if row_offset < _header_group_size:
                            candidates = [fm for fm in _cfg.field_mappings
                                          if fm.row_offset == row_offset]
                        else:
                            candidates = list(_cfg.field_mappings)
                        if not candidates:
                            continue
                        for cell_x, cell_text in row_cells:
                            best = min(candidates, key=lambda fm: abs(fm.x - cell_x))
                            if abs(best.x - cell_x) > X_TOLERANCE:
                                continue
                            field = best.standard_field
                            raw[field] = (
                                raw[field] + " " + cell_text if raw.get(field) else cell_text
                            )
                    transactions.append(Transaction(
                        date=raw.get("date", ""),
                        type=raw.get("type", ""),
                        ticker=raw.get("ticker", ""),
                        name=raw.get("name", ""),
                        quantity=_parse_num(raw.get("quantity", "")),
                        price=_parse_num(raw.get("price", "")),
                        amount=_parse_num(raw.get("amount", "")),
                        fee=_parse_num(raw.get("fee", "")),
                        tax=_parse_num(raw.get("tax", "")),
                        balance=_parse_num(raw.get("balance", "")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    ))
                    raw_rows.append(raw)

        elif _cfg.layout_type == "rotated":
            # keep existing rotated logic unchanged
            for page_idx, page in enumerate(pages):
                if page_idx < _cfg.start_page:
                    continue
                items: list[dict] = []
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    bx = block["bbox"][0]
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span["text"].strip()
                            if text:
                                items.append({
                                    "x": round(bx),
                                    "y_top": round(span["bbox"][1]),
                                    "text": text,
                                })
                for date_item in [it for it in items if _date_compiled.match(it["text"])]:
                    raw = {"date": date_item["text"]}
                    for fm in _cfg.field_mappings:
                        if fm.standard_field == "date":
                            continue
                        candidates = [
                            it for it in items
                            if fm.y_min <= it["y_top"] <= fm.y_max
                            and abs(it["x"] - date_item["x"]) <= 50
                        ]
                        raw[fm.standard_field] = candidates[0]["text"] if candidates else ""
                    transactions.append(Transaction(
                        date=raw.get("date", ""),
                        type=raw.get("type", ""),
                        ticker=raw.get("ticker", ""),
                        name=raw.get("name", ""),
                        quantity=_parse_num(raw.get("quantity", "")),
                        price=_parse_num(raw.get("price", "")),
                        amount=_parse_num(raw.get("amount", "")),
                        fee=_parse_num(raw.get("fee", "")),
                        tax=_parse_num(raw.get("tax", "")),
                        balance=_parse_num(raw.get("balance", "")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    ))
                    raw_rows.append(raw)

        return transactions, raw_rows
```

- [ ] **Step 4: Run all parser registry tests**

```bash
python3 -m pytest tests/test_parser_registry.py -q
```

Expected: all pass

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -q
```

Expected: all tests pass (built-in parsers unaffected)

- [ ] **Step 6: Commit**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat: add header_mapped layout to build_class parser execution"
```

---

## Task 6: UI update

**Files:**
- Modify: `ui/parser_builder_dialog.py`

- [ ] **Step 1: Replace the full content of `ui/parser_builder_dialog.py`**

```python
import fitz
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QSpinBox, QFormLayout, QScrollArea, QWidget,
    QMessageBox, QFileDialog, QTextEdit,
)


class ParserBuilderDialog(QDialog):
    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 추가")
        self.setMinimumSize(640, 520)
        self._pages = pages
        self._template_path: str | None = None
        self._annotations = None

        main = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._broker_edit = QLineEdit()
        form.addRow("증권사명 *:", self._broker_edit)

        self._kw_edit = QLineEdit()
        self._kw_edit.setPlaceholderText("쉼표 구분 (예: 키움증권, 거래내역확인)")
        form.addRow("감지 키워드 *:", self._kw_edit)

        self._data_start_edit = QLineEdit()
        self._data_start_edit.setPlaceholderText("예: 거래일자")
        form.addRow("데이터 시작 키워드 *:", self._data_start_edit)

        self._date_fmt_edit = QLineEdit()
        self._date_fmt_edit.setPlaceholderText("예: yyyy/mm/dd  (빈칸이면 자동 감지)")
        form.addRow("날짜 형식:", self._date_fmt_edit)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 99)
        form.addRow("시작 페이지:", self._start_spin)

        file_row = QHBoxLayout()
        download_btn = QPushButton("포맷 파일 다운로드")
        download_btn.clicked.connect(self._download_template)
        upload_btn = QPushButton("업로드")
        upload_btn.clicked.connect(self._upload_template)
        file_row.addWidget(download_btn)
        file_row.addWidget(upload_btn)
        file_row.addStretch()
        form.addRow("포맷 파일:", file_row)

        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setMinimumHeight(180)
        self._summary.setPlainText(
            "1. 데이터 시작 키워드(예: 거래일자)를 입력하고 포맷 파일을 다운로드하세요.\n"
            "2. 엑셀에서 제목행(회색) 셀을 노란색으로 칠해 필드를 지정하세요.\n"
            "3. 무시할 키워드(합계 등)는 회색으로 칠하세요.\n"
            "4. 저장한 엑셀 파일을 업로드한 뒤 파서를 저장하세요."
        )
        form.addRow("업로드 결과:", self._summary)

        scroll.setWidget(form_widget)
        main.addWidget(scroll)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("저장")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        main.addLayout(btns)

    def _download_template(self):
        from core.parser_template import export_parser_template, date_format_to_re

        data_start = self._data_start_edit.text().strip()
        if not data_start:
            QMessageBox.warning(self, "입력 오류", "데이터 시작 키워드를 입력하세요.")
            return

        date_fmt = self._date_fmt_edit.text().strip()
        date_re = date_format_to_re(date_fmt) if date_fmt else None

        path, _ = QFileDialog.getSaveFileName(
            self, "포맷 파일 다운로드", "parser_format.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            detected_fmt = export_parser_template(
                self._pages, path,
                data_start_keyword=data_start,
                date_re=date_re,
                max_pages=3,
            )
        except Exception as exc:
            QMessageBox.critical(self, "다운로드 실패", str(exc))
            return

        if detected_fmt and not date_fmt:
            self._date_fmt_edit.setText(detected_fmt)

        self._template_path = path
        QMessageBox.information(self, "완료", f"포맷 파일을 저장했습니다:\n{path}")

    def _upload_template(self):
        from core.parser_template import read_parser_template

        path, _ = QFileDialog.getOpenFileName(
            self, "포맷 파일 업로드", self._template_path or "", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        try:
            annotations = read_parser_template(path)
        except Exception as exc:
            QMessageBox.critical(self, "업로드 실패", str(exc))
            return

        self._template_path = path
        self._annotations = annotations

        if annotations.detected_date_format and not self._date_fmt_edit.text().strip():
            self._date_fmt_edit.setText(annotations.detected_date_format)

        lines = [f"업로드 파일: {path}", ""]
        lines.append(f"필드 매핑: {len(annotations.field_mappings)}개")
        for fm in annotations.field_mappings:
            lines.append(f"  - {fm.standard_field}  (row_offset={fm.row_offset}, x={fm.x:.1f})")
        lines.append("")
        lines.append(f"무시 키워드: {len(annotations.skip_keywords)}개")
        for kw in annotations.skip_keywords:
            lines.append(f"  - {kw}")
        self._summary.setPlainText("\n".join(lines))

    def _save(self):
        from core import parser_registry
        from core.parser_registry import DynamicParserConfig, FieldMapping
        from core.parser_template import date_format_to_re

        broker_name = self._broker_edit.text().strip()
        if not broker_name:
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return

        keywords = [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "입력 오류", "감지 키워드를 하나 이상 입력하세요.")
            return

        if self._annotations is None:
            QMessageBox.warning(self, "입력 오류", "노란색/회색 표시를 마친 포맷 파일을 업로드하세요.")
            return

        if not self._annotations.field_mappings:
            QMessageBox.warning(self, "입력 오류", "노란색으로 표시된 필드 셀이 없습니다.")
            return

        date_fmt = self._date_fmt_edit.text().strip()
        if not date_fmt:
            QMessageBox.warning(self, "입력 오류", "날짜 형식을 입력하세요 (예: yyyy/mm/dd).")
            return

        field_mappings = [
            FieldMapping(
                standard_field=af.standard_field,
                row_offset=af.row_offset,
                x=af.x,
            )
            for af in self._annotations.field_mappings
        ]

        config = DynamicParserConfig(
            broker_name=broker_name,
            detection_keywords=keywords,
            date_re=date_format_to_re(date_fmt),
            layout_type="header_mapped",
            start_page=self._start_spin.value(),
            skip_keywords=list(self._annotations.skip_keywords),
            field_mappings=field_mappings,
        )

        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
```

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/ -q
```

Expected: all tests pass

- [ ] **Step 3: Smoke-test the app**

```bash
python3 main.py
```

Open a PDF, click "파서 추가", verify:
- "데이터 시작 키워드" field is present
- "날짜 형식" field shows placeholder "예: yyyy/mm/dd"
- "행/거래" and "레이아웃 타입" fields are gone
- "포맷 파일 다운로드" triggers date auto-detection and fills the format field
- Upload a colored xlsx and verify the summary shows `field_mappings` info

- [ ] **Step 4: Commit**

```bash
git add ui/parser_builder_dialog.py
git commit -m "feat: update ParserBuilderDialog for header_mapped parser flow"
```
