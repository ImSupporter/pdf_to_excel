# Coordinate Template Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace header-derived dynamic parsing with a coordinate-template parser that repeats user-defined x/y cell areas and exports rows using user-entered field names.

**Architecture:** Keep the existing app flow: PDF load -> parser selection -> dynamic parser -> Excel export. Replace the dynamic parser config shape, parser runtime, zone spec conversion, and parser builder UI so the single source of truth is the Zone Editor coordinate template. Excel export already preserves raw dict keys, so it remains unchanged except for regression tests.

**Tech Stack:** Python 3, PyQt6, PyMuPDF (`fitz`), openpyxl, pytest, dataclasses.

---

## Progress Snapshot

Last updated: 2026-05-05.

Completed and reviewed:

- [x] Task 1: Standard Transaction Model
  - Commit: `d5c6489 refactor: reduce transaction standard fields`
  - Verification: `python3 -m pytest tests/test_models.py -q` -> `2 passed`
  - Review status: spec compliance approved; code quality approved to proceed.
- [x] Task 2: Coordinate Parsing Engine
  - Commits:
    - `3c61266 feat: add coordinate template parser runtime`
    - `4fa7dd6 fix: join coordinate parser duplicate fields`
    - `7cd6a66 fix: clamp coordinate parser data bounds`
  - Verification: `python3 -m pytest tests/test_parser_registry.py -q` -> `9 passed`
  - Review status: spec compliance approved; code quality approved after duplicate-field, half-open-bound, invalid-standard-field, and `data_end_y` clamp fixes.
- [x] Task 3: Zone Spec Cell Generation
  - Commits:
    - `1c2800d feat: generate coordinate cell mappings`
    - `31a7c2c fix: validate coordinate zone specs`
  - Verification: `python3 -m pytest tests/test_zone_spec.py -q` -> `15 passed`
  - Review status: initial spec compliance approved under migration boundary; code quality found validation gaps; validation fix committed. Final re-review is still pending.

Remaining:

- [ ] Task 3 final spec/quality re-review after `31a7c2c`
- [ ] Task 4: Zone Editor Template Markers
- [ ] Task 5: Parser Builder Mapping UI
- [ ] Task 6: Export and Full Regression
- [ ] Final whole-branch review

Important current state:

- `Transaction` now has only `date`, `type`, `amount`, `balance`, `broker`, and `raw`.
- `core.parser_registry` now exposes `CellMapping`, coordinate-template `DynamicParserConfig`, and `VALID_STANDARD_FIELDS` derived from `core.models.STANDARD_FIELDS`.
- Coordinate parsing uses user `display_name` keys for raw rows, joins duplicate display/standard mappings, uses half-open cell bounds, skips only fully empty repeated slots, and clamps extraction to `data_end_y`.
- `core.zone_spec` now generates blank `CellMapping` objects from per-column y slots and validates broker, keywords, `start_page`, data/template ranges, mappings, and standard fields.
- `ui.zone_editor_widget.py` and `ui.parser_builder_dialog.py` are not migrated yet. The UI still uses old zone/header concepts until Tasks 4 and 5.
- Known unrelated untracked files are present and should not be removed without user direction: `KakaoTalk_Photo_2026-05-04-21-45-27.png`, `parser_gen.py`, and `증권거래내역변환기.spec`.
- Do not read or use `docs/superpowers/specs/2026-05-05-parser-format-design.md`; AGENTS.md marks it as wrong.

## File Structure

- Modify `core/models.py`: shrink `STANDARD_FIELDS` and `Transaction` to the four standard fields plus broker/raw.
- Modify `core/parser_registry.py`: add `CellMapping`, update `DynamicParserConfig`, save/load new JSON, filter old non-coordinate parsers out of `get_all_parsers()`, implement coordinate-template parsing.
- Modify `core/zone_spec.py`: replace header extraction helpers with coordinate-template cell generation helpers.
- Modify `ui/zone_editor_widget.py`: add first-transaction template end marker and return `template_row_ys_per_col`.
- Modify `ui/parser_builder_dialog.py`: remove header/date-field extraction workflow and add cell mapping card workflow.
- Modify tests:
  - `tests/test_models.py`
  - `tests/test_parser_registry.py`
  - `tests/test_zone_spec.py`
  - `tests/test_zone_editor_widget.py`
  - `tests/test_exporter.py`

