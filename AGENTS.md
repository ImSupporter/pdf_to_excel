# AGENTS.md

This file provides guidance to Codex agents when working with code in this repository.

## Project Overview

Korean brokerage PDF transaction history to Excel converter. This is a PyQt6 GUI app distributed as a Windows EXE with PyInstaller.

## Commands

```bash
# Run the app
python3 main.py

# Run all tests
python3 -m pytest tests/ -q

# Run a single test
python3 -m pytest tests/test_parser_registry.py::test_roundtrip -v

# Build Windows EXE (on Windows)
pyinstaller 증권거래내역변환기.spec
```

Test fixtures: real PDF files (`거래내역확인서_samsung.pdf`, `거래내역증명서_mirae.pdf`, `거래내역_citi.pdf`) must exist in the project root for integration/parser tests. Tests call `pytest.skip` when fixtures are missing. The PDF password is read from `PDF_PASSWORD`, defaulting to `990901`.

## Architecture

### Overall Flow

```text
PDF 추가 -> PasswordDialog -> load_pdf() -> ParserSelectDialog
    -> 파서 선택 (내장 or 동적) -> ConvertWorker (QThread)
    -> parser.parse() -> export_to_excel() -> .xlsx (증권사별 시트)
```

### Core Layers

`parsers/`: built-in parsers. They inherit from `BaseParser` and must define `BROKER_NAME` and `DETECTION_KEYWORDS` class variables. `parse(pages)` returns `(list[Transaction], list[dict])`. The `list[dict]` preserves original rows as-is, and column names differ by parser.

`core/parser_registry.py`: dynamic parser engine. `DynamicParserConfig` is saved as JSON to `%APPDATA%\증권거래내역변환기\parsers.json`. `build_class(config)` uses `type()` to create a `BaseParser` subclass at runtime. `get_all_parsers()` returns both built-in and dynamic parsers.

`core/detector.py`: `detect_parser(pages)` matches `DETECTION_KEYWORDS` against first-page text. It lazy-imports `get_all_parsers` inside the function to avoid circular imports.

`core/exporter.py`: `export_to_excel(broker_raw, output_path)`. `broker_raw` is `{"증권사명": [원본_행_dict, ...]}`. Each broker gets one sheet, and columns are the original row keys.

`core/pdf_utils.py`: `get_page_rows(page)`. Uses EasyOCR fallback for scanned PDFs; otherwise groups `page.get_text("words")` by y-coordinate into rows. Returns a list of rows, where each row is a list of `(x, text)` tuples.

`ui/main_window.py`: stores `_file_entries: list[(path, password, parser_class)]`. Conversion runs through `ConvertWorker(QThread)`.

`ui/parser_select_dialog.py`: parser list dialog. Built-in parsers cannot be deleted; dynamic parsers can. Recommended parser is selected automatically and marked with a star.

`ui/parser_builder_dialog.py`: dynamic parser creation UI. Left side is the PDF preview table; right side is the parser settings form. Layout types are "가로" (rotated, `"rotated"`) and "세로" (table, `"table"`). Code uses the internal strings `"table"` and `"rotated"`.

## Built-In Parser Notes

| Parser | layout_type | Notes |
| --- | --- | --- |
| `SamsungParser` | `table` | One transaction spans 2-3 rows; first row has the date. |
| `MiraeAssetParser` | `rotated` | One transaction is a narrow vertical slot across the page, about 8 px wide. Detects slots using `page.get_text("dict")` block x-coordinates. |
| `CitiParser` | `table` | English PDF. |

When adding a new built-in parser, register it in the `PARSERS` list in `parsers/__init__.py`.

## PyInstaller Distribution Constraints

- `sys._MEIPASS` inside the bundle is read-only. Never write user data inside the bundled app directory.
- Dynamic parser JSON location:
  - Windows: `%APPDATA%\증권거래내역변환기\`
  - Other platforms: `~/.config/증권거래내역변환기\`
  - See `_get_data_dir()` for the source of truth.
