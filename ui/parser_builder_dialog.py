import fitz
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QSpinBox, QFormLayout, QScrollArea, QWidget,
    QMessageBox, QFileDialog, QTextEdit,
)


class ParserBuilderDialog(QDialog):
    def __init__(self, pages: list[fitz.Page], parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 추가")
        self.setMinimumSize(640, 520)
        self._pages = pages
        self._template_path: str | None = None
        self._annotations = None

        main = QVBoxLayout(self)
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

        self._data_start_edit = QLineEdit()
        self._data_start_edit.setPlaceholderText("예: 거래일자")
        form.addRow("데이터 시작 키워드 *:", self._data_start_edit)

        self._date_fmt_edit = QLineEdit()
        self._date_fmt_edit.setPlaceholderText("예: yyyy/mm/dd  (빈칸이면 자동 감지)")
        form.addRow("날짜 형식:", self._date_fmt_edit)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 99)
        form.addRow("시작 페이지:", self._start_spin)

        file_row = QHBoxLayout()
        download_btn = QPushButton("포맷 파일 다운로드")
        download_btn.clicked.connect(self._download_template)
        upload_btn = QPushButton("업로드")
        upload_btn.clicked.connect(self._upload_template)
        file_row.addWidget(download_btn)
        file_row.addWidget(upload_btn)
        file_row.addStretch()
        form.addRow("포맷 파일:", file_row)

        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setMinimumHeight(180)
        self._summary.setPlainText(
            "1. 데이터 시작 키워드(예: 거래일자)를 입력하고 포맷 파일을 다운로드하세요.\n"
            "2. 엑셀에서 제목행(회색) 셀을 노란색으로 칠해 필드를 지정하세요.\n"
            "3. 무시할 키워드(합계 등)는 회색으로 칠하세요.\n"
            "4. 저장한 엑셀 파일을 업로드한 뒤 파서를 저장하세요."
        )
        form.addRow("업로드 결과:", self._summary)

        scroll.setWidget(form_widget)
        main.addWidget(scroll)

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

    def _download_template(self):
        from core.parser_template import export_parser_template, date_format_to_re

        data_start = self._data_start_edit.text().strip()
        if not data_start:
            QMessageBox.warning(self, "입력 오류", "데이터 시작 키워드를 입력하세요.")
            return

        date_fmt = self._date_fmt_edit.text().strip()
        date_re = date_format_to_re(date_fmt) if date_fmt else None

        path, _ = QFileDialog.getSaveFileName(
            self, "포맷 파일 다운로드", "parser_format.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            detected_fmt = export_parser_template(
                self._pages, path,
                data_start_keyword=data_start,
                date_re=date_re,
                max_pages=3,
            )
        except Exception as exc:
            QMessageBox.critical(self, "다운로드 실패", str(exc))
            return

        if detected_fmt and not date_fmt:
            self._date_fmt_edit.setText(detected_fmt)

        self._template_path = path
        QMessageBox.information(self, "완료", f"포맷 파일을 저장했습니다:\n{path}")

    def _upload_template(self):
        from core.parser_template import read_parser_template

        path, _ = QFileDialog.getOpenFileName(
            self, "포맷 파일 업로드", self._template_path or "", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        try:
            annotations = read_parser_template(path)
        except Exception as exc:
            QMessageBox.critical(self, "업로드 실패", str(exc))
            return

        self._template_path = path
        self._annotations = annotations

        if annotations.detected_date_format and not self._date_fmt_edit.text().strip():
            self._date_fmt_edit.setText(annotations.detected_date_format)

        lines = [f"업로드 파일: {path}", ""]
        lines.append(f"필드 매핑: {len(annotations.field_mappings)}개")
        for fm in annotations.field_mappings:
            lines.append(f"  - {fm.standard_field}  (row_offset={fm.row_offset}, x={fm.x:.1f})")
        lines.append("")
        lines.append(f"무시 키워드: {len(annotations.skip_keywords)}개")
        for kw in annotations.skip_keywords:
            lines.append(f"  - {kw}")
        self._summary.setPlainText("\n".join(lines))

    def _save(self):
        from core import parser_registry
        from core.parser_registry import DynamicParserConfig, FieldMapping
        from core.parser_template import date_format_to_re

        broker_name = self._broker_edit.text().strip()
        if not broker_name:
            QMessageBox.warning(self, "입력 오류", "증권사명을 입력하세요.")
            return

        keywords = [k.strip() for k in self._kw_edit.text().split(",") if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "입력 오류", "감지 키워드를 하나 이상 입력하세요.")
            return

        if self._annotations is None:
            QMessageBox.warning(self, "입력 오류", "노란색/회색 표시를 마친 포맷 파일을 업로드하세요.")
            return

        if not self._annotations.field_mappings:
            QMessageBox.warning(self, "입력 오류", "노란색으로 표시된 필드 셀이 없습니다.")
            return

        date_fmt = self._date_fmt_edit.text().strip()
        if not date_fmt:
            QMessageBox.warning(self, "입력 오류", "날짜 형식을 입력하세요 (예: yyyy/mm/dd).")
            return

        field_mappings = [
            FieldMapping(
                standard_field=af.standard_field,
                row_offset=af.row_offset,
                x=af.x,
            )
            for af in self._annotations.field_mappings
        ]

        config = DynamicParserConfig(
            broker_name=broker_name,
            detection_keywords=keywords,
            date_re=date_format_to_re(date_fmt),
            layout_type="header_mapped",
            start_page=self._start_spin.value(),
            skip_keywords=list(self._annotations.skip_keywords),
            field_mappings=field_mappings,
        )

        configs = parser_registry.load()
        configs.append(config)
        parser_registry.save(configs)
        self.accept()
