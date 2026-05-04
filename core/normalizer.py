from core.models import Transaction, STANDARD_FIELDS

def transactions_to_rows(
    transactions: list[Transaction],
    selected_fields: list[str],
) -> list[dict]:
    """
    Convert Transaction list to list of dicts with Korean column names.
    selected_fields: list of STANDARD_FIELDS keys (e.g. ["date", "type", "amount"])
    """
    rows = []
    for tx in transactions:
        row = {}
        for field_key in selected_fields:
            korean_name = STANDARD_FIELDS.get(field_key, field_key)
            row[korean_name] = getattr(tx, field_key, "")
        rows.append(row)
    return rows
