# 파서 포맷 문서 설계 — header_mapped 레이아웃

**날짜**: 2026-05-05  
**상태**: 승인됨

---

## 배경 및 문제

기존 동적 파서(`DynamicParserConfig`)의 `table` / `template` 레이아웃은 다음 세 가지 문제를 가지고 있다.

1. **헤더 영역 포함**: 계좌번호·조회일자 같은 불필요한 상단 정보가 Excel 템플릿에 그대로 포함되어 실제 거래 데이터 컬럼 위치가 어긋남.
2. **컬럼 존 오정렬**: x-좌표 클러스터링을 전체 페이지 기준으로 계산해 헤더 영역과 데이터 영역이 섞임.
3. **멀티행 거래 미지원**: 하나의 거래가 PDF에서 여러 행으로 표현될 때 (텍스트 넘침 + 별도 필드 행) 올바르게 병합되지 않음.

---

## 핵심 설계 결정

### 제목행(헤더 그룹) 기반 컬럼 매핑

PDF 표의 컬럼 헤더 행("거래일자", "종목명" 등)의 **x좌표**를 컬럼 정의로 사용한다.  
데이터 셀은 가장 가까운 헤더 x에 매핑된다.

### 멀티 제목행 지원

제목행이 2행 이상일 수 있다. 예:

```
행0: [거래일자 x=50]  [거래명 x=150]   [거래수량 x=250]  [거래금액 x=350]
행1: [거래번호 x=50]  [종목명  x=150]  [거래단가 x=250]  [정산금액 x=350]
```

같은 x라도 row_offset이 다르면 다른 필드다.  
매핑 키: **(row_offset, x) → standard_field**

### 거래 그룹 규칙

- **anchor 행**: 날짜(`date_re`) 패턴이 "거래일자" 컬럼 x 위치에서 매치되는 행
- **연속 행**: anchor 이후 다음 anchor 전까지의 모든 행
- `rows_per_tx` 고정값 불필요 — 가변 길이 거래 자동 처리

### 연속 행 매핑 규칙

| 행 종류 | row_offset 범위 | 매핑 방법 |
|---|---|---|
| 구조적 행 | `< header_group_size` | 해당 row_offset의 FieldMapping으로 x 매핑 |
| continuation 행 | `>= header_group_size` | 전체 FieldMapping에서 x 최근접 매핑, 기존 값 있으면 concat |

---

## 데이터 모델

### FieldMapping (변경)

```python
@dataclass
class FieldMapping:
    standard_field: str   # "date", "type", "name", ...
    row_offset: int = 0   # 제목행 그룹 내 행 번호 (0 = 첫 번째 제목행)
    x: float = 0.0        # 원본 PDF x좌표

# 제거: column_index, y_min, y_max, page_index, row_index, y, source_text
```

### DynamicParserConfig (변경)

```python
@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str
    layout_type: str          # "header_mapped" | "rotated"
    start_page: int
    skip_keywords: list[str]
    field_mappings: list[FieldMapping]

# 제거: rows_per_tx
# layout_type: "table"/"template" → "header_mapped"으로 통합
```

`header_group_size`는 저장하지 않고 런타임에 계산:

```python
header_group_size = max(fm.row_offset for fm in field_mappings) + 1
```

---

## Excel 템플릿 포맷

### 시트 구조

| 시트명 | 용도 |
|---|---|
| `PDF` | 사용자가 편집하는 메인 시트 |
| `_metadata` | 원본 PDF 좌표 정보 (숨김) |
| `필드목록` | standard field 참고 (읽기 전용) |

### `PDF` 시트 레이아웃

