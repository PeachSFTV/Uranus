#!/usr/bin/env python3
"""
IEC 61850 GOOSE Send Dialog
~~~~~~~~~~~~~~~~~~~~~~~~~~
Dialog for sending GOOSE messages with proper IEC 61850 data types
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QCheckBox, QHeaderView, QSpinBox,
    QDoubleSpinBox, QLineEdit, QPlainTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import time

@dataclass
class GOOSEDataItem:
    """GOOSE data item"""
    path: str
    value: Any
    iec_type: str
    goose_type: str
    description: str = ""

class GOOSESendDialog(QDialog):
    """Dialog for sending GOOSE with IEC 61850 compliant types"""
    
    # Signal emitted when GOOSE should be sent
    goose_send_requested = pyqtSignal(list)  # List[GOOSEDataItem]
    
    # GOOSE type mapping based on IEC 61850-8-1
    IEC_TO_GOOSE_TYPES = {
        "BOOLEAN": ["boolean"],
        "INT8": ["integer", "unsigned"],
        "INT16": ["integer", "unsigned"], 
        "INT32": ["integer", "unsigned"],
        "INT64": ["integer", "unsigned"],
        "INT8U": ["unsigned", "integer"],
        "INT16U": ["unsigned", "integer"],
        "INT32U": ["unsigned", "integer"],
        "INT64U": ["unsigned", "integer"],
        "FLOAT32": ["float"],
        "FLOAT64": ["float"],
        "VisString": ["visible-string", "mms-string"],
        "Unicode255": ["visible-string", "unicode-string"],
        "TIMESTAMP": ["utc-time", "binary-time"],
        "QUALITY": ["bit-string"],
        "Enumerated": ["integer", "unsigned"],
        "CodedEnum": ["integer", "bit-string"]
    }
    
    # Standard GOOSE types per IEC 61850-8-1
    GOOSE_TYPES = {
        "boolean": "BOOLEAN",
        "integer": "INTEGER", 
        "unsigned": "UNSIGNED",
        "float": "FLOATING POINT",
        "octet-string": "OCTET STRING",
        "visible-string": "VISIBLE STRING",
        "mms-string": "MMS STRING",
        "unicode-string": "UNICODE STRING",
        "binary-time": "BINARY TIME",
        "utc-time": "UTC TIME",
        "bit-string": "BIT STRING",
        "generalized-time": "GENERALIZED TIME"
    }
    
    def __init__(self, element_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.element_info = element_info
        self.path = element_info.get('path', '')
        self.value = element_info.get('value', '')
        self.iec_type = element_info.get('iec_type', 'VisString')
        self.da_name = element_info.get('da_name', '')
        self.do_name = element_info.get('do_name', '')
        self.ln_class = element_info.get('ln_class', '')
        
        self.data_items = []
        self.setup_ui()
        self.populate_initial_data()
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle(f"Send GOOSE - {self.da_name}")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Info section
        info_group = QGroupBox("IEC 61850 Element Information")
        info_layout = QVBoxLayout()
        
        info_layout.addWidget(QLabel(f"<b>Path:</b> {self.path}"))
        info_layout.addWidget(QLabel(f"<b>Element:</b> {self.ln_class}.{self.do_name}.{self.da_name}"))
        info_layout.addWidget(QLabel(f"<b>IEC 61850 Type:</b> {self.iec_type}"))
        info_layout.addWidget(QLabel(f"<b>Current Value:</b> {self.value}"))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # GOOSE dataset configuration
        dataset_group = QGroupBox("GOOSE Dataset Configuration")
        dataset_layout = QVBoxLayout()
        
        # Add quality and timestamp checkbox
        self.include_quality_check = QCheckBox("Include Quality (q)")
        self.include_quality_check.setChecked(True)
        self.include_quality_check.stateChanged.connect(self.update_dataset)
        
        self.include_timestamp_check = QCheckBox("Include Timestamp (t)")
        self.include_timestamp_check.setChecked(True)
        self.include_timestamp_check.stateChanged.connect(self.update_dataset)
        
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.include_quality_check)
        checkbox_layout.addWidget(self.include_timestamp_check)
        checkbox_layout.addStretch()
        dataset_layout.addLayout(checkbox_layout)
        
        # Dataset table
        self.dataset_table = QTableWidget()
        self.dataset_table.setColumnCount(5)
        self.dataset_table.setHorizontalHeaderLabels([
            "Index", "Path", "GOOSE Type", "Value", "Description"
        ])
        
        # Configure table
        header = self.dataset_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self.dataset_table.setColumnWidth(0, 50)
        
        dataset_layout.addWidget(self.dataset_table)
        dataset_group.setLayout(dataset_layout)
        layout.addWidget(dataset_group)
        
        # Advanced options
        advanced_group = QGroupBox("Advanced GOOSE Options")
        advanced_layout = QVBoxLayout()
        
        # State number control
        stnum_layout = QHBoxLayout()
        stnum_layout.addWidget(QLabel("State Number (stNum):"))
        self.stnum_spin = QSpinBox()
        self.stnum_spin.setRange(0, 4294967295)
        self.stnum_spin.setValue(1)
        stnum_layout.addWidget(self.stnum_spin)
        
        self.increase_stnum_check = QCheckBox("Increment stNum (state change)")
        self.increase_stnum_check.setChecked(True)
        stnum_layout.addWidget(self.increase_stnum_check)
        
        stnum_layout.addStretch()
        advanced_layout.addLayout(stnum_layout)
        
        # Retransmission
        self.retransmission_check = QCheckBox("Use IEC 61850 retransmission pattern")
        self.retransmission_check.setChecked(True)
        advanced_layout.addWidget(self.retransmission_check)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("Test Values")
        self.test_btn.clicked.connect(self.test_values)
        button_layout.addWidget(self.test_btn)
        
        button_layout.addStretch()
        
        self.send_btn = QPushButton("Send GOOSE")
        self.send_btn.clicked.connect(self.send_goose)
        self.send_btn.setDefault(True)
        button_layout.addWidget(self.send_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def populate_initial_data(self):
        """Populate initial dataset based on element"""
        self.data_items.clear()
        
        # Main data item
        main_item = GOOSEDataItem(
            path=self.path,
            value=self.value,
            iec_type=self.iec_type,
            goose_type=self.get_default_goose_type(self.iec_type),
            description=f"{self.da_name} value"
        )
        self.data_items.append(main_item)
        
        # Add quality if checked
        if self.include_quality_check.isChecked():
            quality_item = GOOSEDataItem(
                path=f"{self.path}.q",
                value=0,  # Good quality
                iec_type="QUALITY",
                goose_type="bit-string",
                description="Quality"
            )
            self.data_items.append(quality_item)
        
        # Add timestamp if checked
        if self.include_timestamp_check.isChecked():
            timestamp_item = GOOSEDataItem(
                path=f"{self.path}.t",
                value=int(time.time() * 1000),
                iec_type="TIMESTAMP",
                goose_type="utc-time",
                description="Timestamp"
            )
            self.data_items.append(timestamp_item)
        
        self.update_table()
    
    def get_default_goose_type(self, iec_type: str) -> str:
        """Get default GOOSE type for IEC type"""
        goose_types = self.IEC_TO_GOOSE_TYPES.get(iec_type, ["visible-string"])
        return goose_types[0]
    
    def get_allowed_goose_types(self, iec_type: str) -> List[str]:
        """Get allowed GOOSE types for IEC type"""
        return self.IEC_TO_GOOSE_TYPES.get(iec_type, ["visible-string"])
    
    def update_dataset(self):
        """Update dataset when checkboxes change"""
        self.populate_initial_data()
    
    def update_table(self):
        """Update dataset table"""
        self.dataset_table.setRowCount(len(self.data_items))
        
        for row, item in enumerate(self.data_items):
            # Index
            index_item = QTableWidgetItem(str(row))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            index_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.dataset_table.setItem(row, 0, index_item)
            
            # Path
            path_item = QTableWidgetItem(item.path)
            path_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.dataset_table.setItem(row, 1, path_item)
            
            # GOOSE Type combo
            type_combo = QComboBox()
            allowed_types = self.get_allowed_goose_types(item.iec_type)
            
            for goose_type in allowed_types:
                display_name = self.GOOSE_TYPES.get(goose_type, goose_type)
                type_combo.addItem(f"{goose_type} - {display_name}", goose_type)
            
            # Set current type
            for i in range(type_combo.count()):
                if type_combo.itemData(i) == item.goose_type:
                    type_combo.setCurrentIndex(i)
                    break
            
            type_combo.currentIndexChanged.connect(
                lambda idx, r=row: self.on_type_changed(r, idx)
            )
            self.dataset_table.setCellWidget(row, 2, type_combo)
            
            # Value editor
            value_widget = self.create_value_editor(item)
            self.dataset_table.setCellWidget(row, 3, value_widget)
            
            # Description
            desc_item = QTableWidgetItem(item.description)
            desc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.dataset_table.setItem(row, 4, desc_item)
            
            # Highlight main value
            if row == 0:
                for col in range(5):
                    if col != 2 and col != 3:  # Not combo/editor cells
                        self.dataset_table.item(row, col).setBackground(QColor(240, 248, 255))
    
    def create_value_editor(self, item: GOOSEDataItem):
        """Create appropriate value editor for GOOSE type"""
        goose_type = item.goose_type
        
        if goose_type == "boolean":
            combo = QComboBox()
            combo.addItem("FALSE (0)", False)
            combo.addItem("TRUE (1)", True)
            
            # Set current value
            if str(item.value).lower() in ['true', '1']:
                combo.setCurrentIndex(1)
            else:
                combo.setCurrentIndex(0)
                
            combo.currentIndexChanged.connect(
                lambda: self.update_item_value(item, combo.currentData())
            )
            return combo
        
        elif goose_type in ["integer", "unsigned"]:
            spin = QSpinBox()
            if goose_type == "unsigned":
                spin.setMinimum(0)
                spin.setMaximum(4294967295)
            else:
                spin.setMinimum(-2147483648)
                spin.setMaximum(2147483647)
            
            try:
                spin.setValue(int(item.value))
            except:
                spin.setValue(0)
            
            spin.valueChanged.connect(
                lambda v: self.update_item_value(item, v)
            )
            return spin
        
        elif goose_type == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(6)
            spin.setRange(-1e9, 1e9)
            
            try:
                spin.setValue(float(item.value))
            except:
                spin.setValue(0.0)
            
            spin.valueChanged.connect(
                lambda v: self.update_item_value(item, v)
            )
            return spin
        
        elif goose_type == "bit-string":
            if item.iec_type == "QUALITY":
                # Special handling for quality
                combo = QComboBox()
                combo.addItem("Good (0x0000)", 0)
                combo.addItem("Invalid (0x0001)", 1) 
                combo.addItem("Questionable (0x0002)", 2)
                combo.addItem("Overflow (0x0004)", 4)
                combo.addItem("Out of Range (0x0008)", 8)
                combo.addItem("Bad Reference (0x0010)", 16)
                combo.addItem("Oscillatory (0x0020)", 32)
                combo.addItem("Failure (0x0040)", 64)
                combo.addItem("Old Data (0x0080)", 128)
                combo.addItem("Inconsistent (0x0100)", 256)
                combo.addItem("Inaccurate (0x0200)", 512)
                
                combo.currentIndexChanged.connect(
                    lambda: self.update_item_value(item, combo.currentData())
                )
                return combo
            else:
                # Generic bit string as hex
                edit = QLineEdit()
                edit.setText(f"0x{int(item.value):04X}" if isinstance(item.value, int) else "0x0000")
                edit.textChanged.connect(
                    lambda t: self.update_item_value(item, self.parse_hex_value(t))
                )
                return edit
        
        elif goose_type in ["utc-time", "binary-time"]:
            # Show as timestamp
            edit = QLineEdit()
            if isinstance(item.value, int):
                from datetime import datetime
                dt = datetime.fromtimestamp(item.value / 1000)
                edit.setText(dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            else:
                edit.setText(str(item.value))
            
            edit.setReadOnly(True)  # Usually timestamp is auto-generated
            return edit
        
        else:  # visible-string, mms-string, etc.
            edit = QLineEdit()
            edit.setText(str(item.value))
            edit.textChanged.connect(
                lambda t: self.update_item_value(item, t)
            )
            return edit
    
    def on_type_changed(self, row: int, combo_index: int):
        """Handle GOOSE type change"""
        if row < len(self.data_items):
            combo = self.dataset_table.cellWidget(row, 2)
            if combo:
                new_type = combo.currentData()
                self.data_items[row].goose_type = new_type
                
                # Recreate value editor for new type
                value_widget = self.create_value_editor(self.data_items[row])
                self.dataset_table.setCellWidget(row, 3, value_widget)
    
    def update_item_value(self, item: GOOSEDataItem, value: Any):
        """Update data item value"""
        item.value = value
    
    def parse_hex_value(self, text: str) -> int:
        """Parse hex value from string"""
        try:
            if text.startswith("0x") or text.startswith("0X"):
                return int(text, 16)
            else:
                return int(text, 16)
        except:
            return 0
    
    def test_values(self):
        """Test current values"""
        from PyQt6.QtWidgets import QMessageBox
        
        msg = "GOOSE Dataset Values:\n\n"
        for i, item in enumerate(self.data_items):
            msg += f"[{i}] {item.path}\n"
            msg += f"    Type: {item.goose_type} ({self.GOOSE_TYPES.get(item.goose_type, '')})\n"
            msg += f"    Value: {item.value} (IEC: {item.iec_type})\n\n"
        
        QMessageBox.information(self, "Test Values", msg)
    
    def send_goose(self):
        """Send GOOSE message"""
        # Update timestamp if included
        for item in self.data_items:
            if item.path.endswith('.t') and item.iec_type == "TIMESTAMP":
                item.value = int(time.time() * 1000)
        
        # Emit signal with data items
        self.goose_send_requested.emit(self.data_items.copy())
        
        # Close dialog
        self.accept()
    
    def get_goose_config(self) -> Dict[str, Any]:
        """Get GOOSE configuration"""
        return {
            'increase_stnum': self.increase_stnum_check.isChecked(),
            'stnum': self.stnum_spin.value(),
            'retransmission': self.retransmission_check.isChecked(),
            'data_items': self.data_items.copy()
        }


# Example usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Test element info
    element_info = {
        'path': 'IED1/LD0/GGIO1.Ind1.stVal',
        'value': 'true',
        'iec_type': 'BOOLEAN',
        'da_name': 'stVal',
        'do_name': 'Ind1',
        'ln_class': 'GGIO'
    }
    
    dialog = GOOSESendDialog(element_info)
    
    def on_goose_send(items):
        print("GOOSE Send requested:")
        for item in items:
            print(f"  {item.path} = {item.value} ({item.goose_type})")
    
    dialog.goose_send_requested.connect(on_goose_send)
    
    dialog.show()
    sys.exit(app.exec())