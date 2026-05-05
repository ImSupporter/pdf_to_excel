import fitz
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QPushButton,
    QLineEdit, QSpinBox, QFormLayout, QLabel,
    QScrollArea, QWidget, QMessageBox, QSplitter, QComboBox,
)
from PyQt6.QtCore import Qt


class ParserBuilderDialog(QDialog):
    """3-패널 단일 창 파서 생성 다이얼로그.

    pages: 이미 로드된 fitz.Page 리스트 (메인 창에서 전달).
    """

    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 생성")
        self.setMinimumSize(1000, 600)
        self._pages = pages
        self._fields: list = []   # build_cell_mappings() 결과 (list[CellMapping])
        self._zone_spec = None    # ZoneSpec — set in _on_generate_cells

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        splitter.addWidget(self._build_form_panel())
        splitter.addWidget(self._build_zone_panel())
        splitter.addWidget(self._build_field_panel())
        splitter.setSizes([230, 600, 210])

        # 초기 비활성화
        self._zone_panel.setEnabled(False)
        self._field_panel.setEnabled(False)
        self._confirm_btn.setEnabled(False)

    # ── 패널 빌더 ─────────────────────────────────────────────────────

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(260)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(10, 10, 10, 10)

        title = QLabel("① 파서 정보")
        title.setStyleSheet("font-weight:bold;font-size:11px;color:#555;")
        vbox.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._broker_edit = QLineEdit()
        form.addRow("증권사명 *:", self._broker_edit)

        self._kw_edit = QLineEdit()
        self._kw_edit.setPlaceholderText("쉼표 구분 (예: 키움증권, 거래내역)")
        form.addRow("감지 키워드 *:", self._kw_edit)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(1, 100)
        self._start_spin.setValue(1)
        form.addRow("시작 페이지:", self._start_spin)

        vbox.addLayout(form)
        vbox.addStretch()

        self._open_zone_btn = QPushButton("영역 지정 →")
        self._open_zone_btn.setStyleSheet(
            "background:#8b5cf6;color:white;padding:8px;font-weight:bold;"
        )
        self._open_zone_btn.clicked.connect(self._on_open_zone_editor)
        vbox.addWidget(self._open_zone_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        vbox.addWidget(cancel_btn)

        return panel

    def _build_zone_panel(self) -> QWidget:
        from ui.zone_editor_widget import ZoneEditorWidget

        self._zone_panel = QWidget()
        vbox = QVBoxLayout(self._zone_panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 툴바
        toolbar = QWidget()
        toolbar.setStyleSheet("background:#f0f0f0;border-bottom:1px solid #ccc;")
        tbar = QHBoxLayout(toolbar)
        tbar.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel("② 존 에디터")
        lbl.setStyleSheet("font-weight:bold;color:#555;font-size:11px;")
        tbar.addWidget(lbl)

        self._add_v_btn = QPushButton("＋세로선")
        self._add_v_btn.setStyleSheet(
            "background:#ef4444;color:white;padding:2px 8px;border-radius:3px;"
        )
        self._add_v_btn.setCheckable(True)
        self._add_v_btn.clicked.connect(self._on_toggle_add_v)
        tbar.addWidget(self._add_v_btn)

        self._add_h_btn = QPushButton("＋가로선")
        self._add_h_btn.setStyleSheet(
            "background:#3b82f6;color:white;padding:2px 8px;border-radius:3px;"
        )
        self._add_h_btn.setCheckable(True)
        self._add_h_btn.clicked.connect(self._on_toggle_add_h)
        tbar.addWidget(self._add_h_btn)
        tbar.addStretch()
        vbox.addWidget(toolbar)

        # PDF 캔버스 (스크롤 가능)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        self._zone_editor = ZoneEditorWidget()
        scroll.setWidget(self._zone_editor)
        vbox.addWidget(scroll, 1)

        # 하단 버튼 바
        bottom = QWidget()
        bottom.setStyleSheet("background:#f0f0f0;border-top:1px solid #ccc;")
        bbar = QHBoxLayout(bottom)
        bbar.setContentsMargins(8, 6, 8, 6)

        reset_btn = QPushButton("초기화")
        reset_btn.clicked.connect(self._zone_editor.reset)
        bbar.addWidget(reset_btn)
        bbar.addStretch()

        extract_btn = QPushButton("셀 목록 생성 →")
        extract_btn.setStyleSheet(
            "background:#2563eb;color:white;padding:4px 14px;font-weight:bold;"
        )
        extract_btn.clicked.connect(self._on_generate_cells)
        bbar.addWidget(extract_btn)
        vbox.addWidget(bottom)

        return self._zone_panel

    def _build_field_panel(self) -> QWidget:
        self._field_panel = QWidget()
        self._field_panel.setMaximumWidth(240)
        vbox = QVBoxLayout(self._field_panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        title = QLabel("③ 셀 매핑")
        title.setStyleSheet(
            "font-weight:bold;font-size:11px;color:#555;"
            "padding:6px 10px;background:#f0f0f0;border-bottom:1px solid #ccc;"
        )
        vbox.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._field_list_widget = QWidget()
        self._field_list_layout = QVBoxLayout(self._field_list_widget)
        self._field_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._field_list_layout.setSpacing(4)
        self._field_list_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(self._field_list_widget)
        vbox.addWidget(scroll, 1)

        bottom = QWidget()
        bottom.setStyleSheet("border-top:1px solid #ddd;")
        bbar = QVBoxLayout(bottom)
        bbar.setContentsMargins(7, 7, 7, 7)
        self._confirm_btn = QPushButton("✓ 확인 (파서 생성)")
        self._confirm_btn.setStyleSheet(
            "background:#16a34a;color:white;padding:7px;font-weight:bold;"
        )
        self._confirm_btn.clicked.connect(self._on_confirm)
        bbar.addWidget(self._confirm_btn)
        vbox.addWidget(bottom)

        return self._field_panel

    # ── 이벤트 핸들러 ────────────────────────────────────────────────

    def _on_toggle_add_v(self, checked: bool) -> None:
        from ui.zone_editor_widget import ZoneEditorWidget
        if checked:
            self._add_h_btn.setChecked(False)
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_ADD_V)
        else:
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_NONE)

    def _on_toggle_add_h(self, checked: bool) -> None:
        from ui.zone_editor_widget import ZoneEditorWidget
        if checked:
            self._add_v_btn.setChecked(False)
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_ADD_H)
        else:
            self._zone_editor.set_mode(ZoneEditorWidget.MODE_NONE)

    def _on_open_zone_editor(self) -> None:
        if not self._broker_edit.text().strip():
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return
        if not [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]:
            QMessageBox.warning(self, "입력 오류", "감지 키워드를 입력하세요.")
            return

        start = self._start_spin.value() - 1
        if start >= len(self._pages):
            QMessageBox.warning(self, "입력 오류", f"시작 페이지({self._start_spin.value()})가 범위를 벗어납니다.")
            return

        self._zone_editor.load_page(self._pages[start])
        self._zone_panel.setEnabled(True)

    def _on_generate_cells(self) -> None:
        from core.zone_spec import ZoneSpec, build_cell_mappings

        kw_text = self._kw_edit.text().strip()
        keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
        zone_data = self._zone_editor.get_zone_data()

        self._zone_spec = ZoneSpec(
            broker_name=self._broker_edit.text().strip(),
            detection_keywords=keywords,
            start_page=self._start_spin.value() - 1,
            column_xs=zone_data["column_xs"],
            template_row_ys_per_col=zone_data["template_row_ys_per_col"],
            data_start_y=zone_data["data_start_y"],
            data_end_y=zone_data["data_end_y"],
            template_height=zone_data["template_height"],
        )

        self._fields = build_cell_mappings(
            self._zone_spec,
            page_width=self._zone_editor._page_w,
        )
        self._populate_field_list()
        self._field_panel.setEnabled(True)
        self._confirm_btn.setEnabled(True)

    def _populate_field_list(self) -> None:
        while self._field_list_layout.count():
            item = self._field_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for fm in self._fields:
            card = QWidget()
            card.setStyleSheet(
                "background:#eff6ff;border:1px solid #bfdbfe;"
                "border-radius:3px;padding:2px;color:#000;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(2)

            name_edit = QLineEdit()
            name_edit.setPlaceholderText("엑셀 필드명")
            name_edit.textChanged.connect(
                lambda text, m=fm: setattr(m, "display_name", text.strip())
            )

            standard_combo = QComboBox()
            standard_combo.addItem("표준 연결 없음", None)
            standard_combo.addItem("거래일자", "date")
            standard_combo.addItem("거래종류", "type")
            standard_combo.addItem("거래금액", "amount")
            standard_combo.addItem("잔액", "balance")
            standard_combo.currentIndexChanged.connect(
                lambda _idx, combo=standard_combo, m=fm: setattr(
                    m, "standard_field", combo.currentData()
                )
            )

            lbl_meta = QLabel(
                f"column={fm.column_index}  "
                f"x=[{fm.x_min:.0f},{fm.x_max:.0f}]  "
                f"y=[{fm.template_y_min:.0f},{fm.template_y_max:.0f}]"
            )
            lbl_meta.setStyleSheet("font-size:9px;color:#555;")

            cl.addWidget(name_edit)
            cl.addWidget(standard_combo)
            cl.addWidget(lbl_meta)
            self._field_list_layout.addWidget(card)

    def _on_confirm(self) -> None:
        from core import parser_registry
        from core.zone_spec import ZoneSpec, zone_spec_to_config

        if not self._fields:
            QMessageBox.warning(self, "오류", "먼저 셀 목록을 생성하세요.")
            return

        mappings = [fm for fm in self._fields if fm.display_name.strip()]
        if not mappings:
            QMessageBox.warning(self, "오류", "저장할 셀 매핑이 없습니다.")
            return

        kw_text = self._kw_edit.text().strip()
        keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
        zone_data = self._zone_editor.get_zone_data()
        zone_spec = ZoneSpec(
            broker_name=self._broker_edit.text().strip(),
            detection_keywords=keywords,
            start_page=self._start_spin.value() - 1,
            column_xs=zone_data["column_xs"],
            template_row_ys_per_col=zone_data["template_row_ys_per_col"],
            data_start_y=zone_data["data_start_y"],
            data_end_y=zone_data["data_end_y"],
            template_height=zone_data["template_height"],
        )

        try:
            config = zone_spec_to_config(zone_spec, mappings)
        except ValueError as exc:
            QMessageBox.warning(self, "입력 오류", str(exc))
            return

        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
