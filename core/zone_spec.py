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
    interior = sorted({y for y in ys if y_start < y < y_end})
    points = [y_start] + interior + [y_end]
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _column_strips(column_xs: list[float], page_width: float) -> list[tuple[float, float]]:
    xs = sorted({x for x in column_xs if 0.0 < x < page_width})
    boundaries = [0.0] + xs + [page_width]
    return [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]


def build_cell_mappings(zone_spec: ZoneSpec, page_width: float) -> list[CellMapping]:
    mappings: list[CellMapping] = []
    strips = _column_strips(zone_spec.column_xs, page_width)
    # 첫 번째(왼쪽 여백)와 마지막(오른쪽 여백) 열은 제외
    inner = strips[1:-1] if len(strips) > 2 else []
    for col_idx, (x_min, x_max) in enumerate(inner, start=1):
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
    if (
        mapping.standard_field is not None
        and mapping.standard_field not in VALID_STANDARD_FIELDS
    ):
        raise ValueError("지원하지 않는 표준 필드입니다.")
    if mapping.x_min >= mapping.x_max:
        raise ValueError("셀의 x 범위가 올바르지 않습니다.")
    if mapping.template_y_min >= mapping.template_y_max:
        raise ValueError("셀의 y 범위가 올바르지 않습니다.")


def validate_zone_spec(zone_spec: ZoneSpec, mappings: list[CellMapping]) -> None:
    if not zone_spec.broker_name.strip():
        raise ValueError("증권사명을 입력하세요.")
    if not _normalize_detection_keywords(zone_spec.detection_keywords):
        raise ValueError("감지 키워드를 1개 이상 입력하세요.")
    if zone_spec.start_page < 0:
        raise ValueError("시작 페이지는 0 이상이어야 합니다.")
    if zone_spec.data_start_y >= zone_spec.data_end_y:
        raise ValueError("데이터 영역의 시작/끝이 올바르지 않습니다.")
    if zone_spec.template_height <= 0:
        raise ValueError("거래 1건 높이는 0보다 커야 합니다.")
    if not mappings:
        raise ValueError("셀 매핑을 1개 이상 입력하세요.")
    for mapping in mappings:
        validate_cell_mapping(mapping)


def _normalize_detection_keywords(keywords: list[str]) -> list[str]:
    return [keyword.strip() for keyword in keywords if keyword.strip()]


def zone_spec_to_config(
    zone_spec: ZoneSpec,
    cell_mappings: list[CellMapping],
) -> DynamicParserConfig:
    validate_zone_spec(zone_spec, cell_mappings)
    return DynamicParserConfig(
        broker_name=zone_spec.broker_name,
        detection_keywords=_normalize_detection_keywords(zone_spec.detection_keywords),
        layout_type="coordinate_template",
        start_page=zone_spec.start_page,
        data_start_y=zone_spec.data_start_y,
        data_end_y=zone_spec.data_end_y,
        template_height=zone_spec.template_height,
        column_xs=zone_spec.column_xs,
        template_row_ys_per_col=zone_spec.template_row_ys_per_col,
        cell_mappings=cell_mappings,
    )
