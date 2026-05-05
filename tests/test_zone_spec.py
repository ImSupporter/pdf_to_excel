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


def test_split_by_ys_deduplicates_splits():
    from core.zone_spec import _split_by_ys

    assert _split_by_ys(0.0, 20.0, [10.0, 10.0, 15.0]) == [
        (0.0, 10.0),
        (10.0, 15.0),
        (15.0, 20.0),
    ]


def test_build_cell_mappings_deduplicates_column_xs():
    from core.zone_spec import ZoneSpec, build_cell_mappings

    # 100.0 중복 → 내부 열 [100, 200] 1개 생성
    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        start_page=0,
        column_xs=[100.0, 100.0, 200.0],
        template_row_ys_per_col={},
        data_start_y=0.0,
        data_end_y=20.0,
        template_height=20.0,
    )
    cells = build_cell_mappings(spec, page_width=300.0)
    assert len(cells) == 1
    assert cells[0].x_min == 100.0
    assert cells[0].x_max == 200.0


def test_build_cell_mappings_supports_different_y_slot_counts_per_column():
    from core.zone_spec import ZoneSpec, build_cell_mappings

    # 바깥쪽 열(col 0: 0~50, col 3: 300~400)은 제외되고 내부 열 2개만 생성
    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        start_page=0,
        column_xs=[50.0, 150.0, 300.0],
        template_row_ys_per_col={1: [10.0], 2: [6.0, 12.0]},
        data_start_y=100.0,
        data_end_y=180.0,
        template_height=20.0,
    )

    cells = build_cell_mappings(spec, page_width=400.0)

    assert [
        (c.column_index, c.x_min, c.x_max, c.template_y_min, c.template_y_max)
        for c in cells
    ] == [
        (1, 50.0, 150.0, 0.0, 10.0),
        (1, 50.0, 150.0, 10.0, 20.0),
        (2, 150.0, 300.0, 0.0, 6.0),
        (2, 150.0, 300.0, 6.0, 12.0),
        (2, 150.0, 300.0, 12.0, 20.0),
    ]
    assert all(c.display_name == "" for c in cells)
    assert all(c.standard_field is None for c in cells)


def test_zone_spec_to_config_keeps_user_named_mappings():
    from core.parser_registry import CellMapping
    from core.zone_spec import ZoneSpec, zone_spec_to_config

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=[" 테스트 ", "", "  ", "거래"],
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
    assert config.detection_keywords == ["테스트", "거래"]
    assert config.template_height == 25.0
    assert config.cell_mappings == mappings


def test_zone_spec_to_config_rejects_blank_broker():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(_valid_zone_spec(broker_name=" "), [_valid_cell_mapping()])


def test_zone_spec_to_config_rejects_blank_or_whitespace_only_keywords():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(
            _valid_zone_spec(detection_keywords=["", "  "]),
            [_valid_cell_mapping()],
        )


def test_zone_spec_to_config_rejects_negative_start_page():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(_valid_zone_spec(start_page=-1), [_valid_cell_mapping()])


def test_zone_spec_to_config_rejects_invalid_data_y_range():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(
            _valid_zone_spec(data_start_y=100.0, data_end_y=100.0),
            [_valid_cell_mapping()],
        )


def test_zone_spec_to_config_rejects_nonpositive_template_height():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(_valid_zone_spec(template_height=0.0), [_valid_cell_mapping()])


def test_zone_spec_to_config_rejects_empty_mappings():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(_valid_zone_spec(), [])


def test_zone_spec_to_config_rejects_blank_display_name():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(_valid_zone_spec(), [_valid_cell_mapping(display_name=" ")])


def test_zone_spec_to_config_rejects_invalid_x_range():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(
            _valid_zone_spec(),
            [_valid_cell_mapping(x_min=100.0, x_max=100.0)],
        )


def test_zone_spec_to_config_rejects_invalid_template_y_range():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(
            _valid_zone_spec(),
            [_valid_cell_mapping(template_y_min=25.0, template_y_max=25.0)],
        )


def test_zone_spec_to_config_rejects_invalid_standard_field():
    import pytest

    from core.zone_spec import zone_spec_to_config

    with pytest.raises(ValueError):
        zone_spec_to_config(
            _valid_zone_spec(),
            [_valid_cell_mapping(standard_field="unsupported")],
        )


def _valid_zone_spec(**overrides):
    from core.zone_spec import ZoneSpec

    values = {
        "broker_name": "테스트",
        "detection_keywords": ["테스트"],
        "start_page": 0,
        "column_xs": [100.0],
        "template_row_ys_per_col": {},
        "data_start_y": 50.0,
        "data_end_y": 150.0,
        "template_height": 25.0,
    }
    values.update(overrides)
    return ZoneSpec(**values)


def _valid_cell_mapping(**overrides):
    from core.parser_registry import CellMapping

    values = {
        "display_name": "내거래일자",
        "standard_field": "date",
        "column_index": 0,
        "x_min": 0.0,
        "x_max": 100.0,
        "template_y_min": 0.0,
        "template_y_max": 25.0,
    }
    values.update(overrides)
    return CellMapping(**values)
