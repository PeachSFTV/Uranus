#!/usr/bin/env python3
"""
Address Editor Dialog for Virtual IED
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Edit GOOSE APP ID and MAC Address
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel,
    QGroupBox, QMessageBox, QScrollArea, QWidget
)
from PyQt6.QtCore import pyqtSignal
from typing import Dict, List, Any

def debug_log(msg: str):
    """Debug logging helper"""
    print(f"[DEBUG] {msg}")

class AddressEditorDialog(QDialog):
    """Dialog for editing GOOSE Address configurations (APP ID, MAC)"""
    
    config_changed = pyqtSignal(dict)  # Signal when config is changed
    
    def __init__(self, ied_configs, goose_configs, parent=None):
        super().__init__(parent)
        
        # Store configs
        self.ied_configs = ied_configs  # List of IED configs
        self.goose_configs = goose_configs  # Dict of GOOSE configs
        
        # Runtime configs (will be modified)
        self.runtime_goose_configs = {}
        
        # Initialize runtime configs from originals
        self._init_runtime_configs()
        
        # Current editing widgets
        self.current_widgets = {}
        
        # Setup UI
        self.setup_ui()
        
    def _init_runtime_configs(self):
        """Initialize runtime configs from original configs"""
        debug_log(f"Initializing runtime configs")
        debug_log(f"IED configs count: {len(self.ied_configs)}")
        debug_log(f"GOOSE configs count: {len(self.goose_configs)}")
        
        # Copy GOOSE configs
        for key, config in self.goose_configs.items():
            if hasattr(config, 'to_dict'):
                self.runtime_goose_configs[key] = config.to_dict()
            elif isinstance(config, dict):
                self.runtime_goose_configs[key] = config.copy()
            else:
                # Create basic dict if config is a different type
                self.runtime_goose_configs[key] = {
                    'app_id': 0x0001,
                    'dst_mac': '01:0C:CD:01:00:00',
                    'go_id': 'DefaultGOOSE',
                    'dataset_ref': 'Dataset1'
                }
            debug_log(f"Added GOOSE config for {key}: {self.runtime_goose_configs[key]}")
        
        debug_log(f"Runtime configs initialized - GOOSE: {len(self.runtime_goose_configs)}")
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("🔧 Edit GOOSE Configuration")
        self.setMinimumSize(600, 400)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # IED Selection
        selection_group = QGroupBox("Select Virtual IED")
        selection_layout = QHBoxLayout()
        
        self.ied_combo = QComboBox()
        self.ied_combo.setMinimumWidth(300)
        selection_layout.addWidget(QLabel("IED:"))
        selection_layout.addWidget(self.ied_combo)
        selection_layout.addStretch()
        
        selection_group.setLayout(selection_layout)
        main_layout.addWidget(selection_group)
        
        # Configuration area (scrollable)
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.config_layout = QVBoxLayout(scroll_widget)
        
        # Placeholder for configuration widgets
        self.config_container = QWidget()
        self.config_container_layout = QVBoxLayout(self.config_container)
        self.config_layout.addWidget(self.config_container)
        self.config_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("✅ Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        
        self.reset_btn = QPushButton("🔄 Reset to Default")
        self.reset_btn.clicked.connect(self.reset_current_ied)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
        
        # Populate IED combo
        self.populate_ied_combo()
        
        # Connect signals
        self.ied_combo.currentIndexChanged.connect(self.on_ied_index_changed)
        
        # Select first IED if available
        if self.ied_combo.count() > 0:
            self.ied_combo.setCurrentIndex(0)
            self.on_ied_index_changed(0)
    
    def on_ied_index_changed(self, index):
        """Handle IED combo box index change"""
        if index < 0:
            return
        
        ied_name = self.ied_combo.currentData()
        if ied_name:
            self.on_ied_selected(ied_name)
    
    def populate_ied_combo(self):
        """Populate IED combo box"""
        self.ied_combo.clear()
        
        for config in self.ied_configs:
            ied_name = config['ied_name']
            display_text = f"🏭 {ied_name}"
            self.ied_combo.addItem(display_text, ied_name)
    
    def on_ied_selected(self, ied_name):
        """Handle IED selection"""
        # Clear current widgets
        self.clear_config_widgets()
        
        # Create configuration widgets for selected IED
        self.create_config_widgets(ied_name)
    
    def clear_config_widgets(self):
        """Clear current configuration widgets"""
        # Clear container
        while self.config_container_layout.count():
            child = self.config_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.current_widgets.clear()
    
    def create_config_widgets(self, ied_name):
        """Create configuration widgets for selected IED"""
        debug_log(f"Creating config widgets for IED: {ied_name}")
        
        # Find matching GOOSE config
        goose_config = None
        goose_key = None
        
        for key in self.runtime_goose_configs:
            if ied_name in key:
                goose_config = self.runtime_goose_configs[key]
                goose_key = key
                debug_log(f"Found GOOSE config: {key}")
                break
        
        # Virtual IED Info
        info_label = QLabel("🤖 Virtual IED - GOOSE Configuration Only")
        info_label.setStyleSheet("color: blue; font-style: italic; padding: 10px;")
        self.config_container_layout.addWidget(info_label)
        
        # GOOSE Configuration Group
        if goose_config:
            goose_group = QGroupBox(f"GOOSE Configuration - {goose_key}")
            goose_layout = QFormLayout()
            
            # APP ID
            appid_edit = QLineEdit()
            current_appid = goose_config.get('app_id', 0x0001)
            if isinstance(current_appid, int):
                appid_edit.setText(f"0x{current_appid:04X}")
            else:
                appid_edit.setText(str(current_appid))
            appid_edit.setPlaceholderText("e.g., 0x0001 or 1")
            appid_edit.textChanged.connect(self.on_config_changed)
            goose_layout.addRow("APP ID:", appid_edit)
            self.current_widgets['app_id'] = appid_edit
            
            # MAC Address
            mac_edit = QLineEdit()
            mac_edit.setText(goose_config.get('dst_mac', '01:0C:CD:01:00:00'))
            mac_edit.setPlaceholderText("e.g., 01:0C:CD:01:00:00")
            mac_edit.textChanged.connect(self.on_config_changed)
            goose_layout.addRow("Destination MAC:", mac_edit)
            self.current_widgets['dst_mac'] = mac_edit
            
            # MAC Address info
            mac_info = QLabel("ℹ️ IEC 61850 GOOSE MAC range: 01:0C:CD:01:00:00 - 01:0C:CD:01:01:FF")
            mac_info.setStyleSheet("color: gray; font-size: 10px;")
            goose_layout.addRow("", mac_info)
            
            # Other info (display only)
            goose_layout.addRow("GoID:", QLabel(goose_config.get('go_id', '')))
            goose_layout.addRow("Dataset:", QLabel(goose_config.get('dataset_ref', '')))
            
            goose_group.setLayout(goose_layout)
            self.config_container_layout.addWidget(goose_group)
            
            # Store goose key for later
            self.current_widgets['goose_key'] = goose_key
        else:
            # No GOOSE config found
            no_goose_label = QLabel("⚠️ No GOOSE configuration found for this IED")
            no_goose_label.setStyleSheet("color: orange; padding: 10px;")
            self.config_container_layout.addWidget(no_goose_label)
        
        # Store current IED name
        self.current_widgets['ied_name'] = ied_name
    
    def on_config_changed(self):
        """Handle configuration value change"""
        self.apply_btn.setEnabled(True)
    
    def validate_inputs(self):
        """Validate current inputs"""
        errors = []
        
        # Validate APP ID
        if 'app_id' in self.current_widgets:
            appid_text = self.current_widgets['app_id'].text().strip()
            try:
                if appid_text.startswith('0x') or appid_text.startswith('0X'):
                    value = int(appid_text, 16)
                else:
                    value = int(appid_text)
                
                # Check range (0x0000 - 0xFFFF)
                if value < 0 or value > 0xFFFF:
                    errors.append("APP ID must be between 0x0000 and 0xFFFF")
            except:
                errors.append("Invalid APP ID format (use hex 0x0001 or decimal 1)")
        
        # Validate MAC Address
        if 'dst_mac' in self.current_widgets:
            mac_text = self.current_widgets['dst_mac'].text().strip()
            mac_parts = mac_text.split(':')
            if len(mac_parts) != 6:
                errors.append("MAC Address must have 6 parts (XX:XX:XX:XX:XX:XX)")
            else:
                try:
                    for part in mac_parts:
                        if len(part) != 2:
                            raise ValueError()
                        int(part, 16)
                    
                    # Check if it's in GOOSE range
                    if mac_text.startswith("01:0C:CD:01:"):
                        # Valid GOOSE MAC
                        pass
                    else:
                        errors.append("Warning: MAC is outside IEC 61850 GOOSE range (01:0C:CD:01:00:00-FF)")
                except:
                    errors.append("Invalid MAC Address format")
        
        return errors
    
    def apply_changes(self):
        """Apply configuration changes"""
        # Validate inputs
        errors = self.validate_inputs()
        if errors:
            QMessageBox.warning(self, "Validation Error", 
                              "Please fix the following:\n\n" + "\n".join(errors))
            return
        
        # Get current IED
        ied_name = self.current_widgets.get('ied_name')
        if not ied_name:
            return
        
        # Update GOOSE config
        goose_key = self.current_widgets.get('goose_key')
        if goose_key and goose_key in self.runtime_goose_configs:
            goose_config = self.runtime_goose_configs[goose_key]
            
            # Update APP ID
            if 'app_id' in self.current_widgets:
                appid_text = self.current_widgets['app_id'].text().strip()
                if appid_text.startswith('0x') or appid_text.startswith('0X'):
                    goose_config['app_id'] = int(appid_text, 16)
                else:
                    goose_config['app_id'] = int(appid_text)
            
            # Update MAC
            if 'dst_mac' in self.current_widgets:
                goose_config['dst_mac'] = self.current_widgets['dst_mac'].text().strip()
        
        # Emit signal with all runtime configs
        self.config_changed.emit({
            'goose_configs': self.runtime_goose_configs
        })
        
        self.apply_btn.setEnabled(False)
        
        # Show confirmation
        QMessageBox.information(self, "Success", 
                              f"✅ GOOSE configuration updated for {ied_name}\n\n" +
                              "Changes will be applied when the system starts.")
    
    def reset_current_ied(self):
        """Reset current IED to default values"""
        ied_name = self.current_widgets.get('ied_name')
        if not ied_name:
            return
        
        # Find original config
        goose_key = self.current_widgets.get('goose_key')
        if goose_key and goose_key in self.goose_configs:
            original_goose = self.goose_configs[goose_key]
            if hasattr(original_goose, 'to_dict'):
                self.runtime_goose_configs[goose_key] = original_goose.to_dict()
            else:
                self.runtime_goose_configs[goose_key] = original_goose.copy()
            
            # Refresh display
            self.on_ied_selected(ied_name)
            
            QMessageBox.information(self, "Reset", 
                                  f"🔄 Configuration reset to default for {ied_name}")