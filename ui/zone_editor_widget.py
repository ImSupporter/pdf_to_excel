import fitz
from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage

_RENDER_SCALE = 1.5   # PDF → pixmap 배율
_HIT_PX = 8           # 선 클릭 인식 반경 (픽셀)


class ZoneEditorWidget(QWidget):
    """PDF 페이지 위에 컬럼/행/영역 경계선을 그리는 위젯.

    좌표계: 내부적으로 PDF 좌표(fitz 단위)로 저장. 렌더링 시 * _RENDER_SCALE.
    """

    MODE_NONE = 0
    MODE_ADD_V = 1   # 빨간 세로선 추가 대기
    MODE_ADD_H = 2   # 파란 가로선 추가 대기

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._page_w = 0.0
        self._page_h = 0.0
        self._mode = self.MODE_NONE

        self._vlines: list[float] = []             # 빨간 세로선 x (PDF 좌표)
        self._hlines: dict[int, list[float]] = {}  # col_idx → [y] (PDF 좌표)
        self._header_start = 0.0
        self._header_end = 0.0
        self._data_start = 0.0
        self._data_end = 0.0

        # 드래그 상태: None 또는 ("v", idx) | ("h", col, idx) | ("hs",) | ("he",) | ("ds",) | ("de",)
        self._drag: tuple | None = None

        self.setMouseTracking(True)

    # ── 공개 메서드 ──────────────────────────────────────────────────

    def load_page(self, page: fitz.Page, header_start_keyword: str = "") -> None:
        """페이지를 pixmap으로 렌더링하고 초기 영역 마커를 설정한다."""
        mat = fitz.Matrix(_RENDER_SCALE, _RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat)
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride,
            QImage.Format.Format_RGB888,
        )
        self._pixmap = QPixmap.fromImage(img)
        self._page_w = page.rect.width
        self._page_h = page.rect.height
        self.setFixedSize(pix.width, pix.height)

        h = self._page_h
        self._header_start = 0.0
        self._header_end = h * 0.25
        self._data_start = h * 0.28
        self._data_end = h * 0.95

        if header_start_keyword:
            for w in page.get_text("words"):
                if header_start_keyword in w[4]:
                    self._header_start = max(0.0, w[1] - 3.0)
                    self._header_end = min(h, w[1] + h * 0.20)
                    self._data_start = min(h, self._header_end + 5.0)
                    break

        self._vlines.clear()
        self._hlines.clear()
        self._drag = None
        self.update()

    def set_mode(self, mode: int) -> None:
        self._mode = mode

    def reset(self) -> None:
        h = self._page_h
        self._vlines.clear()
        self._hlines.clear()
        self._header_start = 0.0
        self._header_end = h * 0.25
        self._data_start = h * 0.28
        self._data_end = h * 0.95
        self.update()

    def get_zone_data(self) -> dict:
        """현재 선 상태를 PDF 좌표 딕셔너리로 반환 (ZoneSpec 생성에 사용)."""
        return {
            "column_xs": sorted(self._vlines),
            "row_ys_per_col": {k: sorted(v) for k, v in self._hlines.items()},
            "header_start_y": self._header_start,
            "header_end_y": self._header_end,
            "data_start_y": self._data_start,
            "data_end_y": self._data_end,
        }

    # ── 좌표 변환 ────────────────────────────────────────────────────

    def _s(self, pdf_val: float) -> int:
        return round(pdf_val * _RENDER_SCALE)

    def _p(self, screen_val: float) -> float:
        return screen_val / _RENDER_SCALE

    def _col_at(self, pdf_x: float) -> int:
        """pdf_x가 속하는 컬럼 인덱스 반환."""
        for i, x in enumerate(sorted(self._vlines)):
            if pdf_x < x:
                return i
        return len(self._vlines)

    # ── 렌더링 ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._pixmap is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)

        w = self._pixmap.width()
        h = self._pixmap.height()

        # 헤더/데이터 영역 반투명 배경
        hs = self._s(self._header_start)
        he = self._s(self._header_end)
        ds = self._s(self._data_start)
        de = self._s(self._data_end)
        p.fillRect(0, hs, w, max(1, he - hs), QColor(251, 146, 60, 40))
        p.fillRect(0, ds, w, max(1, de - ds), QColor(22, 163, 74, 20))

        # 빨간 세로선
        p.setPen(QPen(QColor("#ef4444"), 2))
        for vx in self._vlines:
            sx = self._s(vx)
            p.drawLine(sx, 0, sx, h)

        # 파란 가로선 (컬럼별)
        p.setPen(QPen(QColor("#3b82f6"), 2))
        sorted_v = sorted(self._vlines)
        bx = [0] + [self._s(x) for x in sorted_v] + [w]
        for col_idx, ys in self._hlines.items():
            if col_idx >= len(bx) - 1:
                continue
            for vy in ys:
                sy = self._s(vy)
                p.drawLine(bx[col_idx], sy, bx[col_idx + 1], sy)

        # 주황 영역 마커 (헤더 시작/끝)
        pen_orange = QPen(QColor("#f97316"), 2)
        for yval, label, above in [
            (self._header_start, "헤더 시작 ↕", False),
            (self._header_end,   "헤더 끝 ↕",   True),
        ]:
            sy = self._s(yval)
            p.setPen(pen_orange)
            p.drawLine(0, sy, w, sy)
            lx, ly = 2, (sy - 16 if above else sy + 2)
            p.fillRect(lx, ly, 68, 14, QColor("#f97316"))
            p.setPen(Qt.GlobalColor.white)
            p.drawText(lx, ly, 68, 14, Qt.AlignmentFlag.AlignCenter, label)

        # 초록 영역 마커 (데이터 시작/끝)
        pen_green = QPen(QColor("#16a34a"), 2)
        for yval, label, above in [
            (self._data_start, "↕ 데이터 시작", True),
            (self._data_end,   "↕ 데이터 끝",   True),
        ]:
            sy = self._s(yval)
            p.setPen(pen_green)
            p.drawLine(0, sy, w, sy)
            lx, ly = w - 80, sy - 16
            p.fillRect(lx, ly, 78, 14, QColor("#16a34a"))
            p.setPen(Qt.GlobalColor.white)
            p.drawText(lx, ly, 78, 14, Qt.AlignmentFlag.AlignCenter, label)

        p.end()

    # ── 마우스 이벤트 ────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._pixmap is None:
            return
        sx = event.position().x()
        sy = event.position().y()
        px, py = self._p(sx), self._p(sy)

        if event.button() == Qt.MouseButton.RightButton:
            return  # contextMenuEvent 에서 처리

        if self._mode == self.MODE_ADD_V:
            self._vlines.append(max(0.0, min(self._page_w, px)))
            # 모드 유지 — 버튼 토글로 해제 (연속 추가 가능)
            self.update()
            return

        if self._mode == self.MODE_ADD_H:
            col = self._col_at(px)
            self._hlines.setdefault(col, []).append(
                max(0.0, min(self._page_h, py))
            )
            # 모드 유지 — 버튼 토글로 해제
            self.update()
            return

        self._drag = self._find_target(sx, sy)

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        sx = event.position().x()
        sy = event.position().y()
        px, py = self._p(sx), self._p(sy)
        tag = self._drag[0]

        if tag == "v":
            self._vlines[self._drag[1]] = max(0.0, min(self._page_w, px))
        elif tag == "hs":
            self._header_start = max(0.0, min(self._header_end - 1, py))
        elif tag == "he":
            self._header_end = max(self._header_start + 1,
                                   min(self._data_start - 1, py))
        elif tag == "ds":
            self._data_start = max(self._header_end + 1,
                                   min(self._data_end - 1, py))
        elif tag == "de":
            self._data_end = max(self._data_start + 1, min(self._page_h, py))
        elif tag == "h":
            _, col, idx = self._drag
            self._hlines[col][idx] = max(0.0, min(self._page_h, py))

        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None

    def contextMenuEvent(self, event):
        sx = event.pos().x()
        sy = event.pos().y()
        target = self._find_target(float(sx), float(sy))
        if target is None:
            return
        tag = target[0]
        menu = QMenu(self)
        if tag == "v":
            idx = target[1]
            menu.addAction("삭제", lambda: self._delete_vline(idx))
        elif tag == "h":
            _, col, idx = target
            menu.addAction("삭제", lambda: self._delete_hline(col, idx))
        # 영역 마커(hs/he/ds/de)는 삭제 불가
        if menu.actions():
            menu.exec(event.globalPosition().toPoint())

    # ── 내부 헬퍼 ────────────────────────────────────────────────────

    def _find_target(self, sx: float, sy: float) -> tuple | None:
        """마우스 위치(스크린 좌표)에서 가장 가까운 드래그 대상을 반환."""
        hit = _HIT_PX

        # 영역 마커 우선
        for tag, yval in [
            ("hs", self._header_start),
            ("he", self._header_end),
            ("ds", self._data_start),
            ("de", self._data_end),
        ]:
            if abs(sy - self._s(yval)) <= hit:
                return (tag,)

        # 빨간 세로선
        for i, vx in enumerate(self._vlines):
            if abs(sx - self._s(vx)) <= hit:
                return ("v", i)

        # 파란 가로선
        for col_idx, ys in self._hlines.items():
            for j, vy in enumerate(ys):
                if abs(sy - self._s(vy)) <= hit:
                    return ("h", col_idx, j)

        return None

    def _delete_vline(self, idx: int) -> None:
        """세로선 삭제. 가로선의 컬럼 인덱스를 재매핑한다."""
        # _find_target은 _vlines의 원본 인덱스를 반환하므로 그대로 사용
        sorted_v = sorted(self._vlines)
        del_x = self._vlines[idx]
        sorted_idx = sorted_v.index(del_x)

        new_hlines: dict[int, list[float]] = {}
        for old_col, ys in self._hlines.items():
            if old_col < sorted_idx:
                new_col = old_col
            elif old_col in (sorted_idx, sorted_idx + 1):
                new_col = sorted_idx
            else:
                new_col = old_col - 1
            new_hlines.setdefault(new_col, []).extend(ys)

        del self._vlines[idx]
        self._hlines = new_hlines
        self.update()

    def _delete_hline(self, col_idx: int, line_idx: int) -> None:
        del self._hlines[col_idx][line_idx]
        if not self._hlines[col_idx]:
            del self._hlines[col_idx]
        self.update()
