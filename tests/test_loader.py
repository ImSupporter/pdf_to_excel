import fitz
import pytest
from core.loader import load_pdf, PasswordError


@pytest.fixture
def protected_pdf(tmp_path):
    doc = fitz.open()
    doc.new_page()
    path = str(tmp_path / "protected.pdf")
    doc.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="user123",
    )
    doc.close()
    return path


def test_load_pdf_with_correct_password(protected_pdf):
    pages = load_pdf(protected_pdf, "user123")
    assert len(pages) == 1


def test_load_pdf_without_password_on_unprotected(tmp_path):
    doc = fitz.open()
    doc.new_page()
    path = str(tmp_path / "open.pdf")
    doc.save(path)
    doc.close()
    pages = load_pdf(path, "")
    assert len(pages) == 1


def test_load_pdf_with_wrong_password_raises(protected_pdf):
    with pytest.raises(PasswordError):
        load_pdf(protected_pdf, "wrongpass")
