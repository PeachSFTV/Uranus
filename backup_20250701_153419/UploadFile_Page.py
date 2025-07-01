import faulthandler
faulthandler.enable()

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox
from ui_helper import load_ui_safe, UIHelper
from PyQt6.QtCore import QTimer
import os
import shutil
from pathlib import Path
from resource_helper import get_ui_path

class UploadFilePage(QWidget):
    """หน้าสำหรับอัปโหลดไฟล์ SCL ( .scd / .cid / .xml )
    - ไฟล์จริงจะถูกคัดลอกไปยัง  `upload_file/before_convert/`
    - สคริปต์จะเรียก  `scl_parser.SCLParser`  เพื่อ
        1. แปลงเป็น JSON  (เก็บใน  upload_file/after_convert/  เช่นเดิม)
        2. แตกไฟล์ .cid แยกตาม IED ไปไว้ใน  upload_file/after_convert/<basename>/
    """

    def __init__(self, back_to_main_ui):
        super().__init__()
        from PyQt6 import uic
        ui_file = get_ui_path('Publisher_Page.ui')
        uic.loadUi(ui_file, self)

        self.back_button_pressed = back_to_main_ui
        self.uploadfile_button = self.findChild(QWidget, 'uploadfile_button')
        self.back_button = self.findChild(QWidget, 'back_button')

        self.back_button.clicked.connect(self.back_to_main)
        self.uploadfile_button.clicked.connect(self.upload_file)

    # ------------------------------------------------------------
    def back_to_main(self):
        """ดีเลย์นิดหน่อย เพื่อให้อนิเมชันปุ่มทำงานก่อนกลับ"""
        QTimer.singleShot(100, self.back_button_pressed)

    # ------------------------------------------------------------
    @staticmethod
    def _generate_renamed_filename(path: str) -> str:
        """เพิ่มตัวนับ (_1, _2 …) ต่อท้ายไฟล์หากชื่อซ้ำ"""
        base, ext = os.path.splitext(path)
        counter = 1
        new_path = f"{base}_{counter}{ext}"
        while os.path.exists(new_path):
            counter += 1
            new_path = f"{base}_{counter}{ext}"
        return new_path

    # ------------------------------------------------------------
    def upload_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "เลือกไฟล์ SCL หลายไฟล์",
            "",
            "SCL Files (*.scd *.xml *.cid *.BAK);;All Files (*)"
        )

        if not file_paths:
            return

        # ตำแหน่งโฟลเดอร์หลักของโปรเจกต์ (ไฟล์นี้อยู่ใน  Uranus/code/ )
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        before_dir = os.path.join(base_dir, 'upload_file', 'before_convert')
        after_dir  = os.path.join(base_dir, 'upload_file', 'after_convert')
        os.makedirs(before_dir, exist_ok=True)
        os.makedirs(after_dir,  exist_ok=True)

        from scl_parser import SCLParser  # นำเข้าที่นี่ เพื่อลดเวลาเปิดหน้า UI

        for file_path in file_paths:
            try:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(before_dir, file_name)

                # ------------------------------------------------ check duplicate
                if os.path.exists(dest_path):
                    msg = QMessageBox(self)
                    msg.setWindowTitle("ไฟล์ชื่อซ้ำ")
                    msg.setText(f"มีไฟล์ชื่อ '{file_name}' อยู่แล้ว ต้องการทำอย่างไร?")
                    overwrite_btn = msg.addButton("Overwrite", QMessageBox.ButtonRole.YesRole)
                    skip_btn      = msg.addButton("Skip",      QMessageBox.ButtonRole.NoRole)
                    rename_btn    = msg.addButton("Rename",    QMessageBox.ButtonRole.ApplyRole)
                    msg.setDefaultButton(overwrite_btn)
                    msg.exec()

                    if msg.clickedButton() == skip_btn:
                        print(f"⛔ ข้ามไฟล์: {file_name}")
                        continue
                    elif msg.clickedButton() == rename_btn:
                        dest_path = self._generate_renamed_filename(dest_path)
                        file_name = os.path.basename(dest_path)
                        print(f"✏️ เปลี่ยนชื่อเป็น: {file_name}")

                shutil.copy(file_path, dest_path)
                print(f"📦 คัดลอก: {file_name}")

                # --------------------------------------------- แปลง + แตกไฟล์
                json_path = os.path.join(after_dir, os.path.splitext(file_name)[0] + '.json')

                parser = SCLParser(dest_path)
                parser.split_into_ied_json()          # ← ใช้เมทอดใหม่



            except Exception as e:
                print(f"❌ ผิดพลาดในไฟล์ {file_path}: {e}")

        print("✅ ดำเนินการกับไฟล์ทั้งหมดเสร็จสิ้น")

        QMessageBox.information(
            self,
            "Upload Complete",
            "Upload success",
            QMessageBox.StandardButton.Ok
        )