## Task 1: Standard Transaction Model

**Files:**
- Modify: `core/models.py`
- Test: `tests/test_models.py`

- [x] **Step 1: Write the failing model tests**

Add these tests to `tests/test_models.py`:

```python
def test_standard_fields_are_coordinate_template_core_fields_only():
    from core.models import STANDARD_FIELDS

    assert STANDARD_FIELDS == {
        "date": "거래일자",
        "type": "거래종류",
        "amount": "거래금액",
        "balance": "잔액",
    }


def test_transaction_has_four_standard_values_and_raw_custom_fields():
    from core.models import Transaction

    tx = Transaction(
        date="2026/05/05",
        type="매수",
        amount=12345.0,
        balance=99999.0,
        broker="테스트증권",
        raw={"사용자종목명": "삼성전자", "사용자수량": "10"},
    )

    assert tx.date == "2026/05/05"
    assert tx.type == "매수"
    assert tx.amount == 12345.0
    assert tx.balance == 99999.0
    assert tx.broker == "테스트증권"
    assert tx.raw["사용자종목명"] == "삼성전자"
    assert not hasattr(tx, "ticker")
    assert not hasattr(tx, "quantity")
```

- [x] **Step 2: Run the model tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_models.py -q
```

Expected: FAIL because `STANDARD_FIELDS` and `Transaction` still include the removed fields.

- [x] **Step 3: Update `core/models.py`**

Replace `core/models.py` with:

```python
from dataclasses import dataclass, field

STANDARD_FIELDS = {
    "date": "거래일자",
    "type": "거래종류",
    "amount": "거래금액",
    "balance": "잔액",
}


@dataclass
class Transaction:
    date: str
    type: str
    amount: float
    balance: float
    broker: str
    raw: dict = field(default_factory=dict)
```

- [x] **Step 4: Run the model tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_models.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "refactor: reduce transaction standard fields"
```

## Task 2: Coordinate Parsing Engine

**Files:**
- Modify: `core/parser_registry.py`
- Test: `tests/test_parser_registry.py`

- [x] **Step 1: Replace old parser-registry tests with coordinate-template tests**

Update `tests/test_parser_registry.py` so it covers the new dataclasses, JSON roundtrip, parser filtering, coordinate extraction, row retention, and defaults:

