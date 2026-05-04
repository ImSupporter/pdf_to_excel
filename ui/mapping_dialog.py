from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QScrollArea, QWidget, QLineEdit
)
from core.models import STANDARD_FIELDS

class MappingDialog(QDialog):
    """
    Dialog for mapping unknown broker columns to standard fields.
    detected_columns: list of column names extracted from PDF
    """
    def __init__(self, detected_columns: list[str], broker_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"컬럼 매핑 — {broker_name or '미인식 증권사'}")
        self.setModal(True)
        self.setMinimumSize(480, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("증권사를 자동 인식하지 못했습니다."))
        layout.addWidget(QLabel("증권사 이름을 입력하고 컬럼을 매핑해 주세요:"))

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("증권사명:"))
        self.broker_name_input = QLineEdit(broker_name)
        name_layout.addWidget(self.broker_name_input)
        layout.addLayout(name_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)

        self.combos: dict[str, QComboBox] = {}
        for col in detected_columns:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(col), stretch=2)
            combo = QComboBox()
            combo.addItem("(매핑 안 함)")
            for key, korean in STANDARD_FIELDS.items():
                combo.addItem(f"{korean} ({key})", userData=key)
            self.combos[col] = combo
            row_layout.addWidget(combo, stretch=3)
            container_layout.addLayout(row_layout)

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

    def get_broker_name(self) -> str:
        return self.broker_name_input.text().strip() or "미인식증권사"

    def get_mapping(self) -> dict[str, str]:
        """Returns {original_column: standard_field_key} — excludes unmapped"""
        result = {}
        for col, combo in self.combos.items():
            key = combo.currentData()
            if key:
                result[col] = key
        return result
