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


def test_build_cell_mappings_supports_different_y_slot_counts_per_column():
    from core.zone_spec import ZoneSpec, build_cell_mappings

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        start_page=0,
        column_xs=[100.0, 250.0],
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
        (0, 0.0, 100.0, 0.0, 20.0),
        (1, 100.0, 250.0, 0.0, 10.0),
        (1, 100.0, 250.0, 10.0, 20.0),
        (2, 250.0, 400.0, 0.0, 6.0),
        (2, 250.0, 400.0, 6.0, 12.0),
        (2, 250.0, 400.0, 12.0, 20.0),
    ]
    assert all(c.display_name == "" for c in cells)
    assert all(c.standard_field is None for c in cells)


def test_zone_spec_to_config_keeps_user_named_mappings():
    from core.parser_registry import CellMapping
    from core.zone_spec import ZoneSpec, zone_spec_to_config

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트", "거래"],
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
    assert config.template_height == 25.0
    assert config.cell_mappings == mappings
