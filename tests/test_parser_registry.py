import json
import tempfile
from pathlib import Path
import pytest


def test_field_mapping_roundtrip():
    from core.parser_registry import FieldMapping
    fm = FieldMapping(standard_field="date", column_index=0, row_offset=0, y_min=0, y_max=0)
    assert fm.standard_field == "date"
    assert fm.column_index == 0


def test_dynamic_parser_config_roundtrip(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트", "거래내역"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=["합계"],
        field_mappings=[
            FieldMapping(standard_field="date", column_index=0, row_offset=0, y_min=0, y_max=0),
            FieldMapping(standard_field="amount", column_index=3, row_offset=0, y_min=0, y_max=0),
        ],
    )
    parser_registry.save([cfg])

    loaded = parser_registry.load()
    assert len(loaded) == 1
    assert loaded[0].broker_name == "테스트증권"
    assert loaded[0].detection_keywords == ["테스트", "거래내역"]
    assert len(loaded[0].field_mappings) == 2
    assert loaded[0].field_mappings[1].column_index == 3


def test_load_returns_empty_when_no_file(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    result = parser_registry.load()
    assert result == []


def test_build_class_returns_base_parser_subclass(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class
    from parsers.base import BaseParser

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="테스트증권",
        detection_keywords=["테스트"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="date", column_index=0),
            FieldMapping(standard_field="amount", column_index=2),
        ],
    )
    cls = build_class(cfg)
    assert issubclass(cls, BaseParser)
    assert cls.BROKER_NAME == "테스트증권"
    assert cls.DETECTION_KEYWORDS == ["테스트"]
    inst = cls()
    assert hasattr(inst, "parse")


def test_get_all_parsers_includes_builtins(tmp_path, monkeypatch):
    from core import parser_registry
    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)
    from core.parser_registry import get_all_parsers
    from parsers.samsung import SamsungParser
    from parsers.mirae_asset import MiraeAssetParser

    all_parsers = get_all_parsers()
    names = [p.BROKER_NAME for p in all_parsers]
    assert "삼성증권" in names
    assert "미래에셋증권" in names


def test_template_parser_uses_x_coordinate_to_match_values():
    """Template layout must find values by x proximity, not word-position column_index.

    Scenario: header has "종목명" at column_index=1, "수량" at column_index=2.
    Data row has an extra word ("전자" inserted between "삼성" and "100"),
    shifting "100" to column_index=3. column_index-based lookup returns "전자" for
    "수량", but x-coordinate lookup returns "100" correctly.
    """
    from unittest.mock import patch, MagicMock
    from core.parser_registry import DynamicParserConfig, FieldMapping, build_class

    cfg = DynamicParserConfig(
        broker_name="테스트",
        detection_keywords=["테스트"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="template",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[
            FieldMapping(standard_field="거래일자", column_index=0, row_offset=0, x=50.0),
            FieldMapping(standard_field="종목명",   column_index=1, row_offset=0, x=200.0),
            FieldMapping(standard_field="수량",     column_index=2, row_offset=0, x=350.0),
        ],
    )

    # Data row: "삼성"@200, "전자"@222 (split word), "100"@350
    # column_index=2 → "전자" (WRONG), x=350 → "100" (CORRECT)
    mock_rows = [
        [(50.0, "2024/01/01"), (200.0, "삼성"), (222.0, "전자"), (350.0, "100")]
    ]
    mock_page = MagicMock()

    with patch("core.pdf_utils.get_page_rows", return_value=mock_rows):
        cls = build_class(cfg)
        inst = cls()
        _transactions, raw_rows = inst.parse([mock_page])

    assert len(raw_rows) == 1
    assert raw_rows[0]["종목명"] == "삼성"
    assert raw_rows[0]["수량"] == "100"


def test_get_all_parsers_includes_dynamic(tmp_path, monkeypatch):
    from core import parser_registry
    from core.parser_registry import DynamicParserConfig, FieldMapping, get_all_parsers, save

    monkeypatch.setattr(parser_registry, "_get_data_dir", lambda: tmp_path)

    cfg = DynamicParserConfig(
        broker_name="다이나믹증권",
        detection_keywords=["다이나믹"],
        date_re=r"^\d{4}/\d{2}/\d{2}$",
        layout_type="table",
        start_page=0,
        rows_per_tx=1,
        skip_keywords=[],
        field_mappings=[],
    )
    save([cfg])

    all_parsers = get_all_parsers()
    names = [p.BROKER_NAME for p in all_parsers]
    assert "다이나믹증권" in names
