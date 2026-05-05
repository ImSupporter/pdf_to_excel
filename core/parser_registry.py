import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldMapping:
    standard_field: str
    row_offset: int = 0
    x_min: float = 0.0   # 컬럼 스트립 왼쪽 경계 (PDF 좌표)
    x_max: float = 0.0   # 컬럼 스트립 오른쪽 경계 (PDF 좌표)
    y_min: float = 0.0
    y_max: float = 0.0


@dataclass
class DynamicParserConfig:
    broker_name: str
    detection_keywords: list[str]
    date_re: str
    layout_type: str           # "header_mapped" | "rotated"
    start_page: int
    skip_keywords: list[str]
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

    valid_fm = {f.name for f in dataclasses.fields(FieldMapping)}
    valid_cfg = {f.name for f in dataclasses.fields(DynamicParserConfig)}

    configs = []
    for item in data:
        raw_mappings = item.pop("field_mappings", [])
        mappings = []
        for m in raw_mappings:
            fm_data = {k: v for k, v in m.items() if k in valid_fm}
            # backward compat: old JSON has x field only → convert to x_min/x_max
            if "x" in m and "x_min" not in m and "x_max" not in m:
                fm_data["x_min"] = m["x"] - 50.0
                fm_data["x_max"] = m["x"] + 50.0
            mappings.append(FieldMapping(**fm_data))
        cfg_kwargs = {k: v for k, v in item.items() if k in valid_cfg}
        configs.append(DynamicParserConfig(**cfg_kwargs, field_mappings=mappings))
    return configs


