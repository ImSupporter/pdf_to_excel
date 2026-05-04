import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldMapping:
    standard_field: str  # STANDARD_FIELDS key: "date", "type", "ticker", ...
    column_index: int = 0   # table layout: column index within row group
    row_offset: int = 0     # table layout: row offset within tx group (0=anchor)
    y_min: int = 0          # rotated layout: y_top minimum
    y_max: int = 0          # rotated layout: y_top maximum


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str                    # raw regex string
    layout_type: str                # "table" | "rotated"
    start_page: int                 # page index to start parsing from
    rows_per_tx: int                # rows per transaction (table layout only)
    skip_keywords: list[str]        # row skip keywords (table layout only)
    field_mappings: list[FieldMapping] = field(default_factory=list)


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "증권거래내역변환기"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> list[DynamicParserConfig]:
    path = _get_data_dir() / "parsers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    configs = []
    for item in data:
        mappings = [FieldMapping(**m) for m in item.pop("field_mappings", [])]
        configs.append(DynamicParserConfig(**item, field_mappings=mappings))
    return configs


def save(configs: list[DynamicParserConfig]) -> None:
    path = _get_data_dir() / "parsers.json"
    data = [dataclasses.asdict(cfg) for cfg in configs]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
