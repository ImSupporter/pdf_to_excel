# Coordinate Template Parser Design

## 목적

PDF 거래내역을 최대한 원본에 가깝게 Excel로 변환하기 위해, 파서 생성과 실제 파싱을 모두 사용자가 Zone Editor에서 지정한 x/y 좌표 영역 기준으로 동작하게 바꾼다.

기존 헤더 자동 추론 방식은 제거한다. 헤더 텍스트는 파서 생성의 필수 입력이나 자동 매핑 근거가 아니다. 사용자가 지정한 좌표 템플릿과 셀 매핑만 파싱의 기준이 된다.

## 범위

### 포함

- Zone Editor에서 데이터 영역과 거래 1건의 반복 y 템플릿을 지정한다.
- 사용자가 지정한 x 컬럼 영역과 컬럼별 거래 템플릿 y 슬롯을 조합해 셀 매핑 목록을 만든다.
- 각 셀 매핑에는 Excel에 출력할 사용자 필드명을 입력한다.
- 각 셀 매핑은 선택적으로 표준 필드 4개 중 하나에 연결할 수 있다.
- 실제 파싱은 데이터 영역 안에서 거래 1건 템플릿을 반복 적용한다.
- Excel raw row 컬럼명은 표준 필드와 커스텀 필드 모두 항상 사용자가 입력한 필드명을 사용한다.
- 표준 `Transaction` 필드는 거래일자, 거래종류, 거래금액, 잔액만 남긴다.

### 제외

- 헤더 텍스트 자동 추출로 필드명을 생성하는 기능
- 날짜 정규식을 거래 행 앵커로 사용하는 기능
- PDF row 자동 감지 결과를 거래 단위로 신뢰하는 기능
- 모든 데이터 행 경계를 사용자가 직접 긋는 방식
- 기존 잘못된 parser format 설계 문서의 내용 반영

## 사용자 요구사항

1. 파서는 Zone Editing 화면에서 설정한 x/y 좌표 영역 기준으로만 파싱한다.
2. 데이터 행 구분은 사용자가 지정한 거래 1건 y 템플릿을 반복 적용한다.
3. 헤더 자동 추출은 사용하지 않는다. 사용자가 데이터 템플릿 셀을 직접 필드명에 매핑한다.
4. 셀 영역 안에 여러 단어가 있으면 y, x 좌표순으로 정렬한 뒤 공백으로 결합한다.
5. 표준 필드는 거래일자, 거래종류, 거래금액, 잔액만 유지한다.
6. 그 외 PDF 컬럼은 모두 커스텀 필드로 다룬다.
7. Excel 컬럼명은 표준 필드와 커스텀 필드 모두 사용자가 입력한 필드명을 사용한다.
8. 반복 거래 구간에서 하나라도 값이 있으면 거래 행으로 유지하고 Excel에 출력한다.
9. 반복 거래 구간의 모든 매핑 필드 값이 비어 있을 때만 그 행을 버린다.
10. 표준 필드 값이 비어 있거나 숫자 변환에 실패해도 변환은 계속한다.

## 핵심 개념

### Coordinate Template

Coordinate Template은 한 증권사 PDF의 거래내역 표를 읽기 위한 좌표 기반 파싱 정의다.

- `column_xs`: 컬럼 경계를 나누는 세로선 x 좌표
- `data_start_y`, `data_end_y`: 실제 거래 데이터를 반복 파싱할 y 범위
- `template_height`: 거래 1건의 높이. 사용자가 데이터 영역의 첫 거래 시작/끝 마커를 맞춰 정한다.
- `template_row_ys_per_col`: 컬럼별로 거래 1건 내부를 나누는 y 경계
- `cell_mappings`: x 컬럼 영역과 해당 컬럼의 거래 1건 내부 y 슬롯을 필드로 연결한 목록

파싱 시에는 각 페이지의 데이터 영역에서 `template_height` 단위로 반복 구간을 만들고, 각 반복 구간마다 동일한 셀 매핑을 적용한다.

