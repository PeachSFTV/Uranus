#!/usr/bin/env python3
"""
IEC 61850 DA Value Editor Dialog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dialog for editing Data Attribute values according to IEC 61850 standard
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QDialogButtonBox, QGroupBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import time

class DAValueEditorDialog(QDialog):
    """Dialog for editing DA values according to IEC 61850"""
    
    # Signal emitted when value is changed
    value_changed = pyqtSignal(str, object)  # da_name, new_value
    
    # DA definitions based on IEC 61850
    DA_DEFINITIONS = {
        'stVal': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Status value'
        },
        'q': {
            'type': 'Quality',
            'widget': 'HexInput',
            'default': '0x0000',
            'description': 'Quality flags'
        },
        't': {
            'type': 'Timestamp',
            'widget': 'Label',
            'description': 'UTC Timestamp (Read-only)'
        },
        'ctlVal': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Control value'
        },
        'operRcvd': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Operation received'
        },
        'operOk': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Operation OK'
        },
        'general': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'General trip/close'
        },
        'Health': {
            'type': 'ENUMERATED',
            'widget': 'ComboBox',
            'values': [('Ok', 1), ('Warning', 2), ('Alarm', 3)],
            'description': 'Health status'
        },
        'blkEna': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Block enable'
        },
        'Beh': {
            'type': 'ENUMERATED',
            'widget': 'ComboBox',
            'values': [
                ('on', 1),
                ('blocked', 2),
                ('test', 3),
                ('test/blocked', 4),
                ('off', 5)
            ],
            'description': 'Behavior'
        },
        'Mod': {
            'type': 'ENUMERATED',
            'widget': 'ComboBox',
            'values': [
                ('on', 1),
                ('blocked', 2),
                ('test', 3),
                ('test/blocked', 4),
                ('off', 5)
            ],
            'description': 'Mode'
        },
        'mag': {
            'type': 'FLOAT32',
            'widget': 'SpinBox',
            'description': 'Magnitude'
        },
        'db': {
            'type': 'FLOAT32',
            'widget': 'SpinBox',
            'description': 'Deadband'
        },
        'zeroDb': {
            'type': 'INT32U',
            'widget': 'SpinBox',
            'description': 'Zero deadband'
        },
        'smpRate': {
            'type': 'INT32U',
            'widget': 'SpinBox',
            'description': 'Sample rate'
        },
        'ctlNum': {
            'type': 'INT8U',
            'widget': 'Label',
            'description': 'Control number (Read-only)'
        },
        'T': {
            'type': 'Timestamp',
            'widget': 'Label',
            'description': 'Control timestamp (Read-only)'
        },
        'Test': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Test mode'
        },
        'Oper': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Operate'
        },
        'Cancel': {
            'type': 'BOOLEAN',
            'widget': 'ComboBox',
            'values': [('false', False), ('true', True)],
            'description': 'Cancel operation'
        }
    }
    
    def __init__(self, da_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.da_name = da_info.get('name', '')
        self.da_path = da_info.get('path', '')
        self.current_value = da_info.get('value', '')
        self.element_info = da_info
        
        self.new_value = None
        self.value_widget = None
        
        self.setup_ui()
        self.setWindowTitle(f"Edit DA Value - {self.da_name}")
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Info section
        info_group = QGroupBox("Data Attribute Information")
        info_layout = QVBoxLayout()
        
        info_layout.addWidget(QLabel(f"<b>Path:</b> {self.da_path}"))
        info_layout.addWidget(QLabel(f"<b>DA Name:</b> {self.da_name}"))
        
        # Get DA definition
        da_def = self.DA_DEFINITIONS.get(self.da_name, {})
        if da_def:
            info_layout.addWidget(QLabel(f"<b>Type:</b> {da_def.get('type', 'Unknown')}"))
            info_layout.addWidget(QLabel(f"<b>Description:</b> {da_def.get('description', '')}"))
        
        info_layout.addWidget(QLabel(f"<b>Current Value:</b> {self.current_value}"))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Value editor section
        editor_group = QGroupBox("Edit Value")
        editor_layout = QVBoxLayout()
        
        # Create appropriate widget based on DA type
        self.value_widget = self.create_value_widget()
        if self.value_widget:
            editor_layout.addWidget(self.value_widget)
        else:
            editor_layout.addWidget(QLabel("This DA type is not editable"))
        
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept_value)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_value_widget(self):
        """Create appropriate widget based on DA type"""
        da_def = self.DA_DEFINITIONS.get(self.da_name, {})
        widget_type = da_def.get('widget', 'Label')
        
        if widget_type == 'ComboBox':
            widget = QComboBox()
            values = da_def.get('values', [])
            
            # Add values to combo box
            current_index = 0
            for i, (label, value) in enumerate(values):
                widget.addItem(label, value)
                # Set current value
                if str(value) == str(self.current_value) or label == str(self.current_value):
                    current_index = i
            
            widget.setCurrentIndex(current_index)
            return widget
        
            # ใน da_value_editor_dialog.py - แก้ไขส่วน create_value_widget()

        elif widget_type == 'HexInput':
            # Create hybrid widget for Quality
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
    
            # ComboBox for common values
            combo = QComboBox()
            combo.addItem("Good", "0x0000")
            combo.addItem("Invalid", "0x0001")
            combo.addItem("Questionable", "0x0003")
            combo.addItem("Old Data", "0x0040")
            combo.addItem("Test Mode", "0x0800")
            combo.addItem("Blocked", "0x0400")
            combo.addItem("Invalid + Old", "0x0041")
            combo.addItem("Custom...", "custom")
    
            # LineEdit for custom hex value
            hex_edit = QLineEdit()
            hex_edit.setPlaceholderText("0x0000")
            hex_edit.setVisible(False)
            hex_edit.setMaximumWidth(100)
    
            # Set current value
            current_hex = str(self.current_value) if self.current_value else '0x0000'
    
            # Check if it's a standard value
            standard_found = False
            for i in range(combo.count() - 1):  # Exclude "Custom..."
                if combo.itemData(i) == current_hex:
                    combo.setCurrentIndex(i)
                    standard_found = True
                    break
    
            if not standard_found:
                # Set to Custom and show hex edit
                combo.setCurrentIndex(combo.count() - 1)  # Custom
                hex_edit.setText(current_hex)
                hex_edit.setVisible(True)
    
            # Handle combo change
            def on_combo_changed(index):
                if combo.itemData(index) == "custom":
                    hex_edit.setVisible(True)
                    hex_edit.setFocus()
                else:
                    hex_edit.setVisible(False)
    
            combo.currentIndexChanged.connect(on_combo_changed)
    
            # Validate hex input
            def validate_hex():
                text = hex_edit.text()
                if not text.startswith('0x'):
                    hex_edit.setText('0x' + text)
    
            hex_edit.editingFinished.connect(validate_hex)
    
            # Add to layout
            layout.addWidget(QLabel("Quality:"))
            layout.addWidget(combo)
            layout.addWidget(hex_edit)
            layout.addStretch()
    
            # Store references for value retrieval
            container.combo = combo
            container.hex_edit = hex_edit
    
            return container
        
        elif widget_type == 'SpinBox':
            if da_def.get('type') in ['FLOAT32', 'FLOAT64']:
                widget = QDoubleSpinBox()
                widget.setDecimals(6)
                widget.setRange(-1e9, 1e9)
                try:
                    widget.setValue(float(self.current_value))
                except:
                    widget.setValue(0.0)
            else:
                widget = QSpinBox()
                if 'U' in da_def.get('type', ''):  # Unsigned
                    widget.setRange(0, 2147483647)
                else:
                    widget.setRange(-2147483648, 2147483647)
                try:
                    widget.setValue(int(self.current_value))
                except:
                    widget.setValue(0)
            return widget
        
        elif widget_type == 'Label':
            widget = QLabel()
            if self.da_name in ['t', 'T']:
                # Show timestamp
                try:
                    ts = int(self.current_value) / 1000  # Convert from ms
                    dt = datetime.fromtimestamp(ts)
                    widget.setText(dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
                except:
                    widget.setText(str(self.current_value))
            else:
                widget.setText(str(self.current_value))
            
            widget.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; }")
            return widget
        
        else:
            # Default to line edit
            widget = QLineEdit()
            widget.setText(str(self.current_value))
            return widget
    
    def accept_value(self):
        """Accept the edited value"""
        if not self.value_widget:
            self.reject()
            return
    
        # Get value based on widget type
        if isinstance(self.value_widget, QComboBox):
            self.new_value = self.value_widget.currentData()
    
        # เพิ่มส่วนนี้สำหรับ Hybrid Quality widget
        elif isinstance(self.value_widget, QWidget) and hasattr(self.value_widget, 'combo'):
            # Hybrid widget (for Quality)
            combo = self.value_widget.combo
            hex_edit = self.value_widget.hex_edit
        
            if combo.currentData() == "custom":
                # Get custom hex value
                text = hex_edit.text()
                try:
                    self.new_value = int(text, 16)
                except:
                    self.new_value = 0
            else:
                # Get preset value
                hex_str = combo.currentData()
                try:
                    self.new_value = int(hex_str, 16)
                except:
                    self.new_value = 0
    
        elif isinstance(self.value_widget, QLineEdit):
            text = self.value_widget.text()
            # Handle hex values (for other hex inputs if any)
            if self.da_name == 'q' and text.startswith('0x'):
                try:
                    self.new_value = int(text, 16)
                except:
                    self.new_value = 0
            else:
                self.new_value = text
            
        elif isinstance(self.value_widget, (QSpinBox, QDoubleSpinBox)):
             self.new_value = self.value_widget.value()
        
        elif isinstance(self.value_widget, QLabel):
            # Read-only, no change
            self.new_value = self.current_value
    
        # Emit signal
        self.value_changed.emit(self.da_name, self.new_value)
    
        self.accept()
    
    def get_value(self) -> Tuple[str, Any]:
        """Get the DA name and new value"""
        return self.da_name, self.new_value