import fitz
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QSpinBox, QFormLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QWidget, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from core.models import STANDARD_FIELDS


class ParserBuilderDialog(QDialog):
    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 추가")
        self.setMinimumSize(960, 640)
        self._pages = pages
        self._current_page = 0

        main = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── 왼쪽: PDF 미리보기 ─────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self._preview = QTableWidget()
        self._preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self._preview)

        nav = QHBoxLayout()
        self._prev_btn = QPushButton("← 이전")
        self._prev_btn.clicked.connect(self._prev_page)
        self._page_lbl = QLabel()
        self._next_btn = QPushButton("다음 →")
        self._next_btn.clicked.connect(self._next_page)
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._page_lbl, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._next_btn)
        left_layout.addLayout(nav)
        splitter.addWidget(left)

        # ── 오른쪽: 설정 폼 ────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._broker_edit = QLineEdit()
        form.addRow("증권사명 *:", self._broker_edit)

        self._kw_edit = QLineEdit()
        self._kw_edit.setPlaceholderText("쉼표 구분 (예: 키움증권, 거래내역확인)")
        form.addRow("감지 키워드 *:", self._kw_edit)

        self._date_re_edit = QLineEdit(r"^\d{4}/\d{2}/\d{2}$")
        form.addRow("날짜 정규식:", self._date_re_edit)

        self._layout_combo = QComboBox()
        self._layout_combo.addItems(["일반 테이블", "회전 레이아웃"])
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        form.addRow("레이아웃:", self._layout_combo)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 99)
        self._start_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("시작 페이지:", self._start_spin)

        self._skip_edit = QLineEdit()
        self._skip_edit.setPlaceholderText("쉼표 구분 (예: 거래일자, 합계, 페이지)")
        form.addRow("건너뛸 키워드:", self._skip_edit)

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 5)
        self._rows_spin.valueChanged.connect(self._refresh_field_dropdowns)
        form.addRow("행/거래:", self._rows_spin)

        form.addRow(QLabel("──── 필드 매핑 ────"))

        # 필드 매핑: 레이아웃 타입에 따라 스택 전환
        self._mapping_stack = QStackedWidget()

        # Stack 0: 일반 테이블 — 콤보박스
        table_mapping_widget = QWidget()
        self._table_form = QFormLayout(table_mapping_widget)
        self._field_combos: dict[str, QComboBox] = {}
        for key, label in STANDARD_FIELDS.items():
            combo = QComboBox()
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self._field_combos[key] = combo
            self._table_form.addRow(f"{label} →", combo)
        self._mapping_stack.addWidget(table_mapping_widget)

        # Stack 1: 회전 레이아웃 — y_min/y_max 스핀박스 테이블
        rotated_widget = QWidget()
        rot_layout = QVBoxLayout(rotated_widget)
        rot_layout.addWidget(QLabel("각 필드의 Y좌표 범위를 입력하세요 (PDF 미리보기의 Y 컬럼 참고):"))
        self._rot_table = QTableWidget(len(STANDARD_FIELDS), 3)
        self._rot_table.setHorizontalHeaderLabels(["필드", "y_min", "y_max"])
        self._rot_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._rot_spin_pairs: dict[str, tuple[QSpinBox, QSpinBox]] = {}
        for row_idx, (key, label) in enumerate(STANDARD_FIELDS.items()):
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._rot_table.setItem(row_idx, 0, item)
            y_min_spin = QSpinBox()
            y_min_spin.setRange(0, 9999)
            y_max_spin = QSpinBox()
            y_max_spin.setRange(0, 9999)
            self._rot_table.setCellWidget(row_idx, 1, y_min_spin)
            self._rot_table.setCellWidget(row_idx, 2, y_max_spin)
            self._rot_spin_pairs[key] = (y_min_spin, y_max_spin)
        rot_layout.addWidget(self._rot_table)
        self._mapping_stack.addWidget(rotated_widget)

        form.addRow(self._mapping_stack)
        scroll.setWidget(form_widget)
        right_layout.addWidget(scroll)
        splitter.addWidget(right)

        splitter.setSizes([480, 480])
        main.addWidget(splitter)

        # 하단 버튼
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("저장")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        main.addLayout(btns)

        self._refresh_preview()

    def _prev_page(self):
        self._current_page = max(0, self._current_page - 1)
        self._refresh_preview()

    def _next_page(self):
        self._current_page = min(len(self._pages) - 1, self._current_page + 1)
        self._refresh_preview()

    def _on_layout_changed(self):
        idx = self._layout_combo.currentIndex()
        self._mapping_stack.setCurrentIndex(idx)
        self._refresh_preview()

    def _refresh_preview(self):
        if not self._pages:
            return

        start = self._start_spin.value()
        self._current_page = max(start, min(self._current_page, len(self._pages) - 1))
        page = self._pages[self._current_page]
        layout_type = "table" if self._layout_combo.currentIndex() == 0 else "rotated"

        self._preview.clear()
        self._preview.setRowCount(0)
        self._preview.setColumnCount(0)

        if layout_type == "table":
            from core.pdf_utils import get_page_rows
            rows = list(get_page_rows(page, y_tolerance=4.0))
            if rows:
                max_cols = max(len(r) for r in rows)
                self._preview.setRowCount(len(rows))
                self._preview.setColumnCount(max_cols)
                self._preview.setHorizontalHeaderLabels([f"Col{i}" for i in range(max_cols)])
                for r_idx, row in enumerate(rows):
                    for c_idx, cell in enumerate(row):
                        self._preview.setItem(r_idx, c_idx, QTableWidgetItem(cell[1]))
        else:
            items = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                bx = block["bbox"][0]
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        t = span["text"].strip()
                        if t:
                            items.append((round(bx), round(span["bbox"][1]), t))
            items.sort(key=lambda it: (it[0], it[1]))
            self._preview.setRowCount(len(items))
            self._preview.setColumnCount(3)
            self._preview.setHorizontalHeaderLabels(["X", "Y", "텍스트"])
            for r_idx, (x, y, text) in enumerate(items):
                self._preview.setItem(r_idx, 0, QTableWidgetItem(str(x)))
                self._preview.setItem(r_idx, 1, QTableWidgetItem(str(y)))
                self._preview.setItem(r_idx, 2, QTableWidgetItem(text))

        total = len(self._pages)
        self._page_lbl.setText(f"{self._current_page + 1} / {total}")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total - 1)

        if layout_type == "table":
            self._refresh_field_dropdowns()

    def _refresh_field_dropdowns(self):
        if self._layout_combo.currentIndex() != 0:
            return
        if not self._pages:
            return

        from core.pdf_utils import get_page_rows
        start = self._start_spin.value()
        idx = max(start, min(self._current_page, len(self._pages) - 1))
        page = self._pages[idx]
        rows_per_tx = self._rows_spin.value()

        all_rows = list(get_page_rows(page, y_tolerance=4.0))

        # 첫 3개 트랜잭션 그룹 샘플 수집
        sample_groups: list[list[list[str]]] = []
        i = 0
        while i < len(all_rows) and len(sample_groups) < 3:
            group = []
            for offset in range(rows_per_tx):
                j = i + offset
                group.append([cell[1] for cell in all_rows[j]] if j < len(all_rows) else [])
            sample_groups.append(group)
            i += rows_per_tx

        # 드롭다운 옵션 빌드: (label, col_index, row_offset)
        options: list[tuple[str, int, int]] = []
        if sample_groups:
            first_group = sample_groups[0]
            for r_off, row_texts in enumerate(first_group):
                for c_idx in range(len(row_texts)):
                    samples = []
                    for sg in sample_groups:
                        r = sg[r_off] if r_off < len(sg) else []
                        if c_idx < len(r) and r[c_idx]:
                            samples.append(r[c_idx])
                    sample_str = ", ".join(samples[:2])
                    label = f"Row{r_off}-Col{c_idx}: {sample_str}"
                    options.append((label, c_idx, r_off))

        # 기존 선택값 보존
        prev: dict[str, tuple | None] = {
            key: combo.currentData() for key, combo in self._field_combos.items()
        }

        for key, combo in self._field_combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("미사용", None)
            for label, c_idx, r_off in options:
                combo.addItem(label, (c_idx, r_off))
            p = prev.get(key)
            if p is not None:
                for i_opt in range(combo.count()):
                    if combo.itemData(i_opt) == p:
                        combo.setCurrentIndex(i_opt)
                        break
            combo.blockSignals(False)

    def _save(self):
        from core import parser_registry
        from core.parser_registry import DynamicParserConfig, FieldMapping

        broker_name = self._broker_edit.text().strip()
        if not broker_name:
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return

        keywords = [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "입력 오류", "감지 키워드를 하나 이상 입력하세요.")
            return

        layout_type = "table" if self._layout_combo.currentIndex() == 0 else "rotated"
        skip_kws = [k.strip() for k in self._skip_edit.text().split(",") if k.strip()]

        field_mappings: list[FieldMapping] = []

        if layout_type == "table":
            for standard_field, combo in self._field_combos.items():
                data = combo.currentData()
                if data is None:
                    continue
                c_idx, r_off = data
                field_mappings.append(FieldMapping(
                    standard_field=standard_field,
                    column_index=c_idx,
                    row_offset=r_off,
                    y_min=0,
                    y_max=0,
                ))
        else:
            for standard_field, (y_min_spin, y_max_spin) in self._rot_spin_pairs.items():
                y_min = y_min_spin.value()
                y_max = y_max_spin.value()
                if y_min == 0 and y_max == 0:
                    continue
                field_mappings.append(FieldMapping(
                    standard_field=standard_field,
                    column_index=0,
                    row_offset=0,
                    y_min=y_min,
                    y_max=y_max,
                ))

        config = DynamicParserConfig(
            broker_name=broker_name,
            detection_keywords=keywords,
            date_re=self._date_re_edit.text().strip(),
            layout_type=layout_type,
            start_page=self._start_spin.value(),
            rows_per_tx=self._rows_spin.value(),
            skip_keywords=skip_kws,
            field_mappings=field_mappings,
        )

        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
