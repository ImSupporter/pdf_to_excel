from abc import ABC, abstractmethod
import fitz
from core.models import Transaction

class BaseParser(ABC):
    BROKER_NAME: str = ""
    DETECTION_KEYWORDS: list[str] = []

    @abstractmethod
    def parse(self, pages: list[fitz.Page]) -> tuple[list[Transaction], list[dict]]:
        """
        Returns: (transactions, raw_rows)
        - transactions: normalized Transaction list
        - raw_rows: original column dicts for per-broker sheet
        """
        ...