컬럼별 y 슬롯 수는 서로 달라도 된다. 예를 들어 첫 번째 컬럼은 거래일자 1칸만 갖고, 두 번째 컬럼은 종목명/종목코드 2칸을 갖고, 세 번째 컬럼은 수량/단가/금액 3칸을 가질 수 있다.

### Cell Mapping

Cell Mapping은 PDF의 특정 셀 사각형을 Excel 컬럼으로 변환하는 설정이다.

필수 값:

- `display_name`: Excel 컬럼명. 사용자가 입력한다.
- `column_index`: 셀이 속한 컬럼 인덱스. 저장 후 디버깅과 UI 재표시에 사용한다.
- `x_min`, `x_max`: PDF 좌표계 기준 셀의 가로 범위
- `template_y_min`, `template_y_max`: 거래 1건 템플릿 안에서의 상대 y 범위

선택 값:

- `standard_field`: 내부 `Transaction`에 연결할 표준 필드. 값은 `date`, `type`, `amount`, `balance`, `None` 중 하나다.

`display_name`은 raw row의 key로 사용한다. `standard_field`가 있어도 Excel 컬럼명은 `display_name`을 사용한다.

## 표준 필드

`Transaction` 모델은 다음 4개 표준 필드만 가진다.

| 내부 키 | 표시 의미 | 기본값 |
| --- | --- | --- |
| `date` | 거래일자 | 빈 문자열 |
| `type` | 거래종류 | 빈 문자열 |
| `amount` | 거래금액 | `0.0` |
| `balance` | 잔액 | `0.0` |

기존 `ticker`, `name`, `quantity`, `price`, `fee`, `tax` 등은 표준 필드에서 제거하고 커스텀 필드로 처리한다. 커스텀 필드는 raw row와 Excel 출력에만 포함된다.

## 데이터 모델

### DynamicParserConfig

동적 파서 설정은 좌표 템플릿 중심으로 바뀐다.

```python
@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    layout_type: str  # "coordinate_template"
    start_page: int
    data_start_y: float
    data_end_y: float
    template_height: float
    column_xs: list[float]
    template_row_ys_per_col: dict[int, list[float]]
    cell_mappings: list[CellMapping]
```

`date_re`, `skip_keywords`, `field_mappings`, `header_start_keyword`, `header_start_y`, `header_end_y`, `row_ys_per_col`은 새 파서 생성/파싱 로직에서 필수 개념이 아니다. 하위 호환 로드는 별도 구현 계획에서 다루되, 새 파서 저장 형식의 기준은 위 구조다.

### CellMapping

```python
@dataclass
class CellMapping:
    display_name: str
    standard_field: str | None
    column_index: int
    x_min: float
    x_max: float
    template_y_min: float
    template_y_max: float
```

`standard_field`는 `date`, `type`, `amount`, `balance`, `None`만 허용한다.

## Zone Editor UI

기존 3패널 구조는 유지한다.

### 1패널: 파서 정보

- 증권사명
- 감지 키워드
- 시작 페이지

날짜 형식과 헤더 시작 키워드는 좌표 템플릿 파싱의 필수 입력에서 제거한다.

### 2패널: 좌표 템플릿 편집

사용자가 PDF 위에서 다음 영역을 지정한다.

- 컬럼 x 경계
- 데이터 시작/끝 y
- 거래 1건 템플릿 끝 y
- 컬럼별 거래 1건 내부 y 경계

거래 1건 템플릿 시작 y는 `data_start_y`와 같다. 사용자는 첫 거래의 끝 y를 맞춰 `template_height = template_end_y - data_start_y`를 정한다. 파서는 이 템플릿 높이와 내부 y 경계를 데이터 끝까지 반복 적용한다.

거래 1건 내부 y 경계선은 전체 표 폭에 공통으로 적용하지 않는다. 사용자가 특정 컬럼 안에서 가로선을 추가하면 그 컬럼에만 y 슬롯이 생긴다. 컬럼마다 y 슬롯 개수가 달라도 정상이다.

