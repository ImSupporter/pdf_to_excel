import pytest
import fitz
from core.loader import load_pdf, PasswordError

def test_load_pdf_with_correct_password(samsung_pdf, pdf_password):
    pages = load_pdf(str(samsung_pdf), pdf_password)
    assert len(pages) == 3  # 삼성 PDF는 3페이지

def test_load_pdf_without_password_on_unprotected():
    doc = fitz.open()
    doc.new_page()
    tmp_path = "/tmp/test_nopass.pdf"
    doc.save(tmp_path)
    doc.close()
    pages = load_pdf(tmp_path, "")
    assert len(pages) == 1

def test_load_pdf_with_wrong_password_raises(samsung_pdf):
    with pytest.raises(PasswordError):
        load_pdf(str(samsung_pdf), "wrongpass")
