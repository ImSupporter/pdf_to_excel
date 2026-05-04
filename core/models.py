from dataclasses import dataclass, field

STANDARD_FIELDS = {
    "date": "거래일자",
    "type": "거래종류",
    "ticker": "종목코드",
    "name": "종목명",
    "quantity": "수량",
    "price": "단가",
    "amount": "거래금액",
    "fee": "수수료",
    "tax": "세금",
    "balance": "잔액",
    "broker": "증권사",
}

@dataclass
class Transaction:
    date: str
    type: str
    ticker: str
    name: str
    quantity: float
    price: float
    amount: float
    fee: float
    tax: float
    balance: float
    broker: str
    raw: dict = field(default_factory=dict)
