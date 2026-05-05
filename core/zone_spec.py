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