### 3패널: 셀 매핑 목록

사용자가 "셀 목록 생성"을 누르면 x 컬럼 영역과 각 컬럼의 거래 1건 내부 y 슬롯을 조합해 셀 카드 목록을 만든다.

셀 생성 규칙:

1. `column_xs`로 컬럼 x 범위를 만든다.
2. 각 컬럼별 `template_row_ys_per_col[column_index]`를 정렬한다.
3. 컬럼별 y 경계가 없으면 해당 컬럼은 거래 1건 전체 높이를 하나의 슬롯으로 사용한다.
4. 컬럼별 y 경계가 있으면 `[0] + row_ys + [template_height]`로 해당 컬럼의 y 슬롯을 만든다.
5. 각 컬럼에서만 `x 범위 × 그 컬럼의 y 슬롯` 셀 카드를 만든다.

각 셀 카드는 다음 입력을 가진다.

- 사용자 필드명 `display_name`
- 표준 필드 연결: 없음, 거래일자, 거래종류, 거래금액, 잔액
- 셀 좌표 표시: `column=N`, `x=[x_min,x_max]`, `template_y=[y_min,y_max]`

사용자가 필드명을 비워 둔 셀은 저장하지 않는다. 같은 `display_name`이 여러 셀에 지정되면 파싱 시 같은 raw field에 공백으로 이어 붙인다. 같은 `standard_field`가 여러 셀에 지정되면 같은 방식으로 이어 붙인 값을 `Transaction` 생성에 사용한다.

## 파싱 로직

### 전체 흐름

```text
for page in pages[start_page:]:
    for transaction_rect in repeat_template(data_start_y, data_end_y, template_height):
        raw = {}
        standard_values = {}
        for mapping in cell_mappings:
            abs_y_min = transaction_rect.y_min + mapping.template_y_min
            abs_y_max = transaction_rect.y_min + mapping.template_y_max
            value = collect_words(page, mapping.x_min, mapping.x_max, abs_y_min, abs_y_max)
            raw[mapping.display_name] += value
            if mapping.standard_field:
                standard_values[mapping.standard_field] += value
        if every raw value is empty:
            continue
        append raw row
        append Transaction from standard_values with defaults
```

### 반복 구간 생성

`data_start_y`부터 `data_end_y`까지 `template_height`를 더해 거래 후보 구간을 만든다.

- 후보 구간의 시작 y: `data_start_y + n * template_height`
- 후보 구간의 끝 y: `min(start_y + template_height, data_end_y)`
- 마지막 후보 구간이 템플릿 높이보다 작아도 셀 값이 하나라도 있으면 유지한다.
- `template_height <= 0`은 파서 생성 단계에서 저장을 막는다.

### 셀 텍스트 추출

PDF 단어는 `page.get_text("words")` 결과를 사용한다.

- 단어 중심점 `(cx, cy)`가 셀 사각형 안에 있으면 포함한다.
- 포함 조건은 `x_min <= cx < x_max`, `y_min <= cy < y_max`다.
- 포함된 단어는 `(cy, cx)` 순서로 정렬한다.
- 최종 값은 단어 텍스트를 공백으로 결합한다.
- 스캔 PDF의 OCR fallback은 현재 `pdf_utils`/`ocr` 구조를 따르되, 구현 계획에서 좌표 사각형 추출이 가능한 형태로 조정한다.

### 빈 행 처리

한 거래 후보 구간에서 모든 `display_name` 값이 비어 있으면 버린다.

하나라도 값이 있으면 거래 행으로 유지한다. 이 행은 raw rows에 들어가며 Excel에 출력된다. 표준 필드 값이 없어도 유지한다.

### Transaction 생성

표준 필드는 raw row와 별도로 `standard_field` 연결이 있는 셀에서 만든다.

