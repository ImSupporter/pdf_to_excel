from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QScrollArea, QWidget
)
from core.models import STANDARD_FIELDS

class ColumnSelectDialog(QDialog):
    def __init__(self, selected_fields: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("통합 시트 컬럼 선택")
        self.setModal(True)
        self.setFixedSize(300, 400)

        if selected_fields is None:
            selected_fields = list(STANDARD_FIELDS.keys())

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("통합 시트에 포함할 컬럼을 선택하세요:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        self.checkboxes: dict[str, QCheckBox] = {}
        for key, korean in STANDARD_FIELDS.items():
            cb = QCheckBox(korean)
            cb.setChecked(key in selected_fields)
            self.checkboxes[key] = cb
            container_layout.addWidget(cb)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_selected_fields(self) -> list[str]:
        return [key for key, cb in self.checkboxes.items() if cb.isChecked()]
