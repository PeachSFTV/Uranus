# MainWindow.py
import faulthandler
faulthandler.enable()
import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from ui_helper import load_ui_safe, UIHelper
from PyQt6.QtGui import QIcon
from PyQt6 import uic
from UploadFile_Page import UploadFilePage
from pathlib import Path
from Publisher_Page import VirtualIEDSystem
from Sniffer_Page import GOOSESnifferWindow
from Login_Page import LoginPage
from EasyEditer_Page import EasyEditorWidget
from resource_helper import get_ui_path, get_icon_path
# Fix for PyInstaller sys.stderr issue
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')

# เพิ่ม exception handler
import traceback
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    print("Uncaught exception:", exc_type, exc_value)
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('URANUS')
        def resource_path(relative_path):
            """ Get absolute path to resource, works for dev and for PyInstaller """
            try:
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)

        # ใช้แบบนี้
        self.setWindowIcon(QIcon(get_icon_path('UranusIcon.ico')))
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.load_login_ui()

    def clear_layout(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def load_login_ui(self):
        self.clear_layout()
        self.login_page = LoginPage(self.load_main_ui)
        self.main_layout.addWidget(self.login_page)
        self.resize(self.login_page.size())
        
    def load_main_ui(self):
        ui_file = get_ui_path('MainWindowUi.ui')
        widget = uic.loadUi(ui_file)
        self.main_ui = widget

       # ฝังลงใน layout ของ self
        self.main_layout.addWidget(widget)
        self.resize(widget.size())

        self.upload_file_button = self.findChild(QPushButton, 'upload_file_button')
        self.real_goose_pub_button = self.findChild(QPushButton, 'real_goose_pub_button')
        self.real_goose_sub_button = self.findChild(QPushButton, 'real_goose_sub_button')
        self.easyediter_button = self.findChild(QPushButton, 'easyediter_button')
        self.upload_file_button.clicked.connect(self.load_uploadfile_ui)
        self.real_goose_pub_button.clicked.connect(self.goose_pub_ui)
        self.real_goose_sub_button.clicked.connect(self.goose_sub_ui)
        self.easyediter_button.clicked.connect(self.load_easyediter_ui)

    def goose_pub_ui(self):
        self.clear_layout()
        self.login_page = VirtualIEDSystem(self.load_main_ui)
        self.main_layout.addWidget(self.login_page)
        self.resize(self.login_page.size())

    def goose_sub_ui(self):
        self.clear_layout()
        self.login_page = GOOSESnifferWindow(self.load_main_ui)
        self.main_layout.addWidget(self.login_page)
        self.resize(self.login_page.size())
        
    def load_uploadfile_ui(self):
        self.clear_layout()
        self.uploadfile_page = UploadFilePage(self.load_main_ui)
        self.main_layout.addWidget(self.uploadfile_page)
        self.resize(self.uploadfile_page.size())

    def load_easyediter_ui(self):
        self.clear_layout()
        self.uploadfile_page = EasyEditorWidget(self.load_main_ui)
        self.main_layout.addWidget(self.uploadfile_page)
        self.resize(self.uploadfile_page.size())

# Application Start
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec())