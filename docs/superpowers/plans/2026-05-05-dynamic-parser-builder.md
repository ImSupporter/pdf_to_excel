# Dynamic Parser Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 GUI에서 새 증권사 파서를 만들고 영구 저장하며, PDF 로드 후 파서를 선택할 수 있는 기능 추가.

**Architecture:** `core/parser_registry.py`가 JSON 영구 저장과 런타임 파서 클래스 팩토리를 담당. `ui/parser_select_dialog.py`는 PDF 로드 후 항상 표시되며 추천 파서를 하이라이트. `ui/parser_builder_dialog.py`는 PDF 미리보기 테이블과 필드 매핑 UI를 제공. 출력은 증권사별 개별 시트로 변경.

**Tech Stack:** PyQt6, PyMuPDF(fitz), openpyxl, Python dataclasses, json, sys/os(APPDATA)

---

## File Map

| 파일 | 상태 | 역할 |
|---|---|---|
| `core/parser_registry.py` | 신규 | DynamicParserConfig 데이터 모델, JSON 저장/로드, build_class() 팩토리, get_all_parsers() |
| `ui/parser_select_dialog.py` | 신규 | 파서 선택 다이얼로그 (추천 하이라이트, 삭제) |
| `ui/parser_builder_dialog.py` | 신규 | 파서 생성 UI (PDF 미리보기 + 필드 매핑) |
| `tests/test_parser_registry.py` | 신규 | parser_registry 단위 테스트 |
| `core/detector.py` | 수정 | get_all_parsers() 호출로 동적 파서 포함 |
| `core/exporter.py` | 수정 | 통합 시트 제거, 증권사별 시트만 출력 |
| `ui/main_window.py` | 수정 | ConvertWorker 시그니처 변경, _process_file() 흐름 변경 |
| `tests/test_exporter.py` | 수정 | 새 exporter 시그니처에 맞게 갱신 |
| `ui/column_select.py` | 삭제 | 통합 시트 제거로 불필요 |
| `ui/mapping_dialog.py` | 삭제 | ParserBuilderDialog로 대체 |

---

## Task 1: `core/parser_registry.py` — 데이터 모델 + JSON 영구 저장

**Files:**
- Create: `core/parser_registry.py`
- Create: `tests/test_parser_registry.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_parser_registry.py
import json
import tempfile
from pathlib import Path
import pytest


def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", column_index=0, row_offset=0, y_min=0, y_max=0)
    assert fm.standard_field == "date"
    assert fm.column_index == 0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date", column_index=0, row_offset=0, y_min=0, y_max=0),
            FieldMapping(standard_field="amount", column_index=3, row_offset=0, y_min=0, y_max=0),
        ],
    )
    parser_registry.save([cfg])

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].detection_keywords == ["테스트", "거래내역"]
    assert len(loaded[0].field_mappings) == 2
    assert loaded[0].field_mappings[1].column_index == 3


def test_load_returns_empty_when_no_file(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    result = parser_registry.load()
    assert result == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
python -m pytest tests/test_parser_registry.py -v
```

Expected: `ImportError: No module named 'core.parser_registry'`

- [ ] **Step 3: `core/parser_registry.py` 데이터 모델 + 저장/로드 구현**

```python
# core/parser_registry.py
import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldMapping:
    standard_field: str  # STANDARD_FIELDS key: "date", "type", "ticker", ...
    column_index: int = 0   # table layout: column index within row group
    row_offset: int = 0     # table layout: row offset within tx group (0=anchor)
    y_min: int = 0          # rotated layout: y_top minimum
    y_max: int = 0          # rotated layout: y_top maximum


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str                    # raw regex string
    layout_type: str                # "table" | "rotated"
    start_page: int                 # page index to start parsing from
    rows_per_tx: int                # rows per transaction (table layout only)
    skip_keywords: list[str]        # row skip keywords (table layout only)
    field_mappings: list[FieldMapping] = field(default_factory=list)


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "증권거래내역변환기"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> list[DynamicParserConfig]:
    path = _get_data_dir() / "parsers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    configs = []
    for item in data:
        mappings = [FieldMapping(**m) for m in item.pop("field_mappings", [])]
        configs.append(DynamicParserConfig(**item, field_mappings=mappings))
    return configs


def save(configs: list[DynamicParserConfig]) -> None:
    path = _get_data_dir() / "parsers.json"
    data = [dataclasses.asdict(cfg) for cfg in configs]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_parser_registry.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: 커밋**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat: add DynamicParserConfig dataclass and JSON persistence"
```

