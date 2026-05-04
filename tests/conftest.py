import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent  # save_hj/ folder

@pytest.fixture
def samsung_pdf():
    return FIXTURES_DIR / "거래내역확인서_14515.pdf"

@pytest.fixture
def mirae_pdf():
    return FIXTURES_DIR / "거래내역증명서_20260504_202671300006385.pdf"

@pytest.fixture
def pdf_password():
    return "990901"
