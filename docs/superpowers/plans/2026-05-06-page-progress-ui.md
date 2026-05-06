# 페이지 기준 진행 상황 UI 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF → Excel 변환 시 progress bar와 status label이 파일 단위가 아닌 페이지 단위로 업데이트되도록 한다.

**Architecture:** `parse(pages, progress_cb=None)` 시그니처 확장으로 파서가 페이지마다 콜백을 호출하고, `ConvertWorker`가 파일별 람다를 넘겨 시그널을 emit한다. 파일 전환 시 progress bar를 0%로 리셋한다.

**Tech Stack:** Python 3, PyQt6, pytest, unittest.mock

---

## 파일 구조

| 파일 | 변경 종류 | 내용 |
|------|----------|------|
| `parsers/base.py` | 수정 | `parse()` 추상 메서드에 `progress_cb=None` 추가 |
| `core/parser_registry.py` | 수정 | `build_class` 내부 `parse()` 페이지 루프에 콜백 호출 추가 |
| `ui/main_window.py` | 수정 | `ConvertWorker.run()` 페이지 기준 progress emit으로 교체 |
| `tests/test_parser_registry.py` | 수정 | 콜백 호출 동작 검증 테스트 추가 |
| `tests/test_convert_worker.py` | 생성 | ConvertWorker progress emit 검증 테스트 |

---

## Task 1: `parse()` 콜백 지원 — BaseParser + build_class

**Files:**
- Modify: `parsers/base.py`
- Modify: `core/parser_registry.py:184-226`
- Modify: `tests/test_parser_registry.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_parser_registry.py` 끝에 두 테스트를 추가한다.

```python
def test_progress_cb_called_for_each_page():
    from core.parser_registry import DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=120.0,
        template_height=20.0,
        column_xs=[],
        template_row_ys_per_col={},
        cell_mappings=[],
    )

    calls = []

    def cb(page_idx, total):
        calls.append((page_idx, total))

    pages = [_mock_page([]), _mock_page([])]
    build_class(cfg)().parse(pages, progress_cb=cb)

    assert calls == [(0, 2), (1, 2)]


def test_progress_cb_called_for_skipped_pages():
    from core.parser_registry import DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=1,
        data_start_y=100.0,
        data_end_y=120.0,
        template_height=20.0,
        column_xs=[],
        template_row_ys_per_col={},
        cell_mappings=[],
    )

    calls = []

    def cb(page_idx, total):
        calls.append((page_idx, total))

    pages = [_mock_page([]), _mock_page([])]
    build_class(cfg)().parse(pages, progress_cb=cb)

    assert calls == [(0, 2), (1, 2)]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_parser_registry.py::test_progress_cb_called_for_each_page tests/test_parser_registry.py::test_progress_cb_called_for_skipped_pages -v
```

예상 결과: `FAILED` — `parse()` 가 `progress_cb` 파라미터를 받지 않아 `TypeError`

- [ ] **Step 3: `parsers/base.py` 시그니처 수정**

`parsers/base.py` 전체를 다음으로 교체한다.

```python
from abc import ABC, abstractmethod
import fitz
from core.models import Transaction

class BaseParser(ABC):
    BROKER_NAME: str = ""
    DETECTION_KEYWORDS: list[str] = []

    @abstractmethod
    def parse(self, pages: list[fitz.Page], progress_cb=None) -> tuple[list[Transaction], list[dict]]:
        """
        Returns: (transactions, raw_rows)
        - transactions: normalized Transaction list
        - raw_rows: original column dicts for per-broker sheet
        """
        ...
```

- [ ] **Step 4: `core/parser_registry.py` — `build_class` 내부 `parse()` 수정**

`core/parser_registry.py`의 `parse` 함수(line 184)를 다음으로 교체한다.

```python
    def parse(self, pages, progress_cb=None):
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        if _cfg.layout_type != "coordinate_template" or _cfg.template_height <= 0:
            return transactions, raw_rows

        total_pages = len(pages)
        for page_idx, page in enumerate(pages):
            if page_idx < _cfg.start_page:
                if progress_cb:
                    progress_cb(page_idx, total_pages)
                continue

            words = _words_for_page(page)
            slot_y = _cfg.data_start_y
            while slot_y < _cfg.data_end_y:
                raw = {mapping.display_name: "" for mapping in _cfg.cell_mappings}
                standard_values = {field_name: [] for field_name in VALID_STANDARD_FIELDS}

                for mapping in _cfg.cell_mappings:
                    value = _extract_cell(words, mapping, slot_y)
                    if value:
                        raw[mapping.display_name] = (
                            f"{raw[mapping.display_name]} {value}"
                            if raw[mapping.display_name]
                            else value
                        )
                    if mapping.standard_field in VALID_STANDARD_FIELDS and value:
                        standard_values[mapping.standard_field].append(value)

                if any(value for value in raw.values()):
                    transactions.append(
                        Transaction(
                            date=" ".join(standard_values["date"]),
                            type=" ".join(standard_values["type"]),
                            amount=_parse_num(" ".join(standard_values["amount"])),
                            balance=_parse_num(" ".join(standard_values["balance"])),
                            broker=_cfg.broker_name,
                            raw=raw,
                        )
                    )
                    raw_rows.append(raw)
                slot_y += _cfg.template_height

            if progress_cb:
                progress_cb(page_idx, total_pages)

        return transactions, raw_rows
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_parser_registry.py -v
```

