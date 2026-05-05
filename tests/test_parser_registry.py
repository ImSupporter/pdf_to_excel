import json
from unittest.mock import MagicMock


def _mock_page(words, width=400.0, height=500.0):
    page = MagicMock()
    page.rect.width = width
    page.rect.height = height
    page.get_text.return_value = words
    return page


def test_cell_mapping_roundtrip():
    from core.parser_registry import CellMapping

    cm = CellMapping(
        display_name="사용자거래일자",
        standard_field="date",
        column_index=0,
        x_min=0.0,
        x_max=100.0,
        template_y_min=0.0,
        template_y_max=20.0,
    )

    assert cm.display_name == "사용자거래일자"
    assert cm.standard_field == "date"
    assert cm.column_index == 0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import CellMapping, DynamicParserConfig

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=200.0,
        template_height=20.0,
        column_xs=[100.0, 250.0],
        template_row_ys_per_col={1: [10.0]},
        cell_mappings=[
            CellMapping("거래일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("종목명", None, 1, 100.0, 250.0, 0.0, 10.0),
        ],
    )

    parser_registry.save([cfg])
    loaded = parser_registry.load()

    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].layout_type == "coordinate_template"
    assert loaded[0].template_row_ys_per_col == {1: [10.0]}
    assert loaded[0].cell_mappings[1].display_name == "종목명"


def test_load_ignores_unknown_fields_and_keeps_old_configs_out_of_runtime(tmp_path, monkeypatch):
    from core import parser_registry

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    old_and_new = [
        {
            "broker_name": "구버전증권",
            "detection_keywords": ["구버전"],
            "date_re": r"\d{4}/\d{2}/\d{2}",
            "layout_type": "header_mapped",
            "start_page": 0,
            "skip_keywords": [],
            "field_mappings": [],
        },
        {
            "broker_name": "새증권",
            "detection_keywords": ["새"],
            "layout_type": "coordinate_template",
            "start_page": 0,
            "data_start_y": 100.0,
            "data_end_y": 120.0,
            "template_height": 20.0,
            "column_xs": [],
            "template_row_ys_per_col": {},
            "cell_mappings": [],
        },
    ]
    (tmp_path / "parsers.json").write_text(
        json.dumps(old_and_new, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = parser_registry.load()
    assert [cfg.broker_name for cfg in loaded] == ["구버전증권", "새증권"]

    runtime_names = [cls.BROKER_NAME for cls in parser_registry.get_all_parsers()]
    assert "새증권" in runtime_names
    assert "구버전증권" not in runtime_names


def test_coordinate_template_parses_repeated_rows_with_display_names():
    from core.parser_registry import CellMapping, DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=140.0,
        template_height=20.0,
        column_xs=[100.0, 250.0],
        template_row_ys_per_col={1: [10.0]},
        cell_mappings=[
            CellMapping("사용자일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("사용자종목명", None, 1, 100.0, 250.0, 0.0, 10.0),
            CellMapping("사용자금액", "amount", 1, 100.0, 250.0, 10.0, 20.0),
        ],
    )
    words = [
        (10.0, 102.0, 70.0, 110.0, "2026/05/01", 0, 0, 0),
        (110.0, 102.0, 160.0, 110.0, "삼성", 0, 0, 1),
        (165.0, 102.0, 210.0, 110.0, "전자", 0, 0, 2),
        (110.0, 114.0, 180.0, 122.0, "1,000", 0, 0, 3),
        (10.0, 122.0, 70.0, 130.0, "2026/05/02", 0, 0, 4),
        (110.0, 122.0, 160.0, 130.0, "카카오", 0, 0, 5),
        (110.0, 134.0, 180.0, 138.0, "bad-number", 0, 0, 6),
    ]

    txns, raws = build_class(cfg)().parse([_mock_page(words)])

    assert raws == [
        {"사용자일자": "2026/05/01", "사용자종목명": "삼성 전자", "사용자금액": "1,000"},
        {"사용자일자": "2026/05/02", "사용자종목명": "카카오", "사용자금액": "bad-number"},
    ]
    assert txns[0].date == "2026/05/01"
    assert txns[0].amount == 1000.0
    assert txns[1].date == "2026/05/02"
    assert txns[1].amount == 0.0


def test_coordinate_template_skips_only_completely_empty_repeated_slot():
    from core.parser_registry import CellMapping, DynamicParserConfig, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        layout_type="coordinate_template",
        start_page=0,
        data_start_y=100.0,
        data_end_y=160.0,
        template_height=20.0,
        column_xs=[100.0],
        template_row_ys_per_col={},
        cell_mappings=[
            CellMapping("사용자일자", "date", 0, 0.0, 100.0, 0.0, 20.0),
            CellMapping("사용자잔액", "balance", 1, 100.0, 400.0, 0.0, 20.0),
        ],
    )
    words = [
        (10.0, 102.0, 70.0, 110.0, "2026/05/01", 0, 0, 0),
        (110.0, 142.0, 180.0, 150.0, "9,999", 0, 0, 1),
    ]

    txns, raws = build_class(cfg)().parse([_mock_page(words)])

    assert raws == [
        {"사용자일자": "2026/05/01", "사용자잔액": ""},
        {"사용자일자": "", "사용자잔액": "9,999"},
    ]
    assert txns[1].date == ""
    assert txns[1].balance == 9999.0