```
Row 1: 안내 텍스트
Row 2: (빈 행)
Row 3: 거래일자 │ 거래명 │ 거래수량 │ 거래금액   ← 제목행0 (굵게, 회색 배경)
Row 4: 거래번호 │ 종목명 │ 거래단가 │ 정산금액   ← 제목행1 (굵게, 회색 배경)
Row 5: 2025/11/06 │ 매도 │ 1,019,462 │ ...      ─┐ 샘플 거래1 (흰 배경)
Row 6:  1 │ (001)삼성신종... │ 1,020.7 │ ...     ─┤
Row 7:    │ MMF제4호-CP │ │                       ─┘
Row 8: 2025/11/07 │ 매수 │ ... │ ...              ─┐ 샘플 거래2 (연한 배경)
...
```

- 제목행: 회색 배경 + 굵은 글씨 (시스템이 자동 적용)
- 샘플 데이터 행: 거래 그룹별 흰색/연한 배경 교차 (참고용, 사용자가 색칠하지 않음)

### 사용자 작업 규칙

| 색상 | 의미 |
|---|---|
| 노란색 | 제목행 셀 → standard field 매핑 (`infer_standard_field()`) |
| 회색 | 스킵 키워드 (합계, 소계 등) |

사용자는 **제목행 셀만 노란색으로 칠한다**. 데이터 행은 색칠 불필요.

### `_metadata` 시트 변경사항

기존 컬럼에 `is_header_row` 플래그 추가:

| sheet | excel_row | excel_col | page_index | row_index | x | y | text | is_header_row |
|---|---|---|---|---|---|---|---|---|
| PDF | 3 | 1 | 0 | 12 | 50.2 | 180.4 | 거래일자 | True |
| PDF | 5 | 1 | 0 | 14 | 50.2 | 206.3 | 2025/11/06 | False |

---

## 템플릿 생성 로직 (`export_parser_template`)

```
입력: pages, data_start_keyword, date_re (optional)

1. data_start_keyword가 있는 행 탐색 → 제목행 그룹 시작
2. date_re 미입력 시 자동 감지 시도:
   - 후보 패턴: \d{4}[/\-.]\d{2}[/\-.]\d{2}
   - 발견된 패턴을 UI에 반환하여 사용자 확인
   - 자동 감지 실패 시 템플릿 생성 불가 → UI에서 date_re 직접 입력 요구
3. 제목행 그룹 끝 = date_re 패턴이 처음 등장하는 행 직전
4. 컬럼 존 = 제목행 그룹의 x좌표 기준으로 정의
5. 이후 데이터 행: 각 셀 → 가장 가까운 제목행 x에 배치
6. 샘플 3~5 거래 그룹 출력, 그룹별 교차 배경색 적용
7. 헤더 이전 행(계좌번호, 조회일자 등) 제외
```

---

## 템플릿 읽기 로직 (`read_parser_template`)

```
1. _metadata에서 is_header_row=True인 행들 추출
2. 제목행 그룹의 첫 번째 excel_row = header_start_row
3. 노란색 셀:
   - is_header_row=True인 경우만 유효 FieldMapping으로 처리 (데이터 행의 노란 셀은 무시)
   - row_offset = 해당 셀의 excel_row - header_start_row
   - x = metadata의 원본 x 좌표
   - standard_field = infer_standard_field(셀 텍스트)
     → 인식 실패 시 셀 텍스트를 그대로 field key로 사용 (커스텀 필드)
4. 회색 셀 → skip_keywords
5. 반환: FieldMapping 리스트 + skip_keywords
```

---

## 파서 실행 로직 (`build_class` — layout_type="header_mapped")

