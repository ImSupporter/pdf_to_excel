import os
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def pdf_password() -> str:
    return os.environ.get("PDF_PASSWORD", "990901")
