import sys

# PyTorch 2.9+ on Windows can fail to load c10.dll if it is imported after PyQt.
import torch  # noqa: F401

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("증권 거래내역 변환기")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