def save(configs: list[DynamicParserConfig]) -> None:
    path = _get_data_dir() / "parsers.json"
    data = [dataclasses.asdict(cfg) for cfg in configs]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_class(config: "DynamicParserConfig") -> type:
    """config를 받아 BaseParser를 상속하는 런타임 클래스를 반환한다."""
    import re as _re
    from parsers.base import BaseParser
    from core.models import Transaction
    from core.parser_template import infer_standard_field

    _cfg = config
    _date_re = _re.compile(config.date_re)

    def _standard_key(field_name: str) -> str | None:
        return infer_standard_field(field_name) or field_name

    def _raw_value(raw: dict, standard_key: str) -> str:
        for fm in _cfg.field_mappings:
            if (
                _standard_key(fm.standard_field) == standard_key
                and fm.standard_field in raw
            ):
                return raw.get(fm.standard_field, "")
        return raw.get(standard_key, "")

    def _parse_num(s: str) -> float:
        try:
            return float(str(s).replace(",", "").replace(" ", ""))
        except (ValueError, AttributeError):
            return 0.0

    def parse(self, pages):
        import re as _re_mod
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        _header_group_size = max(
            (fm.row_offset for fm in _cfg.field_mappings), default=0
        ) + 1
        _date_fm = next(
            (fm for fm in _cfg.field_mappings if _standard_key(fm.standard_field) == "date"), None
        )
        _date_x_min = _date_fm.x_min if _date_fm else None
        _date_x_max = _date_fm.x_max if _date_fm else None
        _date_compiled = _re_mod.compile(_cfg.date_re)

        def _contains_skip(row_cells):
            joined = " ".join(t for _, t in row_cells)
            return any(kw in joined for kw in _cfg.skip_keywords)

        from core.pdf_utils import get_page_rows_with_y as _get_rows_with_y

        if _cfg.layout_type == "header_mapped":
            for page_idx, page in enumerate(pages):
                if page_idx < _cfg.start_page:
                    continue

                rows_with_y = [
                    (ry, rc)
                    for ry, rc in _get_rows_with_y(page, y_tolerance=4.0)
                    if rc and not _contains_skip(rc)
                ]

                groups: list[list[tuple]] = []
                current: list[tuple] = []
                for row_y, row_cells in rows_with_y:
                    is_anchor = False
                    if _date_fm is not None:
                        date_cells = [c for c in row_cells if _date_x_min <= c[0] <= _date_x_max]
                        if date_cells and _date_compiled.match(date_cells[0][1]):
                            is_anchor = True
                    if not is_anchor and any(_date_compiled.match(t) for _, t in row_cells):
                        is_anchor = True

                    if is_anchor:
                        if current:
                            groups.append(current)
                        current = [(row_y, row_cells)]
                    elif current:
                        current.append((row_y, row_cells))
                if current:
                    groups.append(current)

                for group in groups:
                    raw: dict = {
                        fm.standard_field: ""
                        for fm in _cfg.field_mappings
                    }
                    for row_offset, (row_y, row_cells) in enumerate(group):
                        if row_offset < _header_group_size:
                            candidates = [fm for fm in _cfg.field_mappings
                                          if fm.row_offset == row_offset]
                        else:
                            candidates = list(_cfg.field_mappings)
                        if not candidates:
                            continue
                        for cell_x, cell_text in row_cells:
                            matching = [fm for fm in candidates if fm.x_min <= cell_x <= fm.x_max]
                            if not matching:
                                continue
                            # column strips from ZoneEditorWidget are non-overlapping; first match wins
                            field = matching[0].standard_field
                            raw[field] = (
                                raw[field] + " " + cell_text if raw.get(field) else cell_text
                            )
                    transactions.append(Transaction(
                        date=_raw_value(raw, "date"),
                        type=_raw_value(raw, "type"),
                        ticker=_raw_value(raw, "ticker"),
                        name=_raw_value(raw, "name"),
                        quantity=_parse_num(_raw_value(raw, "quantity")),
                        price=_parse_num(_raw_value(raw, "price")),
                        amount=_parse_num(_raw_value(raw, "amount")),
                        fee=_parse_num(_raw_value(raw, "fee")),
                        tax=_parse_num(_raw_value(raw, "tax")),
                        balance=_parse_num(_raw_value(raw, "balance")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    ))
                    raw_rows.append(raw)

        elif _cfg.layout_type == "rotated":
            for page_idx, page in enumerate(pages):
                if page_idx < _cfg.start_page:
                    continue
                items: list[dict] = []
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    bx = block["bbox"][0]
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span["text"].strip()
                            if text:
                                items.append({
                                    "x": round(bx),
                                    "y_top": round(span["bbox"][1]),
                                    "text": text,
                                })
                for date_item in [it for it in items if _date_compiled.match(it["text"])]:
                    date_field_name = _date_fm.standard_field if _date_fm else "date"
                    raw = {date_field_name: date_item["text"]}
                    for fm in _cfg.field_mappings:
                        if _standard_key(fm.standard_field) == "date":
                            continue
                        candidates = [
                            it for it in items
                            if fm.y_min <= it["y_top"] <= fm.y_max
                            and abs(it["x"] - date_item["x"]) <= 50
                        ]
                        raw[fm.standard_field] = candidates[0]["text"] if candidates else ""
                    transactions.append(Transaction(
                        date=_raw_value(raw, "date"),
                        type=_raw_value(raw, "type"),
                        ticker=_raw_value(raw, "ticker"),
                        name=_raw_value(raw, "name"),
                        quantity=_parse_num(_raw_value(raw, "quantity")),
                        price=_parse_num(_raw_value(raw, "price")),
                        amount=_parse_num(_raw_value(raw, "amount")),
                        fee=_parse_num(_raw_value(raw, "fee")),
                        tax=_parse_num(_raw_value(raw, "tax")),
                        balance=_parse_num(_raw_value(raw, "balance")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    ))
                    raw_rows.append(raw)

        return transactions, raw_rows

    from parsers.base import BaseParser as _BaseParser
    return type(
        f"DynamicParser_{config.broker_name}",
        (_BaseParser,),
        {
            "BROKER_NAME": config.broker_name,
            "DETECTION_KEYWORDS": list(config.detection_keywords),
            "parse": parse,
        },
    )


def get_all_parsers() -> list:
    from parsers import PARSERS
    return PARSERS + [build_class(cfg) for cfg in load()]
