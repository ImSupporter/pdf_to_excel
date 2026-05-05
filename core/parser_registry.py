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
    page_index: int = 0     # template layout: source page index used as mapping hint
    row_index: int = 0      # template layout: source row index used as mapping hint
    x: float = 0.0          # template layout: source x coordinate hint
    y: float = 0.0          # template layout: source y coordinate hint
    source_text: str = ""   # template layout: original/edited template cell text


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


def build_class(config: "DynamicParserConfig") -> type:
    """config를 받아 BaseParser를 상속하는 런타임 클래스를 반환한다."""
    import re as _re
    from parsers.base import BaseParser
    from core.models import Transaction
    from core.pdf_utils import get_page_rows
    from core.parser_template import infer_standard_field

    _cfg = config
    _date_re = _re.compile(config.date_re)

    def _parse_num(s: str) -> float:
        try:
            return float(str(s).replace(",", "").replace(" ", ""))
        except (ValueError, AttributeError):
            return 0.0

    def parse(self, pages):
        transactions: list[Transaction] = []
        raw_rows: list[dict] = []

        for page_idx, page in enumerate(pages):
            if page_idx < _cfg.start_page:
                continue

            if _cfg.layout_type in {"table", "template"}:
                all_rows = list(get_page_rows(page, y_tolerance=4.0))
                i = 0
                while i < len(all_rows):
                    anchor_texts = [cell[1] for cell in all_rows[i]]
                    if not anchor_texts:
                        i += 1
                        continue
                    if any(kw in " ".join(anchor_texts) for kw in _cfg.skip_keywords):
                        i += 1
                        continue
                    if not _date_re.match(anchor_texts[0]):
                        i += 1
                        continue

                    raw: dict = {}
                    if _cfg.layout_type == "template":
                        for fm in _cfg.field_mappings:
                            row_idx = i + fm.row_offset
                            row = all_rows[row_idx] if row_idx < len(all_rows) else []
                            if row:
                                closest = min(row, key=lambda c, _x=fm.x: abs(c[0] - _x))
                                raw[fm.standard_field] = closest[1]
                            else:
                                raw[fm.standard_field] = ""
                    else:
                        groups: list[list[str]] = [anchor_texts]
                        for offset in range(1, _cfg.rows_per_tx):
                            j = i + offset
                            groups.append([cell[1] for cell in all_rows[j]] if j < len(all_rows) else [])
                        for fm in _cfg.field_mappings:
                            grp = groups[fm.row_offset] if fm.row_offset < len(groups) else []
                            raw[fm.standard_field] = grp[fm.column_index] if fm.column_index < len(grp) else ""

                    normalized = {
                        infer_standard_field(key) or key: value
                        for key, value in raw.items()
                    }
                    transactions.append(Transaction(
                        date=normalized.get("date", ""),
                        type=normalized.get("type", ""),
                        ticker=normalized.get("ticker", ""),
                        name=normalized.get("name", ""),
                        quantity=_parse_num(normalized.get("quantity", "")),
                        price=_parse_num(normalized.get("price", "")),
                        amount=_parse_num(normalized.get("amount", "")),
                        fee=_parse_num(normalized.get("fee", "")),
                        tax=_parse_num(normalized.get("tax", "")),
                        balance=_parse_num(normalized.get("balance", "")),
                        broker=_cfg.broker_name,
                        raw=raw,
                    ))
                    raw_rows.append(raw)
                    i += _cfg.rows_per_tx

            elif _cfg.layout_type == "rotated":
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

                for date_item in [it for it in items if _date_re.match(it["text"])]:
                    raw = {"date": date_item["text"]}
                    for fm in _cfg.field_mappings:
                        if fm.standard_field == "date":
                            continue
                        candidates = [
                            it for it in items
                            if fm.y_min <= it["y_top"] <= fm.y_max
                            and abs(it["x"] - date_item["x"]) <= 50
                        ]
                        raw[fm.standard_field] = candidates[0]["text"] if candidates else ""

                    transactions.append(Transaction(
                        date=raw.get("date", ""),
                        type=raw.get("type", ""),
                        ticker=raw.get("ticker", ""),
                        name=raw.get("name", ""),
                        quantity=_parse_num(raw.get("quantity", "")),
                        price=_parse_num(raw.get("price", "")),
                        amount=_parse_num(raw.get("amount", "")),
                        fee=_parse_num(raw.get("fee", "")),
                        tax=_parse_num(raw.get("tax", "")),
                        balance=_parse_num(raw.get("balance", "")),
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
