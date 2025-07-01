import sys
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Any, Optional, Tuple
from datetime import datetime
import time
from ui_helper import load_ui_safe, UIHelper
from PyQt6.QtWidgets import (
    QApplication, QWidget, QListWidget, QListWidgetItem, 
    QScrollArea, QVBoxLayout, QFrame, QLabel, QPushButton, 
    QHBoxLayout, QComboBox, QMessageBox, QFileDialog, QDialogButtonBox, 
    QDialog, QGroupBox, QCheckBox, QFormLayout, QSpinBox, QProgressBar,
    QTextEdit, QLineEdit, QTableWidget, QTableWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QDrag, QFont, QColor, QPalette, QAction, QBrush
from PyQt6 import uic
from resource_helper import get_ui_path


# Import IEC 61850 modules
try:
    from iec61850_system.IEC61850_DO_DA_Config import iec61850_config, StatusValue
except ImportError:
    print("Warning: IEC61850_DO_DA_Config not found. Status change feature will be limited.")
    iec61850_config = None

try:
    from iec61850_system.ied_connection_manager import IEDConnectionManager, IEDConnection
    from iec61850_system.time_sync_utils import get_synchronized_timestamp_ms
    HAS_IED_CONNECTION = True
except ImportError:
    print("Warning: IED connection modules not found. Real IED control will be disabled.")
    HAS_IED_CONNECTION = False
    
    # Create stub classes for type annotations
    class IEDConnectionManager:
        def __init__(self): pass
        def connect_to_ied(self, *args, **kwargs): return None
        def disconnect_from_ied(self, *args, **kwargs): pass
        def read_value(self, *args, **kwargs): return None, "Module not available"
        def control_operation(self, *args, **kwargs): return "Module not available"
        def get_connection(self, *args, **kwargs): return None
        def add_connection_callback(self, *args, **kwargs): pass
    
    class IEDConnection:
        def __init__(self): pass
        def read_value(self, *args, **kwargs): return None, "Not connected"
        def control_operation(self, *args, **kwargs): return "Not connected"
    
    def get_synchronized_timestamp_ms():
        import time
        return int(time.time() * 1000)


class IEDSelectionDialog(QDialog):
    """Simple IED Selection Dialog"""
    
    def __init__(self, ied_configs, parent=None):
        super().__init__(parent)
        self.ied_configs = ied_configs
        self.selected_ieds = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Select IEDs to Load")
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🏭 Select IEDs for Logical Node Editor")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # IED List
        self.ied_list = QListWidget()
        layout.addWidget(self.ied_list)
        
        # Populate list
        for config in self.ied_configs:
            item = QListWidgetItem(f"🏭 {config['ied_name']} - {config.get('ip_address', 'Unknown IP')}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.ied_list.addItem(item)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_all_btn)
        
        layout.addLayout(button_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def select_all(self):
        for i in range(self.ied_list.count()):
            self.ied_list.item(i).setCheckState(Qt.CheckState.Checked)
    
    def clear_all(self):
        for i in range(self.ied_list.count()):
            self.ied_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    
    def get_selected_ieds(self):
        selected = []
        for i in range(self.ied_list.count()):
            item = self.ied_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected


class IEDConnectionDialog(QDialog):
    """Dialog for connecting to IEDs"""
    
    def __init__(self, ied_configs, parent=None):
        super().__init__(parent)
        self.ied_configs = ied_configs
        self.connections_to_make = []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Connect to IEDs")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🔌 Connect to Selected IEDs")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # Connection table
        self.connection_table = QTableWidget()
        self.connection_table.setColumnCount(4)
        self.connection_table.setHorizontalHeaderLabels(["IED Name", "IP Address", "Port", "Connect"])
        
        # Populate table
        self.connection_table.setRowCount(len(self.ied_configs))
        for row, config in enumerate(self.ied_configs):
            # IED Name
            self.connection_table.setItem(row, 0, QTableWidgetItem(config['ied_name']))
            
            # IP Address (editable)
            ip_item = QTableWidgetItem(config.get('ip_address', '192.168.1.100'))
            self.connection_table.setItem(row, 1, ip_item)
            
            # Port (editable)
            port_item = QTableWidgetItem(str(config.get('mms_port', 102)))
            self.connection_table.setItem(row, 2, port_item)
            
            # Connect checkbox
            check_widget = QCheckBox()
            check_widget.setChecked(True)
            self.connection_table.setCellWidget(row, 3, check_widget)
            
        self.connection_table.resizeColumnsToContents()
        layout.addWidget(self.connection_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        test_btn = QPushButton("🧪 Test Connection")
        test_btn.clicked.connect(self.test_connections)
        button_layout.addWidget(test_btn)
        
        button_layout.addStretch()
        
        connect_btn = QPushButton("🔌 Connect")
        connect_btn.clicked.connect(self.accept)
        button_layout.addWidget(connect_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
    def test_connections(self):
        """Test selected connections"""
        # TODO: Implement connection testing
        QMessageBox.information(self, "Test", "Connection test not implemented yet")
        
    def get_connections_to_make(self):
        """Get list of connections to establish"""
        connections = []
        
        for row in range(self.connection_table.rowCount()):
            check_widget = self.connection_table.cellWidget(row, 3)
            if check_widget and check_widget.isChecked():
                connection_info = {
                    'ied_name': self.connection_table.item(row, 0).text(),
                    'ip_address': self.connection_table.item(row, 1).text(),
                    'port': int(self.connection_table.item(row, 2).text())
                }
                connections.append(connection_info)
                
        return connections


class LogicalNodeItem(QListWidgetItem):
    """Custom list item สำหรับ Logical Node"""
    
    def __init__(self, ln_data: Dict[str, Any]):
        self.ln_data = ln_data
        
        # สร้างชื่อที่แสดงให้ถูกต้อง
        prefix = ln_data.get('@prefix', '')
        ln_class = ln_data.get('@lnClass', '')
        inst = ln_data.get('@inst', '')
        
        # จัดการกรณีพิเศษสำหรับ LLN0 (LN0)
        if ln_class == 'LLN0':
            display_name = 'LLN0'  # LLN0 ไม่มี prefix และ inst
        else:
            # สร้างชื่อตามรูปแบบ prefix-lnClass-inst
            parts = []
            if prefix:
                parts.append(prefix)
            if ln_class:
                parts.append(ln_class)
            if inst:
                parts.append(inst)
            display_name = '-'.join(parts) if parts else 'Unknown'
        
        super().__init__(display_name)
        self.setData(Qt.ItemDataRole.UserRole, ln_data)


class LogicalNodeBox(QFrame):
    """Widget แสดง Logical Node ที่ถูก drop มา พร้อม dropdown DO/DA และการเปลี่ยนสถานะ"""
    
    delete_requested = pyqtSignal(object)
    
    def __init__(self, ln_data: Dict[str, Any], ied_connection: Optional['IEDConnection'] = None, parent=None):
        super().__init__(parent)
        self.ln_data = ln_data
        self.ied_connection = ied_connection
        self.current_da_value = None  # เก็บค่าปัจจุบันของ DA
        self.monitoring_enabled = False
        self.object_path = None  # เก็บ path สำหรับอ่านค่า
        self.setup_ui()
        
    def setup_ui(self):
        """สร้าง UI สำหรับ LN Box"""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 2px solid #888;
                border-radius: 8px;
                padding: 5px;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #4CAF50;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Header แสดงชื่อ LN
        header_layout = QHBoxLayout()
        
        # สร้างชื่อที่แสดงให้ถูกต้อง (เหมือน LogicalNodeItem)
        prefix = self.ln_data.get('@prefix', '')
        ln_class = self.ln_data.get('@lnClass', '')
        inst = self.ln_data.get('@inst', '')
        
        if ln_class == 'LLN0':
            title = 'LLN0'
        else:
            parts = []
            if prefix:
                parts.append(prefix)
            if ln_class:
                parts.append(ln_class)
            if inst:
                parts.append(inst)
            title = '-'.join(parts) if parts else 'Unknown'
            
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Connection status indicator
        self.connection_status = QLabel("🔴" if not self.ied_connection else "🟢")
        self.connection_status.setToolTip("Not connected" if not self.ied_connection else "Connected")
        
        # ปุ่มลบ
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(20, 20)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.connection_status)
        header_layout.addStretch()
        header_layout.addWidget(delete_btn)
        
        layout.addLayout(header_layout)
        
        # Dropdown สำหรับ DO
        do_label = QLabel("Data Object:")
        do_label.setFont(QFont("Arial", 8))
        self.do_combo = QComboBox()
        self.do_combo.addItem("Select DO...")
        
        # เติมข้อมูล DO จาก DOI
        doi_list = self.ln_data.get('DOI', [])
        if isinstance(doi_list, dict):
            doi_list = [doi_list]
            
        for doi in doi_list:
            if isinstance(doi, dict):
                do_name = doi.get('@name', 'Unknown DO')
                self.do_combo.addItem(do_name, doi)
        
        self.do_combo.currentIndexChanged.connect(self.on_do_changed)
        
        layout.addWidget(do_label)
        layout.addWidget(self.do_combo)
        
        # Dropdown สำหรับ DA
        da_label = QLabel("Data Attribute:")
        da_label.setFont(QFont("Arial", 8))
        self.da_combo = QComboBox()
        self.da_combo.addItem("Select DA...")
        self.da_combo.setEnabled(False)
        self.da_combo.currentIndexChanged.connect(self.on_da_changed)
        
        layout.addWidget(da_label)
        layout.addWidget(self.da_combo)
        
        # Status section
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                margin-top: 5px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setSpacing(3)
        
        # Current value display
        value_layout = QHBoxLayout()
        value_label = QLabel("Current Value:")
        value_label.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.current_value_label = QLabel("--")
        self.current_value_label.setFont(QFont("Arial", 8))
        self.current_value_label.setStyleSheet("color: #0066cc;")
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(20, 20)
        self.refresh_btn.setToolTip("Refresh value from IED")
        self.refresh_btn.clicked.connect(self.refresh_value)
        self.refresh_btn.setEnabled(False)
        
        value_layout.addWidget(value_label)
        value_layout.addWidget(self.current_value_label)
        value_layout.addWidget(self.refresh_btn)
        value_layout.addStretch()
        status_layout.addLayout(value_layout)
        
        # Status change section
        change_layout = QHBoxLayout()
        change_label = QLabel("Change to:")
        change_label.setFont(QFont("Arial", 8))
        self.status_combo = QComboBox()
        self.status_combo.setEnabled(False)
        self.status_combo.setMinimumWidth(100)
        self.status_combo.currentIndexChanged.connect(self.on_status_changed)
        
        change_layout.addWidget(change_label)
        change_layout.addWidget(self.status_combo)
        change_layout.addStretch()
        status_layout.addLayout(change_layout)
        
        layout.addWidget(status_frame)
        
        # Hide status frame initially
        status_frame.setVisible(False)
        self.status_frame = status_frame
        
    def set_connection(self, ied_connection: Optional['IEDConnection']):
        """Set or update IED connection"""
        self.ied_connection = ied_connection
        self.connection_status.setText("🟢" if ied_connection else "🔴")
        self.connection_status.setToolTip("Connected" if ied_connection else "Not connected")
        
        # Enable/disable controls based on connection
        if self.object_path:
            self.refresh_btn.setEnabled(bool(ied_connection))
            if ied_connection:
                self.refresh_value()
                
    def on_do_changed(self, index):
        """เมื่อเลือก DO ให้อัพเดท DA dropdown"""
        self.da_combo.clear()
        self.da_combo.addItem("Select DA...")
        self.da_combo.setEnabled(False)
        self.status_frame.setVisible(False)
        self.status_combo.setEnabled(False)
        self.object_path = None
        self.refresh_btn.setEnabled(False)
        
        if index > 0:  # ไม่ใช่ "Select DO..."
            doi_data = self.do_combo.itemData(index)
            if doi_data:
                self.da_combo.setEnabled(True)
                
                # เติม DA จาก DAI
                dai_data = doi_data.get('DAI')
                if dai_data:
                    if isinstance(dai_data, dict):
                        dai_list = [dai_data]
                    else:
                        dai_list = dai_data if isinstance(dai_data, list) else []
                    
                    for dai in dai_list:
                        if isinstance(dai, dict):
                            da_name = dai.get('@name', 'Unknown DA')
                            datasrc = dai.get('@sel:datasrc', '')
                            display_name = f"{da_name} ({datasrc})" if datasrc else da_name
                            self.da_combo.addItem(display_name, dai)
    
    def on_da_changed(self, index):
        """เมื่อเลือก DA ให้แสดงสถานะและตัวเลือกการเปลี่ยนสถานะ"""
        if index <= 0:  # "Select DA..." 
            self.status_frame.setVisible(False)
            self.object_path = None
            self.refresh_btn.setEnabled(False)
            return
        
        dai_data = self.da_combo.itemData(index)
        if not dai_data:
            return
        
        # แสดง status frame
        self.status_frame.setVisible(True)
        
        # สร้าง object path สำหรับอ่านค่าจาก IED
        ied_name = self.ln_data.get('_ied_name', '')
        ld_name = self.ln_data.get('_ld_name', '')
        ln_class = self.ln_data.get('@lnClass', '')
        ln_inst = self.ln_data.get('@inst', '')
        do_name = self.do_combo.currentText()
        da_name = dai_data.get('@name', '')
        
        # Format: IEDName.LDName/LNClass.LNInst.DOName.DAName
        if ln_class == 'LLN0':
            self.object_path = f"{ied_name}.{ld_name}/LLN0.{do_name}.{da_name}"
        else:
            self.object_path = f"{ied_name}.{ld_name}/{ln_class}{ln_inst}.{do_name}.{da_name}"
        
        # Enable refresh button if connected
        self.refresh_btn.setEnabled(bool(self.ied_connection))
        
        # Try to read value from IED if connected
        if self.ied_connection:
            self.refresh_value()
        else:
            # ดึงค่าจาก SCL file (fallback)
            val_element = dai_data.get('Val')
            if val_element:
                if isinstance(val_element, dict):
                    current_value = val_element.get('#text', '--')
                else:
                    current_value = str(val_element)
            else:
                current_value = '--'
            
            self.current_value_label.setText(current_value)
            self.current_da_value = current_value
        
        # อัพเดท status combo ถ้ามี IEC 61850 config
        self.update_status_combo(da_name)
    
    def refresh_value(self):
        """Read current value from IED"""
        if not self.ied_connection or not self.object_path:
            return
            
        try:
            # Get main window reference
            main_window = self.window()
            if hasattr(main_window, 'read_da_value'):
                value, error = main_window.read_da_value(
                    self.ln_data.get('_ied_name', ''),
                    self.object_path
                )
                
                if not error:
                    # Update display
                    display_value = str(value)
                    self.current_value_label.setText(display_value)
                    self.current_da_value = value
                    
                    # Flash green to indicate update
                    self.current_value_label.setStyleSheet("color: #00cc00; font-weight: bold;")
                    QTimer.singleShot(500, lambda: self.current_value_label.setStyleSheet("color: #0066cc;"))
                else:
                    self.current_value_label.setText(f"Error: {error}")
                    self.current_value_label.setStyleSheet("color: red;")
        except Exception as e:
            self.current_value_label.setText(f"Error: {str(e)}")
            self.current_value_label.setStyleSheet("color: red;")
    
    def update_status_combo(self, da_name: str):
        """อัพเดท combobox สำหรับเปลี่ยนสถานะตาม IEC 61850 config"""
        self.status_combo.clear()
        self.status_combo.setEnabled(False)
        
        if not iec61850_config:
            self.status_combo.addItem("No config available")
            return
        
        # ดึง DO name และ LN class
        do_name = self.do_combo.currentText()
        ln_class = self.ln_data.get('@lnClass', '')
        
        # ดึงค่าที่เป็นไปได้จาก config
        possible_values = iec61850_config.get_da_values(ln_class, do_name, da_name)
        
        if possible_values:
            self.status_combo.setEnabled(True)
            self.status_combo.addItem("-- Select new value --")
            
            for value in possible_values:
                display_text = iec61850_config.format_value(value)
                self.status_combo.addItem(display_text, value)
        else:
            # ถ้าไม่มี config เฉพาะ ให้ใช้ default ตามชื่อ DA
            if da_name.lower() in ['stval', 'ctlval']:
                self.status_combo.setEnabled(True)
                self.status_combo.addItem("-- Select new value --")
                self.status_combo.addItem("FALSE", False)
                self.status_combo.addItem("TRUE", True)
            elif da_name.lower() == 'q':
                self.status_combo.addItem("Quality attributes")
            else:
                self.status_combo.addItem(f"No config for {da_name}")
    
    def on_status_changed(self, index):
        """เมื่อเลือกสถานะใหม่ - ส่งคำสั่งไปที่ IED จริง"""
        if index <= 0:  # "-- Select new value --"
            return
        
        new_value = self.status_combo.itemData(index)
        display_value = self.status_combo.currentText()
        
        # Check if connected
        if not self.ied_connection:
            QMessageBox.warning(self, "Not Connected", 
                              "Cannot send command - IED not connected")
            self.status_combo.setCurrentIndex(0)
            return
        
        # Confirm action
        reply = QMessageBox.question(self, "Confirm Control", 
                                   f"Send control command to IED?\n\n"
                                   f"Path: {self.object_path}\n"
                                   f"New Value: {display_value}",
                                   QMessageBox.StandardButton.Yes | 
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            self.status_combo.setCurrentIndex(0)
            return
        
        try:
            # Get main window reference
            main_window = self.window()
            if hasattr(main_window, 'send_control_command'):
                # For control objects, we need the control path (without .stVal)
                control_path = self.object_path.replace('.stVal', '')
                
                success = main_window.send_control_command(
                    self.ln_data.get('_ied_name', ''),
                    control_path,
                    new_value
                )
                
                if success:
                    # Update display
                    self.current_value_label.setText(display_value)
                    self.current_da_value = display_value
                    
                    # Flash green
                    self.current_value_label.setStyleSheet("color: #00cc00; font-weight: bold;")
                    QTimer.singleShot(1000, lambda: self.current_value_label.setStyleSheet("color: #0066cc;"))
                    
                    QMessageBox.information(self, "Success", "Control command sent successfully")
                else:
                    QMessageBox.warning(self, "Failed", "Failed to send control command")
            else:
                QMessageBox.warning(self, "Error", "Control function not available")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error sending command: {str(e)}")
        
        # Reset combo
        self.status_combo.setCurrentIndex(0)


class CustomListWidget(QListWidget):
    """Custom List Widget สำหรับ Logical Nodes พร้อม drag support"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        
    def startDrag(self, supportedActions):
        """เริ่ม drag operation"""
        item = self.currentItem()
        if item:
            drag = QDrag(self)
            mimeData = QMimeData()
            
            # เก็บข้อมูล LN ใน mime data
            ln_data = item.data(Qt.ItemDataRole.UserRole)
            mimeData.setText(json.dumps(ln_data))
            mimeData.setData("application/x-logical-node", json.dumps(ln_data).encode())
            
            drag.setMimeData(mimeData)
            drag.exec(Qt.DropAction.CopyAction)


class CustomScrollArea(QScrollArea):
    """Custom Scroll Area สำหรับรับ dropped Logical Nodes"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        
        # Container widget สำหรับ LN boxes
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout.setSpacing(10)
        
        self.setWidget(self.container)
        
        # Style
        self.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: 2px dashed #ccc;
                border-radius: 10px;
            }
            QScrollArea[dragActive="true"] {
                border-color: #4CAF50;
                background-color: #f0fff0;
            }
        """)
        
        # เก็บ LN boxes
        self.ln_boxes: List[LogicalNodeBox] = []
        
    def dragEnterEvent(self, event):
        """เมื่อ drag เข้ามา"""
        if event.mimeData().hasFormat("application/x-logical-node"):
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().polish(self)
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        """เมื่อ drag ออกไป"""
        self.setProperty("dragActive", False)
        self.style().polish(self)
        
    def dropEvent(self, event):
        """เมื่อ drop LN"""
        if event.mimeData().hasFormat("application/x-logical-node"):
            try:
                ln_data = json.loads(event.mimeData().data("application/x-logical-node").data().decode())
                self.add_logical_node(ln_data)
                event.acceptProposedAction()
            except Exception as e:
                print(f"Error processing drop: {e}")
                event.ignore()
        else:
            event.ignore()
            
        self.setProperty("dragActive", False)
        self.style().polish(self)
        
    def add_logical_node(self, ln_data: Dict[str, Any]):
        """เพิ่ม Logical Node box"""
        # Get IED connection if available
        ied_connection = None
        main_window = self.window()
        if hasattr(main_window, 'get_ied_connection'):
            ied_name = ln_data.get('_ied_name', '')
            ied_connection = main_window.get_ied_connection(ied_name)
        
        ln_box = LogicalNodeBox(ln_data, ied_connection)
        ln_box.delete_requested.connect(self.remove_logical_node)
        
        self.layout.addWidget(ln_box)
        self.ln_boxes.append(ln_box)
        
    def remove_logical_node(self, ln_box: LogicalNodeBox):
        """ลบ Logical Node box"""
        if ln_box in self.ln_boxes:
            self.ln_boxes.remove(ln_box)
            self.layout.removeWidget(ln_box)
            ln_box.deleteLater()
            
    def update_connections(self, ied_name: str, connection: Optional['IEDConnection']):
        """Update connection status for all LN boxes of an IED"""
        for ln_box in self.ln_boxes:
            if ln_box.ln_data.get('_ied_name', '') == ied_name:
                ln_box.set_connection(connection)


class EasyEditorWidget(QWidget):
    """Main EasyEditor Widget - Changed from QMainWindow to QWidget"""
    
    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        
        # ข้อมูลแอป
        self.scl_data = None
        self.logical_nodes: List[Dict[str, Any]] = []
        self.filtered_nodes: List[Dict[str, Any]] = []
        self.selected_ied_configs: List[Dict[str, Any]] = []
        self.current_folder = None
        self.current_file = None
        
        # IED Connection Management
        if HAS_IED_CONNECTION:
            self.connection_manager = IEDConnectionManager()
            self.connection_manager.add_connection_callback(self.on_connection_state_changed)
        else:
            self.connection_manager = None
        self.active_connections = {}
        
        # Monitoring
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self.refresh_all_values)
        self.monitoring_enabled = False
        
        # Operation log
        self.operation_log = []
        
        # Safety and mode
        self.safety_enabled = True
        self.test_mode = True  # True = test mode, False = live mode
        
        # File management - ใช้ path เดียวกับ Publisher_Page
        self.root_dir = Path(__file__).resolve().parent.parent / 'upload_file' / 'after_convert'
        
        # LN Type categories
        self.ln_categories = {
            'Protection': ['PTOC', 'PDIF', 'PIOC', 'PTUV', 'PTOV', 'PDIS', 'PFRC', 'PSCH', 'PSDE'],
            'Measurement': ['MMXU', 'TCTR', 'TVTR', 'MSQI', 'MSTA', 'MHAI'],
            'Control': ['CSWI', 'CILO', 'XCBR', 'XSWI', 'CALH', 'CCGR', 'LLN0'],  # เพิ่ม LLN0
            'Status': ['STMP', 'SPDC', 'SIMG', 'SIML'],
            'Other': []  # สำหรับ LN ที่ไม่อยู่ในหมวดหมู่ใดๆ
        }
        
        self.load_ui()
        self.setup_custom_widgets()
        self.connect_signals()
        self.initialize_ui()
        
    def load_ui(self):
        """โหลด UI จากไฟล์ .ui"""
        # หา path ของไฟล์ .ui    
        ui_file = get_ui_path('EasyEditer_Page.ui')    
        try:
            # Load UI file 
            widget = load_ui_safe(ui_file)
            if widget:
                # Copy widget attributes
                for attr in dir(widget):
                    if not attr.startswith('_'):
                        try:
                            setattr(self, attr, getattr(widget, attr))
                        except:
                            pass
            
            # Extract UI elements using findChild
            self.backBtn = self.findChild(QPushButton, 'backBtn')
            self.connectBtn = self.findChild(QPushButton, 'connectBtn')
            self.monitorBtn = self.findChild(QPushButton, 'monitorBtn')
            self.connectionStatus = self.findChild(QLabel, 'connectionStatus')
            self.safetyMode = self.findChild(QCheckBox, 'safetyMode')
            self.testMode = self.findChild(QCheckBox, 'testMode')
            
            # File management widgets
            self.loadFilesBtn = self.findChild(QPushButton, 'loadFilesBtn')
            self.filesListShow = self.findChild(QListWidget, 'filesListShow')
            
            # IED and filter widgets
            self.iedCombo = self.findChild(QComboBox, 'iedCombo')
            self.categoryCombo = self.findChild(QComboBox, 'categoryCombo')
            self.searchBox = self.findChild(QLineEdit, 'searchBox')
            
            # Main content widgets
            self.lnList = self.findChild(QListWidget, 'lnList')
            self.dropZone = self.findChild(QScrollArea, 'dropZone')
            self.instructionLabel = self.findChild(QLabel, 'instructionLabel')
            self.mainSplitter = self.findChild(QSplitter, 'mainSplitter')
            
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", f"UI file not found: {ui_file}")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load UI: {str(e)}")
            sys.exit(1)
    
    def setup_custom_widgets(self):
        """แทนที่ widgets ใน UI ด้วย custom widgets"""
        # แทนที่ lnList ด้วย CustomListWidget
        if self.lnList:
            parent = self.lnList.parent()
            geometry = self.lnList.geometry()
            self.lnList.setParent(None)
            
            self.lnList = CustomListWidget(parent)
            self.lnList.setGeometry(geometry)
        
        # แทนที่ dropZone ด้วย CustomScrollArea  
        if self.dropZone:
            parent = self.dropZone.parent()
            geometry = self.dropZone.geometry()
            self.dropZone.setParent(None)
            
            self.dropZone = CustomScrollArea(parent)
            self.dropZone.setGeometry(geometry)
            
    def connect_signals(self):
        """เชื่อม signals กับ slots"""
        # Back button
        if self.backBtn:
            self.backBtn.clicked.connect(self.go_back)
            
        # Control buttons
        if self.connectBtn:
            self.connectBtn.clicked.connect(self.show_connection_dialog)
        if self.monitorBtn:
            self.monitorBtn.clicked.connect(self.toggle_monitoring)
            
        # Safety and mode checkboxes
        if self.safetyMode:
            self.safetyMode.toggled.connect(self.toggle_safety_mode)
        if self.testMode:
            self.testMode.toggled.connect(self.toggle_test_mode)
            
        # File management
        if self.loadFilesBtn:
            self.loadFilesBtn.clicked.connect(self.load_files)
        if self.filesListShow:
            self.filesListShow.itemDoubleClicked.connect(self.open_file)
            
        # Filtering
        if self.iedCombo:
            self.iedCombo.currentTextChanged.connect(self.on_ied_changed)
        if self.categoryCombo:
            self.categoryCombo.currentTextChanged.connect(self.filter_logical_nodes)
        if self.searchBox:
            self.searchBox.textChanged.connect(self.filter_logical_nodes)
        
    def initialize_ui(self):
        """เตรียม UI เริ่มต้น"""
        # เติมข้อมูล category combo
        if self.categoryCombo:
            self.categoryCombo.addItem("All Categories")
            self.categoryCombo.addItems(list(self.ln_categories.keys()))
        
        # เติมข้อมูล IED combo - เริ่มต้นว่าง
        if self.iedCombo:
            self.iedCombo.addItem("Select IED first...")
            self.iedCombo.setEnabled(False)
            
        # Set initial button states
        if self.connectBtn:
            self.connectBtn.setEnabled(False)
        if self.monitorBtn:
            self.monitorBtn.setEnabled(False)
        
    def go_back(self):
        """กลับไปหน้าหลัก"""
        # Stop monitoring
        if self.monitoring_enabled:
            self.stop_monitoring()
            
        # Disconnect all IEDs
        if self.active_connections:
            for ied_name in list(self.active_connections.keys()):
                if self.connection_manager:
                    self.connection_manager.disconnect_from_ied(ied_name)
                    
        self.active_connections.clear()
        
        # Call back callback
        if self.back_callback:
            self.back_callback()
    
    # IED Connection Methods
    def show_connection_dialog(self):
        """Show dialog to connect to IEDs"""
        if not self.selected_ied_configs:
            QMessageBox.warning(self, "No IEDs", "Please load and select IEDs first")
            return
            
        if not HAS_IED_CONNECTION:
            QMessageBox.warning(self, "Module Not Available", 
                              "IED connection module not available.\n"
                              "Real IED control is disabled.")
            return
            
        # Show connection dialog
        dialog = IEDConnectionDialog(self.selected_ied_configs, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            connections_to_make = dialog.get_connections_to_make()
            
            if connections_to_make:
                self.connect_to_ieds(connections_to_make)
                
    def connect_to_ieds(self, connection_list: List[Dict]):
        """Connect to multiple IEDs"""
        connected_count = 0
        failed_count = 0
        
        for conn_info in connection_list:
            ied_name = conn_info['ied_name']
            ip_address = conn_info['ip_address']
            port = conn_info.get('port', 102)
            
            try:
                self.log_operation(f"Connecting to {ied_name} at {ip_address}:{port}")
                
                connection = self.connection_manager.connect_to_ied(
                    ied_name, ip_address, port
                )
                
                if connection:
                    self.active_connections[ied_name] = connection
                    connected_count += 1
                    self.log_operation(f"Successfully connected to {ied_name}")
                    
                    # Update LN boxes with connection
                    self.dropZone.update_connections(ied_name, connection)
                else:
                    failed_count += 1
                    self.log_operation(f"Failed to connect to {ied_name}", "error")
                    
            except Exception as e:
                failed_count += 1
                self.log_operation(f"Error connecting to {ied_name}: {str(e)}", "error")
                
        # Update UI
        self.update_connection_status()
        
        # Show summary
        message = f"Connected to {connected_count} IED(s)"
        if failed_count > 0:
            message += f"\nFailed: {failed_count}"
            
        QMessageBox.information(self, "Connection Result", message)
        
    def disconnect_all(self):
        """Disconnect from all IEDs"""
        if not self.active_connections:
            return
            
        # Stop monitoring first
        if self.monitoring_enabled:
            self.stop_monitoring()
            
        # Disconnect all
        for ied_name in list(self.active_connections.keys()):
            if self.connection_manager:
                self.connection_manager.disconnect_from_ied(ied_name)
            self.dropZone.update_connections(ied_name, None)
            self.log_operation(f"Disconnected from {ied_name}")
            
        self.active_connections.clear()
        self.update_connection_status()
        
    def get_ied_connection(self, ied_name: str) -> Optional['IEDConnection']:
        """Get connection for specific IED"""
        return self.active_connections.get(ied_name)
        
    def on_connection_state_changed(self, ied_name: str, state):
        """Handle connection state change"""
        # Update dropzone connections
        if state.value == "Connected":
            connection = self.connection_manager.get_connection(ied_name)
            self.dropZone.update_connections(ied_name, connection)
        else:
            self.dropZone.update_connections(ied_name, None)
            if ied_name in self.active_connections:
                del self.active_connections[ied_name]
                
        self.update_connection_status()
        
    def update_connection_status(self):
        """Update connection status in UI"""
        connected_count = len(self.active_connections)
        
        if connected_count == 0:
            if self.connectionStatus:
                self.connectionStatus.setText("🔴 Disconnected")
            if self.monitorBtn:
                self.monitorBtn.setEnabled(False)
        else:
            if self.connectionStatus:
                self.connectionStatus.setText(f"🟢 Connected ({connected_count})")
            if self.monitorBtn:
                self.monitorBtn.setEnabled(True)
                
    # Monitoring Methods
    def toggle_monitoring(self):
        """Toggle monitoring on/off"""
        if self.monitoring_enabled:
            self.stop_monitoring()
        else:
            self.start_monitoring()
            
    def start_monitoring(self):
        """Start automatic value refresh"""
        if self.monitoring_enabled:
            return
            
        self.monitoring_enabled = True
        self.monitoring_timer.start(1000)  # Refresh every 1 second
        
        if self.monitorBtn:
            self.monitorBtn.setText("⏹️ Stop Monitor")
        
        self.log_operation("Started value monitoring")
        
    def stop_monitoring(self):
        """Stop automatic value refresh"""
        if not self.monitoring_enabled:
            return
            
        self.monitoring_enabled = False
        self.monitoring_timer.stop()
        
        if self.monitorBtn:
            self.monitorBtn.setText("▶️ Monitor")
        
        self.log_operation("Stopped value monitoring")
        
    def refresh_all_values(self):
        """Refresh all displayed values"""
        if not self.monitoring_enabled:
            return
            
        # Refresh values in all LN boxes
        for ln_box in self.dropZone.ln_boxes:
            if ln_box.ied_connection and ln_box.object_path:
                ln_box.refresh_value()
                
    # Safety and Mode Methods
    def toggle_safety_mode(self, checked: bool):
        """Toggle safety mode"""
        self.safety_enabled = checked
        
        if not checked:
            # Show warning
            QMessageBox.warning(self, "Safety Warning",
                              "⚠️ Safety checks are now DISABLED!\n\n"
                              "Be very careful with control operations.")
            
        self.log_operation(f"Safety mode: {'ON' if checked else 'OFF'}")
        
    def toggle_test_mode(self, checked: bool):
        """Toggle between test and live mode"""
        self.test_mode = checked
        
        if not checked:
            # Show warning
            reply = QMessageBox.warning(self, "Live Mode Warning",
                                      "⚠️ Switching to LIVE MODE!\n\n"
                                      "All commands will be sent to real IEDs.\n"
                                      "Are you sure?",
                                      QMessageBox.StandardButton.Yes | 
                                      QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                if self.testMode:
                    self.testMode.setChecked(True)
                self.test_mode = True
                return
                
        self.log_operation(f"Mode: {'Test' if checked else 'LIVE'}")
        
    # Value Reading/Writing Methods
    def read_da_value(self, ied_name: str, object_path: str) -> Tuple[Optional[Any], Optional[str]]:
        """Read value from IED"""
        if not self.connection_manager:
            return None, "Connection manager not available"
            
        if ied_name not in self.active_connections:
            return None, "IED not connected"
            
        try:
            value, error = self.connection_manager.read_value(ied_name, object_path)
            
            if not error:
                self.log_operation(f"Read {object_path}: {value}")
                
            return value, error
            
        except Exception as e:
            return None, str(e)
            
    def send_control_command(self, ied_name: str, control_path: str, value: Any) -> bool:
        """Send control command to IED"""
        if not self.connection_manager:
            self.log_operation("Connection manager not available", "error")
            return False
            
        if ied_name not in self.active_connections:
            self.log_operation(f"{ied_name} not connected", "error")
            return False
            
        # Safety check
        if not self.perform_safety_check(ied_name, control_path, value):
            self.log_operation("Safety check failed", "warning")
            return False
            
        try:
            self.log_operation(f"Sending control to {control_path}: {value}")
            
            error = self.connection_manager.control_operation(
                ied_name,
                control_path,
                value,
                select_before_operate=True,
                test_mode=self.test_mode
            )
            
            if error:
                self.log_operation(f"Control failed: {error}", "error")
                return False
            else:
                self.log_operation(f"Control successful: {control_path} = {value}", "success")
                return True
                
        except Exception as e:
            self.log_operation(f"Control error: {str(e)}", "error")
            return False
            
    def perform_safety_check(self, ied_name: str, control_path: str, value: Any) -> bool:
        """Perform safety checks before control operation"""
        if not self.safety_enabled:
            return True
            
        # Check if in test mode
        if not self.test_mode:
            # Extra confirmation for live mode
            reply = QMessageBox.warning(self, "Live Mode Warning",
                                       "⚠️ You are in LIVE MODE!\n\n"
                                       "This will send real commands to the IED.\n"
                                       "Are you sure you want to continue?",
                                       QMessageBox.StandardButton.Yes | 
                                       QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return False
                
        # TODO: Add more safety checks
        # - Check local/remote mode
        # - Check interlocks
        # - Check protection status
        
        return True
        
    # Logging Methods
    def log_operation(self, message: str, level: str = "info"):
        """Log operation"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if level == "error":
            prefix = "❌"
        elif level == "warning":
            prefix = "⚠️"
        elif level == "success":
            prefix = "✅"
        else:
            prefix = "ℹ️"
            
        log_entry = f"[{timestamp}] {prefix} {message}"
        self.operation_log.append(log_entry)
        
        # Keep log size reasonable
        if len(self.operation_log) > 1000:
            self.operation_log = self.operation_log[-1000:]
            
        # Also print to console
        print(log_entry)
        
    def load_files(self):
        """Load SCL files from directory - เหมือนกับ Publisher_Page"""
        try:
            if self.filesListShow:
                self.filesListShow.clear()
            self.current_folder = None
            
            if not self.root_dir.exists():
                if self.filesListShow:
                    self.filesListShow.addItem("❌ after_convert folder not found")
                return
            
            # List folders
            for folder in sorted(self.root_dir.iterdir()):
                if folder.is_dir():
                    if self.filesListShow:
                        self.filesListShow.addItem(f"📁 {folder.name}")
            
            print(f"📂 Found {self.filesListShow.count() if self.filesListShow else 0} folders")
            
        except Exception as e:
            print(f"❌ Error loading files: {e}")
    
    def open_file(self, item: QListWidgetItem):
        """Open folder or file - เหมือนกับ Publisher_Page"""
        try:
            text = item.text()
            
            if text.startswith("📁"):  # Folder
                folder_name = text.replace("📁 ", "")
                self.current_folder = self.root_dir / folder_name
                self.show_folder_contents()
                
            elif text.startswith("📄") or text.startswith("📋"):  # File
                filename = text.replace("📄 ", "").replace("📋 ", "")
                if self.current_folder:
                    file_path = self.current_folder / filename
                    self.load_scl_file(file_path)
                    
            elif text.startswith("⬅️"):  # Back
                self.load_files()
                
        except Exception as e:
            print(f"❌ Error opening: {e}")
    
    def show_folder_contents(self):
        """Show contents of selected folder - เหมือนกับ Publisher_Page"""
        try:
            if self.filesListShow:
                self.filesListShow.clear()
                self.filesListShow.addItem("⬅️ Back to folders")
            
            # List SCL and JSON files
            files = list(self.current_folder.glob("*.scl")) + list(self.current_folder.glob("*.json"))
            
            for file in sorted(files):
                icon = "📄" if file.suffix == ".scl" else "📋"
                if self.filesListShow:
                    self.filesListShow.addItem(f"{icon} {file.name}")
            
            print(f"📁 {self.current_folder.name}: {len(files)} files")
            
        except Exception as e:
            print(f"❌ Error reading folder: {e}")
    
    def load_scl_file(self, file_path: Path):
        """Load SCL or JSON file"""
        try:
            print(f"📖 Loading {file_path.name}...")
            
            # Load JSON
            if file_path.suffix == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.scl_data = json.load(f)
            else:
                # Try to find corresponding JSON
                json_path = file_path.with_suffix('.json')
                if json_path.exists():
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.scl_data = json.load(f)
                else:
                    QMessageBox.warning(self, "File Error", "No JSON file found for SCL")
                    return
            
            self.current_file = file_path
            self.process_scl_data()
            
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            QMessageBox.critical(self, "Load Error", f"Cannot load file:\n{e}")
    
    def process_scl_data(self):
        """Process loaded SCL data"""
        try:
            if not self.scl_data:
                return
          
            # Extract IED configurations
            ied_configs = self.extract_ied_configs()
        
            if not ied_configs:
                QMessageBox.warning(self, "No IEDs", "No IEDs found in SCL file")
                return
        
            # Show selection dialog
            dialog = IEDSelectionDialog(ied_configs, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.selected_ied_configs = dialog.get_selected_ieds()
                print(f"DEBUG: Selected IEDs = {self.selected_ied_configs}")
            
                if self.selected_ied_configs:
                    # Extract logical nodes ทันทีหลังเลือก IED
                    self.extract_logical_nodes()
                    # จากนั้นค่อย populate IED combo
                    self.populate_ied_combo()
                    print(f"✅ Selected {len(self.selected_ied_configs)} IEDs")
                    
                    # Enable connection action
                    if self.connectBtn:
                        self.connectBtn.setEnabled(True)
                    
                    # กลับไปหน้า folders list หลังเลือก IED เสร็จ
                    self.load_files()
                else:
                    print("❌ No IEDs selected")
        
        except Exception as e:
            print(f"❌ Error processing SCL: {e}")
    
    def extract_ied_configs(self) -> List[Dict]:
        """Extract IED configurations from SCL"""
        configs = []
        
        try:
            if 'SCL' not in self.scl_data:
                return configs
            
            # Get IEDs
            ieds = self.scl_data['SCL'].get('IED', [])
            if not isinstance(ieds, list):
                ieds = [ieds]
            
            # Extract basic info
            for ied in ieds:
                config = {
                    'ied_name': ied.get('@name', 'Unknown'),
                    'manufacturer': ied.get('@manufacturer', ''),
                    'type': ied.get('@type', ''),
                    'ip_address': '192.168.1.100',  # Default
                    'mms_port': 102
                }
                
                # Try to find IP from Communication section
                comm = self.scl_data['SCL'].get('Communication', {})
                subnets = comm.get('SubNetwork', [])
                if not isinstance(subnets, list):
                    subnets = [subnets]
                
                for subnet in subnets:
                    caps = subnet.get('ConnectedAP', [])
                    if not isinstance(caps, list):
                        caps = [caps]
                    
                    for cap in caps:
                        if cap.get('@iedName') == config['ied_name']:
                            # Extract IP
                            address = cap.get('Address', {})
                            p_elements = address.get('P', [])
                            if not isinstance(p_elements, list):
                                p_elements = [p_elements]
                            
                            for p in p_elements:
                                if isinstance(p, dict) and p.get('@type') == 'IP':
                                    config['ip_address'] = p.get('#text', config['ip_address'])
                
                configs.append(config)
            
        except Exception as e:
            print(f"Error extracting IED configs: {e}")
        
        return configs
    
    def populate_ied_combo(self):
        """Populate IED combo with selected IEDs"""
        if self.iedCombo:
            self.iedCombo.clear()
            self.iedCombo.addItem("Select IED...")
            
            for config in self.selected_ied_configs:
                ied_name = config['ied_name']
                self.iedCombo.addItem(f"🏭 {ied_name}", ied_name)
            
            self.iedCombo.setEnabled(True)
            print(f"📋 Populated IED combo with {len(self.selected_ied_configs)} IEDs")
        
    def extract_logical_nodes(self):
        """แยก logical nodes จาก SCL data สำหรับ IED ที่เลือก"""
        self.logical_nodes = []
        
        if not self.scl_data or not self.selected_ied_configs:
            return
            
        # Get selected IED names
        selected_ied_names = [config['ied_name'] for config in self.selected_ied_configs]
            
        scl = self.scl_data.get('SCL', {})
        ieds = scl.get('IED', [])
        
        if isinstance(ieds, dict):
            ieds = [ieds]
            
        for ied in ieds:
            if not isinstance(ied, dict):
                continue
                
            ied_name = ied.get('@name', 'Unknown')
            
            # Skip IEDs ที่ไม่ได้เลือก
            if ied_name not in selected_ied_names:
                continue
            
            print(f"  🔍 Processing IED: {ied_name}")
            
            # ดึง AccessPoint -> Server -> LDevice (เหมือน Publisher_Page.py)
            aps = ied.get('AccessPoint', [])
            if not isinstance(aps, list):
                aps = [aps]
            
            for ap in aps:
                if not isinstance(ap, dict):
                    continue
                
                server = ap.get('Server', {})
                if not server:
                    continue
                
                # ดึง Logical Devices จาก Server
                lds = server.get('LDevice', [])
                if isinstance(lds, dict):
                    lds = [lds]
                    
                for ld in lds:
                    if not isinstance(ld, dict):
                        continue
                        
                    ld_name = ld.get('@inst', 'Unknown')
                    print(f"    📂 Found LogicalDevice: {ld_name}")
                    
                    # ดึง Logical Nodes
                    ln_count = 0
                    
                    # ดึง LN0 (ถ้ามี)
                    ln0 = ld.get('LN0')
                    if ln0 and isinstance(ln0, dict):
                        ln0['@lnClass'] = 'LLN0'  # ใช้ LLN0 สำหรับ LN0
                        ln0['@inst'] = ''  # LN0 ไม่มี inst
                        ln0['@prefix'] = ''  # LN0 ไม่มี prefix
                        ln0['_ied_name'] = ied_name
                        ln0['_ld_name'] = ld_name
                        self.logical_nodes.append(ln0)
                        ln_count += 1
                    
                    # ดึง LN อื่นๆ
                    lns = ld.get('LN', [])
                    if isinstance(lns, dict):
                        lns = [lns]
                        
                    for ln in lns:
                        if isinstance(ln, dict):
                            # เพิ่มข้อมูล context
                            ln['_ied_name'] = ied_name
                            ln['_ld_name'] = ld_name
                            self.logical_nodes.append(ln)
                            ln_count += 1
                    
                    print(f"      ✅ Found {ln_count} logical nodes")
        
        print(f"📊 Total: Extracted {len(self.logical_nodes)} logical nodes from selected IEDs")
        
    def on_ied_changed(self, ied_text: str):
        """เมื่อเลือก IED ใหม่ - filter logical nodes"""
        if not ied_text or ied_text == "Select IED...":
            # Clear list when no IED selected
            if self.lnList:
                self.lnList.clear()
            return
        
        # Filter logical nodes ตาม IED ที่เลือก
        self.filter_logical_nodes()
        
    def filter_logical_nodes(self):
        """กรอง logical nodes ตาม criteria รวมถึง IED ที่เลือก"""
        if not self.logical_nodes:
            if self.lnList:
                self.lnList.clear()
            return
        
        # Filter by selected IED first
        ied_text = self.iedCombo.currentText() if self.iedCombo else ""
        if ied_text and ied_text != "Select IED...":
            # Extract IED name from combo text
            if ied_text.startswith("🏭 "):
                selected_ied_name = ied_text.replace("🏭 ", "")
                filtered_by_ied = [ln for ln in self.logical_nodes if ln.get('_ied_name') == selected_ied_name]
            else:
                filtered_by_ied = self.logical_nodes[:]
        else:
            # No IED selected - show empty list
            if self.lnList:
                self.lnList.clear()
            return
            
        # Filter by category
        category_filter = self.categoryCombo.currentText() if self.categoryCombo else ""
        if category_filter and category_filter != "All Categories":
            category_lns = self.ln_categories.get(category_filter, [])
            filtered_by_category = [
                ln for ln in filtered_by_ied 
                if ln.get('@lnClass', '') in category_lns
            ]
        else:
            # If "All Categories" or "Other", include all
            filtered_by_category = filtered_by_ied[:]
            
            # Special handling for "Other" category - include LNs not in any defined category
            if category_filter == "Other":
                all_defined_lns = []
                for cat_lns in self.ln_categories.values():
                    if isinstance(cat_lns, list):
                        all_defined_lns.extend(cat_lns)
                
                filtered_by_category = [
                    ln for ln in filtered_by_ied 
                    if ln.get('@lnClass', '') not in all_defined_lns
                ]
            
        # Filter by search text
        search_text = self.searchBox.text().lower() if self.searchBox else ""
        if search_text:
            self.filtered_nodes = [
                ln for ln in filtered_by_category
                if (search_text in ln.get('@prefix', '').lower() or
                    search_text in ln.get('@lnClass', '').lower() or
                    search_text in str(ln.get('@inst', '')).lower())
            ]
        else:
            self.filtered_nodes = filtered_by_category[:]
            
        self.populate_ln_list()
        
        # Debug info
        if ied_text and ied_text != "Select IED...":
            ied_name = ied_text.replace("🏭 ", "")
            print(f"📊 Filtered to {len(self.filtered_nodes)} logical nodes for IED: {ied_name}")
        
    def populate_ln_list(self):
        """เติมข้อมูล logical nodes ใน list"""
        if self.lnList:
            self.lnList.clear()
            
            for ln in self.filtered_nodes:
                item = LogicalNodeItem(ln)
                self.lnList.addItem(item)


def main():
    """Main function - for testing only"""
    app = QApplication(sys.argv)
    
    # Apply modern style
    app.setStyle('Fusion')
    
    # Set application properties
    app.setApplicationName("SCL Logical Node Editor")
    app.setOrganizationName("IEC61850Tools")
    
    try:
        # Create widget with a simple back callback for testing
        def test_back():
            print("Back button pressed - would go back to main window")
            
        window = EasyEditorWidget(test_back)
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        QMessageBox.critical(None, "Fatal Error", f"Failed to start application:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()