예상 결과: 모든 테스트 `PASSED`

- [ ] **Step 6: 커밋**

```bash
git add parsers/base.py core/parser_registry.py tests/test_parser_registry.py
git commit -m "feat: parse()에 progress_cb 콜백 파라미터 추가"
```

---

## Task 2: `ConvertWorker` — 페이지 기준 진행률 emit

**Files:**
- Modify: `ui/main_window.py:24-47`
- Create: `tests/test_convert_worker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_convert_worker.py` 를 새로 생성한다.

```python
import os
from unittest.mock import MagicMock, call, patch


def _make_worker(file_entries, output_path):
    """QThread.__init__ 없이 ConvertWorker 인스턴스 생성."""
    from ui.main_window import ConvertWorker

    with patch("PyQt6.QtCore.QThread.__init__", return_value=None):
        worker = ConvertWorker.__new__(ConvertWorker)
        worker.file_entries = file_entries
        worker.output_path = output_path
        worker.progress = MagicMock()
        worker.finished = MagicMock()
    return worker


class _FakeParser:
    BROKER_NAME = "테스트증권"

    def parse(self, pages, progress_cb=None):
        for i, _ in enumerate(pages):
            if progress_cb:
                progress_cb(i, len(pages))
        return [], [{"col": "val"}]


def test_progress_resets_to_zero_at_file_start(tmp_path):
    pages = [MagicMock(), MagicMock(), MagicMock()]
    worker = _make_worker([("a/파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    first_call = worker.progress.emit.call_args_list[0]
    assert first_call == call(0, "로딩 중: 파일.pdf")


def test_page_progress_emits_correct_percent_and_label(tmp_path):
    pages = [MagicMock(), MagicMock(), MagicMock()]
    worker = _make_worker([("파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = worker.progress.emit.call_args_list
    # 파일 시작(0%) + 페이지 3개(33,66,100%) + 엑셀(100%) = 5번
    assert emitted[1] == call(33, "파일.pdf 페이지 1/3")
    assert emitted[2] == call(66, "파일.pdf 페이지 2/3")
    assert emitted[3] == call(100, "파일.pdf 페이지 3/3")


def test_second_file_resets_to_zero(tmp_path):
    pages = [MagicMock()]
    worker = _make_worker(
        [("first.pdf", "", _FakeParser), ("second.pdf", "", _FakeParser)],
        str(tmp_path / "out.xlsx"),
    )

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = [args for args, _ in worker.progress.emit.call_args_list]
    # first.pdf: (0, "로딩 중: first.pdf"), (100, "first.pdf 페이지 1/1")
    # second.pdf: (0, "로딩 중: second.pdf"), (100, "second.pdf 페이지 1/1")
    assert emitted[0] == (0, "로딩 중: first.pdf")
    assert emitted[2] == (0, "로딩 중: second.pdf")


def test_excel_step_emits_correct_label(tmp_path):
    pages = [MagicMock()]
    worker = _make_worker([("파일.pdf", "", _FakeParser)], str(tmp_path / "out.xlsx"))

    with patch("ui.main_window.load_pdf", return_value=pages), \
         patch("ui.main_window.export_to_excel"):
        worker.run()

    emitted = [args for args, _ in worker.progress.emit.call_args_list]
    assert emitted[-2] == (100, "엑셀 파일 생성 중...")
    assert emitted[-1] == (100, "완료!")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python3 -m pytest tests/test_convert_worker.py -v
```

예상 결과: `FAILED` — `ConvertWorker.run()` 이 기존 파일 단위 progress를 emit하여 기댓값과 불일치

- [ ] **Step 3: `ui/main_window.py` — `ConvertWorker.run()` 교체**

`ui/main_window.py`의 `ConvertWorker.run()` 메서드(line 24-47)를 다음으로 교체한다.

```python
    def run(self):
        broker_raw: dict[str, list[dict]] = defaultdict(list)

        for path, password, parser_class in self.file_entries:
            filename = os.path.basename(path)
            self.progress.emit(0, f"로딩 중: {filename}")
            try:
                pages = load_pdf(path, password)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

            total_pages = len(pages)

            def make_cb(fn, tp):
                def cb(page_idx, _total):
                    pct = int((page_idx + 1) / tp * 100)
                    self.progress.emit(pct, f"{fn} 페이지 {page_idx + 1}/{tp}")
                return cb

            try:
                parser = parser_class()
                _transactions, raw_rows = parser.parse(
                    pages, progress_cb=make_cb(filename, total_pages)
                )
                broker_raw[parser_class.BROKER_NAME].extend(raw_rows)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

        self.progress.emit(100, "엑셀 파일 생성 중...")
        try:
            export_to_excel(dict(broker_raw), self.output_path)
        except PermissionError:
            self.finished.emit(
                False,
                f"파일이 열려 있습니다. 닫고 다시 시도하세요:\n{self.output_path}",
            )
            return

        self.progress.emit(100, "완료!")
        self.finished.emit(True, self.output_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python3 -m pytest tests/test_convert_worker.py -v
```

예상 결과: 4개 테스트 모두 `PASSED`

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
python3 -m pytest tests/ -q
```

예상 결과: 모든 테스트 `PASSED`

- [ ] **Step 6: 커밋**

```bash
git add ui/main_window.py tests/test_convert_worker.py
git commit -m "feat: 변환 진행률을 파일 단위에서 페이지 단위로 변경"
```
