import faulthandler

faulthandler.enable()



import os

from PyQt6.QtWidgets import QWidget, QLineEdit, QTextBrowser, QPushButton

from PyQt6 import uic

from PyQt6.QtCore import QTimer, Qt

from pathlib import Path

from resource_helper import get_ui_path







class LoginPage(QWidget):

    # แก้ไขในฟังก์ชัน __init__
    def __init__(self, on_login_success):
        super().__init__()

         # โหลด UI จาก Qt Designer (.ui) - ใช้ resource_helper
        ui_file = get_ui_path('LoginUi.ui')
        uic.loadUi(ui_file, self)


        self.on_login_success = on_login_success  # ฟังก์ชันที่จะเรียกเมื่อ login สำเร็จ
        self.password_visible = False  # toggle การแสดงรหัส

        # ดึง widget จาก UI
        self.username_input = self.findChild(QLineEdit, 'username')
        self.password_input = self.findChild(QLineEdit, 'password')
        self.login_text = self.findChild(QTextBrowser, 'login_text')
        self.showpassword_button = self.findChild(QPushButton, 'showpassword_button')
        self.login_button = self.findChild(QPushButton, 'login_button')

        # ตั้งค่าเริ่มต้น
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)       

        # เซต focus ที่ช่อง username เมื่อเปิดหน้า

        self.username_input.setFocus()



        # เชื่อมปุ่มกับฟังก์ชัน

        self.showpassword_button.clicked.connect(self.toggle_password_visibility)

        self.login_button.clicked.connect(self.check_login)

        

        # เชื่อม Enter key กับการทำงาน

        self.username_input.returnPressed.connect(self.on_username_enter)

        self.password_input.returnPressed.connect(self.check_login)



    def on_username_enter(self):

        """ฟังก์ชันเมื่อกด Enter ที่ช่อง username"""

        # ตรวจสอบว่า username ไม่ว่าง

        if self.username_input.text().strip():

            # ถ้าไม่ว่างให้ย้ายไปช่อง password

            self.password_input.setFocus()

        else:

            # ถ้าว่างให้แสดงข้อความเตือน

            original_html = self.login_text.toHtml()

            self.login_text.setHtml("""

                <div align="center">

                    <span style="color: orange; font-size: 18px;">

                        ⚠️ กรุณากรอก Username

                    </span>

                </div>

            """)

            

            # เน้นช่อง username

            self.username_input.setFocus()

            self.username_input.selectAll()

            

            # รีเซตข้อความหลัง 2 วินาที

            def reset_text():
                self.login_text.setHtml(original_html)

            QTimer.singleShot(2000, reset_text)

    def toggle_password_visibility(self):
        if self.password_visible:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_visible = False
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.password_visible = True

    def check_login(self):
        username = 'admin'
        password = '1234'

        # ตรวจสอบว่ากรอกข้อมูลครบหรือไม่
        if not self.username_input.text().strip():

            self.show_warning_message("⚠️ กรุณากรอก Username")
            self.username_input.setFocus()
            return

        if not self.password_input.text():
            self.show_warning_message("⚠️ กรุณากรอก Password")
            self.password_input.setFocus()
            return

        # ตรวจสอบความถูกต้องของ username และ password
        if self.username_input.text() == username and self.password_input.text() == password:
            self.login_text.setHtml("""
                <div align="center">
                    <span style="color: green; font-size: 24px;">
                        ✅ Login Success
                    </span>
                </div>
            """)
            # ปิดการใช้งานปุ่มและช่องกรอกข้อมูลระหว่างรอ
            self.disable_inputs()
            QTimer.singleShot(1000, self.on_login_success)
        else:
            original_html = self.login_text.toHtml()
            self.login_text.setHtml("""
                <div align="center">
                    <span style="color: red; font-size: 20px;">
                        ❌ Username or Password incorrect
                    </span>
                </div>
            """)
            self.password_input.clear()
            self.password_input.setFocus()

            def reset_text():
                self.login_text.setHtml(original_html)

            QTimer.singleShot(3000, reset_text)

    def show_warning_message(self, message):
        """แสดงข้อความเตือน"""
        original_html = self.login_text.toHtml()
        self.login_text.setHtml(f"""
            <div align="center">
                <span style="color: orange; font-size: 18px;">
                    {message}
                </span>
            </div>
        """)
        def reset_text():
            self.login_text.setHtml(original_html)

        QTimer.singleShot(2000, reset_text)

    

    def disable_inputs(self):
        """ปิดการใช้งาน input และปุ่มต่างๆ"""
        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)
        self.login_button.setEnabled(False)
        self.showpassword_button.setEnabled(False)

    

    def enable_inputs(self):
        """เปิดการใช้งาน input และปุ่มต่างๆ"""
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.login_button.setEnabled(True)
        self.showpassword_button.setEnabled(True)