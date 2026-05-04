import fitz
import numpy as np

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['ko', 'en'], gpu=False)
    return _reader


def is_scanned_page(page: fitz.Page, text_threshold: int = 20) -> bool:
    """페이지에 추출 가능한 텍스트가 거의 없으면 스캔 이미지로 판단."""
    return len(page.get_text().strip()) < text_threshold


def ocr_page_to_rows(page: fitz.Page, dpi: int = 200) -> list[list[tuple]]:
    """
    스캔 페이지를 이미지로 렌더링 후 OCR, get_page_rows()와 동일한 형식으로 반환.
    Returns: [[(x0, text), ...], ...]  — y 오름차순, 각 행 내 x 오름차순
    """
    reader = _get_reader()
    scale = dpi / 72

    # 페이지를 그레이스케일 이미지로 렌더링
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

    results = reader.readtext(img, detail=1)
    # results: [([[x1,y1],...,[x4,y4]], text, confidence), ...]

    # PDF 좌표계로 변환 후 (x0, y0, text) 목록 생성
    words = []
    for bbox, text, conf in results:
        if conf < 0.3 or not text.strip():
            continue
        x0 = min(p[0] for p in bbox) / scale
        y0 = min(p[1] for p in bbox) / scale
        words.append((x0, y0, text.strip()))

    if not words:
        return []

    # y 좌표 기준으로 행 그룹핑 (get_page_rows와 동일 로직)
    words.sort(key=lambda w: w[1])
    y_tolerance = 4.0

    rows: list[list[tuple]] = []
    current_row: list[tuple] = []
    current_y = words[0][1]

    for x0, y0, text in words:
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
