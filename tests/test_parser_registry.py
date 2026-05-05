import json
import tempfile
from pathlib import Path
import pytest


def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", row_offset=0, x_min=10.0, x_max=90.0)
    assert fm.standard_field == "date"
    assert fm.row_offset == 0
    assert fm.x_min == 10.0
    assert fm.x_max == 90.0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x_min=0.0, x_max=100.0),
            FieldMapping(standard_field="amount", row_offset=0, x_min=250.0, x_max=350.0),
        ],
    )
    parser_registry.save([cfg])

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].detection_keywords == ["테스트", "거래내역"]
    assert len(loaded[0].field_mappings) == 2
    assert loaded[0].field_mappings[1].x_min == 250.0
    assert loaded[0].field_mappings[1].x_max == 350.0


def test_load_returns_empty_when_no_file(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    result = parser_registry.load()
    assert result == []


def test_load_ignores_unknown_fields_in_old_json(tmp_path, monkeypatch):
    """Old parsers.json with column_index/rows_per_tx must load without error."""
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    old_format = [{
        "broker_name": "구버전증권",
        "detection_keywords": ["구버전"],
        "date_re": r"\d{4}/\d{2}/\d{2}",
        "layout_type": "table",
        "start_page": 0,
        "rows_per_tx": 2,
        "skip_keywords": [],
        "field_mappings": [{
            "standard_field": "date",
            "column_index": 0,
            "row_offset": 0,
            "y_min": 0,
            "y_max": 0,
            "x": 50.0,
        }]
    }]
    (tmp_path / "parsers.json").write_text(json.dumps(old_format), encoding="utf-8")

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "구버전증권"
    assert loaded[0].field_mappings[0].x_min == 0.0
    assert loaded[0].field_mappings[0].x_max == 100.0


def test_build_class_returns_base_parser_subclass():
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class
    from parsers.base import BaseParser

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x_min=0.0, x_max=100.0),
        ],
    )
    cls = build_class(cfg)
    assert issubclass(cls, BaseParser)
    assert cls.BROKER_NAME == "테스트증권"
    assert cls.DETECTION_KEYWORDS == ["테스트"]
    assert hasattr(cls(), "parse")


def test_header_mapped_cell_outside_all_ranges_skipped():
    """Cells whose x-coordinate falls outside all FieldMapping ranges are ignored."""
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    config = DynamicParserConfig(
        broker_name="Test",
        detection_keywords=["Test"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date",   row_offset=0, x_min=0.0,   x_max=100.0,
                         y_min=0.0, y_max=900.0),
            FieldMapping(standard_field="amount", row_offset=0, x_min=300.0, x_max=400.0,
                         y_min=0.0, y_max=900.0),
        ],
    )
    ParserClass = build_class(config)

    # cell_x=200 is outside both ranges [0,100] and [300,400] — should be ignored
    mock_rows = [
        (10.0, [(50.0, "2025/01/01"), (200.0, "IGNORED"), (350.0, "1000")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txs, _ = ParserClass().parse([MagicMock()])
    assert len(txs) == 1
    assert txs[0].amount == 1000.0
    # The ignored cell should not appear in any field
    assert txs[0].name is None or "IGNORED" not in str(txs[0].name)


def test_get_all_parsers_includes_builtins(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    from core.parser_registry import get_all_parsers

    all_parsers = get_all_parsers()
    names = [p.BROKER_NAME for p in all_parsers]
    assert "삼성증권" in names
    assert "미래에셋증권" in names


def test_get_all_parsers_includes_dynamic(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, get_all_parsers, save

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="다이나믹증권",
        detection_keywords=["다이나믹"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])
    names = [p.BROKER_NAME for p in get_all_parsers()]
    assert "다이나믹증권" in names


def test_header_mapped_single_header_parses_two_transactions():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date",   row_offset=0, x_min=0.0,   x_max=100.0),
            FieldMapping(standard_field="name",   row_offset=0, x_min=150.0, x_max=250.0),
            FieldMapping(standard_field="amount", row_offset=0, x_min=300.0, x_max=400.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (200.0, "삼성전자"), (350.0, "1000000")]),
        (20.0, [(50.0, "2024/01/02"), (200.0, "카카오"),   (350.0, "500000")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, raws = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 2
    assert txns[0].date == "2024/01/01"
    assert txns[0].name == "삼성전자"
    assert txns[0].amount == 1000000.0
    assert txns[1].date == "2024/01/02"


def test_header_mapped_continuation_row_concatenates():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", row_offset=0, x_min=0.0,   x_max=100.0),
            FieldMapping(standard_field="name", row_offset=0, x_min=150.0, x_max=250.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (200.0, "1Q미국S&P500")]),
        (20.0, [(200.0, "채혼합50액티브")]),  # continuation
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].name == "1Q미국S&P500 채혼합50액티브"


def test_header_mapped_two_header_rows_separate_fields():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=[],
        field_mappings=[
            # Header row 0: date@50, type@150
            FieldMapping(standard_field="date", row_offset=0, x_min=0.0,   x_max=100.0),
            FieldMapping(standard_field="type", row_offset=0, x_min=100.0, x_max=200.0),
            # Header row 1: name@50, amount@150 (same x — different field by row_offset)
            FieldMapping(standard_field="name",   row_offset=1, x_min=0.0,   x_max=100.0),
            FieldMapping(standard_field="amount", row_offset=1, x_min=100.0, x_max=200.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (150.0, "매도")]),
        (20.0, [(50.0, "삼성전자"),   (150.0, "1000000")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].type == "매도"
    assert txns[0].name == "삼성전자"
    assert txns[0].amount == 1000000.0


def test_header_mapped_skip_keywords_filter_rows():
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"\d{4}/\d{2}/\d{2}",
        layout_type="header_mapped",
        start_page=0,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date",   row_offset=0, x_min=0.0,   x_max=100.0),
            FieldMapping(standard_field="amount", row_offset=0, x_min=100.0, x_max=200.0),
        ],
    )
    mock_rows = [
        (10.0, [(50.0, "2024/01/01"), (150.0, "1000000")]),
        (20.0, [(50.0, "합계"),       (150.0, "9999999")]),
    ]
    with patch("core.pdf_utils.get_page_rows_with_y", return_value=mock_rows):
        txns, _ = build_class(cfg)().parse([MagicMock()])

    assert len(txns) == 1
    assert txns[0].amount == 1000000.0
