import json
import tempfile
from pathlib import Path
import pytest


def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", row_offset=0, x=50.0)
    assert fm.standard_field == "date"
    assert fm.row_offset == 0
    assert fm.x == 50.0


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
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
            FieldMapping(standard_field="amount", row_offset=0, x=300.0),
        ],
    )
    parser_registry.save([cfg])

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].detection_keywords == ["테스트", "거래내역"]
    assert len(loaded[0].field_mappings) == 2
    assert loaded[0].field_mappings[1].x == 300.0


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
    assert loaded[0].field_mappings[0].x == 50.0


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
            FieldMapping(standard_field="date", row_offset=0, x=50.0),
        ],
    )
    cls = build_class(cfg)
    assert issubclass(cls, BaseParser)
    assert cls.BROKER_NAME == "테스트증권"
    assert cls.DETECTION_KEYWORDS == ["테스트"]
    assert hasattr(cls(), "parse")


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
