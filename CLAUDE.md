# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 증권사 PDF 거래내역 → Excel 변환기. PyQt6 GUI 앱으로, Windows EXE(PyInstaller)로 배포된다.

## 명령어

```bash
# 앱 실행
python3 main.py

# 테스트 전체
python3 -m pytest tests/ -q

# 단일 테스트
python3 -m pytest tests/test_parser_registry.py::test_roundtrip -v

# Windows EXE 빌드 (Windows에서)
pyinstaller 증권거래내역변환기.spec
```

**테스트 픽스처:** 실제 PDF 파일(`거래내역확인서_samsung.pdf`, `거래내역증명서_mirae.pdf`, `거래내역_citi.pdf`)이 프로젝트 루트에 있어야 integration/parser 테스트가 돌아간다. 없으면 `pytest.skip`. 비밀번호는 환경변수 `PDF_PASSWORD` (기본값 `990901`).

## 아키텍처

### 전체 흐름

```
PDF 추가 → PasswordDialog → load_pdf() → ParserSelectDialog
    → 파서 선택 (내장 or 동적) → ConvertWorker (QThread)
    → parser.parse() → export_to_excel() → .xlsx (증권사별 시트)
```

### 핵심 레이어

**`parsers/`** — 내장 파서들. `BaseParser` 상속, `BROKER_NAME`·`DETECTION_KEYWORDS` 클래스 변수 필수. `parse(pages)` → `(list[Transaction], list[dict])` 반환. `list[dict]`는 원본 행 그대로 (컬럼명은 파서마다 다름).

**`core/parser_registry.py`** — 동적 파서 엔진. `DynamicParserConfig`를 JSON으로 `%APPDATA%\증권거래내역변환기\parsers.json`에 저장. `build_class(config)` 가 `type()`으로 런타임에 `BaseParser` 서브클래스를 생성. `get_all_parsers()`가 내장 + 동적 파서 전체 반환.

**`core/detector.py`** — `detect_parser(pages)`가 첫 페이지 텍스트에서 `DETECTION_KEYWORDS` 매칭. circular import 방지를 위해 `get_all_parsers`를 함수 내부에서 lazy import.

**`core/exporter.py`** — `export_to_excel(broker_raw, output_path)`. `broker_raw`는 `{"증권사명": [원본_행_dict, ...]}`. 증권사당 시트 1개, 컬럼은 원본 행의 키 그대로.

**`core/pdf_utils.py`** — `get_page_rows(page)`: 스캔 PDF면 easyocr fallback, 아니면 `page.get_text("words")`로 y좌표 기준 행 묶음. `(x, text)` 튜플 리스트의 리스트 반환.

**`ui/main_window.py`** — `_file_entries: list[(path, password, parser_class)]`. 변환은 `ConvertWorker(QThread)`가 담당.

**`ui/parser_select_dialog.py`** — 파서 목록 다이얼로그. 내장 파서(삭제 불가) + 동적 파서(삭제 가능). 추천 파서 ★ 자동 선택.

**`ui/parser_builder_dialog.py`** — 동적 파서 생성 UI. 좌: PDF 미리보기 테이블, 우: 파서 설정 폼. 레이아웃 타입 "가로"(rotated, `"rotated"`) / "세로"(table, `"table"`) — 내부 layout_type 값은 코드에서 `"table"`/`"rotated"` 문자열 사용.

### 내장 파서별 특성

| 파서 | layout_type | 특이사항 |
|------|-------------|---------|
| `SamsungParser` | `table` | 거래 1건 = 2–3행, 첫 행에 날짜 |
| `MiraeAssetParser` | `rotated` | 거래 1건 = 페이지를 가로로 가르는 좁은 세로 슬롯(~8px). `page.get_text("dict")` 블록 x좌표로 슬롯 검출 |
| `CitiParser` | `table` | 영문 PDF |

새 내장 파서 추가 시 `parsers/__init__.py`의 `PARSERS` 리스트에 등록 필요.

### PyInstaller 배포 제약

- `sys._MEIPASS` (번들 내부)는 읽기 전용 → 사용자 데이터는 절대 번들 내부에 쓰지 말 것
- 동적 파서 JSON: Windows `%APPDATA%\증권거래내역변환기\`, 그 외 `~/.config/증권거래내역변환기\` (`_get_data_dir()` 참조)
