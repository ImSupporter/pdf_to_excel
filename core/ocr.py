import fitz
import numpy as np

_reader = None


def _backend_available(backend) -> bool:
    if backend is None:
        return False
    try:
        return bool(backend.is_available())
    except Exception:
        return False


def _gpu_available() -> bool:
    try:
        import torch
    except ImportError:
        return False

    if _backend_available(getattr(torch, "cuda", None)):
        return True

    backends = getattr(torch, "backends", None)
    return _backend_available(getattr(backends, "mps", None))


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr

        _reader = easyocr.Reader(['ko', 'en'], gpu=_gpu_available())
    return _reader


def is_scanned_page(page: fitz.Page, text_threshold: int = 20) -> bool:
    """페이지에 추출 가능한 텍스트가 거의 없으면 스캔 이미지로 판단."""
    return len(page.get_text().strip()) < text_threshold


def ocr_page_to_words(
    page: fitz.Page,
    dpi: int = 200,
    min_confidence: float = 0.3,
) -> list[tuple[float, float, float, float, str]]:
    """
    스캔 페이지를 이미지로 렌더링 후 OCR 결과를 PDF 좌표계 단어 박스로 반환.
    Returns: [(x0, y0, x1, y1, text), ...]
    """
    reader = _get_reader()
    scale = dpi / 72

    # 페이지를 그레이스케일 이미지로 렌더링
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

    results = reader.readtext(img, detail=1)
    # results: [([[x1,y1],...,[x4,y4]], text, confidence), ...]

    words = []
    for bbox, text, conf in results:
        if conf < min_confidence or not text.strip():
            continue
        x0 = min(p[0] for p in bbox) / scale
        y0 = min(p[1] for p in bbox) / scale
        x1 = max(p[0] for p in bbox) / scale
        y1 = max(p[1] for p in bbox) / scale
        words.append((x0, y0, x1, y1, text.strip()))

    return sorted(words, key=lambda w: (w[1], w[0]))


def ocr_page_to_rows(page: fitz.Page, dpi: int = 200) -> list[list[tuple]]:
    """
    스캔 페이지를 이미지로 렌더링 후 OCR, get_page_rows()와 동일한 형식으로 반환.
    Returns: [[(x0, text), ...], ...]  — y 오름차순, 각 행 내 x 오름차순
    """
    words = ocr_page_to_words(page, dpi=dpi)

    if not words:
        return []

    # y 좌표 기준으로 행 그룹핑 (get_page_rows와 동일 로직)
    words.sort(key=lambda w: w[1])
    y_tolerance = 4.0

    rows: list[list[tuple]] = []
    current_row: list[tuple] = []
    current_y = words[0][1]

    for x0, y0, _x1, _y1, text in words:
        if abs(y0 - current_y) <= y_tolerance:
            current_row.append((x0, text))
        else:
            if current_row:
                rows.append(sorted(current_row, key=lambda c: c[0]))
            current_row = [(x0, text)]
            current_y = y0

    if current_row:
        rows.append(sorted(current_row, key=lambda c: c[0]))

    return rows
