import os
from collections import defaultdict
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.loader import load_pdf, PasswordError
from core.detector import detect_parser
from core.exporter import export_to_excel
from core.models import STANDARD_FIELDS
from ui.password_dialog import PasswordDialog
from ui.column_select import ColumnSelectDialog
from ui.mapping_dialog import MappingDialog


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_entries, selected_fields, output_path):
        super().__init__()
        self.file_entries = file_entries  # list of (path, password, parser_class, mapping)
        self.selected_fields = selected_fields
        self.output_path = output_path

    def run(self):
        all_transactions = []
        broker_raw: dict[str, list[dict]] = defaultdict(list)
        total = len(self.file_entries)

        for i, (path, password, parser_class, mapping) in enumerate(self.file_entries):
            try:
                self.progress.emit(int((i / total) * 80), f"파싱 중: {os.path.basename(path)}")
                pages = load_pdf(path, password)
                parser = parser_class()
                transactions, raw_rows = parser.parse(pages)
                all_transactions.extend(transactions)
                broker_name = parser_class.BROKER_NAME
                broker_raw[broker_name].extend(raw_rows)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

        self.progress.emit(90, "엑셀 파일 생성 중...")
        try:
            export_to_excel(all_transactions, dict(broker_raw), self.selected_fields, self.output_path)
        except PermissionError:
            self.finished.emit(False, f"파일이 열려 있습니다. 닫고 다시 시도하세요:\n{self.output_path}")
            return

        self.progress.emit(100, "완료!")
        self.finished.emit(True, self.output_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("증권 거래내역 → 엑셀 변환기")
        self.setMinimumSize(700, 480)

        self._last_password = ""
        self._file_entries: list[tuple] = []  # (path, password, parser_class, mapping)
        self._selected_fields: list[str] = list(STANDARD_FIELDS.keys())
        self._output_path = os.path.expanduser("~/Desktop/거래내역.xlsx")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # File list buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("PDF 파일 추가")
        add_btn.clicked.connect(self._add_files)
        del_btn = QPushButton("선택 삭제")
        del_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["파일명", "증권사", "상태"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Column selection
        col_btn = QPushButton("컬럼 선택 (통합 시트)")
        col_btn.clicked.connect(self._select_columns)
        layout.addWidget(col_btn)

        # Output path
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("저장 위치:"))
        self.output_label = QLabel(self._output_path)
        self.output_label.setStyleSheet("color: gray;")
        save_row.addWidget(self.output_label, stretch=1)
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self._browse_output)
        save_row.addWidget(browse_btn)
        layout.addLayout(save_row)

        # Convert button and progress
        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.setFixedHeight(40)
        self.convert_btn.clicked.connect(self._start_convert)
        layout.addWidget(self.convert_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 파일 선택", "", "PDF Files (*.pdf)"
        )
        for path in paths:
            self._process_file(path)

    def _process_file(self, path: str):
        filename = os.path.basename(path)
        dlg = PasswordDialog(filename, self._last_password, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        password = dlg.get_password()
        if password:
            self._last_password = password

        try:
            pages = load_pdf(path, password)
        except PasswordError as e:
            QMessageBox.critical(self, "비밀번호 오류", str(e))
            return

        parser_class = detect_parser(pages)
        mapping = {}

        if parser_class is None:
            # Unknown broker — show mapping UI
            sample_lines = [ln.strip() for ln in pages[0].get_text().split("\n") if ln.strip()][:30]
            map_dlg = MappingDialog(sample_lines, parent=self)
            if map_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            mapping = map_dlg.get_mapping()
            broker_name = map_dlg.get_broker_name()

            from parsers.base import BaseParser
            from core.models import Transaction

            class DynamicParser(BaseParser):
                BROKER_NAME = broker_name
                DETECTION_KEYWORDS: list[str] = []

                def parse(self_, pages_):
                    return [], []

            parser_class = DynamicParser

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setItem(row, 1, QTableWidgetItem(parser_class.BROKER_NAME))
        status = "✓ 인식됨" if not mapping else "⚠ 수동 매핑"
        self.table.setItem(row, 2, QTableWidgetItem(status))
        self._file_entries.append((path, password, parser_class, mapping))

    def _remove_selected(self):
        rows = sorted(
            set(idx.row() for idx in self.table.selectedIndexes()), reverse=True
        )
        for row in rows:
            self.table.removeRow(row)
            self._file_entries.pop(row)

    def _select_columns(self):
        dlg = ColumnSelectDialog(self._selected_fields, self)
        if dlg.exec() == ColumnSelectDialog.DialogCode.Accepted:
            self._selected_fields = dlg.get_selected_fields()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택", self._output_path, "Excel Files (*.xlsx)"
        )
        if path:
            self._output_path = path
            self.output_label.setText(path)

    def _start_convert(self):
        if not self._file_entries:
            QMessageBox.warning(self, "경고", "PDF 파일을 먼저 추가하세요.")
            return
        if not self._selected_fields:
            QMessageBox.warning(self, "경고", "통합 시트에 포함할 컬럼을 선택하세요.")
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = ConvertWorker(self._file_entries, self._selected_fields, self._output_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        self.convert_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "완료", f"변환이 완료되었습니다:\n{message}")
            self.status_label.setText("완료!")
        else:
            QMessageBox.critical(self, "오류", message)
            self.status_label.setText("오류 발생")
