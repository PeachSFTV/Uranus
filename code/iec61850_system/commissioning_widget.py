# commissioning_widget.py
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QPushButton, QComboBox, QTextEdit, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox,
    QLineEdit, QFormLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QBrush

# Import our modules
from time_sync_utils import time_sync_manager, get_synchronized_timestamp_us
from goose_handler import GOOSEHandler
from ied_connection_manager import IEDConnectionManager
from test_executor import TestExecutor, TestResult, TestStatus
from report_generator import ReportGenerator

# Import pyiec61850
import pyiec61850 as iec61850


class TestType(Enum):
    """Types of commissioning tests"""
    CONNECTIVITY = "Connectivity Test"
    CONTROL = "Control Test"
    STATUS = "Status Verification"
    PROTECTION = "Protection Test"
    MEASUREMENT = "Measurement Test"
    INTERLOCKING = "Interlocking Test"
    SEQUENCE = "Sequence Test"
    PERFORMANCE = "Performance Test"


class CommissioningWidget(QWidget):
    """Main commissioning widget for IEC 61850 testing"""
    
    # Signals
    test_started = pyqtSignal(str)
    test_completed = pyqtSignal(str, bool)
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(self, scl_data: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.scl_data = scl_data
        self.selected_ieds = []
        self.active_connections = {}
        self.test_results = []
        self.is_testing = False
        
        # Initialize components
        self.goose_handler = None
        self.connection_manager = IEDConnectionManager()
        self.test_executor = None
        self.report_generator = ReportGenerator()
        
        # Safety flags
        self.safety_checks_enabled = True
        self.test_mode = True  # True = test mode, False = live mode
        
        self.setup_ui()
        self.initialize_components()
        
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Title
        title = QLabel("🔧 IEC 61850 Commissioning System")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Time sync status
        self.time_sync_widget = self.create_time_sync_widget()
        main_layout.addWidget(self.time_sync_widget)
        
        # Main content - use tabs
        self.tab_widget = QTabWidget()
        
        # Test Configuration Tab
        self.config_widget = self.create_configuration_tab()
        self.tab_widget.addTab(self.config_widget, "⚙️ Configuration")
        
        # Test Execution Tab
        self.execution_widget = self.create_execution_tab()
        self.tab_widget.addTab(self.execution_widget, "▶️ Execution")
        
        # Monitoring Tab
        self.monitoring_widget = self.create_monitoring_tab()
        self.tab_widget.addTab(self.monitoring_widget, "📊 Monitoring")
        
        # Results Tab
        self.results_widget = self.create_results_tab()
        self.tab_widget.addTab(self.results_widget, "📋 Results")
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = self.create_status_bar()
        main_layout.addWidget(self.status_bar)
        
    def create_time_sync_widget(self) -> QWidget:
        """Create time synchronization status widget"""
        widget = QGroupBox("⏰ Time Synchronization Status")
        layout = QHBoxLayout(widget)
        
        # Sync status
        self.sync_status_label = QLabel("Checking...")
        self.sync_status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.sync_status_label)
        
        # Accuracy
        self.sync_accuracy_label = QLabel("--")
        layout.addWidget(QLabel("Accuracy:"))
        layout.addWidget(self.sync_accuracy_label)
        
        # Current time
        self.current_time_label = QLabel("--")
        layout.addWidget(QLabel("UTC Time:"))
        layout.addWidget(self.current_time_label)
        
        layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_time_sync_status)
        layout.addWidget(refresh_btn)
        
        # Setup timer for auto-update
        self.time_sync_timer = QTimer()
        self.time_sync_timer.timeout.connect(self.update_time_sync_status)
        self.time_sync_timer.start(1000)  # Update every second
        
        return widget
        
    def create_configuration_tab(self) -> QWidget:
        """Create test configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Split into left (IED selection) and right (test selection)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: IED Selection
        ied_group = QGroupBox("🏭 IED Selection")
        ied_layout = QVBoxLayout(ied_group)
        
        # IED tree
        self.ied_tree = QTreeWidget()
        self.ied_tree.setHeaderLabels(["IED/Logical Device", "Status", "IP Address"])
        self.ied_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        ied_layout.addWidget(self.ied_tree)
        
        # IED control buttons
        ied_btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("🔌 Connect Selected")
        self.connect_btn.clicked.connect(self.connect_selected_ieds)
        ied_btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_selected_ieds)
        self.disconnect_btn.setEnabled(False)
        ied_btn_layout.addWidget(self.disconnect_btn)
        
        ied_layout.addLayout(ied_btn_layout)
        splitter.addWidget(ied_group)
        
        # Right: Test Configuration
        test_group = QGroupBox("🧪 Test Configuration")
        test_layout = QVBoxLayout(test_group)
        
        # Test type selection
        test_type_layout = QFormLayout()
        
        # Test mode
        self.test_mode_combo = QComboBox()
        self.test_mode_combo.addItems(["Test Mode (Simulation)", "Live Mode"])
        self.test_mode_combo.currentIndexChanged.connect(self.on_test_mode_changed)
        test_type_layout.addRow("Mode:", self.test_mode_combo)
        
        # Safety checks
        self.safety_check = QCheckBox("Enable Safety Checks")
        self.safety_check.setChecked(True)
        self.safety_check.toggled.connect(self.on_safety_check_toggled)
        test_type_layout.addRow("Safety:", self.safety_check)
        
        test_layout.addLayout(test_type_layout)
        
        # Test selection tree
        self.test_tree = QTreeWidget()
        self.test_tree.setHeaderLabels(["Test", "Description", "Required"])
        self.populate_test_tree()
        test_layout.addWidget(self.test_tree)
        
        splitter.addWidget(test_group)
        layout.addWidget(splitter)
        
        # Network configuration
        network_group = QGroupBox("🌐 Network Configuration")
        network_layout = QFormLayout(network_group)
        
        # Interface selection
        self.interface_combo = QComboBox()
        self.interface_combo.addItems(self.get_network_interfaces())
        network_layout.addRow("Interface:", self.interface_combo)
        
        # VLAN configuration
        self.vlan_spin = QSpinBox()
        self.vlan_spin.setRange(0, 4095)
        self.vlan_spin.setValue(0)
        network_layout.addRow("VLAN ID:", self.vlan_spin)
        
        # Priority
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 7)
        self.priority_spin.setValue(4)
        network_layout.addRow("Priority:", self.priority_spin)
        
        layout.addWidget(network_group)
        
        return widget
        
    def create_execution_tab(self) -> QWidget:
        """Create test execution tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Control panel
        control_group = QGroupBox("🎮 Test Control")
        control_layout = QHBoxLayout(control_group)
        
        # Start button
        self.start_btn = QPushButton("🚀 Start Tests")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.start_btn.clicked.connect(self.start_tests)
        control_layout.addWidget(self.start_btn)
        
        # Pause button
        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_tests)
        control_layout.addWidget(self.pause_btn)
        
        # Stop button
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_tests)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        layout.addWidget(control_group)
        
        # Progress
        progress_group = QGroupBox("📊 Test Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        # Overall progress
        self.overall_progress = QProgressBar()
        self.overall_progress.setTextVisible(True)
        progress_layout.addWidget(QLabel("Overall Progress:"))
        progress_layout.addWidget(self.overall_progress)
        
        # Current test
        self.current_test_label = QLabel("No test running")
        self.current_test_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        progress_layout.addWidget(QLabel("Current Test:"))
        progress_layout.addWidget(self.current_test_label)
        
        # Test progress
        self.test_progress = QProgressBar()
        progress_layout.addWidget(self.test_progress)
        
        layout.addWidget(progress_group)
        
        # Execution log
        log_group = QGroupBox("📝 Execution Log")
        log_layout = QVBoxLayout(log_group)
        
        self.execution_log = QTextEdit()
        self.execution_log.setReadOnly(True)
        self.execution_log.setMaximumHeight(300)
        log_layout.addWidget(self.execution_log)
        
        # Clear log button
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.clicked.connect(self.execution_log.clear)
        log_layout.addWidget(clear_btn)
        
        layout.addWidget(log_group)
        
        return widget
        
    def create_monitoring_tab(self) -> QWidget:
        """Create real-time monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # GOOSE monitoring
        goose_group = QGroupBox("📡 GOOSE Monitoring")
        goose_layout = QVBoxLayout(goose_group)
        
        # GOOSE statistics
        self.goose_stats_table = QTableWidget()
        self.goose_stats_table.setColumnCount(6)
        self.goose_stats_table.setHorizontalHeaderLabels([
            "GOOSE ID", "Publisher", "Status", "StNum", "SqNum", "Last Update"
        ])
        self.goose_stats_table.horizontalHeader().setStretchLastSection(True)
        goose_layout.addWidget(self.goose_stats_table)
        
        # GOOSE control
        goose_control_layout = QHBoxLayout()
        self.monitor_goose_btn = QPushButton("📡 Start Monitoring")
        self.monitor_goose_btn.clicked.connect(self.toggle_goose_monitoring)
        goose_control_layout.addWidget(self.monitor_goose_btn)
        
        self.clear_goose_btn = QPushButton("🗑️ Clear")
        self.clear_goose_btn.clicked.connect(self.clear_goose_stats)
        goose_control_layout.addWidget(self.clear_goose_btn)
        
        goose_control_layout.addStretch()
        goose_layout.addLayout(goose_control_layout)
        
        layout.addWidget(goose_group)
        
        # Value monitoring
        value_group = QGroupBox("📊 Value Monitoring")
        value_layout = QVBoxLayout(value_group)
        
        self.value_table = QTableWidget()
        self.value_table.setColumnCount(5)
        self.value_table.setHorizontalHeaderLabels([
            "IED", "Path", "Value", "Quality", "Timestamp"
        ])
        self.value_table.horizontalHeader().setStretchLastSection(True)
        value_layout.addWidget(self.value_table)
        
        layout.addWidget(value_group)
        
        # Setup monitoring timer
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self.update_monitoring)
        
        return widget
        
    def create_results_tab(self) -> QWidget:
        """Create test results tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results summary
        summary_group = QGroupBox("📊 Test Summary")
        summary_layout = QFormLayout(summary_group)
        
        self.total_tests_label = QLabel("0")
        summary_layout.addRow("Total Tests:", self.total_tests_label)
        
        self.passed_tests_label = QLabel("0")
        self.passed_tests_label.setStyleSheet("color: green; font-weight: bold;")
        summary_layout.addRow("Passed:", self.passed_tests_label)
        
        self.failed_tests_label = QLabel("0")
        self.failed_tests_label.setStyleSheet("color: red; font-weight: bold;")
        summary_layout.addRow("Failed:", self.failed_tests_label)
        
        self.pass_rate_label = QLabel("0%")
        self.pass_rate_label.setStyleSheet("font-weight: bold;")
        summary_layout.addRow("Pass Rate:", self.pass_rate_label)
        
        layout.addWidget(summary_group)
        
        # Detailed results table
        results_group = QGroupBox("📋 Detailed Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Test ID", "Test Name", "IED", "Status", "Duration", "Details", "Timestamp"
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.results_table)
        
        # Export buttons
        export_layout = QHBoxLayout()
        
        self.export_html_btn = QPushButton("📄 Export HTML")
        self.export_html_btn.clicked.connect(self.export_results_html)
        export_layout.addWidget(self.export_html_btn)
        
        self.export_csv_btn = QPushButton("📊 Export CSV")
        self.export_csv_btn.clicked.connect(self.export_results_csv)
        export_layout.addWidget(self.export_csv_btn)
        
        self.export_pdf_btn = QPushButton("📑 Export PDF")
        self.export_pdf_btn.clicked.connect(self.export_results_pdf)
        export_layout.addWidget(self.export_pdf_btn)
        
        export_layout.addStretch()
        results_layout.addLayout(export_layout)
        
        layout.addWidget(results_group)
        
        return widget
        
    def create_status_bar(self) -> QWidget:
        """Create status bar widget"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Connection status
        self.connection_status = QLabel("🔴 Disconnected")
        layout.addWidget(self.connection_status)
        
        layout.addWidget(QLabel("|"))
        
        # Test status
        self.test_status = QLabel("⏸️ Idle")
        layout.addWidget(self.test_status)
        
        layout.addWidget(QLabel("|"))
        
        # Safety status
        self.safety_status = QLabel("🛡️ Safety ON")
        self.safety_status.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.safety_status)
        
        layout.addStretch()
        
        # Message area
        self.status_message = QLabel("Ready")
        layout.addWidget(self.status_message)
        
        return widget
        
    def initialize_components(self):
        """Initialize internal components"""
        # Initialize GOOSE handler
        if self.scl_data:
            self.goose_handler = GOOSEHandler(self.scl_data)
            
        # Initialize test executor
        self.test_executor = TestExecutor(
            self.connection_manager,
            self.goose_handler,
            self.safety_checks_enabled
        )
        
        # Connect test executor signals
        self.test_executor.test_started.connect(self.on_test_started)
        self.test_executor.test_completed.connect(self.on_test_completed)
        self.test_executor.log_message.connect(self.on_log_message)
        
        # Load IED data if available
        if self.scl_data:
            self.load_ied_data()
            
    def load_ied_data(self):
        """Load IED data from SCL"""
        self.ied_tree.clear()
        
        if not self.scl_data:
            return
            
        # Extract IEDs from SCL
        scl = self.scl_data.get('SCL', {})
        ieds = scl.get('IED', [])
        
        if isinstance(ieds, dict):
            ieds = [ieds]
            
        for ied in ieds:
            if not isinstance(ied, dict):
                continue
                
            ied_name = ied.get('@name', 'Unknown')
            
            # Create IED item
            ied_item = QTreeWidgetItem([ied_name, "Disconnected", ""])
            ied_item.setData(0, Qt.ItemDataRole.UserRole, ied)
            
            # Get IP address from Communication section
            ip_address = self.get_ied_ip_address(ied_name)
            if ip_address:
                ied_item.setText(2, ip_address)
                
            # Add logical devices
            aps = ied.get('AccessPoint', [])
            if isinstance(aps, dict):
                aps = [aps]
                
            for ap in aps:
                if not isinstance(ap, dict):
                    continue
                    
                server = ap.get('Server', {})
                lds = server.get('LDevice', [])
                if isinstance(lds, dict):
                    lds = [lds]
                    
                for ld in lds:
                    if isinstance(ld, dict):
                        ld_name = ld.get('@inst', 'Unknown')
                        ld_item = QTreeWidgetItem([f"  └─ {ld_name}", "", ""])
                        ld_item.setData(0, Qt.ItemDataRole.UserRole, ld)
                        ied_item.addChild(ld_item)
                        
            self.ied_tree.addTopLevelItem(ied_item)
            
        # Expand all items
        self.ied_tree.expandAll()
        
    def get_ied_ip_address(self, ied_name: str) -> Optional[str]:
        """Get IP address for IED from SCL"""
        if not self.scl_data:
            return None
            
        comm = self.scl_data.get('SCL', {}).get('Communication', {})
        subnets = comm.get('SubNetwork', [])
        
        if isinstance(subnets, dict):
            subnets = [subnets]
            
        for subnet in subnets:
            caps = subnet.get('ConnectedAP', [])
            if isinstance(caps, dict):
                caps = [caps]
                
            for cap in caps:
                if cap.get('@iedName') == ied_name:
                    address = cap.get('Address', {})
                    p_elements = address.get('P', [])
                    if not isinstance(p_elements, list):
                        p_elements = [p_elements]
                        
                    for p in p_elements:
                        if isinstance(p, dict) and p.get('@type') == 'IP':
                            return p.get('#text')
                            
        return None
        
    def populate_test_tree(self):
        """Populate test selection tree"""
        self.test_tree.clear()
        
        # Define test categories and tests
        test_categories = {
            "Basic Tests": {
                "connectivity": ("Connectivity Test", "Verify IED connection", True),
                "time_sync": ("Time Synchronization", "Check time sync status", True),
                "data_model": ("Data Model Verification", "Verify IED data model", True),
            },
            "Control Tests": {
                "xcbr_control": ("Circuit Breaker Control", "Test CB open/close", False),
                "xswi_control": ("Switch Control", "Test switch operations", False),
                "cswi_control": ("Control Switch", "Test control commands", False),
            },
            "Protection Tests": {
                "ptoc_test": ("Overcurrent Protection", "Test 50/51 protection", False),
                "pdif_test": ("Differential Protection", "Test 87 protection", False),
                "ptov_test": ("Overvoltage Protection", "Test 59 protection", False),
                "ptuv_test": ("Undervoltage Protection", "Test 27 protection", False),
            },
            "Measurement Tests": {
                "mmxu_verify": ("Measurement Verification", "Verify measurements", False),
                "msqi_test": ("Sequence Measurement", "Test sequence values", False),
            },
            "GOOSE Tests": {
                "goose_publish": ("GOOSE Publishing", "Test GOOSE transmission", False),
                "goose_subscribe": ("GOOSE Subscription", "Test GOOSE reception", False),
                "goose_performance": ("GOOSE Performance", "Measure GOOSE timing", False),
            },
            "Interlocking Tests": {
                "interlock_basic": ("Basic Interlocking", "Test interlock logic", False),
                "interlock_complex": ("Complex Interlocking", "Test advanced interlocks", False),
            },
            "Performance Tests": {
                "response_time": ("Response Time", "Measure control response", False),
                "throughput": ("Data Throughput", "Test data capacity", False),
            }
        }
        
        # Create tree structure
        for category, tests in test_categories.items():
            category_item = QTreeWidgetItem([category, "", ""])
            category_item.setFont(0, QFont("Arial", 9, QFont.Weight.Bold))
            
            for test_id, (test_name, description, required) in tests.items():
                test_item = QTreeWidgetItem([test_name, description, "Yes" if required else "No"])
                test_item.setData(0, Qt.ItemDataRole.UserRole, test_id)
                
                # Add checkbox
                test_item.setCheckState(0, Qt.CheckState.Checked if required else Qt.CheckState.Unchecked)
                
                # Disable unchecking for required tests
                if required:
                    test_item.setFlags(test_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                    test_item.setForeground(0, QBrush(QColor("darkgreen")))
                    
                category_item.addChild(test_item)
                
            self.test_tree.addTopLevelItem(category_item)
            category_item.setExpanded(True)
            
    def get_network_interfaces(self) -> List[str]:
        """Get list of network interfaces"""
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            # Filter out loopback and virtual interfaces
            return [iface for iface in interfaces if not iface.startswith(('lo', 'vir'))]
        except ImportError:
            # Fallback if netifaces not available
            return ['eth0', 'eth1', 'ens33', 'enp0s3']
            
    def update_time_sync_status(self):
        """Update time synchronization status display"""
        is_synced, accuracy_us = time_sync_manager.check_time_sync()
        
        if is_synced:
            self.sync_status_label.setText("✅ Synchronized")
            self.sync_status_label.setStyleSheet("color: green; font-weight: bold;")
            
            if accuracy_us:
                if accuracy_us < 1000:
                    self.sync_accuracy_label.setText(f"{accuracy_us:.1f} µs")
                else:
                    self.sync_accuracy_label.setText(f"{accuracy_us/1000:.1f} ms")
            else:
                self.sync_accuracy_label.setText("< 1 ms")
        else:
            self.sync_status_label.setText("❌ Not Synchronized")
            self.sync_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.sync_accuracy_label.setText("--")
            
        # Update current time
        timestamp_us = get_synchronized_timestamp_us()
        iso_time = time_sync_manager.format_timestamp_iso(timestamp_us // 1000)
        self.current_time_label.setText(iso_time)
        
    @pyqtSlot()
    def connect_selected_ieds(self):
        """Connect to selected IEDs"""
        selected_items = self.ied_tree.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select IEDs to connect")
            return
            
        # Get unique IEDs (not logical devices)
        ieds_to_connect = []
        for item in selected_items:
            # Check if it's an IED (top level) or get parent IED
            if item.parent() is None:
                ied_data = item.data(0, Qt.ItemDataRole.UserRole)
                if ied_data and item not in ieds_to_connect:
                    ieds_to_connect.append((item, ied_data))
                    
        if not ieds_to_connect:
            return
            
        # Connect to each IED
        connected_count = 0
        for item, ied_data in ieds_to_connect:
            ied_name = ied_data.get('@name', 'Unknown')
            ip_address = item.text(2)
            
            if not ip_address:
                self.log_message(f"No IP address for {ied_name}", "warning")
                continue
                
            try:
                # Create connection using pyiec61850
                connection = self.connection_manager.connect_to_ied(
                    ied_name, ip_address, 102  # MMS port
                )
                
                if connection:
                    self.active_connections[ied_name] = connection
                    item.setText(1, "✅ Connected")
                    item.setForeground(1, QBrush(QColor("green")))
                    connected_count += 1
                    self.log_message(f"Connected to {ied_name} ({ip_address})", "info")
                else:
                    item.setText(1, "❌ Failed")
                    item.setForeground(1, QBrush(QColor("red")))
                    self.log_message(f"Failed to connect to {ied_name}", "error")
                    
            except Exception as e:
                item.setText(1, "❌ Error")
                item.setForeground(1, QBrush(QColor("red")))
                self.log_message(f"Error connecting to {ied_name}: {str(e)}", "error")
                
        # Update UI
        if connected_count > 0:
            self.connection_status.setText(f"🟢 Connected ({connected_count})")
            self.disconnect_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
        else:
            self.connection_status.setText("🔴 Connection Failed")
            
    @pyqtSlot()
    def disconnect_selected_ieds(self):
        """Disconnect selected IEDs"""
        selected_items = self.ied_tree.selectedItems()
        
        for item in selected_items:
            if item.parent() is None:  # IED level
                ied_data = item.data(0, Qt.ItemDataRole.UserRole)
                ied_name = ied_data.get('@name', 'Unknown')
                
                if ied_name in self.active_connections:
                    self.connection_manager.disconnect_from_ied(ied_name)
                    del self.active_connections[ied_name]
                    item.setText(1, "Disconnected")
                    item.setForeground(1, QBrush(QColor("black")))
                    self.log_message(f"Disconnected from {ied_name}", "info")
                    
        # Update UI
        if not self.active_connections:
            self.connection_status.setText("🔴 Disconnected")
            self.disconnect_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
        else:
            self.connection_status.setText(f"🟢 Connected ({len(self.active_connections)})")
            
    @pyqtSlot(int)
    def on_test_mode_changed(self, index: int):
        """Handle test mode change"""
        self.test_mode = (index == 0)  # 0 = Test Mode, 1 = Live Mode
        
        if not self.test_mode:
            # Show warning for live mode
            reply = QMessageBox.warning(
                self,
                "Live Mode Warning",
                "⚠️ You are switching to LIVE MODE!\n\n"
                "This will send real commands to the IEDs.\n"
                "Make sure all safety conditions are met.\n\n"
                "Continue to Live Mode?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.test_mode_combo.setCurrentIndex(0)
                return
                
        # Update test executor
        if self.test_executor:
            self.test_executor.set_test_mode(self.test_mode)
            
        # Update status
        mode_text = "Test Mode" if self.test_mode else "LIVE MODE"
        self.status_message.setText(f"Mode: {mode_text}")
        
    @pyqtSlot(bool)
    def on_safety_check_toggled(self, checked: bool):
        """Handle safety check toggle"""
        self.safety_checks_enabled = checked
        
        if not checked:
            # Show warning
            reply = QMessageBox.warning(
                self,
                "Safety Warning",
                "⚠️ You are disabling safety checks!\n\n"
                "This may allow dangerous operations.\n"
                "Only disable if you know what you're doing.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.safety_check.setChecked(True)
                return
                
        # Update test executor
        if self.test_executor:
            self.test_executor.set_safety_checks(self.safety_checks_enabled)
            
        # Update status
        if self.safety_checks_enabled:
            self.safety_status.setText("🛡️ Safety ON")
            self.safety_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.safety_status.setText("⚠️ Safety OFF")
            self.safety_status.setStyleSheet("color: red; font-weight: bold;")
            
    @pyqtSlot()
    def start_tests(self):
        """Start commissioning tests"""
        if not self.active_connections:
            QMessageBox.warning(self, "No Connection", "Please connect to IEDs first")
            return
            
        # Get selected tests
        selected_tests = self.get_selected_tests()
        if not selected_tests:
            QMessageBox.warning(self, "No Tests", "Please select tests to execute")
            return
            
        # Confirm start
        test_count = len(selected_tests)
        ied_count = len(self.active_connections)
        
        message = f"Start {test_count} tests on {ied_count} IED(s)?\n\n"
        message += f"Mode: {'Test Mode' if self.test_mode else 'LIVE MODE'}\n"
        message += f"Safety: {'Enabled' if self.safety_checks_enabled else 'DISABLED'}"
        
        reply = QMessageBox.question(
            self, "Start Tests", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
            
        # Initialize test execution
        self.is_testing = True
        self.test_results.clear()
        self.current_test_index = 0
        self.selected_tests = selected_tests
        
        # Update UI
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.test_status.setText("🔄 Testing...")
        
        # Clear previous results
        self.execution_log.clear()
        self.results_table.setRowCount(0)
        
        # Start GOOSE monitoring if needed
        if any('goose' in test for test in selected_tests):
            self.start_goose_monitoring()
            
        # Execute tests
        self.execute_next_test()
        
    def get_selected_tests(self) -> List[str]:
        """Get list of selected tests"""
        selected_tests = []
        
        # Iterate through test tree
        for i in range(self.test_tree.topLevelItemCount()):
            category_item = self.test_tree.topLevelItem(i)
            
            for j in range(category_item.childCount()):
                test_item = category_item.child(j)
                
                if test_item.checkState(0) == Qt.CheckState.Checked:
                    test_id = test_item.data(0, Qt.ItemDataRole.UserRole)
                    if test_id:
                        selected_tests.append(test_id)
                        
        return selected_tests
        
    def execute_next_test(self):
        """Execute next test in queue"""
        if not self.is_testing or self.current_test_index >= len(self.selected_tests):
            self.finish_tests()
            return
            
        # Get current test
        test_id = self.selected_tests[self.current_test_index]
        
        # Update progress
        progress = int((self.current_test_index / len(self.selected_tests)) * 100)
        self.overall_progress.setValue(progress)
        self.current_test_label.setText(f"Executing: {test_id}")
        
        # Execute test on all connected IEDs
        for ied_name, connection in self.active_connections.items():
            self.log_message(f"Starting {test_id} on {ied_name}", "info")
            
            # Execute test asynchronously
            self.test_executor.execute_test_async(
                test_id, ied_name, connection,
                self.on_single_test_completed
            )
            
    def on_single_test_completed(self, result: TestResult):
        """Handle single test completion"""
        # Add to results
        self.test_results.append(result)
        
        # Update results table
        self.add_result_to_table(result)
        
        # Log result
        status_text = "PASSED" if result.status == TestStatus.PASSED else "FAILED"
        self.log_message(
            f"{result.test_name} on {result.ied_name}: {status_text}",
            "info" if result.status == TestStatus.PASSED else "error"
        )
        
        # Check if all IEDs completed current test
        current_test = self.selected_tests[self.current_test_index]
        completed_count = sum(
            1 for r in self.test_results 
            if r.test_id == current_test
        )
        
        if completed_count >= len(self.active_connections):
            # Move to next test
            self.current_test_index += 1
            self.execute_next_test()
            
    def finish_tests(self):
        """Finish test execution"""
        self.is_testing = False
        
        # Update UI
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.test_status.setText("✅ Complete")
        
        self.overall_progress.setValue(100)
        self.current_test_label.setText("All tests completed")
        
        # Update summary
        self.update_test_summary()
        
        # Stop GOOSE monitoring
        if self.monitoring_timer.isActive():
            self.stop_goose_monitoring()
            
        # Show completion message
        passed = sum(1 for r in self.test_results if r.status == TestStatus.PASSED)
        total = len(self.test_results)
        
        QMessageBox.information(
            self,
            "Tests Complete",
            f"Commissioning tests completed!\n\n"
            f"Total: {total}\n"
            f"Passed: {passed}\n"
            f"Failed: {total - passed}\n"
            f"Pass Rate: {(passed/total*100):.1f}%"
        )
        
    @pyqtSlot()
    def pause_tests(self):
        """Pause test execution"""
        # TODO: Implement pause functionality
        pass
        
    @pyqtSlot()
    def stop_tests(self):
        """Stop test execution"""
        if not self.is_testing:
            return
            
        reply = QMessageBox.question(
            self, "Stop Tests",
            "Are you sure you want to stop the tests?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.is_testing = False
            self.test_executor.stop_all_tests()
            self.finish_tests()
            self.log_message("Tests stopped by user", "warning")
            
    def add_result_to_table(self, result: TestResult):
        """Add test result to results table"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Test ID
        self.results_table.setItem(row, 0, QTableWidgetItem(result.test_id))
        
        # Test Name
        self.results_table.setItem(row, 1, QTableWidgetItem(result.test_name))
        
        # IED
        self.results_table.setItem(row, 2, QTableWidgetItem(result.ied_name))
        
        # Status
        status_item = QTableWidgetItem(result.status.value)
        if result.status == TestStatus.PASSED:
            status_item.setForeground(QBrush(QColor("green")))
        elif result.status == TestStatus.FAILED:
            status_item.setForeground(QBrush(QColor("red")))
        else:
            status_item.setForeground(QBrush(QColor("orange")))
        self.results_table.setItem(row, 3, status_item)
        
        # Duration
        duration_text = f"{result.duration:.2f}s" if result.duration else "--"
        self.results_table.setItem(row, 4, QTableWidgetItem(duration_text))
        
        # Details
        details = result.details or result.error_message or "--"
        self.results_table.setItem(row, 5, QTableWidgetItem(details))
        
        # Timestamp
        timestamp = datetime.fromtimestamp(result.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.results_table.setItem(row, 6, QTableWidgetItem(timestamp))
        
    def update_test_summary(self):
        """Update test summary display"""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.test_results if r.status == TestStatus.FAILED)
        
        self.total_tests_label.setText(str(total))
        self.passed_tests_label.setText(str(passed))
        self.failed_tests_label.setText(str(failed))
        
        if total > 0:
            pass_rate = (passed / total) * 100
            self.pass_rate_label.setText(f"{pass_rate:.1f}%")
        else:
            self.pass_rate_label.setText("0%")
            
    @pyqtSlot()
    def toggle_goose_monitoring(self):
        """Toggle GOOSE monitoring"""
        if self.monitoring_timer.isActive():
            self.stop_goose_monitoring()
        else:
            self.start_goose_monitoring()
            
    def start_goose_monitoring(self):
        """Start GOOSE monitoring"""
        if not self.goose_handler:
            QMessageBox.warning(self, "No GOOSE Handler", "GOOSE handler not initialized")
            return
            
        try:
            # Get network interface
            interface = self.interface_combo.currentText()
            
            # Start GOOSE receiver
            self.goose_handler.start_receiver(interface)
            
            # Start monitoring timer
            self.monitoring_timer.start(100)  # Update every 100ms
            
            # Update UI
            self.monitor_goose_btn.setText("⏹️ Stop Monitoring")
            self.log_message("GOOSE monitoring started", "info")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start GOOSE monitoring: {str(e)}")
            
    def stop_goose_monitoring(self):
        """Stop GOOSE monitoring"""
        # Stop timer
        self.monitoring_timer.stop()
        
        # Stop GOOSE receiver
        if self.goose_handler:
            self.goose_handler.stop_receiver()
            
        # Update UI
        self.monitor_goose_btn.setText("📡 Start Monitoring")
        self.log_message("GOOSE monitoring stopped", "info")
        
    @pyqtSlot()
    def update_monitoring(self):
        """Update monitoring displays"""
        if not self.goose_handler:
            return
            
        # Update GOOSE statistics
        goose_stats = self.goose_handler.get_goose_statistics()
        
        self.goose_stats_table.setRowCount(len(goose_stats))
        
        for row, (goose_id, stats) in enumerate(goose_stats.items()):
            self.goose_stats_table.setItem(row, 0, QTableWidgetItem(goose_id))
            self.goose_stats_table.setItem(row, 1, QTableWidgetItem(stats.get('publisher', '--')))
            self.goose_stats_table.setItem(row, 2, QTableWidgetItem(stats.get('status', '--')))
            self.goose_stats_table.setItem(row, 3, QTableWidgetItem(str(stats.get('stNum', 0))))
            self.goose_stats_table.setItem(row, 4, QTableWidgetItem(str(stats.get('sqNum', 0))))
            
            # Format last update time
            last_update = stats.get('last_update', 0)
            if last_update:
                update_time = datetime.fromtimestamp(last_update).strftime("%H:%M:%S.%f")[:-3]
            else:
                update_time = "--"
            self.goose_stats_table.setItem(row, 5, QTableWidgetItem(update_time))
            
    @pyqtSlot()
    def clear_goose_stats(self):
        """Clear GOOSE statistics"""
        self.goose_stats_table.setRowCount(0)
        if self.goose_handler:
            self.goose_handler.clear_statistics()
            
    @pyqtSlot(str, str)
    def on_test_started(self, test_id: str, ied_name: str):
        """Handle test started signal"""
        self.log_message(f"Test {test_id} started on {ied_name}", "info")
        
    @pyqtSlot(str, TestResult)
    def on_test_completed(self, test_id: str, result: TestResult):
        """Handle test completed signal"""
        self.on_single_test_completed(result)
        
    @pyqtSlot(str, str)
    def on_log_message(self, message: str, level: str):
        """Handle log message"""
        self.log_message(message, level)
        
    def log_message(self, message: str, level: str = "info"):
        """Add message to execution log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message with color based on level
        if level == "error":
            color = "red"
            prefix = "❌"
        elif level == "warning":
            color = "orange"
            prefix = "⚠️"
        elif level == "success":
            color = "green"
            prefix = "✅"
        else:
            color = "black"
            prefix = "ℹ️"
            
        formatted_message = f'<span style="color: {color};">[{timestamp}] {prefix} {message}</span>'
        self.execution_log.append(formatted_message)
        
        # Also update status message
        self.status_message.setText(message)
        
    @pyqtSlot()
    def export_results_html(self):
        """Export results to HTML"""
        if not self.test_results:
            QMessageBox.information(self, "No Results", "No test results to export")
            return
            
        try:
            filename = f"commissioning_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            html_content = self.report_generator.generate_html_report(
                self.test_results,
                self.scl_data,
                self.active_connections
            )
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            QMessageBox.information(self, "Export Complete", f"Report saved to {filename}")
            self.log_message(f"Report exported to {filename}", "success")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export report: {str(e)}")
            
    @pyqtSlot()
    def export_results_csv(self):
        """Export results to CSV"""
        if not self.test_results:
            QMessageBox.information(self, "No Results", "No test results to export")
            return
            
        try:
            filename = f"commissioning_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.report_generator.generate_csv_report(self.test_results, filename)
            
            QMessageBox.information(self, "Export Complete", f"Results saved to {filename}")
            self.log_message(f"Results exported to {filename}", "success")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results: {str(e)}")
            
    @pyqtSlot()
    def export_results_pdf(self):
        """Export results to PDF"""
        # TODO: Implement PDF export using reportlab
        QMessageBox.information(self, "Not Implemented", "PDF export not yet implemented")
        
    def closeEvent(self, event):
        """Handle widget close event"""
        # Disconnect all IEDs
        for ied_name in list(self.active_connections.keys()):
            self.connection_manager.disconnect_from_ied(ied_name)
            
        # Stop monitoring
        if self.monitoring_timer.isActive():
            self.stop_goose_monitoring()
            
        # Stop any running tests
        if self.is_testing:
            self.test_executor.stop_all_tests()
            
        event.accept()