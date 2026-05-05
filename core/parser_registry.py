import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_STANDARD_FIELDS = {"date", "type", "amount", "balance"}


@dataclass
class CellMapping:
    display_name: str
    standard_field: str | None
    column_index: int
    x_min: float
    x_max: float
    template_y_min: float
    template_y_max: float


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    layout_type: str
    start_page: int
    data_start_y: float = 0.0
    data_end_y: float = 0.0
    template_height: float = 0.0
    column_xs: list[float] = field(default_factory=list)
    template_row_ys_per_col: dict[int, list[float]] = field(default_factory=dict)
    cell_mappings: list[CellMapping] = field(default_factory=list)


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / "증권거래내역변환기"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_cell_mappings(raw_mappings: Any) -> list[CellMapping]:
    if not isinstance(raw_mappings, list):
        return []

    valid = {f.name for f in dataclasses.fields(CellMapping)}
    mappings: list[CellMapping] = []
    for item in raw_mappings:
        if not isinstance(item, dict):
            continue
        data = {k: v for k, v in item.items() if k in valid}
        try:
            mappings.append(CellMapping(**data))
        except TypeError:
            continue
    return mappings


def _coerce_template_row_ys(raw: Any) -> dict[int, list[float]]:
    if not isinstance(raw, dict):
        return {}

    coerced: dict[int, list[float]] = {}
    for key, value in raw.items():
        try:
            int_key = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, list):
            continue
        try:
            coerced[int_key] = [float(v) for v in value]
        except (TypeError, ValueError):
            continue
    return coerced


def load() -> list[DynamicParserConfig]:
    path = _get_data_dir() / "parsers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    valid_cfg = {f.name for f in dataclasses.fields(DynamicParserConfig)}
    configs: list[DynamicParserConfig] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cfg_kwargs = {k: v for k, v in item.items() if k in valid_cfg}
        cfg_kwargs["template_row_ys_per_col"] = _coerce_template_row_ys(
            cfg_kwargs.get("template_row_ys_per_col", {})
        )
        cfg_kwargs["cell_mappings"] = _load_cell_mappings(
            cfg_kwargs.get("cell_mappings", [])
        )
        try:
            configs.append(DynamicParserConfig(**cfg_kwargs))
        except TypeError:
            continue
    return configs


def save(configs: list[DynamicParserConfig]) -> None:
    path = _get_data_dir() / "parsers.json"
    data = [dataclasses.asdict(cfg) for cfg in configs]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_num(value: str) -> float:
    try:
        return float(str(value).replace(",", "").replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


def build_class(config: DynamicParserConfig) -> type:
    """config를 받아 BaseParser를 상속하는 런타임 클래스를 반환한다."""
    from core.models import Transaction
    from parsers.base import BaseParser

    _cfg = config

    def _standard_value(raw: dict[str, str], standard_field: str) -> str:
        for mapping in _cfg.cell_mappings:
            if mapping.standard_field == standard_field:
                return raw.get(mapping.display_name, "")
        return ""

    def _words_for_page(page: Any) -> list[tuple[float, float, float, float, str]]:
        words = page.get_text("words")
        normalized = []
        for word in words:
            if len(word) < 5:
                continue
            text = str(word[4]).strip()
            if not text:
                continue
            normalized.append(
                (
                    float(word[0]),
                    float(word[1]),
                    float(word[2]),
                    float(word[3]),
                    text,
                )
            )
        return normalized

    def _extract_cell(
        words: list[tuple[float, float, float, float, str]],
        mapping: CellMapping,
        slot_y: float,
    ) -> str:
        y_min = slot_y + mapping.template_y_min
        y_max = slot_y + mapping.template_y_max
        selected = []
        for x0, y0, x1, y1, text in words:
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            if mapping.x_min <= cx <= mapping.x_max and y_min <= cy <= y_max:
                selected.append((cy, cx, text))
        return " ".join(
            text
            for _y, _x, text in sorted(selected, key=lambda item: (item[0], item[1]))
        )

    def parse(self, pages):
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        if _cfg.layout_type != "coordinate_template" or _cfg.template_height <= 0:
            return transactions, raw_rows

        for page_idx, page in enumerate(pages):
            if page_idx < _cfg.start_page:
                continue

            words = _words_for_page(page)
            slot_y = _cfg.data_start_y
            while slot_y < _cfg.data_end_y:
                raw = {
                    mapping.display_name: _extract_cell(words, mapping, slot_y)
                    for mapping in _cfg.cell_mappings
                }
                if any(value for value in raw.values()):
                    transactions.append(
                        Transaction(
                            date=_standard_value(raw, "date"),
                            type=_standard_value(raw, "type"),
                            amount=_parse_num(_standard_value(raw, "amount")),
                            balance=_parse_num(_standard_value(raw, "balance")),
                            broker=_cfg.broker_name,
                            raw=raw,
                        )
                    )
                    raw_rows.append(raw)
                slot_y += _cfg.template_height

        return transactions, raw_rows

    return type(
        f"DynamicParser_{config.broker_name}",
        (BaseParser,),
        {
            "BROKER_NAME": config.broker_name,
            "DETECTION_KEYWORDS": list(config.detection_keywords),
            "parse": parse,
        },
    )


def get_all_parsers() -> list:
    from parsers import PARSERS

    return PARSERS + [
        build_class(cfg)
        for cfg in load()
        if cfg.layout_type == "coordinate_template"
    ]
