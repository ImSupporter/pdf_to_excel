import fitz

class PasswordError(Exception):
    pass

def load_pdf(path: str, password: str) -> list[fitz.Page]:
    """
    Open a PDF file and return its pages.
    Raises PasswordError if password is wrong or missing for a protected file.
    """
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password:
            raise PasswordError(f"비밀번호가 필요한 파일입니다: {path}")
        result = doc.authenticate(password)
        if result == 0:
            raise PasswordError(f"비밀번호가 올바르지 않습니다: {path}")
    return list(doc)