---

## Task 2: `core/parser_registry.py` — `build_class()` + `get_all_parsers()`

**Files:**
- Modify: `core/parser_registry.py`
- Modify: `tests/test_parser_registry.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
# tests/test_parser_registry.py 에 추가

def test_build_class_returns_base_parser_subclass(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class
    from parsers.base import BaseParser

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", column_index=0),
            FieldMapping(standard_field="amount", column_index=2),
        ],
    )
    cls = build_class(cfg)
    assert issubclass(cls, BaseParser)
    assert cls.BROKER_NAME == "테스트증권"
    assert cls.DETECTION_KEYWORDS == ["테스트"]
    inst = cls()
    assert hasattr(inst, "parse")


def test_get_all_parsers_includes_builtins(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    from core.parser_registry import get_all_parsers
    from parsers.samsung import SamsungParser
    from parsers.mirae_asset import MiraeAssetParser

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
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])

    all_parsers = get_all_parsers()
    names = [p.BROKER_NAME for p in all_parsers]
    assert "다이나믹증권" in names
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_parser_registry.py::test_build_class_returns_base_parser_subclass -v
```

Expected: `ImportError` 또는 `AttributeError: module has no attribute 'build_class'`

- [ ] **Step 3: `build_class()` + `get_all_parsers()` 구현 — `core/parser_registry.py` 하단에 추가**

```python
# core/parser_registry.py 하단에 추가

def build_class(config: "DynamicParserConfig") -> type:
    """config를 받아 BaseParser를 상속하는 런타임 클래스를 반환한다."""
    import re as _re
    from parsers.base import BaseParser
    from core.models import Transaction
    from core.pdf_utils import get_page_rows

    _cfg = config
    _date_re = _re.compile(config.date_re)

    def _parse_num(s: str) -> float:
        try:
            return float(str(s).replace(",", "").replace(" ", ""))
        except (ValueError, AttributeError):
            return 0.0

    def parse(self, pages):
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        for page_idx, page in enumerate(pages):
            if page_idx < _cfg.start_page:
                continue

            if _cfg.layout_type == "table":
                all_rows = list(get_page_rows(page, y_tolerance=4.0))
                i = 0
                while i < len(all_rows):
                    anchor_texts = [cell[1] for cell in all_rows[i]]
                    if not anchor_texts:
                        i += 1
                        continue
                    if any(kw in " ".join(anchor_texts) for kw in _cfg.skip_keywords):
                        i += 1
                        continue
                    if not _date_re.match(anchor_texts[0]):
                        i += 1
                        continue

                    groups: list[list[str]] = [anchor_texts]
                    for offset in range(1, _cfg.rows_per_tx):
                        j = i + offset
                        groups.append([cell[1] for cell in all_rows[j]] if j < len(all_rows) else [])

                    raw: dict = {}
                    for fm in _cfg.field_mappings:
                        grp = groups[fm.row_offset] if fm.row_offset < len(groups) else []
                        raw[fm.standard_field] = grp[fm.column_index] if fm.column_index < len(grp) else ""

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
                    i += _cfg.rows_per_tx

            elif _cfg.layout_type == "rotated":
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

                for date_item in [it for it in items if _date_re.match(it["text"])]:
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
    return PARSERS + [build_class(cfg) for cfg in load()]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_parser_registry.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: 커밋**

```bash
git add core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat: add build_class() factory and get_all_parsers()"
```

---

## Task 3: `core/detector.py` — `get_all_parsers()` 사용

**Files:**
- Modify: `core/detector.py`
- Modify: `tests/test_detector.py`

- [ ] **Step 1: 동적 파서 감지 실패 테스트 추가**

```python
# tests/test_detector.py 에 추가

def test_detects_dynamic_parser(tmp_path, monkeypatch):
    import fitz
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, save
    from core.detector import detect_parser

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트다이나믹",
        detection_keywords=["UNIQUE_KEYWORD_XYZ"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])

    doc = fitz.open()
    page = doc.new_page()
    # insert the keyword into the page
    page.insert_text((100, 100), "UNIQUE_KEYWORD_XYZ")
    pages = list(doc)

    result = detect_parser(pages)
    assert result is not None
    assert result.BROKER_NAME == "테스트다이나믹"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_detector.py::test_detects_dynamic_parser -v
