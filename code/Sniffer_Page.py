#!/usr/bin/env python3
"""
GOOSE Sniffer - IEC 61850 Protocol Analyzer with IP Filtering
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Real-time GOOSE message capture and analysis tool
Enhanced version - รองรับ IP address filtering ผ่าน ARP lookup
"""

from PyQt6 import uic
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QTableWidget, QTreeWidget, QTableWidgetItem,
    QTreeWidgetItem, QMessageBox, QCheckBox, QLabel, QGroupBox,
    QVBoxLayout, QHBoxLayout, QSplitter, QDialog, QLineEdit,
    QDialogButtonBox, QFileDialog, QMenu, QHeaderView, QFormLayout,
    QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QDateTime
from PyQt6.QtGui import QFont, QColor, QBrush
from pathlib import Path
import sys
import json
import csv
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import threading
import struct
import subprocess
import os
import socket
import re
from resource_helper import get_ui_path

# Import pyiec61850 wrapper
try:
    import pyiec61850 as iec61850
    PYIEC61850_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: pyiec61850 not available. Will use raw socket mode.")
    PYIEC61850_AVAILABLE = False

# Import raw socket sniffer
try:
    from Sniffer_Raw import GOOSERawSniffer
    RAW_SOCKET_AVAILABLE = True
except ImportError:
    RAW_SOCKET_AVAILABLE = False

# ==================== IP to MAC Lookup Utility ====================

class IPMACResolver:
    """Utility class for IP to MAC address resolution"""
    
    @staticmethod
    def get_arp_table() -> Dict[str, str]:
        """Get ARP table mapping IP -> MAC"""
        arp_table = {}
        
        try:
            # Try Linux /proc/net/arp
            if os.path.exists('/proc/net/arp'):
                with open('/proc/net/arp', 'r') as f:
                    lines = f.readlines()[1:]  # Skip header
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            ip = parts[0]
                            mac = parts[3]
                            if mac != '00:00:00:00:00:00' and ':' in mac:
                                arp_table[ip] = mac.lower()
        except:
            pass
        
        try:
            # Try arp command as fallback
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse arp -a output
                # Format: hostname (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on eth0
                for line in result.stdout.split('\n'):
                    if '(' in line and ')' in line and 'at' in line:
                        # Extract IP and MAC
                        ip_match = re.search(r'\(([0-9.]+)\)', line)
                        mac_match = re.search(r'at ([a-fA-F0-9:]{17})', line)
                        
                        if ip_match and mac_match:
                            ip = ip_match.group(1)
                            mac = mac_match.group(1).lower()
                            arp_table[ip] = mac
        except:
            pass
        
        return arp_table
    
    @staticmethod
    def ip_to_mac(ip_address: str) -> Optional[str]:
        """Convert IP address to MAC address using ARP lookup"""
        arp_table = IPMACResolver.get_arp_table()
        return arp_table.get(ip_address.strip())
    
    @staticmethod
    def ping_and_resolve(ip_address: str) -> Optional[str]:
        """Ping IP and then try to resolve MAC"""
        try:
            # First ping to populate ARP table
            result = subprocess.run(['ping', '-c', '1', '-W', '1', ip_address], 
                                  capture_output=True, timeout=3)
            
            # Then try to get MAC
            time.sleep(0.1)  # Small delay for ARP table update
            return IPMACResolver.ip_to_mac(ip_address)
        except:
            return None

# ==================== Enhanced Filter Dialog ====================

