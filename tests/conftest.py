import os
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent  # save_hj/ folder

@pytest.fixture
def samsung_pdf() -> Path:
    p = PROJECT_ROOT / "거래내역확인서_14515.pdf"
    if not p.exists():
        pytest.skip(f"Fixture PDF not found: {p}")
    return p

@pytest.fixture
def mirae_pdf() -> Path:
    p = PROJECT_ROOT / "거래내역증명서_20260504_202671300006385.pdf"
    if not p.exists():
        pytest.skip(f"Fixture PDF not found: {p}")
    return p

@pytest.fixture
def pdf_password() -> str:
    return os.environ.get("PDF_PASSWORD", "990901")