```

Expected: FAIL (detect_parser returns None — dynamic parser not in search list yet)

- [ ] **Step 3: `core/detector.py` 수정**

```python
# core/detector.py (전체 교체)
import fitz
from parsers.base import BaseParser


def detect_parser(pages: list[fitz.Page]) -> type[BaseParser] | None:
    from core.parser_registry import get_all_parsers
    sample_text = " ".join(pages[0].get_text().split())
    for parser_class in get_all_parsers():
        if any(kw in sample_text for kw in parser_class.DETECTION_KEYWORDS):
            return parser_class
    return None
```

- [ ] **Step 4: 전체 detector 테스트 통과 확인**

```bash
python -m pytest tests/test_detector.py -v
```

Expected: 4 tests PASS (기존 3 + 신규 1)

- [ ] **Step 5: 커밋**

```bash
git add core/detector.py tests/test_detector.py
git commit -m "feat: detect_parser() now includes dynamic parsers via get_all_parsers()"
```

---

## Task 4: `core/exporter.py` — 증권사별 시트만 출력

**Files:**
- Modify: `core/exporter.py`
- Modify: `tests/test_exporter.py`

- [ ] **Step 1: 새 시그니처에 맞는 테스트로 교체**

```python
# tests/test_exporter.py (전체 교체)
import os
import tempfile
import openpyxl
from core.exporter import export_to_excel


def test_export_creates_broker_sheets():
    broker_raw = {
        "삼성증권": [
            {"거래일자": "2025/11/06", "거래명": "매수", "거래금액": "113,775"},
            {"거래일자": "2025/11/07", "거래명": "매도", "거래금액": "50,000"},
        ],
        "미래에셋증권": [
            {"거래일자": "2025/11/06", "거래종류": "매수", "거래금액": "200,000"},
        ],
    }
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(broker_raw, path)
        wb = openpyxl.load_workbook(path)
        assert "삼성증권" in wb.sheetnames
        assert "미래에셋증권" in wb.sheetnames
        assert "통합" not in wb.sheetnames
    finally:
        os.unlink(path)


def test_export_broker_sheet_headers_match_raw_keys():
    broker_raw = {
        "테스트증권": [
            {"거래일자": "2025/01/01", "종목명": "삼성전자", "거래금액": "100,000"},
        ]
    }
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(broker_raw, path)
        wb = openpyxl.load_workbook(path)
        ws = wb["테스트증권"]
        headers = [ws.cell(1, c).value for c in range(1, 4)]
        assert "거래일자" in headers
        assert "종목명" in headers
        assert "거래금액" in headers
    finally:
        os.unlink(path)


def test_export_broker_sheet_data_rows():
    broker_raw = {
        "테스트증권": [
            {"거래일자": "2025/01/01", "거래금액": "100,000"},
            {"거래일자": "2025/01/02", "거래금액": "200,000"},
        ]
    }
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(broker_raw, path)
        wb = openpyxl.load_workbook(path)
        ws = wb["테스트증권"]
        assert ws.max_row == 3  # header + 2 data rows
    finally:
        os.unlink(path)


def test_export_skips_empty_broker():
    broker_raw = {
        "빈증권": [],
        "테스트증권": [{"거래일자": "2025/01/01"}],
    }
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        export_to_excel(broker_raw, path)
        wb = openpyxl.load_workbook(path)
        assert "빈증권" not in wb.sheetnames
        assert "테스트증권" in wb.sheetnames
    finally:
        os.unlink(path)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: 4 tests FAIL (시그니처 불일치)

- [ ] **Step 3: `core/exporter.py` 수정**

