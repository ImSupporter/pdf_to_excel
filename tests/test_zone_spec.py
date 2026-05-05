from unittest.mock import MagicMock


def test_split_by_ys_no_splits():
    from core.zone_spec import _split_by_ys
    result = _split_by_ys(10.0, 50.0, [])
    assert result == [(10.0, 50.0)]


def test_split_by_ys_one_split():
    from core.zone_spec import _split_by_ys
    result = _split_by_ys(10.0, 50.0, [30.0])
    assert result == [(10.0, 30.0), (30.0, 50.0)]


def test_split_by_ys_ignores_out_of_range():
    from core.zone_spec import _split_by_ys
    # y=5 < header_start=10, y=60 > header_end=50 → ignored
    result = _split_by_ys(10.0, 50.0, [5.0, 30.0, 60.0])
    assert result == [(10.0, 30.0), (30.0, 50.0)]


def test_collect_text_picks_cells_in_range():
    from core.zone_spec import _collect_text
    # words: (x0, y0, x1, y1, text, block_no, line_no, word_no)
    words = [
        (5.0,  10.0, 55.0, 20.0, "거래일자", 0, 0, 0),
        (60.0, 10.0, 110.0, 20.0, "거래명",  0, 0, 1),
        (200.0, 10.0, 250.0, 20.0, "outside", 0, 0, 2),
    ]
    result = _collect_text(words, 0.0, 120.0, 5.0, 25.0)
    assert "거래일자" in result
    assert "거래명" in result
    assert "outside" not in result


def test_collect_text_empty_when_no_match():
    from core.zone_spec import _collect_text
    words = [(200.0, 10.0, 250.0, 20.0, "outside", 0, 0, 0)]
    result = _collect_text(words, 0.0, 100.0, 5.0, 25.0)
    assert result == ""


def test_collect_text_boundary_exclusive():
    from core.zone_spec import _collect_text
    # word center exactly at x1=100 → should NOT be included in [0, 100)
    words = [(95.0, 10.0, 105.0, 20.0, "boundary", 0, 0, 0)]
    result = _collect_text(words, 0.0, 100.0, 5.0, 25.0)
    assert result == ""
    # but it SHOULD be included in [100, 200)
    result2 = _collect_text(words, 100.0, 200.0, 5.0, 25.0)
    assert "boundary" in result2


def test_extract_fields_two_columns_no_hlines():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 300.0
    mock_page.rect.height = 400.0
    mock_page.get_text.return_value = [
        # col 0: 0~100, header y: 10~40
        (10.0, 15.0, 80.0, 25.0, "거래일자", 0, 0, 0),
        # col 1: 100~300, header y: 10~40
        (110.0, 15.0, 200.0, 25.0, "거래명", 0, 0, 1),
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[100.0],
        row_ys_per_col={},
        header_start_y=10.0,
        header_end_y=40.0,
        data_start_y=45.0,
        data_end_y=380.0,
    )
    fields = extract_fields(spec, mock_page)

    assert len(fields) == 2
    assert fields[0].x_min == 0.0
    assert fields[0].x_max == 100.0
    assert fields[0].y_min == 45.0
    assert fields[0].y_max == 380.0
    assert fields[0].row_offset == 0
    assert fields[1].x_min == 100.0
    assert fields[1].x_max == 300.0


def test_extract_fields_skips_empty_slots():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 200.0
    mock_page.rect.height = 300.0
    # col 1 (100~200) has no text in header → should be skipped
    mock_page.get_text.return_value = [
        (10.0, 15.0, 80.0, 25.0, "거래일자", 0, 0, 0),
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[100.0],
        row_ys_per_col={},
        header_start_y=10.0,
        header_end_y=40.0,
        data_start_y=45.0,
        data_end_y=280.0,
    )
    fields = extract_fields(spec, mock_page)
    assert len(fields) == 1  # col 1 empty → skipped


def test_extract_fields_two_row_offsets():
    from core.zone_spec import ZoneSpec, extract_fields

    mock_page = MagicMock()
    mock_page.rect.width = 200.0
    mock_page.rect.height = 300.0
    mock_page.get_text.return_value = [
        (10.0, 12.0, 80.0, 22.0, "거래일자", 0, 0, 0),  # row_offset=0
        (10.0, 32.0, 80.0, 42.0, "거래번호", 0, 0, 1),  # row_offset=1
    ]

    spec = ZoneSpec(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[],
        row_ys_per_col={0: [27.0]},  # split at y=27 → slots (10,27) and (27,50)
        header_start_y=10.0,
        header_end_y=50.0,
        data_start_y=55.0,
        data_end_y=280.0,
    )
    fields = extract_fields(spec, mock_page)
    assert len(fields) == 2
    assert fields[0].row_offset == 0
    assert fields[1].row_offset == 1


def test_zone_spec_to_config():
    from core.zone_spec import ZoneSpec, zone_spec_to_config
    from core.parser_registry import FieldMapping

    spec = ZoneSpec(
        broker_name="삼성증권",
        detection_keywords=["삼성"],
        date_format="yyyy/mm/dd",
        header_start_keyword="거래일자",
        start_page=0,
        column_xs=[],
        row_ys_per_col={},
        header_start_y=0.0,
        header_end_y=50.0,
        data_start_y=55.0,
        data_end_y=500.0,
    )
    fms = [
        FieldMapping(standard_field="date", row_offset=0,
                     x_min=0.0, x_max=100.0, y_min=55.0, y_max=500.0)
    ]
    config = zone_spec_to_config(spec, fms)

    assert config.broker_name == "삼성증권"
    assert config.layout_type == "header_mapped"
    assert config.date_re == r"\d{4}/\d{2}/\d{2}"
    assert config.start_page == 0
    assert config.skip_keywords == []
    assert config.field_mappings[0].x_min == 0.0
    assert config.field_mappings[0].x_max == 100.0
