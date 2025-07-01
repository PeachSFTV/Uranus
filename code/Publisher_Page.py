#!/usr/bin/env python3
"""
Virtual IED System - IEC 61850 GOOSE Publisher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure software IED that publishes GOOSE messages
No hardware connections required
Fixed version with safety features for commissioning
"""

from ui_helper import load_ui_safe, UIHelper
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QListWidget, QTreeWidget, QListWidgetItem,
    QTreeWidgetItem, QMessageBox, QComboBox, QPlainTextEdit,
    QMenu, QDialog, QCheckBox, QLabel, QVBoxLayout, QHBoxLayout, 
    QDialogButtonBox, QFileDialog, QApplication, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from pathlib import Path
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from resource_helper import get_ui_path

# Import enhanced wrapper
from pyiec61850_wrapper import (
    IEC61850System,
    IEDElement,
    GOOSEManager,
    debug_log
)

# Import IEDScout view manager
from iec61850_system.iedscout_view_manager import IEDScoutViewManager, IEDScoutItem

# Import DA Value Editor Dialog
from iec61850_system.da_value_editor_dialog import DAValueEditorDialog

# Import time sync utilities
try:
    from iec61850_system.time_sync_utils import (
        get_synchronized_timestamp_ms,
        check_time_synchronization
    )
    TIME_SYNC_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: time_sync_utils not found, using system time")
    TIME_SYNC_AVAILABLE = False
    
    def get_synchronized_timestamp_ms():
        return int(time.time() * 1000)
    
    def check_time_synchronization():
        return False, None

# ==================== Constants ====================

# IEC 61850-8-1 Retransmission intervals (milliseconds)
# T0=2ms, T1=10ms, T2=100ms, T3=1000ms per standard
IEC61850_RETRANSMISSION_INTERVALS = [2, 4, 8, 10, 20, 40, 80, 100, 200, 400, 800, 1000]

# Safe default values for Virtual IED
SAFE_DEFAULT_VALUES = {
    'boolean': False,      # CB=Open, Switch=Off
    'integer': 0,         
    'unsigned': 0,        
    'float': 0.0,         
    'visible-string': '',
    'bit-string': 0x0000,  # Good quality
    'utc-time': None,      # Will use current time
    'binary-time': None
}

# ==================== IED Selection Dialog ====================

class IEDSelectionDialog(QDialog):
    """Simple IED Selection Dialog"""
    
    def __init__(self, ied_configs, parent=None):
        super().__init__(parent)
        self.ied_configs = ied_configs
        self.selected_ieds = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Select Virtual IEDs")
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🤖 Select Virtual IEDs to Simulate")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # IED List
        self.ied_list = QListWidget()
        layout.addWidget(self.ied_list)
        
        # Populate list
        for config in self.ied_configs:
            item = QListWidgetItem(f"🏭 {config['ied_name']}")
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

# ==================== Main Virtual IED System ====================