```python
import json
from unittest.mock import MagicMock


def _mock_page(words, width=400.0, height=500.0):
    page = MagicMock()
    page.rect.width = width
    page.rect.height = height
    page.get_text.return_value = words
    return page


def test_cell_mapping_roundtrip():
    from core.parser_registry import CellMapping

    cm = CellMapping(
        display_name="사용자거래일자",
        standard_field="date",
        column_index=0,
        x_min=0.0,
        x_max=100.0,
        template_y_min=0.0,
        template_y_max=20.0,
    )

    assert cm.display_name == "사용자거래일자"
    assert cm.standard_field == "date"
    assert cm.column_index == 0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import CellMapping, DynamicParserConfig

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=200.0,
        template_height=20.0,
        column_xs=[100.0, 250.0],
        template_row_ys_per_col={1: [10.0]},
        cell_mappings=[
            CellMapping("거래일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("종목명", None, 1, 100.0, 250.0, 0.0, 10.0),
        ],
    )

    parser_registry.save([cfg])
    loaded = parser_registry.load()

    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].layout_type == "coordinate_template"
    assert loaded[0].template_row_ys_per_col == {1: [10.0]}
    assert loaded[0].cell_mappings[1].display_name == "종목명"


def test_load_ignores_unknown_fields_and_keeps_old_configs_out_of_runtime(tmp_path, monkeypatch):
    from core import parser_registry

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    old_and_new = [
        {
            "broker_name": "구버전증권",
            "detection_keywords": ["구버전"],
            "date_re": r"\d{4}/\d{2}/\d{2}",
            "layout_type": "header_mapped",
            "start_page": 0,
            "skip_keywords": [],
            "field_mappings": [],
        },
        {
            "broker_name": "새증권",
            "detection_keywords": ["새"],
            "layout_type": "coordinate_template",
            "start_page": 0,
            "data_start_y": 100.0,
            "data_end_y": 120.0,
            "template_height": 20.0,
            "column_xs": [],
            "template_row_ys_per_col": {},
            "cell_mappings": [],
        },
    ]
    (tmp_path / "parsers.json").write_text(
        json.dumps(old_and_new, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = parser_registry.load()
    assert [cfg.broker_name for cfg in loaded] == ["구버전증권", "새증권"]

    runtime_names = [cls.BROKER_NAME for cls in parser_registry.get_all_parsers()]
    assert "새증권" in runtime_names
    assert "구버전증권" not in runtime_names


def test_coordinate_template_parses_repeated_rows_with_display_names():
    from core.parser_registry import CellMapping, DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=140.0,
        template_height=20.0,
        column_xs=[100.0, 250.0],
        template_row_ys_per_col={1: [10.0]},
        cell_mappings=[
            CellMapping("사용자일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("사용자종목명", None, 1, 100.0, 250.0, 0.0, 10.0),
            CellMapping("사용자금액", "amount", 1, 100.0, 250.0, 10.0, 20.0),
        ],
    )
    words = [
        (10.0, 102.0, 70.0, 110.0, "2026/05/01", 0, 0, 0),
        (110.0, 102.0, 160.0, 110.0, "삼성", 0, 0, 1),
        (165.0, 102.0, 210.0, 110.0, "전자", 0, 0, 2),
        (110.0, 114.0, 180.0, 122.0, "1,000", 0, 0, 3),
        (10.0, 122.0, 70.0, 130.0, "2026/05/02", 0, 0, 4),
        (110.0, 122.0, 160.0, 130.0, "카카오", 0, 0, 5),
        (110.0, 134.0, 180.0, 138.0, "bad-number", 0, 0, 6),
    ]

    txns, raws = build_class(cfg)().parse([_mock_page(words)])

    assert raws == [
        {"사용자일자": "2026/05/01", "사용자종목명": "삼성 전자", "사용자금액": "1,000"},
        {"사용자일자": "2026/05/02", "사용자종목명": "카카오", "사용자금액": "bad-number"},
    ]
    assert txns[0].date == "2026/05/01"
    assert txns[0].amount == 1000.0
    assert txns[1].date == "2026/05/02"
    assert txns[1].amount == 0.0


def test_coordinate_template_skips_only_completely_empty_repeated_slot():
    from core.parser_registry import CellMapping, DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=160.0,
        template_height=20.0,
        column_xs=[100.0],
        template_row_ys_per_col={},
        cell_mappings=[
            CellMapping("사용자일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("사용자잔액", "balance", 1, 100.0, 400.0, 0.0, 20.0),
        ],
    )
    words = [
        (10.0, 102.0, 70.0, 110.0, "2026/05/01", 0, 0, 0),
        (110.0, 142.0, 180.0, 150.0, "9,999", 0, 0, 1),
    ]

    txns, raws = build_class(cfg)().parse([_mock_page(words)])

    assert raws == [
        {"사용자일자": "2026/05/01", "사용자잔액": ""},
        {"사용자일자": "", "사용자잔액": "9,999"},
    ]
    assert txns[1].date == ""
    assert txns[1].balance == 9999.0
```

- [x] **Step 2: Run parser-registry tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_parser_registry.py -q
```

Expected: FAIL because `CellMapping` and the coordinate-template parser are not implemented.

- [x] **Step 3: Implement `core/parser_registry.py`**

Replace the old field-mapping parser runtime with this structure:

```python
import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_STANDARD_FIELDS = {"date", "type", "amount", "balance"}