```python
header_group_size = max(fm.row_offset for fm in field_mappings) + 1
date_x = [fm.x for fm in field_mappings if fm.standard_field == "date"][0]

for page in pages[start_page:]:
    rows = get_page_rows_with_y(page)
    
    # skip_keyword 포함 행 제거
    rows = [r for r in rows if not contains_skip_keyword(r, skip_keywords)]
    
    # 거래 그룹 묶기
    groups = []
    current = []
    for row_y, row_cells in rows:
        date_cell = min(row_cells, key=lambda c: abs(c[0] - date_x))
        if date_re.match(date_cell[1]):
            if current: groups.append(current)
            current = [(row_y, row_cells)]
        elif current:
            current.append((row_y, row_cells))
    if current: groups.append(current)
    
    # 그룹 → Transaction
    for group in groups:
        raw = {}
        for row_offset, (row_y, row_cells) in enumerate(group):
            if row_offset < header_group_size:
                candidates = [fm for fm in field_mappings if fm.row_offset == row_offset]
            else:
                candidates = field_mappings  # continuation: 전체 후보
            
            for cell_x, cell_text in row_cells:
                best = min(candidates, key=lambda fm: abs(fm.x - cell_x))
                if abs(best.x - cell_x) > X_TOLERANCE:  # 기본값: 50px
                    continue
                field = best.standard_field
                raw[field] = (raw[field] + " " + cell_text) if raw.get(field) else cell_text
        
        transactions.append(Transaction(..., raw=raw))
```

---

## UI 변경사항 (`parser_builder_dialog.py`)

### 입력 폼 변경

| 필드 | 상태 | 비고 |
|---|---|---|
| 증권사명 | 유지 | |
| 자동인식 키워드 | 유지 | |
| 데이터 시작 키워드 | **신규** | 예: `거래일자` |
| 날짜 형식 | 변경 (선택) | `yyyy/mm/dd` 형식으로 입력 → 내부에서 regex 변환 |
| 시작 페이지 | 유지 | |
| 거래당 행 수 | **제거** | |
| 레이아웃 타입 | **제거** (내부 자동 결정) | |

### 날짜 형식 → regex 변환

사용자는 regex 대신 친숙한 형식으로 입력한다.

| 사용자 입력 | 변환된 regex |
|---|---|
| `yyyy/mm/dd` | `\d{4}/\d{2}/\d{2}` |
| `yyyy-mm-dd` | `\d{4}-\d{2}-\d{2}` |
| `yyyy.mm.dd` | `\d{4}\.\d{2}\.\d{2}` |
| `yy/mm/dd` | `\d{2}/\d{2}/\d{2}` |

변환 규칙:
- `yyyy` → `\d{4}`, `yy` → `\d{2}`, `mm` → `\d{2}`, `dd` → `\d{2}`
- `.` → `\.` (regex 이스케이프)
- `/`, `-` → 그대로

변환은 UI 폼 제출 시점에 수행하며, `DynamicParserConfig.date_re`에는 변환된 regex가 저장된다.  
자동 감지 결과도 사용자에게는 `yyyy/mm/dd` 형태로 표시하고, 저장 시 regex로 변환한다.

### 템플릿 생성 → 업로드 플로우

```
[1] 폼 입력: 증권사명, 키워드, data_start_keyword, (date_re 선택)
[2] "템플릿 생성" → PDF 선택 → export_parser_template() → Excel 저장
    → 자동 감지된 date_re 있으면 폼에 자동 채움
[3] 사용자 Excel 편집 (제목행 → 노란색, 스킵 셀 → 회색)
[4] "포맷 파일 업로드" → read_parser_template() → DynamicParserConfig 생성
    → layout_type = "header_mapped" (자동, 사용자에게 노출 안 함)
[5] 파서 저장 → parser_registry 등록
```

---

## 마이그레이션

- **built-in 파서** (samsung.py, mirae_asset.py, citi.py): 영향 없음
- **기존 동적 파서 JSON** (`layout_type: "table"` / `"template"`): `"header_mapped"`으로 변환 필요  
  → 기존 `column_index` + `row_offset` 기반 매핑은 동작 불가, 재생성 필요
- **`"rotated"` 레이아웃**: 기존 로직 그대로 유지

---

## 범위 외 (이번 설계에서 제외)

- OCR 스캔 PDF의 헤더 감지 정확도 개선
- built-in 파서의 header_mapped 레이아웃 전환
- 다중 테이블이 한 페이지에 있는 경우 처리