```python
# core/exporter.py (전체 교체)
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9E1F2")


def _write_sheet(ws, headers: list[str], rows: list[dict]) -> None:
    for col, header in enumerate(headers, 1):
        cell = ws.cell(1, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for row_idx, row in enumerate(rows, 2):
        for col, header in enumerate(headers, 1):
            ws.cell(row_idx, col, row.get(header, ""))


def export_to_excel(
    broker_raw: dict[str, list[dict]],
    output_path: str,
) -> None:
    """
    broker_raw: {"증권사명": [원본_행_dict, ...]}
    output_path: 저장할 .xlsx 경로
    증권사별로 시트 1개씩 생성. 빈 증권사는 건너뜀.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # 기본 Sheet 제거

    for broker_name, raw_rows in broker_raw.items():
        if not raw_rows:
            continue
        ws = wb.create_sheet(title=broker_name[:31])  # Excel 시트명 31자 제한
        headers = list(raw_rows[0].keys())
        _write_sheet(ws, headers, raw_rows)

    if not wb.sheetnames:
        ws = wb.create_sheet(title="결과없음")

    wb.save(output_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: 커밋**

```bash
git add core/exporter.py tests/test_exporter.py
git commit -m "feat: exporter outputs per-broker sheets only, removing unified sheet"
```

---

## Task 5: `ui/main_window.py` — `ConvertWorker` 시그니처 + 불필요한 코드 제거

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: `ui/main_window.py` 전체를 아래로 교체**

`_process_file()` 내부에서 `ParserSelectDialog`는 아직 없으므로 임시로 `detect_parser()` 직접 호출을 유지. Task 8에서 교체.

```python
# ui/main_window.py
import os
from collections import defaultdict
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QHeaderView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.loader import load_pdf, PasswordError
from core.detector import detect_parser
from core.exporter import export_to_excel
from ui.password_dialog import PasswordDialog


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_entries, output_path):
        super().__init__()
        self.file_entries = file_entries  # list of (path, password, parser_class)
        self.output_path = output_path

    def run(self):
        broker_raw: dict[str, list[dict]] = defaultdict(list)
        total = len(self.file_entries)

        for i, (path, password, parser_class) in enumerate(self.file_entries):
            try:
                self.progress.emit(int((i / total) * 80), f"파싱 중: {os.path.basename(path)}")
                pages = load_pdf(path, password)
                parser = parser_class()
                _transactions, raw_rows = parser.parse(pages)
                broker_raw[parser_class.BROKER_NAME].extend(raw_rows)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

        self.progress.emit(90, "엑셀 파일 생성 중...")
        try:
            export_to_excel(dict(broker_raw), self.output_path)
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
        self._file_entries: list[tuple] = []  # (path, password, parser_class)
        self._output_path = os.path.expanduser("~/Desktop/거래내역.xlsx")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

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

        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("저장 위치:"))
        self.output_label = QLabel(self._output_path)
        self.output_label.setStyleSheet("color: gray;")
        save_row.addWidget(self.output_label, stretch=1)
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self._browse_output)
        save_row.addWidget(browse_btn)
        layout.addLayout(save_row)

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
        paths, _ = QFileDialog.getOpenFileNames(self, "PDF 파일 선택", "", "PDF Files (*.pdf)")
        for path in paths:
            self._process_file(path)

    def _process_file(self, path: str):
        filename = os.path.basename(path)
        dlg = PasswordDialog(filename, self._last_password, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        password = dlg.get_password()
        if password:
            self._last_password = password

        try:
            pages = load_pdf(path, password)
        except PasswordError as e:
            QMessageBox.critical(self, "비밀번호 오류", str(e))
            return

        # TODO Task 8: replace with ParserSelectDialog
        recommended = detect_parser(pages)
        if recommended is None:
            QMessageBox.warning(self, "파서 없음", "인식된 파서가 없습니다. 파서를 추가하세요.")
            return
        parser_class = recommended

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setItem(row, 1, QTableWidgetItem(parser_class.BROKER_NAME))
        self.table.setItem(row, 2, QTableWidgetItem("✓ 인식됨"))
        self._file_entries.append((path, password, parser_class))

    def _remove_selected(self):
        rows = sorted(
            set(idx.row() for idx in self.table.selectedIndexes()), reverse=True
        )
        for row in rows:
            self.table.removeRow(row)
            self._file_entries.pop(row)

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

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = ConvertWorker(self._file_entries, self._output_path)
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

- [ ] **Step 2: 기존 테스트 통과 확인**

```bash
python -m pytest tests/ -v --ignore=tests/test_integration.py -x
```

Expected: 모두 PASS (integration test는 PDF 파일 의존으로 제외 가능)

- [ ] **Step 3: 커밋**

```bash
git add ui/main_window.py
git commit -m "refactor: ConvertWorker removes mapping/selected_fields, uses new exporter signature"
```

---

## Task 6: `ui/parser_select_dialog.py` — 파서 선택 다이얼로그

**Files:**
- Create: `ui/parser_select_dialog.py`

- [ ] **Step 1: `ui/parser_select_dialog.py` 생성**

```python
# ui/parser_select_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt
import fitz


class ParserSelectDialog(QDialog):
    """PDF 로드 후 항상 표시되는 파서 선택 다이얼로그.

    recommended: detect_parser()가 반환한 파서 클래스 (None 가능)
    """

    def __init__(self, pages: list[fitz.Page], recommended, parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 선택")
        self.setMinimumSize(520, 360)
        self._pages = pages
        self._recommended = recommended
        self._selected = recommended
        self._parser_map: dict[str, type] = {}

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "증권사", "유형", ""])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("파서 추가")
        add_btn.clicked.connect(self._open_builder)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("선택 확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._populate()

    def _populate(self):
        from core.parser_registry import get_all_parsers, load
        from parsers import PARSERS

        self._table.setRowCount(0)
        self._parser_map.clear()
        builtin_names = {p.BROKER_NAME for p in PARSERS}
        rec_name = self._recommended.BROKER_NAME if self._recommended else None

        for parser_cls in get_all_parsers():
            name = parser_cls.BROKER_NAME
            self._parser_map[name] = parser_cls
            row = self._table.rowCount()
            self._table.insertRow(row)

            star_item = QTableWidgetItem("★" if name == rec_name else "")
            star_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, star_item)
            self._table.setItem(row, 1, QTableWidgetItem(name))
            is_builtin = name in builtin_names
            self._table.setItem(row, 2, QTableWidgetItem("내장" if is_builtin else "동적"))

            if not is_builtin:
                del_btn = QPushButton("삭제")
                del_btn.clicked.connect(lambda _checked, b=name: self._delete(b))
                self._table.setCellWidget(row, 3, del_btn)

            if name == rec_name:
                self._table.selectRow(row)

        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(2, 60)
        self._table.setColumnWidth(3, 60)

    def _delete(self, broker_name: str):
        from core import parser_registry

        reply = QMessageBox.question(
            self, "파서 삭제",
            f"'{broker_name}' 파서를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        configs = parser_registry.load()
        parser_registry.save([c for c in configs if c.broker_name != broker_name])
        if self._selected and self._selected.BROKER_NAME == broker_name:
            self._selected = None
        self._populate()

    def _open_builder(self):
        from ui.parser_builder_dialog import ParserBuilderDialog

        dlg = ParserBuilderDialog(self._pages, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate()

    def _confirm(self):
        indexes = self._table.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "경고", "파서를 선택하세요.")
            return
        row = indexes[0].row()
        broker = self._table.item(row, 1).text()
        self._selected = self._parser_map.get(broker)
        self.accept()

    def get_selected_parser(self):
        return self._selected
```

- [ ] **Step 2: 앱 실행해서 임포트 오류 없는지 확인**

```bash
cd /Users/parktaehyun/opencode_pjt/save_hj
python -c "from ui.parser_select_dialog import ParserSelectDialog; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add ui/parser_select_dialog.py
git commit -m "feat: add ParserSelectDialog with recommended highlight and delete"
```

---

## Task 7: `ui/parser_builder_dialog.py` — 파서 생성 UI

**Files:**
- Create: `ui/parser_builder_dialog.py`

- [ ] **Step 1: `ui/parser_builder_dialog.py` 생성**

```python
# ui/parser_builder_dialog.py
import fitz
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QSpinBox, QFormLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QWidget, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from core.models import STANDARD_FIELDS


class ParserBuilderDialog(QDialog):
    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 추가")
        self.setMinimumSize(960, 640)
        self._pages = pages
        self._current_page = 0

        main = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 왼쪽: PDF 미리보기 ─────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self._preview = QTableWidget()
        self._preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self._preview)

        nav = QHBoxLayout()
        self._prev_btn = QPushButton("← 이전")
        self._prev_btn.clicked.connect(self._prev_page)
        self._page_lbl = QLabel()
        self._next_btn = QPushButton("다음 →")
        self._next_btn.clicked.connect(self._next_page)
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._page_lbl, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._next_btn)
        left_layout.addLayout(nav)
        splitter.addWidget(left)

        # ── 오른쪽: 설정 폼 ────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
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

        self._date_re_edit = QLineEdit(r"^\d{4}/\d{2}/\d{2}$")
        form.addRow("날짜 정규식:", self._date_re_edit)

        self._layout_combo = QComboBox()
        self._layout_combo.addItems(["일반 테이블", "회전 레이아웃"])
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        form.addRow("레이아웃:", self._layout_combo)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 99)
        self._start_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("시작 페이지:", self._start_spin)

        self._skip_edit = QLineEdit()
        self._skip_edit.setPlaceholderText("쉼표 구분 (예: 거래일자, 합계, 페이지)")
        form.addRow("건너뛸 키워드:", self._skip_edit)

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 5)
        self._rows_spin.valueChanged.connect(self._refresh_field_dropdowns)
        form.addRow("행/거래:", self._rows_spin)

        form.addRow(QLabel("──── 필드 매핑 ────"))

        # 필드 매핑: 레이아웃 타입에 따라 스택 전환
        self._mapping_stack = QStackedWidget()

        # Stack 0: 일반 테이블 — 컴보박스
        table_mapping_widget = QWidget()
        self._table_form = QFormLayout(table_mapping_widget)
        self._field_combos: dict[str, QComboBox] = {}
        for key, label in STANDARD_FIELDS.items():
            combo = QComboBox()
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self._field_combos[key] = combo
            self._table_form.addRow(f"{label} →", combo)
        self._mapping_stack.addWidget(table_mapping_widget)

        # Stack 1: 회전 레이아웃 — y_min/y_max 테이블
        rotated_widget = QWidget()
        rot_layout = QVBoxLayout(rotated_widget)
        rot_layout.addWidget(QLabel("각 필드의 Y좌표 범위를 입력하세요 (PDF 미리보기의 Y 컬럼 참고):"))
        self._rot_table = QTableWidget(len(STANDARD_FIELDS), 3)
        self._rot_table.setHorizontalHeaderLabels(["필드", "y_min", "y_max"])
        self._rot_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._rot_spin_pairs: dict[str, tuple[QSpinBox, QSpinBox]] = {}
        for row_idx, (key, label) in enumerate(STANDARD_FIELDS.items()):
            self._rot_table.setItem(row_idx, 0, QTableWidgetItem(label))
            self._rot_table.item(row_idx, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)
            y_min_spin = QSpinBox()
            y_min_spin.setRange(0, 9999)
            y_max_spin = QSpinBox()
            y_max_spin.setRange(0, 9999)
            self._rot_table.setCellWidget(row_idx, 1, y_min_spin)
            self._rot_table.setCellWidget(row_idx, 2, y_max_spin)
            self._rot_spin_pairs[key] = (y_min_spin, y_max_spin)
        rot_layout.addWidget(self._rot_table)
        self._mapping_stack.addWidget(rotated_widget)

        form.addRow(self._mapping_stack)
        scroll.setWidget(form_widget)
        right_layout.addWidget(scroll)
        splitter.addWidget(right)

        splitter.setSizes([480, 480])
        main.addWidget(splitter)

        # 하단 버튼
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

        self._refresh_preview()

    # ── 페이지 이동 ─────────────────────────────────────────

    def _prev_page(self):
        self._current_page = max(0, self._current_page - 1)
        self._refresh_preview()

    def _next_page(self):
        self._current_page = min(len(self._pages) - 1, self._current_page + 1)
        self._refresh_preview()

    # ── 레이아웃 타입 전환 ───────────────────────────────────

    def _on_layout_changed(self):
        idx = self._layout_combo.currentIndex()
        self._mapping_stack.setCurrentIndex(idx)
        self._refresh_preview()

    # ── PDF 미리보기 갱신 ────────────────────────────────────

    def _refresh_preview(self):
        if not self._pages:
            return

        start = self._start_spin.value()
        self._current_page = max(start, min(self._current_page, len(self._pages) - 1))
        page = self._pages[self._current_page]
        layout_type = "table" if self._layout_combo.currentIndex() == 0 else "rotated"

        self._preview.clear()
        self._preview.setRowCount(0)
        self._preview.setColumnCount(0)

        if layout_type == "table":
            from core.pdf_utils import get_page_rows
            rows = list(get_page_rows(page, y_tolerance=4.0))
            if rows:
                max_cols = max(len(r) for r in rows)
                self._preview.setRowCount(len(rows))
                self._preview.setColumnCount(max_cols)
                self._preview.setHorizontalHeaderLabels([f"Col{i}" for i in range(max_cols)])
                for r_idx, row in enumerate(rows):
                    for c_idx, cell in enumerate(row):
                        self._preview.setItem(r_idx, c_idx, QTableWidgetItem(cell[1]))
        else:
            items = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                bx = block["bbox"][0]
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        t = span["text"].strip()
                        if t:
                            items.append((round(bx), round(span["bbox"][1]), t))
            items.sort(key=lambda it: (it[0], it[1]))
            self._preview.setRowCount(len(items))
            self._preview.setColumnCount(3)
            self._preview.setHorizontalHeaderLabels(["X", "Y", "텍스트"])
            for r_idx, (x, y, text) in enumerate(items):
                self._preview.setItem(r_idx, 0, QTableWidgetItem(str(x)))
                self._preview.setItem(r_idx, 1, QTableWidgetItem(str(y)))
                self._preview.setItem(r_idx, 2, QTableWidgetItem(text))

        total = len(self._pages)
        self._page_lbl.setText(f"{self._current_page + 1} / {total}")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total - 1)

        if layout_type == "table":
            self._refresh_field_dropdowns()

    # ── 필드 매핑 드롭다운 갱신 (일반 테이블 전용) ─────────────

    def _refresh_field_dropdowns(self):
        if self._layout_combo.currentIndex() != 0:
            return
        if not self._pages:
            return

        from core.pdf_utils import get_page_rows
        start = self._start_spin.value()
        idx = max(start, min(self._current_page, len(self._pages) - 1))
        page = self._pages[idx]
        rows_per_tx = self._rows_spin.value()

        all_rows = list(get_page_rows(page, y_tolerance=4.0))

        # 첫 3개 트랜잭션 그룹 샘플 수집
        sample_groups: list[list[list[str]]] = []
        i = 0
        while i < len(all_rows) and len(sample_groups) < 3:
            group = []
            for offset in range(rows_per_tx):
                j = i + offset
                group.append([cell[1] for cell in all_rows[j]] if j < len(all_rows) else [])
            sample_groups.append(group)
            i += rows_per_tx

        # 드롭다운 옵션 빌드: (label, col_index, row_offset)
        options: list[tuple[str, int, int]] = []
        if sample_groups:
            first_group = sample_groups[0]
            for r_off, row_texts in enumerate(first_group):
                for c_idx, _ in enumerate(row_texts):
                    samples = []
                    for sg in sample_groups:
                        r = sg[r_off] if r_off < len(sg) else []
                        if c_idx < len(r) and r[c_idx]:
                            samples.append(r[c_idx])
                    sample_str = ", ".join(samples[:2])
                    label = f"Row{r_off}-Col{c_idx}: {sample_str}"
                    options.append((label, c_idx, r_off))

        # 기존 선택값 보존
        prev: dict[str, tuple | None] = {
            key: combo.currentData() for key, combo in self._field_combos.items()
        }

        for key, combo in self._field_combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("미사용", None)
            for label, c_idx, r_off in options:
                combo.addItem(label, (c_idx, r_off))
            # 이전 선택 복원
            p = prev.get(key)
            if p is not None:
                for i_opt in range(combo.count()):
                    if combo.itemData(i_opt) == p:
                        combo.setCurrentIndex(i_opt)
                        break
            combo.blockSignals(False)

    # ── 저장 ─────────────────────────────────────────────────

    def _save(self):
        from core import parser_registry
        from core.parser_registry import DynamicParserConfig, FieldMapping

        broker_name = self._broker_edit.text().strip()
        if not broker_name:
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return

        keywords = [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "입력 오류", "감지 키워드를 하나 이상 입력하세요.")
            return

        layout_type = "table" if self._layout_combo.currentIndex() == 0 else "rotated"
        skip_kws = [k.strip() for k in self._skip_edit.text().split(",") if k.strip()]

        field_mappings: list[FieldMapping] = []

        if layout_type == "table":
            for standard_field, combo in self._field_combos.items():
                data = combo.currentData()
                if data is None:
                    continue
                c_idx, r_off = data
                field_mappings.append(FieldMapping(
                    standard_field=standard_field,
                    column_index=c_idx,
                    row_offset=r_off,
                    y_min=0,
                    y_max=0,
                ))
        else:
            for standard_field, (y_min_spin, y_max_spin) in self._rot_spin_pairs.items():
                y_min = y_min_spin.value()
                y_max = y_max_spin.value()
                if y_min == 0 and y_max == 0:
                    continue
                field_mappings.append(FieldMapping(
                    standard_field=standard_field,
                    column_index=0,
                    row_offset=0,
                    y_min=y_min,
                    y_max=y_max,
                ))

        config = DynamicParserConfig(
            broker_name=broker_name,
            detection_keywords=keywords,
            date_re=self._date_re_edit.text().strip(),
            layout_type=layout_type,
            start_page=self._start_spin.value(),
            rows_per_tx=self._rows_spin.value(),
            skip_keywords=skip_kws,
            field_mappings=field_mappings,
        )

        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
```

- [ ] **Step 2: 임포트 오류 없는지 확인**

```bash
python -c "from ui.parser_builder_dialog import ParserBuilderDialog; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add ui/parser_builder_dialog.py
git commit -m "feat: add ParserBuilderDialog with PDF preview and field mapping UI"
```

---

## Task 8: `_process_file()` 연결 + 구 파일 삭제 + 최종 검증

**Files:**
- Modify: `ui/main_window.py`
- Delete: `ui/column_select.py`
- Delete: `ui/mapping_dialog.py`

- [ ] **Step 1: `ui/main_window.py`의 `_process_file()` 수정 — TODO 주석 대체**

`_process_file()` 메서드를 아래로 교체 (나머지 클래스 코드는 Task 5와 동일):

```python
    def _process_file(self, path: str):
        from ui.parser_select_dialog import ParserSelectDialog

        filename = os.path.basename(path)
        dlg = PasswordDialog(filename, self._last_password, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        password = dlg.get_password()
        if password:
            self._last_password = password

        try:
            pages = load_pdf(path, password)
        except PasswordError as e:
            QMessageBox.critical(self, "비밀번호 오류", str(e))
            return

        recommended = detect_parser(pages)
        select_dlg = ParserSelectDialog(pages, recommended, parent=self)
        if select_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        parser_class = select_dlg.get_selected_parser()
        if parser_class is None:
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setItem(row, 1, QTableWidgetItem(parser_class.BROKER_NAME))
        rec_mark = "★ 추천" if recommended and recommended.BROKER_NAME == parser_class.BROKER_NAME else "✓ 선택"
        self.table.setItem(row, 2, QTableWidgetItem(rec_mark))
        self._file_entries.append((path, password, parser_class))
```

- [ ] **Step 2: 구 파일 삭제**

```bash
git rm ui/column_select.py ui/mapping_dialog.py
```

- [ ] **Step 3: `ui/__init__.py` 또는 다른 파일에서 삭제된 파일 참조 제거**

```bash
grep -rn "column_select\|mapping_dialog\|ColumnSelectDialog\|MappingDialog" /Users/parktaehyun/opencode_pjt/save_hj --include="*.py"
```

검색 결과에서 남은 참조가 있으면 해당 파일에서 제거.

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
python -m pytest tests/test_parser_registry.py tests/test_detector.py tests/test_exporter.py tests/test_models.py tests/test_normalizer.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 앱 실행해서 전체 UX 흐름 수동 확인**

```bash
python main.py
```

확인 항목:
1. PDF 파일 추가 → 비밀번호 입력 → ParserSelectDialog 표시 확인
2. 추천 파서 ★ 표시 확인
3. [파서 추가] → ParserBuilderDialog 열림, PDF 미리보기 확인
4. 파서 저장 → ParserSelectDialog 목록 갱신 확인
5. 동적 파서 [삭제] 확인
6. 변환 시작 → 증권사별 시트 Excel 파일 생성 확인

- [ ] **Step 6: 최종 커밋**

```bash
git add ui/main_window.py
git commit -m "feat: wire ParserSelectDialog into _process_file(), remove legacy column_select and mapping_dialog"
```
