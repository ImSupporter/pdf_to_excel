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

**테스트 픽스처:** 단위 테스트는 mock 기반으로 PDF 파일 불필요. 비밀번호는 환경변수 `PDF_PASSWORD` (기본값 `990901`).

## 아키텍처

### 전체 흐름

```
PDF 추가 → PasswordDialog → load_pdf() → ParserSelectDialog
    → 파서 선택 (내장 or 동적) → ConvertWorker (QThread)
    → parser.parse() → export_to_excel() → .xlsx (증권사별 시트)
```

### 핵심 레이어

**`parsers/`** — 파서 베이스만 존재. `BaseParser`를 상속하는 내장 파서는 없음. `BROKER_NAME`·`DETECTION_KEYWORDS` 클래스 변수 필수. `parse(pages)` → `(list[Transaction], list[dict])` 반환.

**`core/parser_registry.py`** — 동적 파서 엔진. `DynamicParserConfig`를 JSON으로 `%APPDATA%\증권거래내역변환기\parsers.json`에 저장. `build_class(config)` 가 `type()`으로 런타임에 `BaseParser` 서브클래스를 생성. `get_all_parsers()`가 내장 + 동적 파서 전체 반환. `FieldMapping`은 `x_min: float, x_max: float`로 컬럼 범위를 직접 지정 (`x` 단일 좌표 방식은 제거됨, 구 JSON 하위호환 로드 지원).

**`core/detector.py`** — `detect_parser(pages)`가 첫 페이지 텍스트에서 `DETECTION_KEYWORDS` 매칭. circular import 방지를 위해 `get_all_parsers`를 함수 내부에서 lazy import.

**`core/exporter.py`** — `export_to_excel(broker_raw, output_path)`. `broker_raw`는 `{"증권사명": [원본_행_dict, ...]}`. 증권사당 시트 1개, 컬럼은 원본 행의 키 그대로.

**`core/pdf_utils.py`** — `get_page_rows(page)`: 스캔 PDF면 easyocr fallback, 아니면 `page.get_text("words")`로 y좌표 기준 행 묶음. `(x, text)` 튜플 리스트의 리스트 반환.

**`ui/main_window.py`** — `_file_entries: list[(path, password, parser_class)]`. 변환은 `ConvertWorker(QThread)`가 담당.

**`ui/parser_select_dialog.py`** — 파서 목록 다이얼로그. 내장 파서(삭제 불가) + 동적 파서(삭제 가능). 추천 파서 ★ 자동 선택.

**`ui/parser_builder_dialog.py`** — 동적 파서 생성 UI. 3-패널 단일 창: ① 파서 정보 폼 → ② ZoneEditorWidget (PDF 위에서 컬럼/행/영역 경계 지정) → ③ 추출된 필드 카드 목록. 생성자: `ParserBuilderDialog(pages: list[fitz.Page], parent)`. 메인 창에서 이미 로드된 pages를 전달받으며 내부 PDF 파일 선택 없음.

**`ui/zone_editor_widget.py`** — PDF 페이지를 배경으로 4종의 드래그 가능 선을 오버레이하는 커스텀 QWidget. 빨간 세로선(컬럼 x 경계, 추가/이동/삭제), 파란 가로선(컬럼별 행 y 경계, 추가/이동/삭제), 주황 가로선(헤더 시작/끝, 이동만), 초록 가로선(데이터 시작/끝, 이동만). 좌표는 내부적으로 PDF 좌표계로 저장(`_RENDER_SCALE = 1.5`). `get_zone_data()` → `ZoneSpec` 생성에 사용할 딕셔너리 반환.

**`core/zone_spec.py`** — `ZoneSpec` 데이터클래스(ZoneEditorWidget에서 수집한 좌표 + 폼 입력값). `extract_fields(zone_spec, page)` → `list[FieldMapping]` (헤더 셀 텍스트 읽어 표준 필드 매핑 생성). `zone_spec_to_config(zone_spec, field_mappings)` → `DynamicParserConfig`.

### 파서 구조

모든 파서는 ZoneEditorWidget으로 생성하는 동적 파서뿐이다.

| layout_type | 설명 |
|-------------|------|
| `header_mapped` | ZoneEditorWidget으로 생성. FieldMapping의 `x_min/x_max` 범위로 셀 매칭. `parsers.json`에 저장 |

동적 파서는 `core/parser_registry.py`의 `build_class(config)`가 런타임에 `BaseParser` 서브클래스를 생성한다.

### PyInstaller 배포 제약

- `sys._MEIPASS` (번들 내부)는 읽기 전용 → 사용자 데이터는 절대 번들 내부에 쓰지 말 것
- 동적 파서 JSON: Windows `%APPDATA%\증권거래내역변환기\`, 그 외 `~/.config/증권거래내역변환기\` (`_get_data_dir()` 참조)