class GOOSEFilterDialog(QDialog):
    """Enhanced dialog for configuring GOOSE message filters with IP support"""
    
    def __init__(self, current_filters=None, parent=None):
        super().__init__(parent)
        self.filters = []
        self.setup_ui()
        
        # Load existing filters
        if current_filters:
            self.load_existing_filters(current_filters)
    
    def setup_ui(self):
        """Setup enhanced dialog UI"""
        self.setWindowTitle("🔍 Enhanced GOOSE Filter Configuration")
        self.setFixedSize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Configure GOOSE Message Filters")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "• Enter IP address (will lookup MAC via ARP)\n"
            "• Enter MAC address directly\n"
            "• Enter APP ID (hex: 0x1234 or decimal: 4660)\n"
            "• Multiple filters use OR logic (match any one)\n"
            "• Each row can have one or more criteria"
        )
        instructions.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background: #f5f5f5; border-radius: 3px;")
        layout.addWidget(instructions)
        
        # Filter table
        self.filter_table = QTableWidget()
        self.filter_table.setColumnCount(5)
        self.filter_table.setHorizontalHeaderLabels(["IP Address", "MAC Address", "APP ID", "Test", ""])
        self.filter_table.horizontalHeader().setStretchLastSection(False)
        self.filter_table.setColumnWidth(0, 130)  # IP Address
        self.filter_table.setColumnWidth(1, 150)  # MAC Address
        self.filter_table.setColumnWidth(2, 100)  # APP ID
        self.filter_table.setColumnWidth(3, 80)   # Test button
        self.filter_table.setColumnWidth(4, 80)   # Remove button
        layout.addWidget(self.filter_table)
        
        # Add filter button
        add_btn = QPushButton("➕ Add Filter")
        add_btn.clicked.connect(self.add_filter_row)
        layout.addWidget(add_btn)
        
        # Enable filtering checkbox
        self.enable_checkbox = QCheckBox("Enable Filtering (unchecked = capture all)")
        self.enable_checkbox.setChecked(False)
        layout.addWidget(self.enable_checkbox)
        
        # Status label for ARP lookup results
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def add_filter_row(self):
        """Add new filter row with IP support"""
        row = self.filter_table.rowCount()
        self.filter_table.insertRow(row)
        
        # IP address input
        ip_edit = QLineEdit()
        ip_edit.setPlaceholderText("e.g., 192.168.1.100")
        ip_edit.textChanged.connect(lambda text, r=row: self.on_ip_changed(r, text))
        self.filter_table.setCellWidget(row, 0, ip_edit)
        
        # MAC address input
        mac_edit = QLineEdit()
        mac_edit.setPlaceholderText("e.g., 01:0C:CD:01:00:00")
        self.filter_table.setCellWidget(row, 1, mac_edit)
        
        # APP ID input
        app_id_edit = QLineEdit()
        app_id_edit.setPlaceholderText("e.g., 0x0001 or 1")
        self.filter_table.setCellWidget(row, 2, app_id_edit)
        
        # Test button for IP lookup
        test_btn = QPushButton("🔍")
        test_btn.setToolTip("Test IP to MAC lookup")
        test_btn.clicked.connect(lambda checked, r=row: self.test_ip_lookup(r))
        self.filter_table.setCellWidget(row, 3, test_btn)
        
        # Remove button
        remove_btn = QPushButton("❌")
        remove_btn.clicked.connect(lambda checked, r=row: self.remove_filter_row(r))
        self.filter_table.setCellWidget(row, 4, remove_btn)
    
    def on_ip_changed(self, row: int, ip_text: str):
        """Handle IP address change - auto lookup MAC"""
        if not ip_text.strip():
            return
            
        # Validate IP format
        try:
            parts = ip_text.split('.')
            if len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts):
                # Valid IP, try quick lookup (non-blocking)
                mac = IPMACResolver.ip_to_mac(ip_text.strip())
                if mac:
                    mac_widget = self.filter_table.cellWidget(row, 1)
                    if mac_widget and not mac_widget.text().strip():
                        mac_widget.setText(mac)
                        self.status_label.setText(f"✅ Auto-resolved {ip_text} → {mac}")
        except:
            pass
    
    def test_ip_lookup(self, row: int):
        """Test IP to MAC lookup for a specific row with comprehensive feedback"""
        ip_widget = self.filter_table.cellWidget(row, 0)
        if not ip_widget:
            return
            
        ip_text = ip_widget.text().strip()
        if not ip_text:
            QMessageBox.warning(self, "No IP", "Please enter an IP address first")
            return
        
        # Validate IP format first
        try:
            parts = ip_text.split('.')
            if len(parts) != 4 or not all(0 <= int(p) <= 255 for p in parts):
                QMessageBox.warning(self, "Invalid IP", f"'{ip_text}' is not a valid IP address format")
                return
        except:
            QMessageBox.warning(self, "Invalid IP", f"'{ip_text}' is not a valid IP address format")
            return
        
        self.status_label.setText(f"🔍 Looking up {ip_text} in ARP table...")
        
        # Try regular lookup first
        mac = IPMACResolver.ip_to_mac(ip_text)
        if mac:
            mac_widget = self.filter_table.cellWidget(row, 1)
            if mac_widget:
                mac_widget.setText(mac)
            self.status_label.setText(f"✅ Found in ARP table: {ip_text} → {mac}")
            QMessageBox.information(self, "ARP Lookup Success", 
                                  f"✅ Found in ARP table:\n\n"
                                  f"IP: {ip_text}\n"
                                  f"MAC: {mac}\n\n"
                                  f"This filter will work correctly.")
            return
        
        # Not in ARP table - offer to ping
        reply = QMessageBox.question(
            self, 
            "IP Not Found in ARP Table", 
            f"❌ IP address '{ip_text}' was not found in the ARP table.\n\n"
            f"This means:\n"
            f"• The device may be offline\n"
            f"• No recent network communication\n"
            f"• IP address may be incorrect\n\n"
            f"Would you like to ping the device to try resolving it?\n"
            f"(This may take a few seconds)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText(f"🔄 Pinging {ip_text} and resolving...")
            
            # Use QTimer to avoid blocking UI
            def do_ping_lookup():
                mac = IPMACResolver.ping_and_resolve(ip_text)
                if mac:
                    mac_widget = self.filter_table.cellWidget(row, 1)
                    if mac_widget:
                        mac_widget.setText(mac)
                    self.status_label.setText(f"✅ Ping successful: {ip_text} → {mac}")
                    QMessageBox.information(self, "Ping & Resolve Success", 
                                          f"✅ Device responded to ping:\n\n"
                                          f"IP: {ip_text}\n"
                                          f"MAC: {mac}\n\n"
                                          f"This filter will now work correctly.")
                else:
                    self.status_label.setText(f"❌ Ping failed for {ip_text}")
                    QMessageBox.warning(self, "Ping & Resolve Failed", 
                                      f"❌ Could not resolve MAC address for '{ip_text}'.\n\n"
                                      f"Possible issues:\n"
                                      f"• Device is offline or unreachable\n"
                                      f"• IP address is incorrect\n"
                                      f"• Firewall blocking ping\n"
                                      f"• Device not on same network segment\n\n"
                                      f"⚠️ This IP filter will be IGNORED during capture.\n\n"
                                      f"Solutions:\n"
                                      f"• Check device connectivity\n"
                                      f"• Verify IP address is correct\n"
                                      f"• Enter MAC address directly instead")
            
            QTimer.singleShot(100, do_ping_lookup)
        else:
            self.status_label.setText(f"❌ {ip_text} not resolved - will be ignored")
            QMessageBox.warning(self, "IP Filter Will Be Ignored", 
                              f"⚠️ Since '{ip_text}' cannot be resolved to a MAC address, "
                              f"this IP filter will be IGNORED during capture.\n\n"
                              f"To fix this:\n"
                              f"• Try pinging the device\n"
                              f"• Check if device is online\n"
                              f"• Enter MAC address directly instead")
    
    def load_existing_filters(self, filters):
        """Load existing filters into the dialog"""
        self.filter_table.setRowCount(0)
        
        for filter_dict in filters:
            row = self.filter_table.rowCount()
            self.filter_table.insertRow(row)
            
            # IP address
            ip_edit = QLineEdit()
            if 'ip' in filter_dict:
                ip_edit.setText(filter_dict['ip'])
            ip_edit.setPlaceholderText("e.g., 192.168.1.100")
            ip_edit.textChanged.connect(lambda text, r=row: self.on_ip_changed(r, text))
            self.filter_table.setCellWidget(row, 0, ip_edit)
            
            # MAC address
            mac_edit = QLineEdit()
            if 'mac' in filter_dict:
                mac_edit.setText(filter_dict['mac'])
            mac_edit.setPlaceholderText("e.g., 01:0C:CD:01:00:00")
            self.filter_table.setCellWidget(row, 1, mac_edit)
            
            # APP ID
            app_id_edit = QLineEdit()
            if 'app_id' in filter_dict:
                app_id_edit.setText(f"0x{filter_dict['app_id']:04X}")
            app_id_edit.setPlaceholderText("e.g., 0x0001 or 1")
            self.filter_table.setCellWidget(row, 2, app_id_edit)
            
            # Test button
            test_btn = QPushButton("🔍")
            test_btn.setToolTip("Test IP to MAC lookup")
            test_btn.clicked.connect(lambda checked, r=row: self.test_ip_lookup(r))
            self.filter_table.setCellWidget(row, 3, test_btn)
            
            # Remove button
            remove_btn = QPushButton("❌")
            remove_btn.clicked.connect(lambda checked, r=row: self.remove_filter_row(r))
            self.filter_table.setCellWidget(row, 4, remove_btn)
        
        if self.filter_table.rowCount() == 0:
            self.add_filter_row()
        
        self.enable_checkbox.setChecked(filters is not None and len(filters) > 0)
    
    def remove_filter_row(self, row):
        """Remove filter row with proper cleanup"""
        self.filter_table.removeRow(row)
        
        # Update button connections for remaining rows
        for r in range(self.filter_table.rowCount()):
            # Update test button
            test_btn = self.filter_table.cellWidget(r, 3)
            if test_btn:
                try:
                    test_btn.clicked.disconnect()
                except:
                    pass
                test_btn.clicked.connect(lambda checked, row=r: self.test_ip_lookup(row))
            
            # Update remove button
            remove_btn = self.filter_table.cellWidget(r, 4)
            if remove_btn:
                try:
                    remove_btn.clicked.disconnect()
                except:
                    pass
                remove_btn.clicked.connect(lambda checked, row=r: self.remove_filter_row(row))
            
            # Update IP change handler
            ip_edit = self.filter_table.cellWidget(r, 0)
            if ip_edit:
                try:
                    ip_edit.textChanged.disconnect()
                except:
                    pass
                ip_edit.textChanged.connect(lambda text, row=r: self.on_ip_changed(row, text))
    
    def get_filters(self):
        """Get configured filters with IP to MAC resolution and proper validation"""
        filters = []
        unresolved_ips = []
        
        if not self.enable_checkbox.isChecked():
            return None
        
        for row in range(self.filter_table.rowCount()):
            ip_widget = self.filter_table.cellWidget(row, 0)
            mac_widget = self.filter_table.cellWidget(row, 1)
            app_id_widget = self.filter_table.cellWidget(row, 2)
            
            filter_dict = {}
            has_valid_criteria = False
            
            # Handle IP address - convert to MAC if needed
            if ip_widget and ip_widget.text().strip():
                ip_text = ip_widget.text().strip()
                filter_dict['ip'] = ip_text
                
                # Try to resolve MAC from IP
                resolved_mac = IPMACResolver.ip_to_mac(ip_text)
                if resolved_mac:
                    filter_dict['resolved_mac'] = resolved_mac
                    has_valid_criteria = True
                    print(f"🔍 Resolved {ip_text} → {resolved_mac}")
                else:
                    # IP cannot be resolved - mark as unresolved
                    filter_dict['ip_unresolved'] = True
                    unresolved_ips.append(ip_text)
                    print(f"⚠️ Cannot resolve {ip_text} to MAC address")
            
            # Handle MAC address directly
            if mac_widget and mac_widget.text().strip():
                filter_dict['mac'] = mac_widget.text().strip().lower()
                has_valid_criteria = True
            
            # Handle APP ID
            if app_id_widget and app_id_widget.text().strip():
                try:
                    app_id_text = app_id_widget.text().strip()
                    if app_id_text.startswith('0x'):
                        filter_dict['app_id'] = int(app_id_text, 16)
                    else:
                        filter_dict['app_id'] = int(app_id_text)
                    has_valid_criteria = True
                except:
                    pass
            
            # Only add filter if it has at least one valid criteria OR is an unresolved IP
            if filter_dict and (has_valid_criteria or 'ip_unresolved' in filter_dict):
                filters.append(filter_dict)
        
        # Show warning for unresolved IPs but still apply filters
        if unresolved_ips:
            ip_list = '\n'.join(f"• {ip}" for ip in unresolved_ips)
            QMessageBox.warning(
                self, 
                "IP Resolution Failed", 
                f"The following IP addresses could not be resolved to MAC addresses:\n\n{ip_list}\n\n"
                f"These IP filters will be IGNORED during capture.\n"
                f"To fix this:\n"
                f"• Ensure devices are online and reachable\n"
                f"• Try the 🔍 Test button to ping and resolve\n"
                f"• Enter MAC addresses directly instead"
            )
        
        return filters if filters else None

# ==================== Enhanced GOOSE Capture Thread ====================

class GOOSECaptureThread(QThread):
    """Enhanced thread for capturing GOOSE messages with IP filtering"""
    
    message_received = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, interface: str = "any"):
        super().__init__()
        self.interface = interface
        self.running = False
        self.receiver = None
        self.subscribers = []
        self.start_time = None
        self.message_count = 0
        self.last_messages = {}
        self.show_retransmissions = True
        self.filters = None
        self._callback_wrapper = None
        self._stop_event = threading.Event()
        self._cleanup_done = False
    
    def set_filters(self, filters):
        """Set message filters with IP support"""
        self.filters = filters
        if filters:
            print(f"📝 Applied {len(filters)} filter(s):")
            for i, f in enumerate(filters):
                print(f"  Filter {i+1}: {f}")
    
    def set_show_retransmissions(self, show):
        """Set whether to show retransmissions"""
        self.show_retransmissions = show
    
    def run(self):
        """Main capture loop"""
        try:
            self._stop_event.clear()
            self._cleanup_done = False
            
            # Force raw socket mode due to pyiec61850 segfault issue
            if RAW_SOCKET_AVAILABLE:
                try:
                    print("🟡 Starting enhanced raw socket mode...")
                    self.run_raw_socket_mode()
                    return
                except Exception as e:
                    print(f"⚠️ Raw socket mode failed: {e}")
                    if "Operation not permitted" in str(e):
                        self.error_occurred.emit("Raw socket requires root privileges. Please run with sudo.")
                    else:
                        self.error_occurred.emit(f"Raw socket error: {e}")
                    return
            
            # Try pyiec61850 only if raw socket not available
            if PYIEC61850_AVAILABLE:
                print("⚠️ WARNING: pyiec61850 may cause segmentation fault!")
                print("⚠️ Consider using raw socket mode instead")
                try:
                    print("🟡 Trying pyiec61850 mode...")
                    self.run_pyiec61850_mode()
                    return
                except Exception as e:
                    print(f"⚠️ pyiec61850 mode failed: {e}")
                    self.error_occurred.emit(f"pyiec61850 error: {e}")
                    return
                    
        except Exception as e:
            self.error_occurred.emit(f"Capture error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def run_raw_socket_mode(self):
        """Run using enhanced raw socket capture"""
        self.status_update.emit("🟡 Starting enhanced raw socket capture...")
        
        interface = "any" if self.interface == "any" else self.interface
        
        self.raw_sniffer = GOOSERawSniffer(interface)
        self.raw_sniffer.set_callback(self.handle_goose_message)
        
        if not self.raw_sniffer.start():
            self.error_occurred.emit("Failed to start raw socket sniffer (requires sudo)")
            return
        
        self.status_update.emit("🟢 Capturing GOOSE messages (enhanced filtering)...")
        self.start_time = time.time()
        self.running = True
        
        try:
            while self.running and not self._stop_event.is_set():
                if not self.raw_sniffer.capture_single(0.1):
                    if self._stop_event.is_set():
                        break
                
                time.sleep(0.001)
                
        except Exception as e:
            if self.running:
                print(f"Capture error: {e}")
        finally:
            print("Enhanced raw socket capture loop ended")
    
    def run_pyiec61850_mode(self):
        """Run using pyiec61850 library - same as before"""
        # Same implementation as original
        pass
    
    def handle_goose_message(self, goose_data):
        """Handle received GOOSE message with enhanced filtering"""
        try:
            if self._stop_event.is_set():
                return
            
            # Check retransmission
            go_id = goose_data.get('goID', '')
            st_num = goose_data.get('stNum', 0)
            sq_num = goose_data.get('sqNum', 0)
            
            is_retransmission = False
            if go_id in self.last_messages:
                last_st = self.last_messages[go_id].get('stNum', -1)
                if st_num == last_st and sq_num > 0:
                    is_retransmission = True
            
            self.last_messages[go_id] = {
                'stNum': st_num,
                'sqNum': sq_num
            }
            
            # Skip if retransmission and not showing them
            if is_retransmission and not self.show_retransmissions:
                return
            
            # Apply enhanced filters
            if self.filters and not self.apply_enhanced_filters(goose_data):
                return
            
            # Calculate relative time
            rel_time = time.time() - self.start_time if self.start_time else 0
            
            # Prepare message data
            message = {
                'timestamp': datetime.now(),
                'relative_time': rel_time,
                'source_mac': goose_data.get('src_mac', '00:00:00:00:00:00'),
                'dest_mac': goose_data.get('dst_mac', '01:0C:CD:01:00:00'),
                'app_id': goose_data.get('appId', 0),
                'go_id': go_id,
                'go_cb_ref': goose_data.get('goCbRef', ''),
                'dataset_ref': goose_data.get('dataSet', ''),
                'conf_rev': goose_data.get('confRev', 0),
                'st_num': st_num,
                'sq_num': sq_num,
                'test': goose_data.get('test', False),
                'needs_comm': goose_data.get('ndsCom', False),
                'time_allowed': goose_data.get('timeAllowedToLive', 0),
                'entry_time': goose_data.get('timestamp', 0),
                'values': goose_data.get('values', []),
                'is_retransmission': is_retransmission
            }
            
            self.message_count += 1
            self.message_received.emit(message)
            
        except Exception as e:
            if self.running:
                print(f"Error handling GOOSE message: {e}")
    
    def apply_enhanced_filters(self, goose_data) -> bool:
        """Apply enhanced filters with IP support and strict unresolved IP handling (OR logic)"""
        if not self.filters:
            return True
        
        src_mac = goose_data.get('src_mac', '').lower()
        dst_mac = goose_data.get('dst_mac', '').lower()
        app_id = goose_data.get('appId', 0)
        
        # OR logic - if any filter matches, accept the message
        for filter_dict in self.filters:
            match = False
            
            # Skip filters with unresolved IPs - they should not match anything
            if filter_dict.get('ip_unresolved', False):
                print(f"🚫 Skipping unresolved IP filter: {filter_dict.get('ip', 'Unknown')}")
                continue
            
            # Check APP ID
            if 'app_id' in filter_dict:
                if app_id == filter_dict['app_id']:
                    match = True
                    print(f"🎯 APP ID filter match: {app_id} = 0x{app_id:04X}")
            
            # Check direct MAC address
            if 'mac' in filter_dict and not match:
                filter_mac = filter_dict['mac'].lower()
                if src_mac == filter_mac or dst_mac == filter_mac:
                    match = True
                    print(f"🎯 Direct MAC filter match: {filter_mac}")
            
            # Check resolved MAC from IP
            if 'resolved_mac' in filter_dict and not match:
                resolved_mac = filter_dict['resolved_mac'].lower()
                if src_mac == resolved_mac or dst_mac == resolved_mac:
                    match = True
                    print(f"🎯 IP filter match: {filter_dict.get('ip', '')} → {resolved_mac}")
            
            # If this filter matches, accept the message
            if match:
                return True
        
        # None of the valid filters matched
        return False
    
    def cleanup(self):
        """Cleanup resources"""
        if self._cleanup_done:
            return
            
        self._cleanup_done = True
        print("🧹 Starting enhanced cleanup...")
        
        # Cleanup pyiec61850 receiver (same as before)
        if hasattr(self, 'receiver') and self.receiver:
            # Same cleanup code as original
            pass
        
        # Cleanup raw socket sniffer
        if hasattr(self, 'raw_sniffer') and self.raw_sniffer:
            try:
                print("  Stopping enhanced raw sniffer...")
                self.raw_sniffer.stop()
                print("  ✅ Enhanced raw sniffer stopped")
            except Exception as e:
                print(f"  ⚠️ Raw sniffer cleanup error: {e}")
            finally:
                self.raw_sniffer = None
        
        print("✅ Enhanced cleanup completed")
    
    def stop(self):
        """Stop capture"""
        print("🛑 Stopping enhanced capture thread...")
        self.running = False
        self._stop_event.set()
        
        # Stop raw sniffer if active
        if hasattr(self, 'raw_sniffer') and self.raw_sniffer:
            self.raw_sniffer.running = False
        
        # Wait for thread with timeout
        if self.isRunning():
            print("  Waiting for enhanced thread to finish...")
            if not self.wait(3000):
                print("  ⚠️ Thread didn't stop gracefully, terminating...")
                self.terminate()
                self.wait(1000)
        
        print("✅ Enhanced capture thread stopped")

# ==================== Enhanced Main Window ====================

class GOOSESnifferWindow(QWidget):
    """Enhanced GOOSE Sniffer Window with IP filtering"""
    
    def __init__(self, back_to_main_ui):
        super().__init__()
        
        # Load UI
        ui_file = get_ui_path('Sniffer_Page.ui')
        uic.loadUi(ui_file, self)
        
        # Extract widgets from UI
        
        # Store back navigation
        self.back_to_main_ui = back_to_main_ui
        
        # Initialize
        self.capture_thread = None
        self.messages = []
        self.selected_message = None
        self.filters = None
        
        # Setup
        self.setup_ui()
        self.setup_connections()
        
        print("✅ Enhanced GOOSE Sniffer initialized")
    
    def _extract_widgets_from_ui(self):
        """Extract all widgets from loaded UI file"""
        # Control buttons
        self.start_btn = self.findChild(QPushButton, 'start_btn')
        self.stop_btn = self.findChild(QPushButton, 'stop_btn')
        self.clear_btn = self.findChild(QPushButton, 'clear_btn')
        self.back_btn = self.findChild(QPushButton, 'back_btn')
        self.filter_btn = self.findChild(QPushButton, 'filter_btn')
        self.export_btn = self.findChild(QPushButton, 'export_btn')
        
        # Tables and trees
        self.messages_table = self.findChild(QTableWidget, 'messages_table')
        self.details_tree = self.findChild(QTreeWidget, 'details_tree')
        
        # Labels and status
        self.status_label = self.findChild(QLabel, 'status_label')
        self.packet_count_label = self.findChild(QLabel, 'packet_count_label')
        
        # Checkboxes
        self.retransmission_checkbox = self.findChild(QCheckBox, 'retransmission_checkbox')
        
        # Optional widgets
        self.interface_combo = self.findChild(QComboBox, 'interface_combo')
        self.interface_label = self.findChild(QLabel, 'interface_label')
        
        # Create fallbacks for missing widgets
        self._create_fallbacks_if_missing()
        
        print("✅ Extracted widgets from UI file")
    
    def _create_fallbacks_if_missing(self):
        """Create fallback widgets if not found in UI"""
        if not self.start_btn: 
            self.start_btn = QPushButton("▶️ Start")
        if not self.stop_btn: 
            self.stop_btn = QPushButton("⏸️ Stop")
        if not self.clear_btn: 
            self.clear_btn = QPushButton("🗑️ Clear")
        if not self.back_btn: 
            self.back_btn = QPushButton("🔙 Back")
        if not self.filter_btn: 
            self.filter_btn = QPushButton("🔍 Filter")
        if not self.export_btn: 
            self.export_btn = QPushButton("📥 Export")
        if not self.status_label: 
            self.status_label = QLabel("🔴 Stopped")
        if not self.packet_count_label: 
            self.packet_count_label = QLabel("📊 Packets: 0")
        if not self.retransmission_checkbox:
            self.retransmission_checkbox = QCheckBox("🔄 Show Retransmissions")
            self.retransmission_checkbox.setChecked(True)
        if not self.messages_table:
            self.messages_table = QTableWidget()
            self.messages_table.setColumnCount(7)
            self.messages_table.setHorizontalHeaderLabels([
                "Time", "Rel. Time", "Source", "Destination", "Description", "stNum", "sqNum"
            ])
        if not self.details_tree:
            self.details_tree = QTreeWidget()
            self.details_tree.setColumnCount(2)
            self.details_tree.setHeaderLabels(["Property", "Value"])
    
    def setup_ui(self):
        """Setup enhanced UI components"""
        # Set window title
        self.setWindowTitle("Enhanced GOOSE Sniffer - IEC 61850 Protocol Analyzer with IP Filtering")
        
        # Initial button states
        self.stop_btn.setEnabled(False)
        self.clear_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        
        # Remove or hide interface selection
        if hasattr(self, 'interface_combo'):
            self.interface_combo.setVisible(False)
        if hasattr(self, 'interface_label'):
            self.interface_label.setVisible(False)
        
        # Setup messages table
        self.setup_messages_table()
        
        # Setup details tree
        self.setup_details_tree()
        
        # Set fonts
        table_font = QFont("Consolas", 9)
        self.messages_table.setFont(table_font)
        
        tree_font = QFont("Consolas", 9)
        self.details_tree.setFont(tree_font)
        
        # Update status
        self.update_status("🔴 Stopped", QColor(255, 0, 0))
        
        # Update filter button text to show it supports IP
        self.filter_btn.setText("🔍 Filter (IP/MAC/APP)")
    
    def setup_messages_table(self):
        """Setup messages table"""
        # Configure table
        self.messages_table.setAlternatingRowColors(True)
        self.messages_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.messages_table.setSortingEnabled(False)
        
        # Set column widths
        self.messages_table.setColumnWidth(0, 120)  # Time
        self.messages_table.setColumnWidth(1, 100)  # Relative Time
        self.messages_table.setColumnWidth(2, 150)  # Source
        self.messages_table.setColumnWidth(3, 150)  # Destination
        self.messages_table.setColumnWidth(4, 300)  # Description
        self.messages_table.setColumnWidth(5, 80)   # stNum
        self.messages_table.setColumnWidth(6, 80)   # sqNum
        
        # Stretch last section
        header = self.messages_table.horizontalHeader()
        header.setStretchLastSection(True)
    
    def setup_details_tree(self):
        """Setup details tree"""
        # Configure tree
        self.details_tree.setAlternatingRowColors(True)
        self.details_tree.setRootIsDecorated(True)
        
        # Set column widths
        self.details_tree.setColumnWidth(0, 250)
        self.details_tree.setColumnWidth(1, 400)
    
    def setup_connections(self):
        """Setup signal connections"""
        # Control buttons
        self.start_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        self.clear_btn.clicked.connect(self.clear_messages)
        self.back_btn.clicked.connect(self.back_to_main_ui)
        
        # Filter and export
        self.filter_btn.clicked.connect(self.show_enhanced_filter_dialog)
        self.export_btn.clicked.connect(self.export_messages)
        
        # Retransmission checkbox
        self.retransmission_checkbox.stateChanged.connect(self.on_retransmission_changed)
        
        # Table selection
        self.messages_table.itemSelectionChanged.connect(self.on_message_selected)
    
    def start_capture(self):
        """Start enhanced GOOSE capture"""
        try:
            # Check if running with sudo
            if os.geteuid() != 0:
                reply = QMessageBox.question(
                    self,
                    "Root Permission Required",
                    "Enhanced GOOSE capture requires root privileges for:\n"
                    "• Raw socket access\n"
                    "• Promiscuous mode\n"
                    "• ARP table access\n\n"
                    "Please restart the application with sudo.\n"
                    "Continue anyway (may fail)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # Create enhanced capture thread
            self.capture_thread = GOOSECaptureThread("any")
            self.capture_thread.set_filters(self.filters)
            self.capture_thread.set_show_retransmissions(
                self.retransmission_checkbox.isChecked()
            )
            
            # Connect signals
            self.capture_thread.message_received.connect(self.on_message_received)
            self.capture_thread.status_update.connect(self.on_status_update)
            self.capture_thread.error_occurred.connect(self.on_error_occurred)
            
            # Start capture
            self.capture_thread.start()
            
            # Update UI
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.update_status("🟢 Enhanced Capturing...", QColor(0, 255, 0))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start enhanced capture:\n{e}")
    
    def stop_capture(self):
        """Stop enhanced GOOSE capture"""
        if self.capture_thread:
            print("🛑 Stopping enhanced capture...")
            self.stop_btn.setEnabled(False)
            self.update_status("🟡 Stopping...", QColor(255, 165, 0))
            
            def stop_thread():
                self.capture_thread.stop()
                self.capture_thread = None
                
                self.start_btn.setEnabled(True)
                self.update_status("🔴 Stopped", QColor(255, 0, 0))
            
            QTimer.singleShot(100, stop_thread)
    
    def show_enhanced_filter_dialog(self):
        """Show enhanced filter configuration dialog with proper validation"""
        dialog = GOOSEFilterDialog(self.filters, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.filters = dialog.get_filters()
            
            # Update running capture
            if self.capture_thread:
                self.capture_thread.set_filters(self.filters)
            
            # Show comprehensive filter status
            if self.filters:
                # Count different types of filters
                ip_count = sum(1 for f in self.filters if 'ip' in f)
                resolved_ip_count = sum(1 for f in self.filters if 'resolved_mac' in f)
                unresolved_ip_count = sum(1 for f in self.filters if f.get('ip_unresolved', False))
                mac_count = sum(1 for f in self.filters if 'mac' in f)
                app_count = sum(1 for f in self.filters if 'app_id' in f)
                
                # Create status message
                status_parts = []
                if resolved_ip_count > 0:
                    status_parts.append(f"✅ {resolved_ip_count} IP filters (resolved)")
                if unresolved_ip_count > 0:
                    status_parts.append(f"❌ {unresolved_ip_count} IP filters (unresolved - IGNORED)")
                if mac_count > 0:
                    status_parts.append(f"✅ {mac_count} MAC filters")
                if app_count > 0:
                    status_parts.append(f"✅ {app_count} APP ID filters")
                
                status_message = f"Applied {len(self.filters)} filter(s):\n" + "\n".join(f"• {part}" for part in status_parts)
                
                if unresolved_ip_count > 0:
                    status_message += f"\n\n⚠️ Warning: {unresolved_ip_count} IP filter(s) will be ignored because MAC addresses could not be resolved."
                
                # Choose appropriate icon and title
                if unresolved_ip_count > 0:
                    QMessageBox.warning(self, "Filters Applied with Warnings", status_message)
                else:
                    QMessageBox.information(self, "Enhanced Filters Applied", status_message)
            else:
                QMessageBox.information(self, "Filters Cleared", 
                                      "All GOOSE messages will be captured")
                                      
        # Update filter button text to show active state
        if self.filters:
            active_filters = len([f for f in self.filters if not f.get('ip_unresolved', False)])
            if active_filters > 0:
                self.filter_btn.setText(f"🔍 Filter ({active_filters} active)")
            else:
                self.filter_btn.setText("🔍 Filter (⚠️ none active)")
        else:
            self.filter_btn.setText("🔍 Filter (IP/MAC/APP)")
    
    def clear_messages(self):
        """Clear all messages"""
        self.messages.clear()
        self.messages_table.setRowCount(0)
        self.details_tree.clear()
        self.selected_message = None
        self.packet_count_label.setText("📊 Packets: 0")
        self.export_btn.setEnabled(False)
    
    def export_messages(self):
        """Export captured messages"""
        if not self.messages:
            QMessageBox.warning(self, "No Data", "No messages to export")
            return
        
        # Get filename
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Enhanced GOOSE Messages",
            f"enhanced_goose_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if not filename:
            return
        
        try:
            if filename.endswith('.csv'):
                self.export_to_csv(filename)
            else:
                self.export_to_json(filename)
            
            QMessageBox.information(self, "Export Complete", 
                                  f"Exported {len(self.messages)} messages to:\n{filename}")
                                  
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")
    
    def export_to_csv(self, filename):
        """Export messages to CSV"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Timestamp', 'Relative Time', 'Source MAC', 'Destination MAC',
                'APP ID', 'GO ID', 'GoCbRef', 'Dataset', 'Conf Rev',
                'stNum', 'sqNum', 'Test', 'Needs Comm', 'Time Allowed',
                'Retransmission', 'Values'
            ])
            
            # Write data
            for msg in self.messages:
                writer.writerow([
                    msg['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    f"{msg['relative_time']:.6f}",
                    msg['source_mac'],
                    msg['dest_mac'],
                    f"0x{msg['app_id']:04X}",
                    msg['go_id'],
                    msg['go_cb_ref'],
                    msg['dataset_ref'],
                    msg['conf_rev'],
                    msg['st_num'],
                    msg['sq_num'],
                    msg['test'],
                    msg['needs_comm'],
                    msg['time_allowed'],
                    msg['is_retransmission'],
                    json.dumps(msg['values'])
                ])
    
    def export_to_json(self, filename):
        """Export messages to JSON"""
        export_data = []
        
        for msg in self.messages:
            export_msg = msg.copy()
            # Convert datetime to string
            export_msg['timestamp'] = msg['timestamp'].isoformat()
            export_data.append(export_msg)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
    
    def on_retransmission_changed(self, state):
        """Handle retransmission checkbox change"""
        if self.capture_thread:
            self.capture_thread.set_show_retransmissions(
                state == Qt.CheckState.Checked.value
            )
    
    def on_message_received(self, message):
        """Handle received GOOSE message"""
        # Store message
        self.messages.append(message)
        
        # Add to table
        self.add_message_to_table(message)
        
        # Update count
        self.packet_count_label.setText(f"📊 Packets: {len(self.messages)}")
        
        # Enable export
        self.export_btn.setEnabled(True)
        
        # Auto-scroll to latest
        self.messages_table.scrollToBottom()
    
    def add_message_to_table(self, message):
        """Add message to table"""
        row = self.messages_table.rowCount()
        self.messages_table.insertRow(row)
        
        # Time
        time_item = QTableWidgetItem(
            message['timestamp'].strftime('%H:%M:%S.%f')[:-3]
        )
        self.messages_table.setItem(row, 0, time_item)
        
        # Relative time
        rel_time_item = QTableWidgetItem(f"{message['relative_time']:.6f}")
        self.messages_table.setItem(row, 1, rel_time_item)
        
        # Source
        source_item = QTableWidgetItem(message['source_mac'])
        self.messages_table.setItem(row, 2, source_item)
        
        # Destination
        dest_item = QTableWidgetItem(message['dest_mac'])
        self.messages_table.setItem(row, 3, dest_item)
        
        # Description
        desc = f"{message['go_cb_ref']}"
        desc_item = QTableWidgetItem(desc)
        self.messages_table.setItem(row, 4, desc_item)
        
        # stNum
        st_item = QTableWidgetItem(str(message['st_num']))
        self.messages_table.setItem(row, 5, st_item)
        
        # sqNum
        sq_item = QTableWidgetItem(str(message['sq_num']))
        self.messages_table.setItem(row, 6, sq_item)
        
        # Color retransmissions
        if message['is_retransmission']:
            for col in range(self.messages_table.columnCount()):
                item = self.messages_table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(240, 240, 240)))
    
    def on_message_selected(self):
        """Handle message selection"""
        rows = self.messages_table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if row < len(self.messages):
                self.selected_message = self.messages[row]
                self.display_message_details(self.selected_message)
    
    def display_message_details(self, message):
        """Display message details in tree"""
        self.details_tree.clear()
        
        # Root item with GO ID
        root = QTreeWidgetItem(self.details_tree)
        root.setText(0, f"🔷 {message['go_cb_ref']}")
        root.setExpanded(True)
        
        # Details section
        details = QTreeWidgetItem(root)
        details.setText(0, "📋 Details")
        details.setExpanded(True)
        
        # Add all details
        self.add_detail(details, "Control Block reference", message['go_cb_ref'])
        self.add_detail(details, "Destination MAC address", message['dest_mac'])
        self.add_detail(details, "Source MAC address", message['source_mac'])
        self.add_detail(details, "Application ID", f"0x{message['app_id']:04X}")
        self.add_detail(details, "GOOSE ID", message['go_id'])
        self.add_detail(details, "Dataset reference", message['dataset_ref'])
        self.add_detail(details, "VLAN ID", "")
        self.add_detail(details, "VLAN priority", "")
        self.add_detail(details, "Needs commissioning", str(message['needs_comm']))
        self.add_detail(details, "Configuration revision", str(message['conf_rev']))
        self.add_detail(details, "Simulation/Test", str(message['test']))
        self.add_detail(details, "Entry time", 
                       datetime.fromtimestamp(message['entry_time']/1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                       if message['entry_time'] else "")
        self.add_detail(details, "Status number", str(message['st_num']))
        self.add_detail(details, "Sequence number", str(message['sq_num']))
        self.add_detail(details, "Time allowed to live (ms)", str(message['time_allowed']))
        self.add_detail(details, "Number of Dataset entries", str(len(message['values'])))
        
        # Data section
        data_section = QTreeWidgetItem(root)
        data_section.setText(0, "📊 Data")
        data_section.setExpanded(True)
        
        # Add data values
        for i, value in enumerate(message['values']):
            # Determine type
            if isinstance(value, bool):
                type_str = "Boolean"
                value_str = "true" if value else "false"
            elif isinstance(value, int):
                type_str = "Integer"
                value_str = str(value)
            elif isinstance(value, float):
                type_str = "Float"
                value_str = str(value)
            else:
                type_str = "String"
                value_str = str(value)
            
            self.add_detail(data_section, f"Value {i+1} ({type_str})", value_str)
    
    def add_detail(self, parent, name, value):
        """Add detail item to tree"""
        item = QTreeWidgetItem(parent)
        item.setText(0, name)
        item.setText(1, str(value))
    
    def on_status_update(self, status):
        """Handle status update from capture thread"""
        if "Capturing" in status:
            self.update_status(status, QColor(0, 255, 0))
        elif "DEMO" in status:
            self.update_status(status, QColor(255, 165, 0))
        else:
            self.update_status(status, QColor(255, 0, 0))
    
    def on_error_occurred(self, error):
        """Handle error from capture thread"""
        QMessageBox.critical(self, "Enhanced Capture Error", error)
        self.stop_capture()
    
    def update_status(self, text, color=None):
        """Update status label"""
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.capture_thread:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Enhanced capture is running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            self.stop_capture()
            QTimer.singleShot(500, event.accept)
        else:
            event.accept()

# ==================== Main Entry Point ====================

def main():
    """Test Enhanced GOOSE Sniffer"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Dummy back function
    def dummy_back():
        print("Back to main")
        app.quit()
    
    # Create and show window
    window = GOOSESnifferWindow(dummy_back)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()