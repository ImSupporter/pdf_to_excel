import os
from collections import defaultdict
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QProgressBar, QMessageBox, QHeaderView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.loader import load_pdf, PasswordError
from core.detector import detect_parser
from core.exporter import export_to_excel
from ui.password_dialog import PasswordDialog


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, file_entries, output_path):
        super().__init__()
        self.file_entries = file_entries  # list of (path, password, parser_class)
        self.output_path = output_path

    def run(self):
        broker_raw: dict[str, list[dict]] = defaultdict(list)

        for path, password, parser_class in self.file_entries:
            filename = os.path.basename(path)
            self.progress.emit(0, f"로딩 중: {filename}")
            try:
                pages = load_pdf(path, password)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

            total_pages = len(pages)

            def make_cb(fn, tp):
                def cb(page_idx, _total):
                    pct = int((page_idx + 1) / tp * 100)
                    self.progress.emit(pct, f"{fn} 페이지 {page_idx + 1}/{tp}")
                return cb

            try:
                parser = parser_class()
                _transactions, raw_rows = parser.parse(
                    pages, progress_cb=make_cb(filename, total_pages)
                )
                broker_raw[parser_class.BROKER_NAME].extend(raw_rows)
            except Exception as e:
                self.finished.emit(False, str(e))
                return

        self.progress.emit(100, "엑셀 파일 생성 중...")
        try:
            export_to_excel(dict(broker_raw), self.output_path)
        except PermissionError:
            self.finished.emit(
                False,
                f"파일이 열려 있습니다. 닫고 다시 시도하세요:\n{self.output_path}",
            )
            return
        except Exception as e:
            self.finished.emit(False, str(e))
            return

        self.progress.emit(100, "완료!")
        self.finished.emit(True, self.output_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("증권 거래내역 → 엑셀 변환기")
        self.setMinimumSize(700, 480)

        self._last_password = ""
        self._file_entries: list[tuple] = []  # (path, password, parser_class)
        self._output_path = os.path.expanduser("~/Desktop/거래내역.xlsx")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

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

        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("저장 위치:"))
        self.output_label = QLabel(self._output_path)
        self.output_label.setStyleSheet("color: gray;")
        save_row.addWidget(self.output_label, stretch=1)
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self._browse_output)
        save_row.addWidget(browse_btn)
        layout.addLayout(save_row)

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
        paths, _ = QFileDialog.getOpenFileNames(self, "PDF 파일 선택", "", "PDF Files (*.pdf)")
        for path in paths:
            self._process_file(path)

    def _process_file(self, path: str):
        from ui.parser_select_dialog import ParserSelectDialog

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

        recommended = detect_parser(pages)
        select_dlg = ParserSelectDialog(pages, recommended, parent=self)
        if select_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        parser_class = select_dlg.get_selected_parser()
        if parser_class is None:
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setItem(row, 1, QTableWidgetItem(parser_class.BROKER_NAME))
        rec_mark = "★ 추천" if recommended and recommended.BROKER_NAME == parser_class.BROKER_NAME else "✓ 선택"
        self.table.setItem(row, 2, QTableWidgetItem(rec_mark))
        self._file_entries.append((path, password, parser_class))

    def _remove_selected(self):
        rows = sorted(
            set(idx.row() for idx in self.table.selectedIndexes()), reverse=True
        )
        for row in rows:
            self.table.removeRow(row)
            self._file_entries.pop(row)

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

        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = ConvertWorker(self._file_entries, self._output_path)
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