class VirtualIEDSystem(QWidget):
    """Pure Virtual IED System - GOOSE Publisher Only"""
    
    def __init__(self, back_to_main_ui):
        super().__init__()
        
        # Load UI
        ui_file = get_ui_path('Publisher_Page.ui')
        widget = load_ui_safe(ui_file)
        if widget:
            # Copy widget attributes
            for attr in dir(widget):
                if not attr.startswith('_'):
                    try:
                        setattr(self, attr, getattr(widget, attr))
                    except:
                        pass
        # Then you need to extract widgets from the loaded widget

        self.fileslist_button = self.findChild(QPushButton, 'fileslist_button')
        self.fileslist_show = self.findChild(QListWidget, 'fileslist_show')
        self.ied_tree = self.findChild(QTreeWidget, 'ied_tree')
        self.start_system_btn = self.findChild(QPushButton, 'start_system_btn')
        self.stop_system_btn = self.findChild(QPushButton, 'stop_system_btn')
        self.back_button = self.findChild(QPushButton, 'back_button')
        self.network_interface_combo = self.findChild(QComboBox, 'network_interface_combo')
        self.external_goose_checkbox = self.findChild(QCheckBox, 'external_goose_checkbox')
        self.test_mode_checkbox = self.findChild(QCheckBox, 'test_mode_checkbox')
        self.pub_log = self.findChild(QPlainTextEdit, 'pub_log')
        self.sub_log = self.findChild(QPlainTextEdit, 'sub_log')
        self.logs_tab_widget = self.findChild(QWidget, 'logs_tab_widget')  # Find the tab widget
        self.time_sync_status = self.findChild(QLabel, 'time_sync_status')
        self.system_status_text = self.findChild(QPlainTextEdit, 'system_status_text')
    
        # Add other widgets as needed...
        self.edit_addr_btn = self.findChild(QPushButton, 'edit_addr_btn')
        self.monitor_goose_btn = self.findChild(QPushButton, 'monitor_goose_btn')
        self.export_data_btn = self.findChild(QPushButton, 'export_data_btn')
        self.clear_mms_log_btn = self.findChild(QPushButton, 'clear_mms_log_btn')
        self.clear_goose_log_btn = self.findChild(QPushButton, 'clear_goose_log_btn')
        self.save_mms_log_btn = self.findChild(QPushButton, 'save_mms_log_btn')
        self.save_goose_log_btn = self.findChild(QPushButton, 'save_goose_log_btn')
        
        # Core attributes
        self.back_to_main_ui = back_to_main_ui
        self.iec61850_system = None
        self.current_scl_data = None
        self.selected_ied_configs = []
        self.system_running = False
        
        # GOOSE related
        self.goose_datasets = {}  # dataset_ref -> list of DA paths
        self.dataset_values = {}  # path -> current value
        self.dataset_defaults = {}  # path -> default value
        self.goose_heartbeat_timer = None
        
        # Store original GOOSE configs from SCL file
        self.original_goose_configs = {}
        
        # Store user modified configs
        self.user_modified_configs = {
            'goose_configs': {}
        }
        
        # File management
        self.root_dir = Path(__file__).parent.parent / 'upload_file' / 'after_convert'
        self.current_folder = None
        self.current_file = None
        
        # IEDScout view manager
        self.iedscout_manager = IEDScoutViewManager(self.ied_tree)
        self.iedscout_manager.item_edited.connect(self.on_iedscout_item_edited)
        
        # Statistics
        self.stats = {
            'goose_sent': 0,
            'start_time': None
        }
        
        # Safety features
        self.test_mode = True  # Default to test mode for safety
        self.goose_monitor_timer = None
        self.monitored_goose = {}
        
        # Time sync status
        self.time_sync_timer = QTimer()
        self.time_sync_timer.timeout.connect(self.check_time_sync_status)
        self.time_sync_timer.start(5000)  # Check every 5 seconds
        
        # Setup
        self.setup_ui()
        self.setup_connections()
        
        print("✅ Virtual IED System initialized")
    
    def setup_ui(self):
        """Setup UI components"""
        # Set window title
        self.setWindowTitle("Virtual IED System - IEC 61850 GOOSE Publisher")
        
        # Hide unnecessary components
        self.hide_unused_components()
        
        # Setup IEDScout headers
        self.iedscout_manager.setup_iedscout_view()
        
        # Initial states
        self.stop_system_btn.setEnabled(False)
        self.external_goose_checkbox.setChecked(True)
        self.external_goose_checkbox.setVisible(False)  # Always enabled
        
        # Setup test mode checkbox if exists
        if hasattr(self, 'test_mode_checkbox'):
            self.test_mode_checkbox.setChecked(True)
            self.test_mode_checkbox.toggled.connect(self.on_test_mode_changed)
        
        # Fonts
        tree_font = QFont("Consolas", 9)
        self.ied_tree.setFont(tree_font)
        
        log_font = QFont("Consolas", 8)
        self.pub_log.setFont(log_font)
        self.sub_log.setFont(log_font)
        
        # Setup tabs
        self.setup_tab_widget()
        
        # Populate network interfaces
        self.populate_network_interfaces()
        
        # Initial messages
        self.update_status("🤖 Virtual IED System ready. Load SCL file to begin.")
        self.pub_log.setPlainText("=== 📤 Virtual IED System Log ===")
        self.sub_log.setPlainText("=== 📡 GOOSE Multicast Log ===")
        
        # Check time sync on startup
        self.check_time_sync_status()
    
    def hide_unused_components(self):
        """Hide components not needed for Virtual IED"""
        # Hide connection related
        if hasattr(self, 'discover_ieds_btn'):
            self.discover_ieds_btn.setVisible(False)
        if hasattr(self, 'test_connectivity_btn'):
            self.test_connectivity_btn.setVisible(False)
        if hasattr(self, 'read_all_btn'):
            self.read_all_btn.setVisible(False)
        
        # Hide view mode buttons
        if hasattr(self, 'iedscout_view_btn'):
            self.iedscout_view_btn.setVisible(False)
        if hasattr(self, 'traditional_view_btn'):
            self.traditional_view_btn.setVisible(False)
        
        # Hide statistics labels
        for attr in ['total_ieds_label', 'total_ieds_value', 'connected_ieds_label', 
                    'connected_ieds_value', 'mms_operations_label', 'mms_operations_value']:
            if hasattr(self, attr):
                getattr(self, attr).setVisible(False)
    
    def setup_tab_widget(self):
        """Setup tab widget for logs"""
        self.logs_tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Initially show Virtual IED log
        self.pub_log.setVisible(True)
        self.sub_log.setVisible(False)
        
        # Update tab labels
        self.logs_tab_widget.setTabText(0, "Virtual IED Log")
        self.logs_tab_widget.setTabText(1, "GOOSE Multicast")
        
        # Hide events tab if exists
        if self.logs_tab_widget.count() > 2:
            self.logs_tab_widget.removeTab(2)
    
    def on_tab_changed(self, index: int):
        """Handle tab change"""
        self.pub_log.setVisible(index == 0)
        self.sub_log.setVisible(index == 1)
    
    def setup_connections(self):
        """Setup signal connections"""
        # File management
        self.fileslist_button.clicked.connect(self.load_files)
        self.fileslist_show.itemDoubleClicked.connect(self.open_file)
        
        # System control
        self.start_system_btn.clicked.connect(self.start_system)
        self.stop_system_btn.clicked.connect(self.stop_system)
        self.back_button.clicked.connect(self.back_to_main_ui)
        
        # Tree
        self.ied_tree.itemDoubleClicked.connect(self.on_tree_double_click)
        self.ied_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ied_tree.customContextMenuRequested.connect(self.show_tree_menu)
        
        # Address Editor
        if hasattr(self, 'edit_addr_btn'):
            self.edit_addr_btn.clicked.connect(self.open_address_editor)
        
        # Monitor GOOSE button
        if hasattr(self, 'monitor_goose_btn'):
            self.monitor_goose_btn.clicked.connect(self.monitor_goose_traffic)
        
        # Test mode checkbox
        if hasattr(self, 'test_mode_checkbox'):
            self.test_mode_checkbox.toggled.connect(self.on_test_mode_changed)
        
        # Export data
        if hasattr(self, 'export_data_btn'):
            self.export_data_btn.clicked.connect(self.export_data)
        
        # Log controls
        self.clear_mms_log_btn.clicked.connect(lambda: self.pub_log.clear())
        self.clear_goose_log_btn.clicked.connect(lambda: self.sub_log.clear())
        self.save_mms_log_btn.clicked.connect(self.save_virtual_log)
        self.save_goose_log_btn.clicked.connect(self.save_goose_log)
    
    def populate_network_interfaces(self):
        """Populate network interfaces"""
        self.network_interface_combo.clear()
        
        try:
            import netifaces
            interfaces = []
            for iface in netifaces.interfaces():
                if any(iface.startswith(prefix) for prefix in ['eth', 'enp', 'ens', 'wlp']):
                    interfaces.append(iface)
            
            if interfaces:
                self.network_interface_combo.addItems(sorted(interfaces))
            else:
                self.network_interface_combo.addItem("eth0")
        except:
            # Default interfaces
            self.network_interface_combo.addItems(["eth0", "enp42s0", "enp0s3"])
    
    def load_files(self):
        """Load SCL files from directory"""
        try:
            self.fileslist_show.clear()
            self.current_folder = None
            
            if not self.root_dir.exists():
                self.fileslist_show.addItem("❌ after_convert folder not found")
                return
            
            # List folders
            for folder in sorted(self.root_dir.iterdir()):
                if folder.is_dir():
                    self.fileslist_show.addItem(f"📁 {folder.name}")
            
            self.update_status(f"📂 Found {self.fileslist_show.count()} folders")
            
        except Exception as e:
            self.update_status(f"❌ Error loading files: {e}")
    
    def open_file(self, item: QListWidgetItem):
        """Open folder or file"""
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
            self.update_status(f"❌ Error opening: {e}")
    
    def show_folder_contents(self):
        """Show contents of selected folder"""
        try:
            self.fileslist_show.clear()
            self.fileslist_show.addItem("⬅️ Back to folders")
            
            # List SCL and JSON files
            files = list(self.current_folder.glob("*.scl")) + list(self.current_folder.glob("*.json"))
            
            for file in sorted(files):
                icon = "📄" if file.suffix == ".scl" else "📋"
                self.fileslist_show.addItem(f"{icon} {file.name}")
            
            self.update_status(f"📁 {self.current_folder.name}: {len(files)} files")
            
        except Exception as e:
            self.update_status(f"❌ Error reading folder: {e}")
    
    def load_scl_file(self, file_path: Path):
        """Load SCL or JSON file"""
        try:
            self.update_status(f"📖 Loading {file_path.name}...")
            
            # Load JSON
            if file_path.suffix == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.current_scl_data = json.load(f)
            else:
                # Try to find corresponding JSON
                json_path = file_path.with_suffix('.json')
                if json_path.exists():
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.current_scl_data = json.load(f)
                else:
                    QMessageBox.warning(self, "File Error", "No JSON file found for SCL")
                    return
            
            self.current_file = file_path
            self.process_scl_data()
            
        except Exception as e:
            self.update_status(f"❌ Error loading file: {e}")
            QMessageBox.critical(self, "Load Error", f"Cannot load file:\n{e}")
    
    def process_scl_data(self):
        """Process loaded SCL data"""
        try:
            if not self.current_scl_data:
                return
            
            # Extract IED configurations
            ied_configs = self.extract_ied_configs()
            
            if not ied_configs:
                QMessageBox.warning(self, "No IEDs", "No IEDs found in SCL file")
                return
            
            # Initialize system
            interface = self.network_interface_combo.currentText()
            self.iec61850_system = IEC61850System(interface)
            
            # Extract GOOSE configs from SCL
            self.iec61850_system.goose_manager._extract_goose_config_from_scl(self.current_scl_data)
            
            # Store original GOOSE configs (before any user modifications)
            self.original_goose_configs = {}
            if hasattr(self.iec61850_system.goose_manager, 'all_goose_configs'):
                for key, config in self.iec61850_system.goose_manager.all_goose_configs.items():
                    self.original_goose_configs[key] = config.to_dict() if hasattr(config, 'to_dict') else config
            
            debug_log(f"📌 Stored {len(self.original_goose_configs)} original GOOSE configs")
            
            # Clear user modifications when loading new file
            self.user_modified_configs = {
                'goose_configs': {}
            }
            
            # Extract dataset configurations
            self.extract_goose_datasets()
            
            # Show selection dialog
            dialog = IEDSelectionDialog(ied_configs, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.selected_ied_configs = dialog.get_selected_ieds()
                
                if self.selected_ied_configs:
                    self.build_tree()
                    self.start_system_btn.setEnabled(True)
                    
                    names = [c['ied_name'] for c in self.selected_ied_configs]
                    self.update_status(f"✅ Selected {len(names)} Virtual IEDs: {', '.join(names)}")
                else:
                    self.update_status("❌ No IEDs selected")
            
        except Exception as e:
            self.update_status(f"❌ Error processing SCL: {e}")
    
    def extract_ied_configs(self) -> List[Dict]:
        """Extract IED configurations from SCL"""
        configs = []
        
        try:
            if 'SCL' not in self.current_scl_data:
                return configs
            
            # Get IEDs
            ieds = self.current_scl_data['SCL'].get('IED', [])
            if not isinstance(ieds, list):
                ieds = [ieds]
            
            # Extract basic info
            for ied in ieds:
                config = {
                    'ied_name': ied.get('@name', 'Unknown'),
                    'manufacturer': ied.get('@manufacturer', ''),
                    'type': ied.get('@type', ''),
                    'desc': ied.get('@desc', '')
                }
                configs.append(config)
            
        except Exception as e:
            print(f"Error extracting IED configs: {e}")
        
        return configs
    
    def extract_goose_datasets(self):
        """Extract GOOSE dataset configuration from SCL"""
        if not self.current_scl_data:
            return
        
        self.goose_datasets.clear()
        self.log_virtual("📊 Extracting GOOSE datasets from SCL...")
        
        # Navigate through SCL structure
        ieds = self.current_scl_data.get('SCL', {}).get('IED', [])
        if not isinstance(ieds, list):
            ieds = [ieds]
        
        for ied in ieds:
            ied_name = ied.get('@name')
            
            # Get AccessPoints
            aps = ied.get('AccessPoint', [])
            if not isinstance(aps, list):
                aps = [aps]
            
            for ap in aps:
                server = ap.get('Server', {})
                lds = server.get('LDevice', [])
                if not isinstance(lds, list):
                    lds = [lds]
                
                for ld in lds:
                    ld_inst = ld.get('@inst')
                    ln0 = ld.get('LN0', {})
                    
                    # Find GSEControl
                    gse_controls = ln0.get('GSEControl', [])
                    if not isinstance(gse_controls, list):
                        gse_controls = [gse_controls]
                    
                    for gse in gse_controls:
                        dataset_name = gse.get('@datSet')
                        if dataset_name:
                            # Build dataset reference
                            dataset_ref = f"{ied_name}/{ld_inst}/LLN0${dataset_name}"
                            
                            # Find dataset definition
                            datasets = ln0.get('DataSet', [])
                            if not isinstance(datasets, list):
                                datasets = [datasets]
                            
                            for ds in datasets:
                                if ds.get('@name') == dataset_name:
                                    # Extract FCDA (dataset members)
                                    fcdas = ds.get('FCDA', [])
                                    if not isinstance(fcdas, list):
                                        fcdas = [fcdas]
                                    
                                    da_paths = []
                                    for fcda in fcdas:
                                        path = self._build_da_path_from_fcda(ied_name, ld_inst, fcda)
                                        if path:
                                            da_paths.append(path)
                                    
                                    self.goose_datasets[dataset_ref] = da_paths
                                    self.log_virtual(f"   📌 {dataset_ref}: {len(da_paths)} items")
        
        self.log_virtual(f"✅ Extracted {len(self.goose_datasets)} GOOSE datasets")
    
    def _build_da_path_from_fcda(self, ied_name: str, ld_inst: str, fcda: dict) -> str:
        """Build complete DA path from FCDA"""
        ln_class = fcda.get('@lnClass', '')
        ln_inst = fcda.get('@lnInst', '')
        do_name = fcda.get('@doName', '')
        da_name = fcda.get('@daName', '')
        
        if not all([ln_class, do_name, da_name]):
            return None
        
        # Build path: IED/LD/LN.DO.DA
        ln_name = f"{ln_class}{ln_inst}" if ln_inst else ln_class
        path = f"{ied_name}/{ld_inst}/{ln_name}.{do_name}.{da_name}"
        
        return path
    
    def build_tree(self):
        """Build IED tree - IEDScout view only"""
        try:
            self.ied_tree.clear()
            
            # Parse SCL to tree structure
            self.tree_root = self.iec61850_system.parse_scl_to_tree(self.current_scl_data)
            
            # Filter for selected IEDs
            selected_names = [c['ied_name'] for c in self.selected_ied_configs]
            
            # Build IEDScout tree
            self.iedscout_manager.parse_scl_for_iedscout(self.current_scl_data, selected_names)
            self.iedscout_manager.build_view()
            
            # Initialize dataset values with safe defaults
            self.initialize_dataset_values()
            
            self.update_status(f"📊 Tree built with {len(selected_names)} Virtual IEDs")
            
        except Exception as e:
            self.update_status(f"❌ Error building tree: {e}")
            import traceback
            traceback.print_exc()
    
    def initialize_dataset_values(self):
        """Initialize all dataset values with safe defaults"""
        self.log_virtual("🔧 Initializing Virtual IED dataset values...")
        
        # For each GOOSE dataset configuration
        for dataset_ref, da_paths in self.goose_datasets.items():
            self.log_virtual(f"📊 Dataset: {dataset_ref}")
            
            for da_path in da_paths:
                # Determine type from DA name/path
                da_type = self.get_da_type(da_path)
                default_value = SAFE_DEFAULT_VALUES.get(da_type, '')
                
                # Special handling for specific DAs
                if da_path.endswith('.stVal'):
                    # For circuit breakers (XCBR) - default to OPEN (safe)
                    if 'XCBR' in da_path or 'XSWI' in da_path:
                        default_value = False  # Open/Off
                    elif 'GGIO' in da_path:
                        # Digital I/O - default to False
                        default_value = False
                        
                elif da_path.endswith('.q'):
                    # Quality - Good (0x0000)
                    default_value = 0x0000
                    
                elif da_path.endswith('.t'):
                    # Timestamp - current time
                    default_value = int(time.time() * 1000)
                
                # Store default value
                self.dataset_values[da_path] = default_value
                self.dataset_defaults[da_path] = default_value
                
                # Update tree display
                self.iedscout_manager.update_item_value(da_path, str(default_value))
                
                self.log_virtual(f"   {da_path} = {default_value} ({da_type})")
        
        self.log_virtual(f"✅ Initialized {len(self.dataset_values)} dataset values")
    
    def get_da_type(self, da_path: str) -> str:
        """Get IEC 61850 type of DA from path or metadata"""
        # Check IEDScout item metadata first
        for section_items in self.iedscout_manager.sections.values():
            for item in section_items:
                if item.path == da_path and item.metadata:
                    iec_type = item.metadata.get('iec_type', '')
                    if iec_type:
                        # Map IEC type to GOOSE type
                        if 'bool' in iec_type.lower():
                            return 'boolean'
                        elif 'int' in iec_type.lower():
                            return 'integer'
                        elif 'float' in iec_type.lower():
                            return 'float'
                        elif 'string' in iec_type.lower():
                            return 'visible-string'
                        elif 'quality' in iec_type.lower():
                            return 'bit-string'
                        elif 'timestamp' in iec_type.lower():
                            return 'utc-time'
        
        # Fallback to DA name detection
        da_name = da_path.split('.')[-1] if '.' in da_path else ''
        
        # Common DA name patterns
        if da_name in ['stVal', 'ctlVal']:
            if 'XCBR' in da_path or 'XSWI' in da_path:
                return 'boolean'
            elif 'GGIO' in da_path:
                return 'boolean'
            else:
                return 'boolean'
        elif da_name == 'q':
            return 'bit-string'  # Quality
        elif da_name == 't':
            return 'utc-time'  # Timestamp
        elif da_name in ['mag', 'instMag', 'cVal']:
            return 'float'  # Magnitude values
        elif da_name == 'general':
            return 'boolean'  # General status
        else:
            return 'visible-string'  # Default
    
    def on_tree_double_click(self, item: QTreeWidgetItem, column: int):
        """Handle tree double click"""
        iedscout_item = self.iedscout_manager.get_item_at(item)
        if iedscout_item and iedscout_item.editable:
            self.edit_da_value_dialog(item, iedscout_item)
    
    def edit_da_value_dialog(self, tree_item: QTreeWidgetItem, iedscout_item: IEDScoutItem):
        """Edit DA value using dialog"""
        try:
            # Prepare DA info
            da_info = {
                'name': iedscout_item.metadata.get('da_name', ''),
                'path': iedscout_item.path,
                'value': iedscout_item.value,
                'metadata': iedscout_item.metadata
            }
            
            # Extract DA name from path if not in metadata
            if not da_info['name']:
                path_parts = iedscout_item.path.split('.')
                if len(path_parts) > 0:
                    da_info['name'] = path_parts[-1]
            
            # Open dialog
            dialog = DAValueEditorDialog(da_info, self)
            
            def on_value_changed(da_name, new_value):
                self.on_iedscout_item_edited(iedscout_item, str(new_value))
            
            dialog.value_changed.connect(on_value_changed)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Edit Error", f"Cannot edit value:\n{e}")
    
    def show_tree_menu(self, pos):
        """Show context menu"""
        item = self.ied_tree.itemAt(pos)
        if not item:
            return
        
        iedscout_item = self.iedscout_manager.get_item_at(item)
        if not iedscout_item:
            return
        
        menu = QMenu(self)
        
        if iedscout_item.editable and iedscout_item.metadata.get('da_name'):
            menu.addAction("✏️ Change Virtual IED value", 
                          lambda: self.edit_da_value_dialog(item, iedscout_item))
        
        menu.addAction("📋 Copy Path", lambda: self.copy_iedscout_path(iedscout_item))
        
        menu.exec(self.ied_tree.viewport().mapToGlobal(pos))
    
    def on_iedscout_item_edited(self, item: IEDScoutItem, new_value: str):
        """Handle value change - triggers GOOSE with state change"""
        try:
            old_value = self.dataset_values.get(item.path, None)
            
            # Update value
            self.dataset_values[item.path] = new_value
            
            # Update display
            item.value = new_value
            self.iedscout_manager.update_item_value(item.path, new_value)
            
            # Log
            self.log_virtual(f"🔧 Value changed: {item.path}")
            self.log_virtual(f"   Old: {old_value}")
            self.log_virtual(f"   New: {new_value}")
            
            # Check if value actually changed
            if old_value != new_value:
                # Send GOOSE with state change (stNum increase)
                if self.system_running:
                    if self.iec61850_system and self.iec61850_system.goose_manager.is_running:
                        self.log_goose(f"⚡ State change detected - publishing complete dataset")
                        self.publish_goose_dataset(trigger_path=item.path)
            
        except Exception as e:
            self.log_virtual(f"❌ Edit error: {e}")
    
    def copy_iedscout_path(self, item: IEDScoutItem):
        """Copy IEDScout item path"""
        QApplication.clipboard().setText(item.path)
        self.update_status(f"📋 Copied: {item.path}")
    
    def open_address_editor(self):
        """Open Address Editor Dialog"""
        # Import here to avoid circular import
        from iec61850_system.address_editor_dialog import AddressEditorDialog
        
        if self.system_running:
            QMessageBox.warning(self, "System Running", 
                              "Please stop the system before editing addresses")
            return
        
        if not self.selected_ied_configs:
            QMessageBox.warning(self, "No IEDs", 
                              "Please load SCL file and select IEDs first")
            return
        
        # Prepare GOOSE configs for dialog (original + user modifications)
        goose_configs_for_dialog = {}
        
        # Start with original configs
        if hasattr(self, 'original_goose_configs'):
            debug_log(f"Loading {len(self.original_goose_configs)} original configs")
            
            for key, config_dict in self.original_goose_configs.items():
                # Create GOOSEConfig object
                from pyiec61850_wrapper import GOOSEConfig
                config = GOOSEConfig()
                
                # Set values from original
                for attr, value in config_dict.items():
                    setattr(config, attr, value)
                
                # Apply user modifications if exist
                if key in self.user_modified_configs.get('goose_configs', {}):
                    user_config = self.user_modified_configs['goose_configs'][key]
                    debug_log(f"Applying user mods to {key} for dialog")
                    
                    if 'app_id' in user_config:
                        config.app_id = user_config['app_id']
                    if 'dst_mac' in user_config:
                        config.dst_mac = user_config['dst_mac']
                
                goose_configs_for_dialog[key] = config
        else:
            # Fallback to current configs if no originals
            if self.iec61850_system and hasattr(self.iec61850_system.goose_manager, 'all_goose_configs'):
                goose_configs_for_dialog = self.iec61850_system.goose_manager.all_goose_configs
        
        # Open dialog
        dialog = AddressEditorDialog(
            self.selected_ied_configs,
            goose_configs_for_dialog,
            self
        )
        
        # Connect signal
        dialog.config_changed.connect(self.on_address_config_changed)
        
        # Show dialog
        dialog.exec()
    
    def on_address_config_changed(self, configs):
        """Handle address configuration changes from dialog"""
        try:
            self.log_virtual("🔧 GOOSE configuration changed")
            
            # Store user modifications
            self.user_modified_configs['goose_configs'] = configs['goose_configs'].copy()
            
            # Debug log changes
            debug_log("User modified configs:")
            debug_log(f"  GOOSE configs: {len(self.user_modified_configs['goose_configs'])}")
            
            # Log changes will be applied
            self.log_virtual("✅ Configuration saved. Changes will be applied when system starts.")
            
        except Exception as e:
            self.log_virtual(f"❌ Error applying config changes: {e}")
    
    def start_system(self):
        """Start Virtual IED System"""
        try:
            interface = self.network_interface_combo.currentText()
            if not interface or "No" in interface:
                QMessageBox.warning(self, "Interface Error", "Please select network interface")
                return
            
            if not self.selected_ied_configs:
                QMessageBox.warning(self, "No IEDs", "Please select IEDs first")
                return
            
            # Safety check before starting
            if not self.verify_safety_before_publish():
                return
            
            self.update_status("🚀 Starting Virtual IED System...")
            self.log_virtual(f"🌐 Using network interface: {interface}")
            self.log_virtual("🤖 Running in VIRTUAL IED MODE")
            
            # Show test mode status
            if self.test_mode:
                self.log_virtual("🧪 TEST MODE ENABLED - Messages marked as simulation")
            else:
                self.log_virtual("⚠️ REAL MODE - Sending actual GOOSE messages!")
            
            # Verify multicast setup
            self.verify_multicast_setup()
            
            # Create or reset IEC61850System
            if not self.iec61850_system:
                self.iec61850_system = IEC61850System(interface)
            else:
                # Reset GOOSE manager for fresh start
                self.iec61850_system.goose_manager = GOOSEManager(interface)
            
            # CRITICAL: Pass reference to self for user modifications
            self.iec61850_system.goose_manager._parent_system = self
            debug_log("Set parent reference for GOOSE manager")
            
            # Restore GOOSE configs from original + user modifications
            if hasattr(self, 'original_goose_configs') and self.original_goose_configs:
                debug_log("📌 Restoring GOOSE configs from original")
                
                # Clear and restore configs
                self.iec61850_system.goose_manager.all_goose_configs = {}
                
                # Restore original configs with user modifications
                for key, config_dict in self.original_goose_configs.items():
                    from pyiec61850_wrapper import GOOSEConfig
                    config = GOOSEConfig()
                    
                    # Set values from original
                    for attr, value in config_dict.items():
                        setattr(config, attr, value)
                    
                    # Apply user modifications if exist
                    if key in self.user_modified_configs.get('goose_configs', {}):
                        user_config = self.user_modified_configs['goose_configs'][key]
                        debug_log(f"Applying user mods for {key}")
                        
                        if 'app_id' in user_config:
                            config.app_id = user_config['app_id']
                            debug_log(f"  User APP ID: 0x{user_config['app_id']:04X}")
                        
                        if 'dst_mac' in user_config:
                            config.dst_mac = user_config['dst_mac']
                            debug_log(f"  User MAC: {user_config['dst_mac']}")
                    
                    self.iec61850_system.goose_manager.all_goose_configs[key] = config
                    debug_log(f"Added config for {key}: AppID=0x{config.app_id:04X}, MAC={config.dst_mac}")
                
                debug_log(f"✅ Restored {len(self.iec61850_system.goose_manager.all_goose_configs)} GOOSE configs")
            
            # Start GOOSE system
            self.log_goose("🚀 Starting GOOSE multicast system...")
            
            # Select the correct GOOSE config for the first IED
            first_ied_name = self.selected_ied_configs[0]['ied_name'] if self.selected_ied_configs else None
            
            # Pass None for scl_data to prevent re-extraction
            if self.iec61850_system.start_goose_system(None, auto_publish=False, ied_name=first_ied_name):
                self.log_goose("✅ GOOSE system started successfully")
                
                # Set test mode if enabled
                if self.test_mode and self.iec61850_system.goose_manager.publisher:
                    # FIXED: Safe test mode setting
                    if hasattr(self.iec61850_system.goose_manager.publisher, 'set_test_mode'):
                        self.iec61850_system.goose_manager.publisher.set_test_mode(True)
                        self.log_goose("🧪 GOOSE publisher in TEST MODE")
                else:
                    self.log_goose("🧪 TEST MODE enabled - method not available")
                    self.log_goose("🧪 GOOSE publisher in TEST MODE")
                
                # Test GOOSE publisher
                if self.iec61850_system.goose_manager.publisher:
                    config = self.iec61850_system.goose_manager.config
                    self.log_goose(f"📡 GOOSE Publisher ready on {interface}")
                    self.log_goose(f"📌 Configuration:")
                    self.log_goose(f"   - APP ID: 0x{config.app_id:04X}")
                    self.log_goose(f"   - MAC: {config.dst_mac}")
                    self.log_goose(f"   - GoID: {config.go_id}")
                    self.log_goose(f"   - Dataset: {config.dataset_ref}")
                    self.log_goose("⏸️ Waiting for value changes or 1s for first heartbeat")
                else:
                    self.log_goose("⚠️ GOOSE Publisher not initialized")
            else:
                self.log_goose("⚠️ GOOSE start failed - continuing anyway")
            
            # Update UI
            self.system_running = True
            self.start_system_btn.setEnabled(False)
            self.stop_system_btn.setEnabled(True)
            self.stats['start_time'] = datetime.now()
            
            # Start heartbeat timer (1 second)
            self.start_periodic_goose()
            
            # Update status
            self.update_status("✅ Virtual IED System running - Multicasting GOOSE")
            
        except Exception as e:
            self.update_status(f"❌ Start failed: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Start Error", f"Cannot start system:\n{e}")
    
    def verify_multicast_setup(self):
        """Verify multicast is properly configured"""
        interface = self.network_interface_combo.currentText()
        
        self.log_goose("🔍 Verifying multicast configuration...")
        self.log_goose(f"   Interface: {interface}")
        
        # Check if interface supports multicast
        import subprocess
        try:
            # Check interface flags
            result = subprocess.run(['ip', 'link', 'show', interface], 
                                  capture_output=True, text=True)
            if 'MULTICAST' in result.stdout:
                self.log_goose(f"✅ Interface {interface} supports multicast")
            else:
                self.log_goose(f"⚠️ Interface {interface} may not support multicast")
                
        except Exception as e:
            self.log_goose(f"⚠️ Cannot verify multicast: {e}")
        
        self.log_goose(f"📡 GOOSE will multicast to MAC range 01:0C:CD:01:00:00-FF")
    
    def start_periodic_goose(self):
        """Start periodic GOOSE transmission (heartbeat)"""
        if not self.system_running or not self.iec61850_system:
            return
        
        self.log_goose("🫀 Starting periodic GOOSE heartbeat (T3=1000ms)")
        
        # Create heartbeat timer
        self.goose_heartbeat_timer = QTimer()
        self.goose_heartbeat_timer.timeout.connect(self.send_goose_heartbeat)
        self.goose_heartbeat_timer.start(1000)  # T3 = 1000ms per IEC 61850
    
    def send_goose_heartbeat(self):
        """Send GOOSE heartbeat (no state change)"""
        if self.iec61850_system and self.iec61850_system.goose_manager.is_running:
            # Send with sqNum increment only (no stNum change)
            self.publish_goose_dataset(heartbeat=True)
    
    def publish_goose_dataset(self, trigger_path: str = None, heartbeat: bool = False):
        """
        Publish complete GOOSE dataset per IEC 61850-8-1
        - Always sends ALL data attributes in the dataset
        - Uses proper retransmission pattern for state changes
        - Sends heartbeat at T3 interval
        """
        try:
            # Get current GOOSE config
            if not self.iec61850_system or not self.iec61850_system.goose_manager.config:
                return
            
            current_config = self.iec61850_system.goose_manager.config
            dataset_ref = current_config.dataset_ref
            
            if heartbeat:
                self.log_goose(f"🫀 Sending GOOSE heartbeat")
            else:
                self.log_goose(f"📡 Publishing GOOSE Dataset (IEC 61850 compliant)")
                self.log_goose(f"📌 Dataset: {dataset_ref}")
                if trigger_path:
                    self.log_goose(f"⚡ State change triggered by: {trigger_path}")
            
            # Get ALL dataset members from configuration
            dataset_items = self.get_dataset_items(dataset_ref)
            
            if not dataset_items:
                self.log_goose("❌ No dataset items found in configuration")
                return
            
            # Create GOOSE message
            class GOOSEMessage:
                def __init__(self):
                    self.data_items = []
                
                def add_data_item(self, path, value, goose_type):
                    self.data_items.append({
                        'da_path': path,
                        'value': value,
                        'type': goose_type
                    })
            
            message = GOOSEMessage()
            
            # Add ALL items in dataset (IEC 61850 requirement)
            if not heartbeat:
                self.log_goose(f"📦 Preparing {len(dataset_items)} dataset members:")
            
            for da_path in dataset_items:
                # Get current value or use safe default
                if da_path in self.dataset_values:
                    value = self.dataset_values[da_path]
                else:
                    # Use safe default based on type
                    da_type = self.get_da_type(da_path)
                    value = SAFE_DEFAULT_VALUES.get(da_type, '')
                    self.dataset_values[da_path] = value
                
                # Determine GOOSE type
                goose_type = self.determine_goose_type(value, da_path)
                
                # Log each item (not for heartbeat)
                if not heartbeat:
                    # Special formatting for quality
                    if da_path.endswith('.q'):
                        if isinstance(value, int):
                            self.log_goose(f"   {da_path} = 0x{value:04X} ({goose_type})")
                        else:
                            self.log_goose(f"   {da_path} = {value} ({goose_type})")
                    else:
                        self.log_goose(f"   {da_path} = {value} ({goose_type})")
                
                # Add to message
                message.add_data_item(da_path, value, goose_type)
            
            # Publish with appropriate method
            if heartbeat:
                # Heartbeat - no stNum increase
                if self.iec61850_system.goose_manager.publisher:
                    self.iec61850_system.goose_manager.publisher.set_dataset(
                        [{'path': item['da_path'], 'value': item['value'], 'type': item['type']} 
                         for item in message.data_items]
                    )
                    # Publish without stNum increase
                    if self.iec61850_system.goose_manager.publisher.publish(increase_stnum=False):
                        self.stats['goose_sent'] += 1
            else:
                # State change - use retransmission pattern
                self.log_goose(f"📡 Publishing with IEC 61850 retransmission pattern")
                
                if self.iec61850_system.goose_manager.publish_message(message):
                    self.log_goose(f"✅ GOOSE multicast sent with {len(message.data_items)} items")
                    self.stats['goose_sent'] += 1
                else:
                    self.log_goose(f"❌ GOOSE publish failed")
            
        except Exception as e:
            self.log_goose(f"❌ GOOSE error: {e}")
            import traceback
            traceback.print_exc()
    
    def get_dataset_items(self, dataset_ref: str) -> List[str]:
        """Get all DA paths in a dataset"""
        return self.goose_datasets.get(dataset_ref, [])
    
    def determine_goose_type(self, value: Any, da_path: str = "") -> str:
        """Determine GOOSE type from value and path"""
        # Check if it's a quality attribute
        if da_path.endswith('.q'):
            return 'bit-string'  # Quality is always bit-string
        
        # Check other types
        if isinstance(value, bool) or str(value).lower() in ['true', 'false']:
            return 'boolean'
        elif str(value).replace('-', '').isdigit():
            return 'integer'
        elif '.' in str(value):
            try:
                float(value)
                return 'float'
            except:
                return 'visible-string'
        else:
            return 'visible-string'
    
    def stop_system(self):
        """Stop Virtual IED system"""
        try:
            self.update_status("🛑 Stopping Virtual IED system...")
            
            # Stop heartbeat timer
            if self.goose_heartbeat_timer:
                self.goose_heartbeat_timer.stop()
                self.goose_heartbeat_timer = None
            
            # Stop IEC 61850 system
            if self.iec61850_system:
                self.iec61850_system.stop_all()
            
            # Update UI
            self.system_running = False
            self.start_system_btn.setEnabled(True)
            self.stop_system_btn.setEnabled(False)
            
            self.update_status("🛑 Virtual IED system stopped")
            
        except Exception as e:
            self.update_status(f"❌ Stop failed: {e}")
    
    def export_data(self):
        """Export current dataset values"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Dataset Values",
                f"virtual_ied_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write("Path,Value,Type\n")
                    for path, value in self.dataset_values.items():
                        da_type = self.get_da_type(path)
                        f.write(f'"{path}","{value}","{da_type}"\n')
                
                self.update_status(f"💾 Data exported to {filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Cannot export:\n{e}")
    
    def save_virtual_log(self):
        """Save Virtual IED log"""
        self.save_log(self.pub_log.toPlainText(), "VirtualIED")
    
    def save_goose_log(self):
        """Save GOOSE log"""
        self.save_log(self.sub_log.toPlainText(), "GOOSE")
    
    def save_log(self, content: str, log_type: str):
        """Save log to file"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"Save {log_type} Log",
                f"{log_type.lower()}_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt)"
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write(content)
                self.update_status(f"💾 {log_type} log saved")
                
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Cannot save:\n{e}")
    
    def log_virtual(self, message: str):
        """Log Virtual IED message"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.pub_log.appendPlainText(f"[{timestamp}] {message}")
    
    def log_goose(self, message: str):
        """Log GOOSE message"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.sub_log.appendPlainText(f"[{timestamp}] {message}")
    
    def update_status(self, message: str):
        """Update status display"""
        if hasattr(self, 'system_status_text'):
            timestamp = datetime.now().strftime("%H:%M:%S")
            current = self.system_status_text.toPlainText()
            lines = current.split('\n')[-2:] if current else []
            lines.append(f"[{timestamp}] {message}")
            self.system_status_text.setPlainText('\n'.join(lines))
        
        # Console
        print(f"{message}")
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.system_running:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Virtual IED System is running. Exit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        # Stop system
        if self.system_running:
            self.stop_system()
        
        # Stop timers
        if hasattr(self, 'time_sync_timer'):
            self.time_sync_timer.stop()
        
        event.accept()
    
    def check_time_sync_status(self):
        """Check and display time synchronization status"""
        try:
            if TIME_SYNC_AVAILABLE:
                is_synced, accuracy_us = check_time_synchronization()
                
                if hasattr(self, 'time_sync_status'):
                    if is_synced:
                        if accuracy_us and accuracy_us < 1000:  # < 1ms
                            self.time_sync_status.setText(
                                f"⏰ Time Sync: ✅ Excellent ({accuracy_us:.0f} µs)"
                            )
                            self.time_sync_status.setStyleSheet("color: green;")
                        elif accuracy_us and accuracy_us < 10000:  # < 10ms
                            self.time_sync_status.setText(
                                f"⏰ Time Sync: ⚠️ Good ({accuracy_us/1000:.1f} ms)"
                            )
                            self.time_sync_status.setStyleSheet("color: orange;")
                        else:
                            self.time_sync_status.setText(
                                f"⏰ Time Sync: ⚠️ Poor ({accuracy_us/1000:.1f} ms)"
                            )
                            self.time_sync_status.setStyleSheet("color: red;")
                    else:
                        self.time_sync_status.setText("⏰ Time Sync: ❌ Not synchronized")
                        self.time_sync_status.setStyleSheet("color: red;")
            else:
                if hasattr(self, 'time_sync_status'):
                    self.time_sync_status.setText("⏰ Time Sync: Using system time")
                    self.time_sync_status.setStyleSheet("color: gray;")
        except Exception as e:
            print(f"Error checking time sync: {e}")
    
    def on_test_mode_changed(self, checked):
        """Handle test mode change"""
        self.test_mode = checked
        if checked:
            self.log_virtual("🧪 TEST MODE ENABLED - GOOSE messages marked as test")
        else:
            # Show warning
            reply = QMessageBox.warning(
                self,
                "Disable Test Mode?",
                "⚠️ WARNING: Disabling test mode will send real GOOSE messages\n"
                "that will be processed by protection IEDs!\n\n"
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.test_mode_checkbox.setChecked(True)
                self.test_mode = True
            else:
                self.log_virtual("⚠️ TEST MODE DISABLED - Sending REAL GOOSE messages!")
    
    def monitor_goose_traffic(self):
        """Monitor existing GOOSE traffic before sending"""
        try:
            duration = 10  # seconds
            self.log_goose(f"📡 Monitoring GOOSE traffic for {duration} seconds...")
            self.log_goose("   Looking for existing publishers...")
            
            # Disable buttons during monitoring
            if hasattr(self, 'monitor_goose_btn'):
                self.monitor_goose_btn.setEnabled(False)
            self.start_system_btn.setEnabled(False)
            
            # Create GOOSE subscriber for monitoring
            from pyiec61850_wrapper import GOOSESubscriber
            
            monitor = GOOSESubscriber(self.network_interface_combo.currentText())
            self.monitored_goose.clear()
            
            def goose_callback(data):
                go_id = data.get('goID', 'Unknown')
                if go_id not in self.monitored_goose:
                    self.monitored_goose[go_id] = {
                        'appID': data.get('appID', 0),
                        'goCbRef': data.get('goCbRef', ''),
                        'count': 0
                    }
                self.monitored_goose[go_id]['count'] += 1
            
            # Create receiver and start monitoring
            if monitor.create_receiver():
                monitor.add_subscription(callback=goose_callback)
                if monitor.start():
                    # Monitor for duration
                    QTimer.singleShot(duration * 1000, lambda: self.finish_monitoring(monitor))
                else:
                    self.log_goose("❌ Failed to start GOOSE monitor")
                    self.finish_monitoring(None)
            else:
                self.log_goose("❌ Failed to create GOOSE receiver")
                self.finish_monitoring(None)
                
        except Exception as e:
            self.log_goose(f"❌ Monitor error: {e}")
            self.finish_monitoring(None)
    
    def finish_monitoring(self, monitor):
        """Finish GOOSE monitoring and show results"""
        if monitor:
            monitor.stop()
            monitor.destroy()
        
        # Show results
        self.log_goose(f"\n📊 Monitoring Results:")
        if self.monitored_goose:
            self.log_goose(f"Found {len(self.monitored_goose)} active GOOSE publishers:")
            for go_id, info in self.monitored_goose.items():
                self.log_goose(f"   • {go_id}")
                self.log_goose(f"     - APP ID: 0x{info['appID']:04X}")
                self.log_goose(f"     - Messages: {info['count']}")
                
            # Check for conflicts
            if hasattr(self, 'config') and self.config:
                if self.config.app_id in [info['appID'] for info in self.monitored_goose.values()]:
                    self.log_goose(f"⚠️ WARNING: APP ID 0x{self.config.app_id:04X} already in use!")
        else:
            self.log_goose("✅ No active GOOSE publishers found")
        
        # Re-enable buttons
        if hasattr(self, 'monitor_goose_btn'):
            self.monitor_goose_btn.setEnabled(True)
        self.start_system_btn.setEnabled(True)
    
    def verify_safety_before_publish(self) -> bool:
        """Verify safety conditions before publishing GOOSE"""
        # Check time sync for protection applications
        if TIME_SYNC_AVAILABLE:
            is_synced, accuracy_us = check_time_synchronization()
            
            if not is_synced:
                reply = QMessageBox.warning(
                    self,
                    "Time Sync Warning",
                    "⚠️ System time is not synchronized!\n\n"
                    "Protection applications require accurate time sync.\n"
                    "Continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return False
            
            elif accuracy_us and accuracy_us > 1000:  # > 1ms
                reply = QMessageBox.warning(
                    self,
                    "Time Sync Warning", 
                    f"⚠️ Time sync accuracy is {accuracy_us/1000:.2f}ms\n\n"
                    "Protection applications require < 1ms accuracy.\n"
                    "Continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return False
        
        # Final confirmation
        if not self.test_mode:
            config = self.iec61850_system.goose_manager.config if self.iec61850_system else None
            if config:
                reply = QMessageBox.question(
                    self,
                    "Confirm GOOSE Publish",
                    f"🚨 Send REAL GOOSE messages to protection IEDs?\n\n"
                    f"Configuration:\n"
                    f"• APP ID: 0x{config.app_id:04X}\n"
                    f"• MAC: {config.dst_mac}\n"
                    f"• GoID: {config.go_id}\n"
                    f"• Dataset: {config.dataset_ref}\n\n"
                    f"⚠️ This will affect real protection systems!",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                return reply == QMessageBox.StandardButton.Yes
        
        return True

# ==================== Main Entry Point ====================

def main():
    """Test Virtual IED application"""
    app = QApplication(sys.argv)
    
    # Dummy back function
    def dummy_back():
        print("Back to main")
        app.quit()
    
    # Create and show window
    window = VirtualIEDSystem(dummy_back)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()