- `date`: 값이 없으면 `""`
- `type`: 값이 없으면 `""`
- `amount`: 숫자 변환 실패 또는 값 없음이면 `0.0`
- `balance`: 숫자 변환 실패 또는 값 없음이면 `0.0`
- `broker`: 증권사명
- `raw`: Excel에 나갈 사용자 필드명 기반 raw row

숫자 변환은 쉼표와 공백을 제거한 뒤 `float()`를 시도한다. 실패해도 변환을 중단하지 않는다.

## Excel 출력

`export_to_excel(broker_raw, output_path)`의 기본 계약은 유지한다.

`broker_raw`의 각 row key는 사용자가 입력한 `display_name`이다. 따라서 Excel 시트 컬럼명도 `display_name`이 된다.

표준 필드에 연결된 셀도 Excel에서는 `date`, `amount` 같은 내부 키가 아니라 사용자가 입력한 필드명으로 출력한다.

## 오류 처리와 검증

파서 저장 전 다음 조건을 검증한다.

- 증권사명이 비어 있지 않다.
- 감지 키워드가 1개 이상 있다.
- 시작 페이지가 로드된 PDF 범위 안에 있다.
- 데이터 시작 y가 데이터 끝 y보다 작다.
- 거래 템플릿 높이가 0보다 크다.
- 셀 매핑이 1개 이상 있다.
- 모든 셀 매핑의 `display_name`이 비어 있지 않다.
- 모든 셀 매핑의 x/y 범위가 양수 면적을 가진다.
- `standard_field` 값은 허용된 4개 또는 `None`이다.

파싱 중 개별 셀 값이 비거나 표준 필드 변환에 실패해도 오류로 처리하지 않는다. 원본 Excel 변환을 우선한다.

## 테스트 전략

단위 테스트는 실제 PDF 없이 mock page와 `get_text("words")` 결과로 작성한다.

주요 테스트:

- 셀 사각형 안 단어를 y,x 순서로 공백 결합한다.
- 사각형 경계 밖 단어는 제외한다.
- 데이터 영역에 거래 템플릿 높이를 반복 적용한다.
- 모든 필드가 빈 반복 구간은 버린다.
- 하나라도 값이 있는 반복 구간은 raw row와 Excel 대상에 유지한다.
- 표준 필드 4개만 `Transaction`에 매핑된다.
- 커스텀 필드는 `Transaction` 표준 속성이 아니라 raw row에만 남는다.
- Excel raw row key가 항상 `display_name`이다.
- 숫자 변환 실패 시 `amount`, `balance`는 `0.0`이 된다.
- 기존 parser registry 저장/로드가 새 `coordinate_template` config를 왕복한다.

## 마이그레이션 방침

새로 생성되는 파서는 `layout_type="coordinate_template"`로 저장한다.

기존 `header_mapped` 파서는 새 파싱 엔진에서 사용하지 않는다. 로드 단계에서는 앱이 깨지지 않도록 기존 JSON을 읽을 수 있어야 하지만, `get_all_parsers()`에는 `coordinate_template` 파서만 포함한다. 기존 `header_mapped` 설정은 사용자가 새 Zone Editor로 다시 생성해야 한다.

기존 설정을 자동 변환하지 않는다. 헤더 자동 추출 기반 필드 매핑은 거래 1건 y 템플릿과 사용자 필드명 매핑을 포함하지 않으므로, 자동 변환하면 사용자가 의도하지 않은 Excel 컬럼이 생성될 수 있다.

## 성공 기준

- 사용자는 헤더 자동 추론 없이 좌표 템플릿과 셀 매핑만으로 파서를 만들 수 있다.
- 실제 파싱 결과는 사용자가 지정한 x/y 사각형 반복 규칙으로 설명 가능하다.
- PDF상 일부 값만 있는 거래 후보도 Excel에 보존된다.
- Excel 컬럼명은 항상 사용자가 입력한 필드명이다.
- 표준 필드는 거래일자, 거래종류, 거래금액, 잔액 4개로 제한된다.
- 코드 구현 전 이 문서와 별도의 구현 계획 문서가 먼저 작성되고 승인된다.