@dataclass
class CellMapping:
    display_name: str
    standard_field: str | None
    column_index: int
    x_min: float
    x_max: float
    template_y_min: float
    template_y_max: float


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    layout_type: str
    start_page: int
    data_start_y: float = 0.0
    data_end_y: float = 0.0
    template_height: float = 0.0
    column_xs: list[float] = field(default_factory=list)
    template_row_ys_per_col: dict[int, list[float]] = field(default_factory=dict)
    cell_mappings: list[CellMapping] = field(default_factory=list)


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "증권거래내역변환기"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _coerce_row_ys(raw: Any) -> dict[int, list[float]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[int, list[float]] = {}
    for key, values in raw.items():
        try:
            col = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(values, list):
            result[col] = [float(v) for v in values]
    return result


def _load_cell_mappings(raw_mappings: Any) -> list[CellMapping]:
    if not isinstance(raw_mappings, list):
        return []
    valid = {f.name for f in dataclasses.fields(CellMapping)}
    mappings: list[CellMapping] = []
    for item in raw_mappings:
        if not isinstance(item, dict):
            continue
        data = {k: v for k, v in item.items() if k in valid}
        standard = data.get("standard_field")
        if standard not in VALID_STANDARD_FIELDS:
            data["standard_field"] = None
        try:
            mappings.append(CellMapping(**data))
        except TypeError:
            continue
    return mappings


def load() -> list[DynamicParserConfig]:
    path = _get_data_dir() / "parsers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    configs: list[DynamicParserConfig] = []
    valid_cfg = {f.name for f in dataclasses.fields(DynamicParserConfig)}
    for item in data:
        if not isinstance(item, dict):
            continue
        cfg_kwargs = {k: v for k, v in item.items() if k in valid_cfg}
        cfg_kwargs["template_row_ys_per_col"] = _coerce_row_ys(
            item.get("template_row_ys_per_col", {})
        )
        cfg_kwargs["cell_mappings"] = _load_cell_mappings(
            item.get("cell_mappings", [])
        )
        if "layout_type" not in cfg_kwargs:
            cfg_kwargs["layout_type"] = "header_mapped"
        try:
            configs.append(DynamicParserConfig(**cfg_kwargs))
        except TypeError:
            continue
    return configs


def save(configs: list[DynamicParserConfig]) -> None:
    path = _get_data_dir() / "parsers.json"
    data = [dataclasses.asdict(cfg) for cfg in configs]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_num(value: str) -> float:
    try:
        return float(str(value).replace(",", "").replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


def _collect_words(page, x_min: float, x_max: float, y_min: float, y_max: float) -> str:
    words = page.get_text("words")
    picked: list[tuple[float, float, str]] = []
    for word in words:
        cx = (float(word[0]) + float(word[2])) / 2
        cy = (float(word[1]) + float(word[3])) / 2
        if x_min <= cx < x_max and y_min <= cy < y_max:
            picked.append((cy, cx, str(word[4])))
    return " ".join(text for _cy, _cx, text in sorted(picked))


def _append_value(target: dict[str, str], key: str, value: str) -> None:
    if key not in target:
        target[key] = ""
    if value:
        target[key] = f"{target[key]} {value}".strip() if target[key] else value


def build_class(config: DynamicParserConfig) -> type:
    from core.models import Transaction
    from parsers.base import BaseParser

    _cfg = config

    def parse(self, pages):
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        if _cfg.layout_type != "coordinate_template":
            return transactions, raw_rows
        if _cfg.template_height <= 0:
            return transactions, raw_rows

        for page_idx, page in enumerate(pages):
            if page_idx < _cfg.start_page:
                continue

            row_start = _cfg.data_start_y
            while row_start < _cfg.data_end_y:
                raw: dict[str, str] = {}
                standard_values: dict[str, str] = {}

                for mapping in _cfg.cell_mappings:
                    raw.setdefault(mapping.display_name, "")
                    abs_y_min = row_start + mapping.template_y_min
                    abs_y_max = row_start + mapping.template_y_max
                    value = _collect_words(
                        page,
                        mapping.x_min,
                        mapping.x_max,
                        abs_y_min,
                        abs_y_max,
                    )
                    _append_value(raw, mapping.display_name, value)
                    if mapping.standard_field in VALID_STANDARD_FIELDS:
                        _append_value(standard_values, mapping.standard_field, value)

                if any(str(value).strip() for value in raw.values()):
                    tx = Transaction(
                        date=standard_values.get("date", ""),
                        type=standard_values.get("type", ""),
                        amount=_parse_num(standard_values.get("amount", "")),
                        balance=_parse_num(standard_values.get("balance", "")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    )
                    transactions.append(tx)
                    raw_rows.append(raw)

                row_start += _cfg.template_height

        return transactions, raw_rows

    return type(
        f"DynamicParser_{config.broker_name}",
        (BaseParser,),
        {
            "BROKER_NAME": config.broker_name,
            "DETECTION_KEYWORDS": list(config.detection_keywords),
            "parse": parse,
        },
    )


def get_all_parsers() -> list:
    from parsers import PARSERS

    dynamic = [
        build_class(cfg)
        for cfg in load()
        if cfg.layout_type == "coordinate_template"
    ]
    return PARSERS + dynamic
```

- [x] **Step 4: Run parser-registry tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_parser_registry.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat: add coordinate template parser runtime"
```

## Task 3: Zone Spec Cell Generation

**Files:**
- Modify: `core/zone_spec.py`
- Test: `tests/test_zone_spec.py`

- [x] **Step 1: Replace zone-spec tests with coordinate-template tests**

Update `tests/test_zone_spec.py`:

```python
def test_split_by_ys_no_splits():
    from core.zone_spec import _split_by_ys

    assert _split_by_ys(0.0, 20.0, []) == [(0.0, 20.0)]


def test_split_by_ys_sorts_and_ignores_out_of_range():
    from core.zone_spec import _split_by_ys

    assert _split_by_ys(0.0, 20.0, [15.0, -1.0, 10.0, 21.0]) == [
        (0.0, 10.0),
        (10.0, 15.0),
        (15.0, 20.0),
    ]


def test_build_cell_mappings_supports_different_y_slot_counts_per_column():
    from core.zone_spec import ZoneSpec, build_cell_mappings

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        start_page=0,
        column_xs=[100.0, 250.0],
        template_row_ys_per_col={1: [10.0], 2: [6.0, 12.0]},
        data_start_y=100.0,
        data_end_y=180.0,
        template_height=20.0,
    )

    cells = build_cell_mappings(spec, page_width=400.0)

    assert [(c.column_index, c.x_min, c.x_max, c.template_y_min, c.template_y_max) for c in cells] == [
        (0, 0.0, 100.0, 0.0, 20.0),
        (1, 100.0, 250.0, 0.0, 10.0),
        (1, 100.0, 250.0, 10.0, 20.0),
        (2, 250.0, 400.0, 0.0, 6.0),
        (2, 250.0, 400.0, 6.0, 12.0),
        (2, 250.0, 400.0, 12.0, 20.0),
    ]
    assert all(c.display_name == "" for c in cells)
    assert all(c.standard_field is None for c in cells)


def test_zone_spec_to_config_keeps_user_named_mappings():
    from core.parser_registry import CellMapping
    from core.zone_spec import ZoneSpec, zone_spec_to_config

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트", "거래"],
        start_page=1,
        column_xs=[100.0],
        template_row_ys_per_col={},
        data_start_y=50.0,
        data_end_y=150.0,
        template_height=25.0,
    )
    mappings = [
        CellMapping("내거래일자", "date", 0, 0.0, 100.0, 0.0, 25.0),
        CellMapping("내커스텀", None, 1, 100.0, 300.0, 0.0, 25.0),
    ]

    config = zone_spec_to_config(spec, mappings)

    assert config.broker_name == "테스트"
    assert config.layout_type == "coordinate_template"
    assert config.start_page == 1
    assert config.template_height == 25.0
    assert config.cell_mappings == mappings
```

- [x] **Step 2: Run zone-spec tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_zone_spec.py -q
```

Expected: FAIL because `ZoneSpec` and `build_cell_mappings()` still use header extraction concepts.

- [x] **Step 3: Implement `core/zone_spec.py`**

Replace `core/zone_spec.py` with:

```python
from dataclasses import dataclass

from core.parser_registry import CellMapping, DynamicParserConfig, VALID_STANDARD_FIELDS


@dataclass
class ZoneSpec:
    broker_name: str
    detection_keywords: list[str]
    start_page: int
    column_xs: list[float]
    template_row_ys_per_col: dict[int, list[float]]
    data_start_y: float
    data_end_y: float
    template_height: float


def _split_by_ys(
    y_start: float, y_end: float, ys: list[float]
) -> list[tuple[float, float]]:
    interior = sorted(y for y in ys if y_start < y < y_end)
    points = [y_start] + interior + [y_end]
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _column_strips(column_xs: list[float], page_width: float) -> list[tuple[float, float]]:
    xs = sorted(x for x in column_xs if 0.0 < x < page_width)
    boundaries = [0.0] + xs + [page_width]
    return [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]


def build_cell_mappings(zone_spec: ZoneSpec, page_width: float) -> list[CellMapping]:
    mappings: list[CellMapping] = []
    for col_idx, (x_min, x_max) in enumerate(
        _column_strips(zone_spec.column_xs, page_width)
    ):
        row_ys = zone_spec.template_row_ys_per_col.get(col_idx, [])
        slots = _split_by_ys(0.0, zone_spec.template_height, row_ys)
        for y_min, y_max in slots:
            mappings.append(
                CellMapping(
                    display_name="",
                    standard_field=None,
                    column_index=col_idx,
                    x_min=x_min,
                    x_max=x_max,
                    template_y_min=y_min,
                    template_y_max=y_max,
                )
            )
    return mappings


def validate_cell_mapping(mapping: CellMapping) -> None:
    if not mapping.display_name.strip():
        raise ValueError("필드명을 입력하세요.")
    if mapping.standard_field is not None and mapping.standard_field not in VALID_STANDARD_FIELDS:
        raise ValueError("지원하지 않는 표준 필드입니다.")
    if mapping.x_min >= mapping.x_max:
        raise ValueError("셀의 x 범위가 올바르지 않습니다.")
    if mapping.template_y_min >= mapping.template_y_max:
        raise ValueError("셀의 y 범위가 올바르지 않습니다.")


def validate_zone_spec(zone_spec: ZoneSpec, mappings: list[CellMapping]) -> None:
    if not zone_spec.broker_name.strip():
        raise ValueError("증권사명을 입력하세요.")
    if not zone_spec.detection_keywords:
        raise ValueError("감지 키워드를 1개 이상 입력하세요.")
    if zone_spec.data_start_y >= zone_spec.data_end_y:
        raise ValueError("데이터 영역의 시작/끝이 올바르지 않습니다.")
    if zone_spec.template_height <= 0:
        raise ValueError("거래 1건 높이는 0보다 커야 합니다.")
    if not mappings:
        raise ValueError("셀 매핑을 1개 이상 입력하세요.")
    for mapping in mappings:
        validate_cell_mapping(mapping)


def zone_spec_to_config(
    zone_spec: ZoneSpec,
    cell_mappings: list[CellMapping],
) -> DynamicParserConfig:
    validate_zone_spec(zone_spec, cell_mappings)
    return DynamicParserConfig(
        broker_name=zone_spec.broker_name,
        detection_keywords=zone_spec.detection_keywords,
        layout_type="coordinate_template",
        start_page=zone_spec.start_page,
        data_start_y=zone_spec.data_start_y,
        data_end_y=zone_spec.data_end_y,
        template_height=zone_spec.template_height,
        column_xs=zone_spec.column_xs,
        template_row_ys_per_col=zone_spec.template_row_ys_per_col,
        cell_mappings=cell_mappings,
    )
```

- [x] **Step 4: Run zone-spec tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_zone_spec.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add core/zone_spec.py tests/test_zone_spec.py
git commit -m "feat: generate coordinate cell mappings"
```

## Task 4: Zone Editor Template Markers

**Files:**
- Modify: `ui/zone_editor_widget.py`
- Test: `tests/test_zone_editor_widget.py`

- [ ] **Step 1: Add tests for returned zone data shape**

Append to `tests/test_zone_editor_widget.py`:

```python
def test_get_zone_data_returns_template_height_and_per_column_rows(qtbot):
    from ui.zone_editor_widget import ZoneEditorWidget

    widget = ZoneEditorWidget()
    qtbot.addWidget(widget)
    widget._page_w = 300.0
    widget._page_h = 400.0
    widget._vlines = [100.0, 200.0]
    widget._hlines = {0: [8.0], 1: [5.0, 15.0]}
    widget._data_start = 100.0
    widget._template_end = 120.0
    widget._data_end = 300.0

    data = widget.get_zone_data()

    assert data["column_xs"] == [100.0, 200.0]
    assert data["template_row_ys_per_col"] == {0: [8.0], 1: [5.0, 15.0]}
    assert data["data_start_y"] == 100.0
    assert data["data_end_y"] == 300.0
    assert data["template_height"] == 20.0
```

- [ ] **Step 2: Run zone-editor tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_zone_editor_widget.py -q
```

Expected: FAIL because `_template_end` and `template_row_ys_per_col` are not part of the public data yet.

- [ ] **Step 3: Update `ZoneEditorWidget` state and `get_zone_data()`**

In `ui/zone_editor_widget.py`, make these exact structural changes:

```python
# in __init__
self._template_end = 0.0
```

Set/reset defaults:

```python
self._data_start = h * 0.28
self._template_end = min(h, self._data_start + 24.0)
self._data_end = h * 0.95
```

Return the new shape:

```python
def get_zone_data(self) -> dict:
    return {
        "column_xs": sorted(self._vlines),
        "template_row_ys_per_col": {k: sorted(v) for k, v in self._hlines.items()},
        "data_start_y": self._data_start,
        "data_end_y": self._data_end,
        "template_height": max(0.0, self._template_end - self._data_start),
    }
```

- [ ] **Step 4: Update drag target handling**

Add template-end drag support beside the existing data markers:

```python
# drag-state comment includes ("te",)
elif tag == "ds":
    self._data_start = max(0.0, min(self._template_end - 1, py))
elif tag == "te":
    self._template_end = max(self._data_start + 1, min(self._data_end - 1, py))
elif tag == "de":
    self._data_end = max(self._template_end + 1, min(self._page_h, py))
```

Add `_find_target()` support:

```python
for tag, yval in [
    ("ds", self._data_start),
    ("te", self._template_end),
    ("de", self._data_end),
]:
    if abs(sy - self._s(yval)) <= hit:
        return (tag,)
```

Remove header marker state, target detection, and drawing from `ZoneEditorWidget` during this task. The coordinate-template builder no longer uses `header_start_y` or `header_end_y`; keeping those markers would make the UI communicate a parsing rule that no longer exists.

- [ ] **Step 5: Run zone-editor tests to verify they pass**

Run:

```bash
python3 -m pytest tests/test_zone_editor_widget.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/zone_editor_widget.py tests/test_zone_editor_widget.py
git commit -m "feat: expose coordinate template zone data"
```

## Task 5: Parser Builder Mapping UI

**Files:**
- Modify: `ui/parser_builder_dialog.py`
- Test: targeted manual smoke through `python3 main.py`

- [ ] **Step 1: Remove header/date form fields**

In `ui/parser_builder_dialog.py`, remove `_date_fmt_edit` and `_header_kw_edit` creation and validation. The form keeps:

```python
self._broker_edit = QLineEdit()
self._kw_edit = QLineEdit()
self._start_spin = QSpinBox()
```

The `_on_open_zone_editor()` validation becomes:

```python
if not self._broker_edit.text().strip():
    QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
    return
if not [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]:
    QMessageBox.warning(self, "입력 오류", "감지 키워드를 입력하세요.")
    return
```

- [ ] **Step 2: Change the extraction button to cell-list generation**

Rename the button text from `"필드 추출 →"` to `"셀 목록 생성 →"` and connect it to `_on_generate_cells`.

Implement `_on_generate_cells()`:

```python
def _on_generate_cells(self) -> None:
    from core.zone_spec import ZoneSpec, build_cell_mappings

    kw_text = self._kw_edit.text().strip()
    keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
    zone_data = self._zone_editor.get_zone_data()

    self._zone_spec = ZoneSpec(
        broker_name=self._broker_edit.text().strip(),
        detection_keywords=keywords,
        start_page=self._start_spin.value(),
        column_xs=zone_data["column_xs"],
        template_row_ys_per_col=zone_data["template_row_ys_per_col"],
        data_start_y=zone_data["data_start_y"],
        data_end_y=zone_data["data_end_y"],
        template_height=zone_data["template_height"],
    )

    self._fields = build_cell_mappings(
        self._zone_spec,
        page_width=self._pages[self._start_spin.value()].rect.width,
    )
    self._populate_field_list()
    self._field_panel.setEnabled(True)
    self._confirm_btn.setEnabled(True)
```

- [ ] **Step 3: Replace field cards with editable mapping cards**

In `_populate_field_list()`, each card must include:

```python
name_edit = QLineEdit()
name_edit.setPlaceholderText("엑셀 필드명")
name_edit.textChanged.connect(lambda text, m=fm: setattr(m, "display_name", text.strip()))

standard_combo = QComboBox()
standard_combo.addItem("표준 연결 없음", None)
standard_combo.addItem("거래일자", "date")
standard_combo.addItem("거래종류", "type")
standard_combo.addItem("거래금액", "amount")
standard_combo.addItem("잔액", "balance")
standard_combo.currentIndexChanged.connect(
    lambda _idx, combo=standard_combo, m=fm: setattr(m, "standard_field", combo.currentData())
)
```

Show metadata:

```python
lbl_meta = QLabel(
    f"column={fm.column_index}  "
    f"x=[{fm.x_min:.0f},{fm.x_max:.0f}]  "
    f"y=[{fm.template_y_min:.0f},{fm.template_y_max:.0f}]"
)
```

Add `QComboBox` to the imports at the top.

- [ ] **Step 4: Filter empty cell mappings on confirm**

Update `_on_confirm()`:

```python
def _on_confirm(self) -> None:
    from core import parser_registry
    from core.zone_spec import zone_spec_to_config

    mappings = [fm for fm in self._fields if fm.display_name.strip()]
    if not mappings:
        QMessageBox.warning(self, "오류", "저장할 셀 매핑이 없습니다.")
        return

    try:
        config = zone_spec_to_config(self._zone_spec, mappings)
    except ValueError as exc:
        QMessageBox.warning(self, "입력 오류", str(exc))
        return

    configs = parser_registry.load()
    configs.append(config)
    parser_registry.save(configs)
    self.accept()
```

- [ ] **Step 5: Run a syntax/import check**

Run:

```bash
python3 -m pytest tests/test_zone_spec.py tests/test_parser_registry.py -q
```

Expected: PASS.

- [ ] **Step 6: Manual smoke the GUI**

Run:

```bash
python3 main.py
```

Expected: App opens. Adding a PDF reaches parser selection. "파서 추가" opens the builder. The builder can generate cell cards after zone setup, and empty cell cards are not saved.

- [ ] **Step 7: Commit**

```bash
git add ui/parser_builder_dialog.py
git commit -m "feat: map coordinate cells in parser builder"
```

## Task 6: Export and Full Regression

**Files:**
- Modify: `tests/test_exporter.py`
- Run: full test suite

- [ ] **Step 1: Add exporter regression for user-entered field names**

Add to `tests/test_exporter.py`:

```python
def test_export_uses_user_display_field_names(tmp_path):
    import openpyxl
    from core.exporter import export_to_excel

    output = tmp_path / "result.xlsx"
    export_to_excel(
        {
            "테스트증권": [
                {
                    "내가쓴거래일자": "2026/05/05",
                    "내가쓴종목명": "삼성전자",
                    "내가쓴거래금액": "1,000",
                }
            ]
        },
        str(output),
    )

    wb = openpyxl.load_workbook(output)
    ws = wb["테스트증권"]
    headers = [ws.cell(1, col).value for col in range(1, 4)]

    assert headers == ["내가쓴거래일자", "내가쓴종목명", "내가쓴거래금액"]
```

- [ ] **Step 2: Run exporter tests**

Run:

```bash
python3 -m pytest tests/test_exporter.py -q
```

Expected: PASS. If this fails, fix only `core/exporter.py` behavior needed to preserve raw dict key order and names.

- [ ] **Step 3: Run the full suite**

Run:

```bash
python3 -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 4: Inspect status**

Run:

```bash
git status --short
```

Expected: only intended modified test files remain staged or unstaged. Existing unrelated untracked files may still appear and must not be removed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_exporter.py
git commit -m "test: preserve user display field names"
```

## Self-Review Checklist

- Spec coverage: Tasks cover standard field reduction, coordinate config, per-column y slots, user display names, raw row retention, parser builder UI, and exporter preservation.
- Placeholder scan: The plan contains no deferred requirements.
- Type consistency: `CellMapping`, `DynamicParserConfig`, `ZoneSpec`, and `template_row_ys_per_col` use the same names throughout.
- Risk: Task 5 is UI-heavy and should be reviewed with a real PDF after the automated tests pass.
