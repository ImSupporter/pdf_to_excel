from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton
)

class PasswordDialog(QDialog):
    def __init__(self, filename: str, last_password: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF 비밀번호")
        self.setModal(True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"파일: {filename}"))
        layout.addWidget(QLabel("비밀번호 (없으면 빈칸):"))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setText(last_password)
        self.password_input.selectAll()
        layout.addWidget(self.password_input)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_password(self) -> str:
        return self.password_input.text()
