from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt
import fitz


class ParserSelectDialog(QDialog):
    """PDF 로드 후 항상 표시되는 파서 선택 다이얼로그.

    pages: 로드된 PDF 페이지 목록
    recommended: detect_parser()가 반환한 파서 클래스 (None 가능)
    """

    def __init__(self, pages: list[fitz.Page], recommended, parent=None):
        super().__init__(parent)
        self.setWindowTitle("파서 선택")
        self.setMinimumSize(520, 360)
        self._pages = pages
        self._recommended = recommended
        self._selected = recommended
        self._parser_map: dict[str, type] = {}

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "증권사", "유형", ""])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("파서 추가")
        add_btn.clicked.connect(self._open_builder)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("선택 확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._populate()

    def _populate(self):
        from core.parser_registry import get_all_parsers

        self._table.setRowCount(0)
        self._parser_map.clear()
        rec_name = self._recommended.BROKER_NAME if self._recommended else None

        for parser_cls in get_all_parsers():
            name = parser_cls.BROKER_NAME
            self._parser_map[name] = parser_cls
            row = self._table.rowCount()
            self._table.insertRow(row)

            star_item = QTableWidgetItem("★" if name == rec_name else "")
            star_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, star_item)
            self._table.setItem(row, 1, QTableWidgetItem(name))
            self._table.setItem(row, 2, QTableWidgetItem("동적"))

            del_btn = QPushButton("삭제")
            del_btn.clicked.connect(lambda _checked, b=name: self._delete(b))
            self._table.setCellWidget(row, 3, del_btn)

            if name == rec_name:
                self._table.selectRow(row)

        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(2, 60)
        self._table.setColumnWidth(3, 60)

    def _delete(self, broker_name: str):
        from core import parser_registry

        reply = QMessageBox.question(
            self, "파서 삭제",
            f"'{broker_name}' 파서를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        configs = parser_registry.load()
        parser_registry.save([c for c in configs if c.broker_name != broker_name])
        if self._selected and self._selected.BROKER_NAME == broker_name:
            self._selected = None
        self._populate()

    def _open_builder(self):
        from ui.parser_builder_dialog import ParserBuilderDialog

        dlg = ParserBuilderDialog(self._pages, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate()

    def _confirm(self):
        indexes = self._table.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "경고", "파서를 선택하세요.")
            return
        row = indexes[0].row()
        broker = self._table.item(row, 1).text()
        self._selected = self._parser_map.get(broker)
        self.accept()

    def get_selected_parser(self):
        return self._selected
