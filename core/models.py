from dataclasses import dataclass, field

STANDARD_FIELDS = {
    "date": "거래일자",
    "type": "거래종류",
    "amount": "거래금액",
    "balance": "잔액",
}


@dataclass
class Transaction:
    date: str
    type: str
    amount: float
    balance: float
    broker: str
    raw: dict = field(default_factory=dict)
