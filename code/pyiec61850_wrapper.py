#!/usr/bin/env python3
"""
PyIEC61850 Enhanced Wrapper - Complete IEC 61850 Solution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive wrapper including all IEC 61850 functionality:
- MMS Client/Server
- GOOSE Publisher/Subscriber  
- IED Model and Tree Management
- SCL Parser Helper

Modified Version: No automatic GOOSE publish on start
"""


import pyiec61850 as iec61850
import time
import threading
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import IntEnum
from dataclasses import dataclass
import json
from PyQt6.QtCore import QObject, pyqtSignal

PYIEC61850_AVAILABLE = False
try:
    import pyiec61850 as iec61850
    PYIEC61850_AVAILABLE = True
    print("✅ pyiec61850 loaded successfully")
except ImportError:
    print("⚠️ pyiec61850 not available - using fallback mode")
    # Create dummy iec61850 module
    class DummyIEC61850:
        def __init__(self):
            pass
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    
    iec61850 = DummyIEC61850()

# Import time sync utilities
try:
    from Uranus.code.iec61850_system.time_sync_utils import (
        get_synchronized_timestamp_ms,
        get_synchronized_timestamp_us,
        get_utc_time_with_quality,
        check_time_synchronization
    )
    TIME_SYNC_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: time_sync_utils not found, using system time")
    TIME_SYNC_AVAILABLE = False
    
    # Fallback functions
    def get_synchronized_timestamp_ms():
        return int(time.time() * 1000)
    
    def get_synchronized_timestamp_us():
        return int(time.time() * 1_000_000)
    
    def get_utc_time_with_quality():
        return int(time.time() * 1000), 0x40  # Not synchronized

# เพิ่ม debug flag
DEBUG_MODE = True

def debug_log(msg: str):
    """Debug logging helper"""
    if DEBUG_MODE:
        print(f"🐛 DEBUG: {msg}")
    # เพิ่ม print ตรงๆ เพื่อให้แน่ใจว่าแสดง
    print(f"[DEBUG] {msg}")

# ==================== Common Classes ====================

class IedClientError(IntEnum):
    """IED Client Error Codes"""
    IED_ERROR_OK = iec61850.IED_ERROR_OK
    IED_ERROR_NOT_CONNECTED = iec61850.IED_ERROR_NOT_CONNECTED
    IED_ERROR_ALREADY_CONNECTED = iec61850.IED_ERROR_ALREADY_CONNECTED
    IED_ERROR_CONNECTION_LOST = iec61850.IED_ERROR_CONNECTION_LOST
    IED_ERROR_SERVICE_NOT_SUPPORTED = iec61850.IED_ERROR_SERVICE_NOT_SUPPORTED
    IED_ERROR_CONNECTION_REJECTED = iec61850.IED_ERROR_CONNECTION_REJECTED
    IED_ERROR_TIMEOUT = iec61850.IED_ERROR_TIMEOUT

class FunctionalConstraint(IntEnum):
    """Functional Constraints (FC)"""
    FC_ST = iec61850.IEC61850_FC_ST   # Status
    FC_MX = iec61850.IEC61850_FC_MX   # Measurement
    FC_SP = iec61850.IEC61850_FC_SP   # Setpoint
    FC_SV = iec61850.IEC61850_FC_SV   # Substitution
    FC_CF = iec61850.IEC61850_FC_CF   # Configuration
    FC_DC = iec61850.IEC61850_FC_DC   # Description
    FC_SG = iec61850.IEC61850_FC_SG   # Setting group
    FC_SE = iec61850.IEC61850_FC_SE   # Setting group editable
    FC_SR = iec61850.IEC61850_FC_SR   # Service response
    FC_OR = iec61850.IEC61850_FC_OR   # Operate received
    FC_BL = iec61850.IEC61850_FC_BL   # Blocking
    FC_EX = iec61850.IEC61850_FC_EX   # Extended definition
    FC_CO = iec61850.IEC61850_FC_CO   # Control

class MmsType(IntEnum):
    """MMS Value Types"""
    MMS_ARRAY = iec61850.MMS_ARRAY
    MMS_STRUCTURE = iec61850.MMS_STRUCTURE
    MMS_BOOLEAN = iec61850.MMS_BOOLEAN
    MMS_BIT_STRING = iec61850.MMS_BIT_STRING
    MMS_INTEGER = iec61850.MMS_INTEGER
    MMS_UNSIGNED = iec61850.MMS_UNSIGNED
    MMS_FLOAT = iec61850.MMS_FLOAT
    MMS_OCTET_STRING = iec61850.MMS_OCTET_STRING
    MMS_VISIBLE_STRING = iec61850.MMS_VISIBLE_STRING
    MMS_GENERALIZED_TIME = iec61850.MMS_GENERALIZED_TIME
    MMS_BINARY_TIME = iec61850.MMS_BINARY_TIME
    MMS_BCD = iec61850.MMS_BCD
    MMS_OBJ_ID = iec61850.MMS_OBJ_ID
    MMS_STRING = iec61850.MMS_STRING
    MMS_UTC_TIME = iec61850.MMS_UTC_TIME

# ==================== Data Classes ====================

@dataclass
class IEDElement:
    """IED Tree Element"""
    name: str
    element_type: str  # 'IED', 'LD', 'LN', 'DO', 'DA'
    value: Any = None
    fc: Optional[str] = None
    path: str = ""
    editable: bool = False
    children: List['IEDElement'] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class GOOSEDataset:
    """GOOSE Dataset Element"""
    path: str
    value: Any
    data_type: str
    quality: int = 0
    timestamp: Optional[int] = None

@dataclass 
class ReportControlBlock:
    """Report Control Block"""
    name: str
    rpt_id: str
    dataset: str
    conf_rev: int
    buffered: bool
    buf_time: int = 0
    enabled: bool = False

# ==================== MMS Client ====================

class MMSClient:
    """MMS/IEC 61850 Client using pyiec61850"""
    
    def __init__(self):
        self.connection = None
        self.connected = False
        self.server_model = None
    
    def connect(self, hostname: str, port: int = 102) -> bool:
        """Connect to IEC 61850 server"""
        try:
            # Create connection
            self.connection = iec61850.IedConnection_create()
            
            # Connect
            error = iec61850.IedConnection_connect(self.connection, hostname, port)
            
            if error == iec61850.IED_ERROR_OK:
                self.connected = True
                print(f"✅ Connected to {hostname}:{port}")
                return True
            else:
                print(f"❌ Connection failed: Error code {error}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        if self.connection and self.connected:
            iec61850.IedConnection_close(self.connection)
            iec61850.IedConnection_destroy(self.connection)
            self.connection = None
            self.connected = False
            self.server_model = None
            print("🔌 Disconnected")
    
    def read(self, object_reference: str, fc: FunctionalConstraint = FunctionalConstraint.FC_MX) -> Any:
        """Read data attribute value"""
        if not self.connected:
            raise Exception("Not connected")
        
        try:
            # Read object
            [mms_value, error] = iec61850.pyWrap_IedConnection_readObject(
                self.connection, object_reference, fc.value
            )
            
            if error != iec61850.IED_ERROR_OK:
                raise Exception(f"Read failed: Error {error}")
            
            # Convert to Python value
            result = self._mms_value_to_python(mms_value)
            
            # Clean up
            iec61850.MmsValue_delete(mms_value)
            
            return result
            
        except Exception as e:
            print(f"Read error: {e}")
            raise
    
    def write(self, object_reference: str, value: Any, fc: FunctionalConstraint = FunctionalConstraint.FC_SP) -> bool:
        """Write data attribute value"""
        if not self.connected:
            raise Exception("Not connected")
        
        try:
            # Create MmsValue
            mms_value = self._python_to_mms_value(value)
            
            # Write
            error = iec61850.pyWrap_IedConnection_writeObject(
                self.connection, object_reference, fc.value, mms_value
            )
            
            # Clean up
            iec61850.MmsValue_delete(mms_value)
            
            return error == iec61850.IED_ERROR_OK
            
        except Exception as e:
            print(f"Write error: {e}")
            return False
    
    def get_server_directory(self, with_model: bool = False) -> Optional[IEDElement]:
        """Get complete server directory as tree structure"""
        if not self.connected:
            raise Exception("Not connected")
        
        try:
            if with_model and hasattr(iec61850, 'IedConnection_getServerDirectory'):
                # Try to get complete model
                [self.server_model, error] = iec61850.IedConnection_getServerDirectory(
                    self.connection, True
                )
                
                if error == iec61850.IED_ERROR_OK and self.server_model:
                    return self._parse_server_model(self.server_model)
            
            # Fallback to manual tree building
            return self._build_server_tree_manual()
            
        except Exception as e:
            print(f"Error getting server directory: {e}")
            return None
    
    def _build_server_tree_manual(self) -> IEDElement:
        """Build server tree manually"""
        root = IEDElement("Server", "ROOT")
        
        # Get logical devices
        devices = self.get_logical_devices()
        
        for ld_name in devices:
            ld_element = IEDElement(ld_name, "LD", path=ld_name)
            
            # Get logical nodes
            nodes = self.get_logical_nodes(ld_name)
            
            for ln_name in nodes:
                ln_path = f"{ld_name}/{ln_name}"
                ln_element = IEDElement(ln_name, "LN", path=ln_path)
                
                # Get data objects (if available)
                if hasattr(self, 'get_logical_node_directory'):
                    dos = self.get_logical_node_directory(ln_path)
                    
                    for do_name in dos:
                        do_path = f"{ln_path}.{do_name}"
                        do_element = IEDElement(do_name, "DO", path=do_path)
                        ln_element.children.append(do_element)
                
                ld_element.children.append(ln_element)
            
            root.children.append(ld_element)
        
        return root
    
    def get_logical_devices(self) -> List[str]:
        """Get list of logical devices"""
        if not self.connected:
            raise Exception("Not connected")
        
        try:
            [device_list, error] = iec61850.IedConnection_getLogicalDeviceList(self.connection)
            
            if error != iec61850.IED_ERROR_OK:
                raise Exception(f"Failed to get devices: Error {error}")
            
            devices = []
            device = device_list
            while device:
                devices.append(iec61850.toCharP(device.data))
                device = iec61850.LinkedList_getNext(device)
            
            # Clean up
            iec61850.LinkedList_destroy(device_list)
            
            return devices
            
        except Exception as e:
            print(f"Error getting logical devices: {e}")
            raise
    
    def get_logical_nodes(self, logical_device: str) -> List[str]:
        """Get logical nodes in a device"""
        if not self.connected:
            raise Exception("Not connected")
        
        try:
            [node_list, error] = iec61850.IedConnection_getLogicalDeviceDirectory(
                self.connection, logical_device
            )
            
            if error != iec61850.IED_ERROR_OK:
                raise Exception(f"Failed to get nodes: Error {error}")
            
            nodes = []
            node = node_list
            while node:
                nodes.append(iec61850.toCharP(node.data))
                node = iec61850.LinkedList_getNext(node)
            
            # Clean up
            iec61850.LinkedList_destroy(node_list)
            
            return nodes
            
        except Exception as e:
            print(f"Error getting logical nodes: {e}")
            raise
    
    def _python_to_mms_value(self, value: Any):
        """Convert Python value to MmsValue"""
        if isinstance(value, bool):
            return iec61850.MmsValue_newBoolean(value)
        elif isinstance(value, int):
            return iec61850.MmsValue_newIntegerFromInt32(value)
        elif isinstance(value, float):
            return iec61850.MmsValue_newFloat(value)
        elif isinstance(value, str):
            return iec61850.MmsValue_newVisibleString(value)
        else:
            # Default to string
            return iec61850.MmsValue_newVisibleString(str(value))
    
    def _mms_value_to_python(self, mms_value) -> Any:
        """Convert MmsValue to Python value"""
        if not mms_value:
            return None
        
        value_type = iec61850.MmsValue_getType(mms_value)
        
        if value_type == iec61850.MMS_BOOLEAN:
            return iec61850.MmsValue_getBoolean(mms_value)
        elif value_type == iec61850.MMS_INTEGER:
            return iec61850.MmsValue_toInt32(mms_value)
        elif value_type == iec61850.MMS_FLOAT:
            return iec61850.MmsValue_toFloat(mms_value)
        elif value_type == iec61850.MMS_VISIBLE_STRING:
            return iec61850.MmsValue_toString(mms_value)
        else:
            # Try to convert to string
            return iec61850.MmsValue_toString(mms_value)
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()

# ==================== GOOSE Publisher ====================

class GOOSEPublisher:
    """GOOSE Publisher using pyiec61850"""
    
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.publisher = None
        self.dataset = None
        self.dataset_values = []
        self.st_num = 0
        self.sq_num = 0
        self.goose_enabled = False
        self._retransmission_thread = None
        self._stop_retransmission = threading.Event()
        self._first_publish = True  # Track if this is first publish
        debug_log(f"GOOSEPublisher init with interface: {interface}")
    
    def create(self, go_cb_ref: Optional[str] = None, 
                dataset_ref: Optional[str] = None,
                go_id: Optional[str] = None,
                app_id: Optional[int] = None,
                conf_rev: Optional[int] = None,
                dst_mac: Optional[str] = None) -> bool:
        """Create GOOSE publisher"""
        # ⭐⭐⭐ CRITICAL DEBUG - Show exactly what values are being used ⭐⭐⭐
        print(f"\n🔴 CRITICAL DEBUG - GOOSEPublisher.create() called with:")
        print(f"   app_id parameter: {app_id} (type: {type(app_id)})")
        print(f"   dst_mac parameter: {dst_mac}")
        print(f"   go_id: {go_id}")
        print(f"   go_cb_ref: {go_cb_ref}")
    
        try:
            debug_log(f"Creating GOOSE publisher on interface: {self.interface}")

            # Create CommParameters and set values
            params = iec61850.CommParameters()

            # Set APP ID if provided
            if app_id is not None:
                params.appId = app_id
                print(f"🔴 DEBUG: Set params.appId = {app_id} (0x{app_id:04X})")
                debug_log(f"Set appId in CommParameters: 0x{app_id:04X}")
            else:
                print(f"🔴 DEBUG: No app_id provided, using default")

            # Set destination MAC if provided
            if dst_mac:
                print(f"🔴 DEBUG: Trying to set MAC address: {dst_mac}")
                debug_log(f"Trying to set MAC address: {dst_mac}")
     
                # Method 1: Try CommParameters_setDstAddress if available
                if hasattr(iec61850, 'CommParameters_setDstAddress'):
                    # Convert MAC string to list of integers
                    mac_parts = dst_mac.split(':')
                    if len(mac_parts) == 6:
                        mac_ints = [int(part, 16) for part in mac_parts]
                        debug_log(f"Using CommParameters_setDstAddress with: {mac_ints}")
                        iec61850.CommParameters_setDstAddress(params, 
                            mac_ints[0], mac_ints[1], mac_ints[2],
                            mac_ints[3], mac_ints[4], mac_ints[5])
                        print(f"🔴 DEBUG: MAC set successfully using setDstAddress")
                    else:
                        print(f"🔴 DEBUG: Invalid MAC format: {dst_mac}")
                        debug_log(f"Invalid MAC format: {dst_mac}")
                else:
                    print(f"🔴 DEBUG: CommParameters_setDstAddress not available")
                    debug_log("CommParameters_setDstAddress not found, skipping MAC setting")

            # Create publisher with parameters  
            print(f"\n🔴 DEBUG: Creating publisher with GoosePublisher_createEx")
            print(f"   Interface: {self.interface}")
            print(f"   params.appId = {getattr(params, 'appId', 'NO ATTR')}")
        
            self.publisher = iec61850.GoosePublisher_createEx(params, self.interface, False)

            if not self.publisher:
               print(f"❌ GoosePublisher_createEx returned NULL")
               return False
   
            debug_log(f"Publisher object created: {self.publisher}")
            print(f"✅ GOOSE Publisher created successfully")
        
            # Show what was actually created
            if app_id is not None:
                print(f"📌 Publisher created with APP ID: 0x{app_id:04X}")
            if dst_mac:
                print(f"📌 Publisher created with MAC: {dst_mac}")

            # Apply additional configuration if provided
            if go_cb_ref or dataset_ref or go_id:
                self.set_gocb_values(
                    go_id=go_id or "TestGOOSE",
                    dataset_ref=dataset_ref or "TestIED/LLN0$Dataset1",
                    go_cb_ref=go_cb_ref,
                    conf_rev=conf_rev or 1
                )

            return True

        except Exception as e:
            print(f"❌ Create publisher failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_gocb_values(self, go_id: str, dataset_ref: str, 
                       go_cb_ref: Optional[str] = None,
                       conf_rev: int = 1, 
                       time_allowed_to_live: int = 10000):
        """Set GOOSE Control Block values"""
        debug_log(f"Setting GOCB values: go_id={go_id}, dataset_ref={dataset_ref}, go_cb_ref={go_cb_ref}")
        
        if not self.publisher:
            raise Exception("Publisher not created")
        
        # Set GOOSE control block reference
        if not go_cb_ref:
            go_cb_ref = f"TestIED/LLN0$GO${go_id}"
        
        debug_log(f"Setting GoCbRef: {go_cb_ref}")
        iec61850.GoosePublisher_setGoCbRef(self.publisher, go_cb_ref)
        
        debug_log(f"Setting DataSetRef: {dataset_ref}")
        iec61850.GoosePublisher_setDataSetRef(self.publisher, dataset_ref)
        
        debug_log(f"Setting GoID: {go_id}")
        iec61850.GoosePublisher_setGoID(self.publisher, go_id)
        
        debug_log(f"Setting ConfRev: {conf_rev}")
        iec61850.GoosePublisher_setConfRev(self.publisher, conf_rev)
        
        debug_log(f"Setting TimeAllowedToLive: {time_allowed_to_live}")
        iec61850.GoosePublisher_setTimeAllowedToLive(self.publisher, time_allowed_to_live)
        
        # Set simulation to false
        iec61850.GoosePublisher_setSimulation(self.publisher, False)
        
        # Set needs commission to false
        iec61850.GoosePublisher_setNeedsCommission(self.publisher, False)
        
        print(f"✅ GOOSE Control Block configured: {go_cb_ref}")
    
    def set_dst_mac(self, dst_mac: str):
        """Set destination MAC address"""
        debug_log(f"Setting destination MAC: {dst_mac}")
        
        if not self.publisher:
            raise Exception("Publisher not created")
        
        try:
            # Check if GoosePublisher_setDstMac is available
            if hasattr(iec61850, 'GoosePublisher_setDstMac'):
                # Parse MAC address string to bytes array
                # Expected format: "01:0C:CD:01:00:00"
                mac_parts = dst_mac.split(':')
                if len(mac_parts) != 6:
                    raise ValueError(f"Invalid MAC address format: {dst_mac}")
                
                # Convert to bytes array
                mac_bytes = [int(part, 16) for part in mac_parts]
                debug_log(f"MAC bytes: {mac_bytes}")
                
                # Set destination MAC using pyiec61850
                iec61850.GoosePublisher_setDstMac(self.publisher, 
                                                mac_bytes[0], mac_bytes[1], mac_bytes[2],
                                                mac_bytes[3], mac_bytes[4], mac_bytes[5])
                
                print(f"✅ Destination MAC set to: {dst_mac}")
            else:
                # Function not available in this version
                print(f"⚠️ Warning: GoosePublisher_setDstMac not available in this pyiec61850 version")
                print(f"   Will use default multicast MAC for GOOSE")
                
                # Try alternative method if available
                if hasattr(iec61850, 'Ethernet_setDstMac'):
                    debug_log("Trying alternative Ethernet_setDstMac method")
                    # Alternative implementation
            
        except Exception as e:
            print(f"⚠️ Warning: Could not set destination MAC: {e}")
            # Continue anyway, will use default multicast MAC
    
    def set_dataset(self, values: List[Dict[str, Any]]):
        """Set dataset values"""
        debug_log(f"Setting dataset with {len(values)} values")
        
        try:
            # Don't clear if we're actively publishing
            # Create new dataset values
            new_dataset_values = []
            
            # Add each value
            for i, value_info in enumerate(values):
                value = value_info.get('value', '')
                value_type = value_info.get('type', 'visible-string')
                path = value_info.get('path', f'item_{i}')
                
                debug_log(f"  [{i}] path={path}, value={value}, type={value_type}")
                
                if value_type == 'boolean':
                    bool_val = value in ['true', 'True', '1', True]
                    mms_val = iec61850.MmsValue_newBoolean(bool_val)
                    debug_log(f"    Created boolean MmsValue: {bool_val}")
                elif value_type == 'integer':
                    int_val = int(value)
                    mms_val = iec61850.MmsValue_newIntegerFromInt32(int_val)
                    debug_log(f"    Created integer MmsValue: {int_val}")
                elif value_type == 'float':
                    float_val = float(value)
                    mms_val = iec61850.MmsValue_newFloat(float_val)
                    debug_log(f"    Created float MmsValue: {float_val}")
                elif value_type == 'visible-string':
                    str_val = str(value)
                    mms_val = iec61850.MmsValue_newVisibleString(str_val)
                    debug_log(f"    Created string MmsValue: {str_val}")
                elif value_type == 'utc-time':
                    timestamp_ms = int(value) if str(value).isdigit() else int(time.time() * 1000)
                    mms_val = iec61850.MmsValue_newUtcTimeByMsTime(timestamp_ms)
                    debug_log(f"    Created timestamp MmsValue: {timestamp_ms}")
                elif value_type == 'bit-string':
                    quality = int(value, 16) if '0x' in str(value) else int(value)
                    debug_log(f"Creating bit-string with value: {quality}, hex: 0x{quality:04X}")
                    mms_val = iec61850.MmsValue_newBitString(16)
                    iec61850.MmsValue_setBitStringFromInteger(mms_val, quality)
                    debug_log(f"Created bitstring MmsValue for quality: 0x{quality:04X}")
                else:
                    str_val = str(value)
                    mms_val = iec61850.MmsValue_newVisibleString(str_val)
                    debug_log(f"    Created default string MmsValue: {str_val}")
                
                new_dataset_values.append(mms_val)
            
            # Replace old dataset
            self.dataset_values = new_dataset_values
            debug_log(f"Dataset values updated: {len(self.dataset_values)} values")
            
            # Re-enable to create new LinkedList
            self.goose_enabled = False
            self.dataset = None
            
            # Enable only if we have values
            if self.dataset_values:
                self.enable(create_default=False)
                
        except Exception as e:
            print(f"Error setting dataset: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_dataset(self):
        """Clear dataset values"""
        # Don't delete MmsValues if already published
        # libiec61850 manages them after GoosePublisher_publish
        
        # Just clear our references
        self.dataset_values.clear()
        self.dataset = None
        self.goose_enabled = False
    
    def add_boolean_value(self, value: bool):
        """Add boolean value to dataset"""
        mms_val = iec61850.MmsValue_newBoolean(value)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def add_int32_value(self, value: int):
        """Add int32 value to dataset"""
        mms_val = iec61850.MmsValue_newIntegerFromInt32(value)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def add_float_value(self, value: float):
        """Add float value to dataset"""
        mms_val = iec61850.MmsValue_newFloat(value)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def add_string_value(self, value: str):
        """Add string value to dataset"""
        mms_val = iec61850.MmsValue_newVisibleString(value)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def add_quality_value(self, quality: int = 0):
        """Add quality (bit string) value to dataset"""
        mms_val = iec61850.MmsValue_newBitString(16)  # 16 bits for quality
        iec61850.MmsValue_setBitStringFromInteger(mms_val, quality)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def add_timestamp_value(self, timestamp_ms: Optional[int] = None):
        """Add timestamp value to dataset"""
        if timestamp_ms is None:
            # Use synchronized time
            timestamp_ms = get_synchronized_timestamp_ms()
            debug_log(f"Using synchronized timestamp: {timestamp_ms}")
    
        mms_val = iec61850.MmsValue_newUtcTimeByMsTime(timestamp_ms)
        self.dataset_values.append(mms_val)
        return len(self.dataset_values) - 1
    
    def enable(self, create_default: bool = True):
        """Enable GOOSE publishing"""
        debug_log(f"Enabling GOOSE publisher (create_default={create_default})")
        
        if not self.publisher:
            raise Exception("Publisher not created")
        
        if not self.dataset_values and create_default:
            debug_log("No dataset values, adding default boolean")
            # Add default empty dataset
            self.add_boolean_value(False)
        elif not self.dataset_values:
            debug_log("No dataset values - waiting for actual data")
            return  # Don't enable yet
        
        # Create dataset as LinkedList
        debug_log("Creating LinkedList for dataset")
        self.dataset = iec61850.LinkedList_create()
        
        if not self.dataset:
            raise Exception("Failed to create dataset LinkedList")
        
        debug_log(f"LinkedList created: {self.dataset}")
        
        # Add all values to LinkedList
        for i, mms_val in enumerate(self.dataset_values):
            debug_log(f"  Adding value [{i}] to LinkedList")
            iec61850.LinkedList_add(self.dataset, mms_val)
        
        self.goose_enabled = True
        print(f"✅ GOOSE Publisher enabled with {len(self.dataset_values)} dataset values")
    
    def publish(self, increase_stnum: bool = False) -> bool:
        """Publish GOOSE message"""
        debug_log(f"Publishing GOOSE: increase_stnum={increase_stnum}, enabled={self.goose_enabled}")
        
        if not self.publisher:
            debug_log("❌ No publisher object")
            return False
            
        if not self.goose_enabled:
            debug_log("❌ GOOSE not enabled")
            return False
        
        try:
            # Enable if not enabled
            if not self.dataset:
                debug_log("Dataset not ready, enabling...")
                self.enable(create_default=False)
                
            # Still no dataset? Can't publish
            if not self.dataset:
                debug_log("❌ No dataset available")
                return False
            
            # Increase state number if requested
            if increase_stnum:
                debug_log(f"Increasing stNum from {self.st_num}")
                iec61850.GoosePublisher_increaseStNum(self.publisher)
                self.st_num += 1
                self.sq_num = 0
                debug_log(f"New stNum: {self.st_num}, sqNum reset to 0")
            else:
                # Just increment sequence number
                self.sq_num += 1
                debug_log(f"Setting sqNum to {self.sq_num}")
                iec61850.GoosePublisher_setSqNum(self.publisher, self.sq_num)
            
            # Publish
            debug_log(f"Calling GoosePublisher_publish with dataset: {self.dataset}")
            result = iec61850.GoosePublisher_publish(self.publisher, self.dataset)
            debug_log(f"GoosePublisher_publish returned: {result}")
            
            if result == 0:
                debug_log("✅ GOOSE published successfully!")
                if self._first_publish:
                    self._first_publish = False
                    print("📡 First GOOSE message published!")
                return True
            else:
                debug_log(f"❌ GOOSE publish failed with code: {result}")
                return False
            
        except Exception as e:
            print(f"Error publishing: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def publish_with_retransmission(self, intervals: Optional[List[int]] = None):
        """Publish with IEC 61850 retransmission pattern"""
        debug_log(f"Starting publish with retransmission, intervals: {intervals}")
        
        if not intervals:
            # Default IEC 61850 retransmission intervals (ms)
            intervals = [1, 2, 4, 8, 16, 32, 64, 128, 256, 500]
        
        # Stop any existing retransmission first
        self.stop_retransmission()
        
        # Ensure we have dataset
        if not self.dataset and self.dataset_values:
            debug_log("Dataset not ready, enabling first")
            self.enable(create_default=False)
        
        # If still no dataset, don't start retransmission
        if not self.dataset:
            debug_log("No dataset available - cannot start retransmission")
            return
        
        # Start new retransmission thread
        self._stop_retransmission.clear()
        self._retransmission_thread = threading.Thread(
            target=self._retransmission_worker,
            args=(intervals,),
            daemon=True
        )
        debug_log("Starting retransmission thread")
        self._retransmission_thread.start()
    
    def _retransmission_worker(self, intervals: List[int]):
        """Worker thread for retransmission"""
        debug_log(f"Retransmission worker started with intervals: {intervals}")
        
        try:
            # First transmission (state change)
            debug_log("First transmission (state change)")
            if self.publish(increase_stnum=True):
                debug_log("✅ First transmission successful")
            else:
                debug_log("❌ First transmission failed")
            
            # Retransmissions
            for i, interval in enumerate(intervals):
                debug_log(f"Waiting {interval}ms before retransmission {i+1}")
                if self._stop_retransmission.wait(interval / 1000.0):
                    debug_log("Retransmission stopped by request")
                    break
                    
                debug_log(f"Retransmission {i+1}")
                if self.publish(increase_stnum=False):
                    debug_log(f"✅ Retransmission {i+1} successful")
                else:
                    debug_log(f"❌ Retransmission {i+1} failed")
            
            # Continue with last interval
            debug_log(f"Continuing with last interval: {intervals[-1]}ms")
            while not self._stop_retransmission.is_set():
                if self._stop_retransmission.wait(intervals[-1] / 1000.0):
                    break
                    
                debug_log("Periodic transmission")
                self.publish(increase_stnum=False)
                
        except Exception as e:
            print(f"Retransmission error: {e}")
            import traceback
            traceback.print_exc()
    
    def stop_retransmission(self):
        """Stop retransmission thread"""
        if self._retransmission_thread and self._retransmission_thread.is_alive():
            self._stop_retransmission.set()
            self._retransmission_thread.join(timeout=1.0)
    
    def start_cyclic_publish(self, interval: float = 1.0):
        """Start cyclic publishing at fixed interval"""
        self.stop_retransmission()
        
        self._stop_retransmission.clear()
        self._retransmission_thread = threading.Thread(
            target=self._cyclic_worker,
            args=(interval,),
            daemon=True
        )
        self._retransmission_thread.start()
    
    def _cyclic_worker(self, interval: float):
        """Worker thread for cyclic publishing"""
        try:
            while not self._stop_retransmission.is_set():
                self.publish(increase_stnum=False)
                if self._stop_retransmission.wait(interval):
                    break
        except Exception as e:
            print(f"Cyclic publish error: {e}")
    
    def stop_cyclic_publish(self):
        """Stop cyclic publishing"""
        self.stop_retransmission()
    
    def destroy(self):
        """Clean up publisher"""
        print(f"🐛 DEBUG destroy: Starting cleanup")
        
        # Stop any retransmission
        self.stop_retransmission()
        
        # DON'T manually free MmsValues or LinkedList after publish
        # libiec61850 manages them after GoosePublisher_publish
        
        # Clear our references
        self.dataset_values.clear()
        self.dataset = None
        
        # Destroy publisher
        if self.publisher:
            iec61850.GoosePublisher_destroy(self.publisher)
            self.publisher = None
        
        self.goose_enabled = False
        print("🗑️ GOOSE Publisher destroyed")
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'publisher') and self.publisher:
            self.destroy()

# ==================== GOOSE Subscriber ====================

class GOOSESubscriber:
    """GOOSE Subscriber using pyiec61850"""
    
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.receiver = None
        self.subscribers = []
        self.running = False
        self._callbacks = {}
    
    def create_receiver(self) -> bool:
        """Create GOOSE receiver"""
        try:
            self.receiver = iec61850.GooseReceiver_create()
            
            if not self.receiver:
                raise Exception("Failed to create GOOSE receiver")
            
            # Set interface
            iec61850.GooseReceiver_setInterfaceId(self.receiver, self.interface)
            
            print("✅ GOOSE Receiver created")
            return True
            
        except Exception as e:
            print(f"❌ Create receiver failed: {e}")
            return False
    
    def add_subscription(self, go_cb_ref: Optional[str] = None, 
                        app_id: Optional[int] = None,
                        callback: Optional[Callable] = None) -> object:
        """Add GOOSE subscription"""
        if not self.receiver:
            raise Exception("Receiver not created")
        
        # Create subscriber
        if go_cb_ref and app_id:
            subscriber = iec61850.GooseSubscriber_create(go_cb_ref, app_id)
        elif app_id:
            subscriber = iec61850.GooseSubscriber_setAppId(None, app_id)
        else:
            subscriber = iec61850.GooseSubscriber_create(None, 0)
        
        if not subscriber:
            raise Exception("Failed to create subscriber")
        
        # Set callback if provided
        if callback:
            self._set_callback(subscriber, callback)
        
        # Add to receiver
        iec61850.GooseReceiver_addSubscriber(self.receiver, subscriber)
        self.subscribers.append(subscriber)
        
        print(f"✅ Added GOOSE subscription")
        return subscriber
    
    def _set_callback(self, subscriber, callback: Callable):
        """Set callback for subscriber"""
        # For pyiec61850, we need to use GooseSubscriberForPython
        # This is a simplified implementation
        def py_callback(subscriber_obj):
            try:
                # Extract GOOSE data
                sv_data = {
                    'stNum': iec61850.GooseSubscriber_getStNum(subscriber_obj),
                    'sqNum': iec61850.GooseSubscriber_getSqNum(subscriber_obj),
                    'confRev': iec61850.GooseSubscriber_getConfRev(subscriber_obj),
                    'timestamp': iec61850.GooseSubscriber_getTimestamp(subscriber_obj),
                    'goID': iec61850.GooseSubscriber_getGoId(subscriber_obj),
                    'goCbRef': iec61850.GooseSubscriber_getGoCbRef(subscriber_obj),
                    'dataSet': iec61850.GooseSubscriber_getDataSet(subscriber_obj),
                    'values': []
                }
                
                # Get dataset values
                dataset_values = iec61850.GooseSubscriber_getDataSetValues(subscriber_obj)
                if dataset_values:
                    # Parse values (simplified)
                    sv_data['values'] = self._parse_dataset_values(dataset_values)
                
                # Call Python callback
                callback(sv_data)
                
            except Exception as e:
                print(f"❌ Callback error: {e}")
        
        # Create wrapper
        subscriber_wrapper = iec61850.GooseSubscriberForPython()
        subscriber_wrapper.setHandlerFunction(py_callback)
        
        # Set listener
        iec61850.GooseSubscriber_setListener(subscriber, subscriber_wrapper, None)
        
        # Store reference
        self._callbacks[id(subscriber)] = (callback, subscriber_wrapper)
    
    def _parse_dataset_values(self, mms_value) -> List[Any]:
        """Parse dataset values from MmsValue"""
        values = []
        
        if not mms_value:
            return values
        
        try:
            # Check if array
            value_type = iec61850.MmsValue_getType(mms_value)
            
            if value_type == iec61850.MMS_ARRAY:
                # Get array size
                array_size = iec61850.MmsValue_getArraySize(mms_value)
                
                # Extract each element
                for i in range(array_size):
                    element = iec61850.MmsValue_getElement(mms_value, i)
                    if element:
                        values.append(self._convert_mms_value(element))
            else:
                # Single value
                values.append(self._convert_mms_value(mms_value))
        
        except Exception as e:
            print(f"⚠️ Error parsing dataset values: {e}")
        
        return values

    def _convert_mms_value(self, mms_value) -> Any:
        """Convert single MmsValue to Python value"""
        if not mms_value:
            return None
        
        try:
            value_type = iec61850.MmsValue_getType(mms_value)
            
            if value_type == iec61850.MMS_BOOLEAN:
                return iec61850.MmsValue_getBoolean(mms_value)
            elif value_type == iec61850.MMS_INTEGER:
                return iec61850.MmsValue_toInt32(mms_value)
            elif value_type == iec61850.MMS_FLOAT:
                return iec61850.MmsValue_toFloat(mms_value)
            elif value_type == iec61850.MMS_VISIBLE_STRING:
                return iec61850.MmsValue_toString(mms_value)
            else:
                return iec61850.MmsValue_toString(mms_value)
        
        except Exception as e:
            print(f"⚠️ Error converting MmsValue: {e}")
            return None
    
    def start(self) -> bool:
        """Start GOOSE receiver"""
        if not self.receiver:
            raise Exception("Receiver not created")
        
        try:
            iec61850.GooseReceiver_start(self.receiver)
            self.running = True
            print(f"▶️ GOOSE Receiver started on {self.interface}")
            return True
            
        except Exception as e:
            print(f"❌ Start receiver failed: {e}")
            return False
    
    def stop(self):
        """Stop GOOSE receiver"""
        if self.receiver and self.running:
            iec61850.GooseReceiver_stop(self.receiver)
            self.running = False
            print("⏹️ GOOSE Receiver stopped")
    
    def is_running(self) -> bool:
        """Check if receiver is running"""
        if self.receiver:
            return iec61850.GooseReceiver_isRunning(self.receiver)
        return False
    
    def destroy(self):
        """Clean up subscriber"""
        if self.running:
            self.stop()
        
        # Destroy all subscribers
        for subscriber in self.subscribers:
            iec61850.GooseSubscriber_destroy(subscriber)
        self.subscribers.clear()
        
        # Destroy receiver
        if self.receiver:
            iec61850.GooseReceiver_destroy(self.receiver)
            self.receiver = None
        
        # Clear callbacks
        self._callbacks.clear()
        
        print("🗑️ GOOSE Subscriber destroyed")
    
    def __del__(self):
        """Cleanup on deletion"""
        self.destroy()

# ==================== Tree Management ====================

class IEC61850TreeManager:
    """IEC 61850 Tree Structure Manager"""
    
    @staticmethod
    def parse_scl_to_tree(scl_data: dict) -> IEDElement:
        """Parse SCL data to tree structure"""
        root = IEDElement("System", "ROOT")
        
        if 'SCL' not in scl_data:
            return root
        
        ieds = scl_data['SCL'].get('IED', [])
        if not isinstance(ieds, list):
            ieds = [ieds]
        
        for ied in ieds:
            ied_element = IEC61850TreeManager._parse_ied(ied)
            if ied_element:
                root.children.append(ied_element)
        
        return root
    
    @staticmethod
    def _parse_ied(ied_data: dict) -> Optional[IEDElement]:
        """Parse single IED"""
        ied_name = ied_data.get('@name', 'Unknown')
        ied_element = IEDElement(
            name=ied_name,
            element_type="IED",
            path=ied_name,
            metadata={
                'manufacturer': ied_data.get('@manufacturer', ''),
                'type': ied_data.get('@type', ''),
                'desc': ied_data.get('@desc', '')
            }
        )
        
        # Parse Access Points
        aps = ied_data.get('AccessPoint', [])
        if not isinstance(aps, list):
            aps = [aps]
        
        for ap in aps:
            server = ap.get('Server', {})
            
            # Parse Logical Devices
            lds = server.get('LDevice', [])
            if not isinstance(lds, list):
                lds = [lds]
            
            for ld in lds:
                ld_element = IEC61850TreeManager._parse_logical_device(ld, ied_name)
                if ld_element:
                    ied_element.children.append(ld_element)
        
        return ied_element
    
    @staticmethod
    def _parse_logical_device(ld_data: dict, ied_name: str) -> Optional[IEDElement]:
        """Parse Logical Device"""
        ld_name = ld_data.get('@inst', 'LD0')
        ld_path = f"{ied_name}/{ld_name}"
        
        ld_element = IEDElement(
            name=ld_name,
            element_type="LD",
            path=ld_path,
            metadata={'desc': ld_data.get('@desc', '')}
        )

        # Parse LN0
        ln0 = ld_data.get('LN0', {})
        if ln0:
            ln0_element = IEC61850TreeManager._parse_logical_node(ln0, ld_path, is_ln0=True)
            if ln0_element:
                ld_element.children.append(ln0_element)
        
        # Parse other LNs
        lns = ld_data.get('LN', [])
        if not isinstance(lns, list):
            lns = [lns]
        
        for ln in lns:
            ln_element = IEC61850TreeManager._parse_logical_node(ln, ld_path, is_ln0=False)
            if ln_element:
                ld_element.children.append(ln_element)
        
        return ld_element
    
    @staticmethod
    def _parse_logical_node(ln_data: dict, ld_path: str, is_ln0: bool = False) -> Optional[IEDElement]:
        """Parse Logical Node"""
        ln_class = ln_data.get('@lnClass', 'Unknown')
        ln_inst = ln_data.get('@inst', '')
        ln_name = f"{ln_class}{ln_inst}" if ln_inst else ln_class
        ln_path = f"{ld_path}/{ln_name}"
        
        ln_element = IEDElement(
            name=ln_name,
            element_type="LN",
            path=ln_path,
            metadata={
                'class': ln_class,
                'inst': ln_inst,
                'desc': ln_data.get('@desc', ''),
                'is_ln0': is_ln0
            }
        )
        
        # Parse DOIs
        dois = ln_data.get('DOI', [])
        if not isinstance(dois, list):
            dois = [dois]
        
        for doi in dois:
            do_element = IEC61850TreeManager._parse_data_object(doi, ln_path)
            if do_element:
                ln_element.children.append(do_element)
        
        return ln_element
    
    @staticmethod
    def _parse_data_object(doi_data: dict, ln_path: str) -> Optional[IEDElement]:
        """Parse Data Object"""
        do_name = doi_data.get('@name', 'Unknown')
        do_path = f"{ln_path}.{do_name}"
        
        do_element = IEDElement(
            name=do_name,
            element_type="DO",
            path=do_path,
            metadata={'desc': doi_data.get('@desc', '')}
        )
        
        # Parse DAIs
        dais = doi_data.get('DAI', [])
        if not isinstance(dais, list):
            dais = [dais]
        
        for dai in dais:
            da_element = IEC61850TreeManager._parse_data_attribute(dai, do_path)
            if da_element:
                do_element.children.append(da_element)
        
        return do_element
    
    @staticmethod
    def _parse_data_attribute(dai_data: dict, do_path: str) -> Optional[IEDElement]:
        """Parse Data Attribute"""
        da_name = dai_data.get('@name', 'Unknown')
        da_path = f"{do_path}.{da_name}"
        
        # Get value
        value = "unknown"
        val_elements = dai_data.get('Val', [])
        if val_elements:
            if not isinstance(val_elements, list):
                val_elements = [val_elements]
            if val_elements[0] and '#text' in val_elements[0]:
                value = val_elements[0]['#text']
        
        # Determine editability
        editable = da_name not in ['q', 't', 'origin', 'ctlNum', 'T', 'timeStamp']
        
        da_element = IEDElement(
            name=da_name,
            element_type="DA",
            path=da_path,
            value=value,
            editable=editable,
            metadata={
                'desc': dai_data.get('@desc', ''),
                'sAddr': dai_data.get('@sAddr', '')
            }
        )
        
        return da_element
    
    @staticmethod
    def find_element_by_path(root: IEDElement, path: str) -> Optional[IEDElement]:
        """Find element by path"""
        if root.path == path:
            return root
        
        for child in root.children:
            result = IEC61850TreeManager.find_element_by_path(child, path)
            if result:
                return result
        
        return None
    
    @staticmethod
    def get_iedscout_sections(root: IEDElement) -> Dict[str, List[IEDElement]]:
        """Get IEDScout-style sections from tree"""
        sections = {
            'GOOSE': [],
            'Reports': [],
            'Settings': [],
            'Datasets': [],
            'DataModel': []
        }
        
        # Traverse tree and categorize
        IEC61850TreeManager._categorize_elements(root, sections)
        
        return sections
    
    @staticmethod
    def _categorize_elements(element: IEDElement, sections: Dict[str, List[IEDElement]]):
        """Categorize elements into IEDScout sections"""
        # Check element type and metadata
        if element.element_type == "LN":
            ln_class = element.metadata.get('class', '')
            
            # GOOSE section
            if element.metadata.get('is_ln0', False):
                # Check for GOOSE control blocks in children
                for child in element.children:
                    if child.name.startswith('GO') or child.name == 'GoCB':
                        sections['GOOSE'].append(child)
            
            # Settings section
            if ln_class in ['LPHD', 'LLNO', 'GGIO']:
                for child in element.children:
                    if child.name in ['Mod', 'Beh', 'Health', 'NamPlt']:
                        sections['Settings'].append(child)
            
            # Reports section
            if any(child.name.startswith('RP') for child in element.children):
                sections['Reports'].extend([c for c in element.children if c.name.startswith('RP')])
        
        # Datasets
        elif element.element_type == "DO" and element.name.startswith('DS'):
            sections['Datasets'].append(element)
        
        # Data Model - all DAs
        elif element.element_type == "DA":
            sections['DataModel'].append(element)
        
        # Recurse for children
        for child in element.children:
            IEC61850TreeManager._categorize_elements(child, sections)

# ==================== Helper Functions ====================

def create_object_reference(ld: str, ln: str, do: str, da: str = None) -> str:
    """Create IEC 61850 object reference string"""
    ref = f"{ld}/{ln}.{do}"
    if da:
        ref += f".{da}"
    return ref

def parse_object_reference(ref: str) -> dict:
    """Parse IEC 61850 object reference"""
    parts = ref.split('/')
    if len(parts) != 2:
        raise ValueError("Invalid reference format")
    
    ld = parts[0]
    remaining = parts[1]
    
    ln_parts = remaining.split('.', 1)
    ln = ln_parts[0]
    
    if len(ln_parts) > 1:
        do_da = ln_parts[1].split('.')
        do = do_da[0]
        da = '.'.join(do_da[1:]) if len(do_da) > 1 else None
    else:
        do = None
        da = None
    
    return {
        'ld': ld,  # Logical Device
        'ln': ln,  # Logical Node
        'do': do,  # Data Object
        'da': da   # Data Attribute
    }

# ==================== Config Classes ====================

class GOOSEConfig:
    """GOOSE configuration helper"""
    
    def __init__(self):
        self.go_cb_ref = "TestDevice/LLN0$GO$gcb01"
        self.dataset_ref = "TestDevice/LLN0$dataset01"
        self.go_id = "TestGOOSE"
        self.app_id = 0x1000
        self.conf_rev = 1
        self.dst_mac = "01:0C:CD:01:00:00"  # Default GOOSE multicast
        self.interface = "eth0"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'go_cb_ref': self.go_cb_ref,
            'dataset_ref': self.dataset_ref,
            'go_id': self.go_id,
            'app_id': self.app_id,
            'conf_rev': self.conf_rev,
            'dst_mac': self.dst_mac,
            'interface': self.interface
        }

# ==================== IED Connection Manager ====================

class IEDConnectionManager:
    """Manage MMS connections to IEDs"""
    
    def __init__(self):
        self.connections = {}  # ied_name -> MMSClient
        self.ied_configs = {}  # ied_name -> config
        self.callbacks = {}    # For status change callbacks
        
    def add_ied_connection(self, config: dict):
        """Add IED configuration"""
        ied_name = config['ied_name']
        self.ied_configs[ied_name] = config
        
    def connect_ied(self, ied_name: str) -> bool:
        """Connect to specific IED"""
        if ied_name not in self.ied_configs:
            return False
            
        config = self.ied_configs[ied_name]
        client = MMSClient()
        
        try:
            if client.connect(config['ip_address'], config.get('mms_port', 102)):
                self.connections[ied_name] = client
                self._notify_status_change(ied_name, 'connected')
                return True
            else:
                self._notify_status_change(ied_name, 'failed')
                return False
        except Exception as e:
            print(f"Connection error for {ied_name}: {e}")
            self._notify_status_change(ied_name, 'error')
            return False
    
    def disconnect_ied(self, ied_name: str):
        """Disconnect from IED"""
        if ied_name in self.connections:
            self.connections[ied_name].disconnect()
            del self.connections[ied_name]
            self._notify_status_change(ied_name, 'disconnected')
    
    def get_connected_ieds(self) -> List[str]:
        """Get list of connected IEDs"""
        return list(self.connections.keys())
    
    def read_value(self, ied_name: str, object_ref: str) -> Any:
        """Read value from IED"""
        if ied_name in self.connections:
            try:
                value = self.connections[ied_name].read(object_ref)
                self._notify_data_received(ied_name, {object_ref: value})
                return value
            except Exception as e:
                print(f"Read error from {ied_name}: {e}")
                return None
        return None
    
    def write_value(self, ied_name: str, object_ref: str, value: Any) -> bool:
        """Write value to IED"""
        if ied_name in self.connections:
            try:
                return self.connections[ied_name].write(object_ref, value)
            except Exception as e:
                print(f"Write error to {ied_name}: {e}")
                return False
        return False
    
    def send_write_request(self, ied_name: str, mms_ref: str, value: Any) -> bool:
        """Compatibility method for existing code"""
        return self.write_value(ied_name, mms_ref, value)
    
    def get_ied_tree(self, ied_name: str) -> Optional[IEDElement]:
        """Get IED tree structure"""
        if ied_name in self.connections:
            return self.connections[ied_name].get_server_directory(with_model=True)
        return None
    
    def disconnect_all(self):
        """Disconnect all IEDs"""
        for ied_name in list(self.connections.keys()):
            self.disconnect_ied(ied_name)
    
    def set_status_callback(self, callback: Callable):
        """Set status change callback"""
        self.callbacks['status'] = callback
    
    def set_data_callback(self, callback: Callable):
        """Set data received callback"""
        self.callbacks['data'] = callback
    
    def _notify_status_change(self, ied_name: str, status: str):
        """Notify status change"""
        if 'status' in self.callbacks:
            self.callbacks['status'](ied_name, status)
    
    def _notify_data_received(self, ied_name: str, data: dict):
        """Notify data received"""
        if 'data' in self.callbacks:
            self.callbacks['data'](ied_name, data)

# ==================== GOOSE Manager ====================

class GOOSEManager:
    """Manage GOOSE publishing"""
    
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self.publisher = None
        self.is_running = False
        self.config = None  # ⭐ ไม่สร้าง default config
        self.all_goose_configs = {}  # ⭐ Initialize empty
        self._parent_system = None
        debug_log(f"GOOSEManager init with interface: {interface}")
        
    def start_publisher(self, scl_data: Optional[Dict] = None, auto_publish: bool = False, ied_name: Optional[str] = None) -> bool:
        """Start GOOSE publisher"""
        debug_log(f"Starting GOOSE publisher (auto_publish={auto_publish}, ied_name={ied_name})")

        try:
            self.publisher = GOOSEPublisher(self.interface)

            # Extract GOOSE config from SCL if available
            # ⭐ Only extract if scl_data is provided (not when restarting)
            if scl_data:
                debug_log("Extracting GOOSE config from SCL")
                self._extract_goose_config_from_scl(scl_data)
            else:
                debug_log("No SCL data provided - using existing GOOSE configs")
                debug_log(f"Available configs: {list(self.all_goose_configs.keys())}")
            
            # ⭐⭐⭐ CRITICAL FIX: Apply user modifications BEFORE selecting config ⭐⭐⭐
            if hasattr(self, '_parent_system') and self._parent_system:
                user_mods = getattr(self._parent_system, 'user_modified_configs', None)
                if user_mods and user_mods.get('goose_configs'):
                    debug_log("⭐ Found user modifications - applying to all_goose_configs")
                    
                    # Apply user modifications to all_goose_configs
                    for key, user_config in user_mods['goose_configs'].items():
                        if key in self.all_goose_configs:
                            debug_log(f"Updating config for {key}")
                            goose_config = self.all_goose_configs[key]
                            
                            # Update with user values
                            if 'app_id' in user_config:
                                old_app_id = goose_config.app_id
                                goose_config.app_id = user_config['app_id']
                                debug_log(f"  APP ID: 0x{old_app_id:04X} -> 0x{user_config['app_id']:04X}")
                            
                            if 'dst_mac' in user_config:
                                old_mac = goose_config.dst_mac
                                goose_config.dst_mac = user_config['dst_mac']
                                debug_log(f"  MAC: {old_mac} -> {user_config['dst_mac']}")
            
            # Select the correct GOOSE config
            if hasattr(self, 'all_goose_configs') and self.all_goose_configs:
                if ied_name:
                    debug_log(f"Selecting GOOSE config for IED: {ied_name}")
                    if not self._select_goose_config(ied_name):
                        # If no config found for specific IED, use first available
                        debug_log("No specific config found, using first available")
                        if self.all_goose_configs:
                            first_key = list(self.all_goose_configs.keys())[0]
                            self.config = self.all_goose_configs[first_key]
                            debug_log(f"Using config: {first_key}")
                else:
                    # No specific IED requested, use first available
                    first_key = list(self.all_goose_configs.keys())[0]
                    self.config = self.all_goose_configs[first_key]
                    debug_log(f"Using first config: {first_key}")
            else:
                debug_log("⚠️ No GOOSE configs available!")
                return False
            
            # Debug: Show selected config values
            if self.config:
                debug_log(f"📌 Selected config values:")
                debug_log(f"   APP ID: 0x{self.config.app_id:04X}")
                debug_log(f"   MAC: {self.config.dst_mac}")
                debug_log(f"   GoID: {self.config.go_id}")
                debug_log(f"   GoCbRef: {self.config.go_cb_ref}")
    
            # Create publisher with final values (including user modifications)
            debug_log("Creating publisher with final configuration")
            if not self.publisher.create(
                app_id=self.config.app_id,      # Use config value (with user mods)
                dst_mac=self.config.dst_mac,    # Use config value (with user mods)
                go_id=self.config.go_id,
                dataset_ref=self.config.dataset_ref,
                go_cb_ref=self.config.go_cb_ref,
                conf_rev=self.config.conf_rev
            ):
                print("Failed to create GOOSE publisher")
                return False

            # Then configure it with the selected config
            debug_log("Configuring publisher with GOCB values")
            debug_log(f"✅ Using APP ID: 0x{self.config.app_id:04X}, MAC: {self.config.dst_mac}")

            self.publisher.set_gocb_values(
                go_id=self.config.go_id,
                dataset_ref=self.config.dataset_ref,
                go_cb_ref=self.config.go_cb_ref,
                conf_rev=self.config.conf_rev
            )

            self.is_running = True
            debug_log("Publisher is_running = True")

            # Only start retransmission if auto_publish is True
            if auto_publish:
                debug_log("Setting initial empty dataset")
                self.publisher.set_dataset([])
                debug_log("Starting initial retransmission")
                self.publisher.publish_with_retransmission()
            else:
                debug_log("GOOSE publisher ready - waiting for value changes")
                print("📝 GOOSE publisher initialized - waiting for first value change")

            return True
 
        except Exception as e:
            print(f"Error starting GOOSE publisher: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _apply_user_goose_modifications(self, user_goose_configs: dict):
        """Apply user modifications to current config"""
        if not self.config:
            debug_log("No current config to apply modifications")
            return
    
        debug_log(f"⭐ Applying user GOOSE modifications")
        debug_log(f"Current config BEFORE apply:")
        debug_log(f"  go_cb_ref: {self.config.go_cb_ref}")
        debug_log(f"  APP ID: 0x{self.config.app_id:04X}")
        debug_log(f"  MAC: {self.config.dst_mac}")
        debug_log(f"Available user configs: {list(user_goose_configs.keys())}")
    
        # Find matching user config
        current_cb_ref = self.config.go_cb_ref
        config_found = False
    
        for key, user_config in user_goose_configs.items():
            debug_log(f"Checking key: '{key}' against cb_ref: '{current_cb_ref}'")
        
            # ⭐ Try multiple matching strategies
            match = False
        
            # Strategy 1: Exact match
            if current_cb_ref == key:
                match = True
                debug_log("  ✅ Exact match")
        
            # Strategy 2: Key is part of cb_ref
            elif key in current_cb_ref:
                match = True
                debug_log("  ✅ Key is substring of cb_ref")
        
            # Strategy 3: Extract GOOSE name and compare
            # cb_ref format: IED/LD/LLN0$GOOSE_NAME
            # key format might be: IED/LD/GOOSE_NAME or IED/CFG/GOOSE_NAME
            if not match and '$' in current_cb_ref:
                # Extract parts
                cb_parts = current_cb_ref.split('$')
                cb_prefix = cb_parts[0]  # IED/LD/LLN0
                cb_goose = cb_parts[1]    # GOOSE_NAME
            
                # Extract IED name from prefix
                cb_ied = cb_prefix.split('/')[0]
            
                # Check if key contains same IED and GOOSE name
                if cb_ied in key and cb_goose in key:
                    match = True
                    debug_log(f"  ✅ Matched by IED ({cb_ied}) and GOOSE name ({cb_goose})")
        
            if match:
                config_found = True
                debug_log(f"✅ Found matching user modification for {key}")
            
                # Apply user values
                if 'app_id' in user_config:
                    old_app_id = self.config.app_id
                    self.config.app_id = user_config['app_id']
                    debug_log(f"  APP ID: 0x{old_app_id:04X} -> 0x{user_config['app_id']:04X}")
                
                if 'dst_mac' in user_config:
                    old_mac = self.config.dst_mac
                    self.config.dst_mac = user_config['dst_mac']
                    debug_log(f"  MAC: {old_mac} -> {user_config['dst_mac']}")
                
                # Update other fields if present
                if 'go_id' in user_config:
                    self.config.go_id = user_config['go_id']
                    debug_log(f"  GoID: -> {user_config['go_id']}")
                
                if 'dataset_ref' in user_config:
                    self.config.dataset_ref = user_config['dataset_ref']
                    debug_log(f"  Dataset: -> {user_config['dataset_ref']}")
                   
                break
    
        if not config_found:
            debug_log(f"⚠️ No matching user config found for {current_cb_ref}")
            debug_log("  This might be because the IED was not modified in Address Editor")
    
        debug_log(f"✅ Config AFTER apply:")
        debug_log(f"  APP ID: 0x{self.config.app_id:04X}")
        debug_log(f"  MAC: {self.config.dst_mac}")
        debug_log(f"  GoID: {self.config.go_id}")
        debug_log(f"  GoCbRef: {self.config.go_cb_ref}")
        
    def _parse_appid_string(self, appid_str: str) -> int:
        """Parse APPID string to integer"""
        try:
            if appid_str.startswith('0x') or appid_str.startswith('0X'):
                return int(appid_str, 16)
            elif all(c in '0123456789ABCDEFabcdef' for c in appid_str):
                return int(appid_str, 16)
            else:
                return int(appid_str)
        except:
            return 0x0001  # Default
    
    def _extract_goose_config_from_scl(self, scl_data: Dict):
        """Extract all GOOSE configurations from SCL data"""
        try:
            self.all_goose_configs = {}
            
            if 'SCL' not in scl_data:
                return
            
            # Step 1: Extract all GSEControl definitions from IED section
            goose_controls = {}  # key: (ied_name, ld_inst, gse_name)
            
            ieds = scl_data['SCL'].get('IED', [])
            if not isinstance(ieds, list):
                ieds = [ieds]
            
            for ied in ieds:
                ied_name = ied.get('@name', 'Unknown')
                
                # Look for GOOSE control blocks
                aps = ied.get('AccessPoint', [])
                if not isinstance(aps, list):
                    aps = [aps]
                
                for ap in aps:
                    ap_name = ap.get('@name', 'S1')
                    server = ap.get('Server', {})
                    lds = server.get('LDevice', [])
                    if not isinstance(lds, list):
                        lds = [lds]
                    
                    for ld in lds:
                        ld_inst = ld.get('@inst', 'LD0')
                        ln0 = ld.get('LN0', {})
                        if ln0:
                            gses = ln0.get('GSEControl', [])
                            if not isinstance(gses, list):
                                gses = [gses]
                            
                            for gse in gses:
                                gse_name = gse.get('@name')
                                if gse_name:
                                    key = (ied_name, ld_inst, gse_name)
                                    
                                    # Create config for this GOOSE
                                    config = GOOSEConfig()
                                    config.go_cb_ref = f"{ied_name}/{ld_inst}/LLN0${gse_name}"
                                    config.dataset_ref = f"{ied_name}/{ld_inst}/LLN0${gse.get('@datSet', 'Dataset1')}"
                                    config.conf_rev = int(gse.get('@confRev', 1))
                                    config.interface = self.interface
                                    
                                    # Extract goID
                                    config.go_id = gse.get('@appID', gse_name)  # Use appID as goID if present
                                    
                                    goose_controls[key] = {
                                        'config': config,
                                        'ap_name': ap_name,
                                        'gse_data': gse
                                    }
            
            # Step 2: Extract Communication section data and match with GSEControl
            comm = scl_data.get('SCL', {}).get('Communication', {})
            if comm:
                subnets = comm.get('SubNetwork', [])
                if not isinstance(subnets, list):
                    subnets = [subnets]
                
                for subnet in subnets:
                    conn_aps = subnet.get('ConnectedAP', [])
                    if not isinstance(conn_aps, list):
                        conn_aps = [conn_aps]
                    
                    for conn_ap in conn_aps:
                        conn_ied = conn_ap.get('@iedName')
                        conn_ap_name = conn_ap.get('@apName', 'S1')
                        
                        # Look for GSE
                        gses = conn_ap.get('GSE', [])
                        if not isinstance(gses, list):
                            gses = [gses]
                        
                        for gse in gses:
                            gse_ld_inst = gse.get('@ldInst')
                            gse_cb_name = gse.get('@cbName')
                            
                            # Find matching GSEControl
                            key = (conn_ied, gse_ld_inst, gse_cb_name)
                            if key in goose_controls:
                                config = goose_controls[key]['config']
                                
                                # Extract Address information
                                address = gse.get('Address', {})
                                ps = address.get('P', [])
                                if not isinstance(ps, list):
                                    ps = [ps]
                                
                                for p in ps:
                                    p_type = p.get('@type')
                                    p_value = p.get('#text', '')
                                    
                                    if p_type == 'APPID':
                                        # Parse appID
                                        try:
                                            if p_value.startswith('0x'):
                                                config.app_id = int(p_value, 16)
                                            elif all(c in '0123456789ABCDEFabcdef' for c in p_value):
                                                config.app_id = int(p_value, 16)
                                            else:
                                                config.app_id = int(p_value)
                                        except:
                                            config.app_id = 0x0001
                                            print(f"⚠️ Cannot parse APPID '{p_value}' for {gse_cb_name}")
                                    
                                    elif p_type == 'MAC-Address':
                                        # Convert MAC format from 01-0C-CD-01-00-00 to 01:0C:CD:01:00:00
                                        config.dst_mac = p_value.replace('-', ':')
                                
                                # Store complete config
                                full_key = f"{conn_ied}/{gse_ld_inst}/{gse_cb_name}"
                                self.all_goose_configs[full_key] = config
                                
                                print(f"📍 Found GOOSE config: {full_key}")
                                print(f"   - appID: 0x{config.app_id:04X}")
                                print(f"   - MAC: {config.dst_mac}")
                                print(f"   - confRev: {config.conf_rev}")
            
            # Step 3: For any GSEControl without Communication entry, store with defaults
            for key, control_data in goose_controls.items():
                ied_name, ld_inst, gse_name = key
                full_key = f"{ied_name}/{ld_inst}/{gse_name}"
                
                if full_key not in self.all_goose_configs:
                    config = control_data['config']
                    # Use appID from GSEControl if it's hex, otherwise generate
                    gse_data = control_data['gse_data']
                    app_id_str = gse_data.get('@appID', '')
                    
                    if app_id_str:
                        config.app_id = self._parse_appid_string(app_id_str)
                    else:
                        config.app_id = 0x0001  # Default
                    
                    self.all_goose_configs[full_key] = config
                    print(f"📍 Found GOOSE config (no comm): {full_key}")
                    print(f"   - appID: 0x{config.app_id:04X} (from GSEControl)")
            
            print(f"\n✅ Total GOOSE configs found: {len(self.all_goose_configs)}")
            
        except Exception as e:
            print(f"Error extracting GOOSE configs: {e}")
            import traceback
            traceback.print_exc()
    
    def _select_goose_config(self, ied_name: Optional[str] = None, goose_name: Optional[str] = None) -> bool:
        """Select specific GOOSE config or first available"""
        if not self.all_goose_configs:
            print("❌ No GOOSE configs available")
            return False
        
        # If specific IED/GOOSE requested
        if ied_name:
            # Find matching configs
            matches = []
            for key, config in self.all_goose_configs.items():
                if ied_name in key:
                    if not goose_name or goose_name in key:
                        matches.append((key, config))
            
            if matches:
                if len(matches) > 1:
                    print(f"⚠️ Found {len(matches)} matching GOOSE configs for IED '{ied_name}':")
                    for key, _ in matches:
                        print(f"   - {key}")
                    print(f"   Using first: {matches[0][0]}")
                
                self.config = matches[0][1]
                print(f"✅ Selected GOOSE config: {matches[0][0]}")
                return True
            else:
                print(f"❌ No GOOSE config found for IED '{ied_name}'")
                return False
        
        # No specific IED - use first available
        first_key = list(self.all_goose_configs.keys())[0]
        self.config = self.all_goose_configs[first_key]
        print(f"✅ Using first available GOOSE config: {first_key}")
        return True
    
    def get_available_goose_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all available GOOSE configurations"""
        result = {}
        for key, config in self.all_goose_configs.items():
            result[key] = config.to_dict()
        return result
    
    def publish_message(self, message) -> bool:
        """Publish GOOSE message with retransmission"""
        debug_log(f"GOOSEManager.publish_message called")
        debug_log(f"Publisher exists: {self.publisher is not None}")
        debug_log(f"Is running: {self.is_running}")
        
        if not self.publisher or not self.is_running:
            debug_log("Publisher not running")
            return False
        
        try:
            # Stop any ongoing retransmission first
            debug_log("Stopping any ongoing retransmission")
            self.publisher.stop_retransmission()
            
            # Debug: แสดงข้อมูลก่อนส่ง
            print(f"🐛 DEBUG: Publishing GOOSE with {len(message.data_items)} items")
            for item in message.data_items:
                print(f"   - {item['da_path']} = {item['value']} ({item['type']})")
        
            # Convert message data to dataset values
            values = []
        
            # Extract data items from message
            if hasattr(message, 'data_items'):
                for item in message.data_items:
                    da_path = item.get('da_path', '')
                    value = item.get('value', '')
                    goose_type = item.get('type', 'visible-string')
                    
                    debug_log(f"Processing item: path={da_path}, value={value}, type={goose_type}")
                
                    values.append({
                        'path': da_path,
                        'value': value,
                        'type': goose_type
                    })
            
            print(f"🐛 DEBUG: Converted to {len(values)} dataset values")
        
            # Update dataset
            debug_log("Updating dataset")
            self.publisher.set_dataset(values)
            
            # ตรวจสอบว่า dataset ถูก set จริงหรือไม่
            print(f"🐛 DEBUG: Dataset values count: {len(self.publisher.dataset_values)}")
            
            # Test immediate publish
            print("🐛 DEBUG: Testing immediate publish...")
            if self.publisher.publish(increase_stnum=True):
                print("✅ Immediate publish SUCCESS")
            else:
                print("❌ Immediate publish FAILED")
        
            # Publish with retransmission pattern (state change)
            debug_log("Starting publish with retransmission")
            self.publisher.publish_with_retransmission()
        
            return True
        
        except Exception as e:
            print(f"❌ Error publishing GOOSE: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def stop_publisher(self):
        """Stop GOOSE publisher"""
        if self.publisher:
            self.publisher.destroy()
            self.publisher = None
            self.is_running = False
    
    def start_subscriber(self, callback=None) -> bool:
        """Start GOOSE subscriber"""
        # Not implemented yet
        return True
    
    def stop_subscriber(self):
        """Stop GOOSE subscriber"""
        pass

# ==================== IEC 61850 System ====================

class IEC61850System:
    """Complete IEC 61850 System"""
    
    def __init__(self, interface: str = "eth0"):
        debug_log(f"IEC61850System init with interface: {interface}")
        self.interface = interface
        self.connection_manager = IEDConnectionManager()
        self.goose_manager = GOOSEManager(interface)
        self.tree_manager = IEC61850TreeManager()
        self.is_initialized = True
        
    def start_connection_manager(self) -> bool:
        """Start connection manager"""
        return True  # Always ready
    
    def start_goose_system(self, scl_data: Optional[Dict] = None, auto_publish: bool = False, ied_name: Optional[str] = None) -> bool:
        """Start GOOSE system"""
        debug_log(f"IEC61850System.start_goose_system called (auto_publish={auto_publish}, ied_name={ied_name})")
        return self.goose_manager.start_publisher(scl_data, auto_publish, ied_name)
    
    def stop_all(self):
        """Stop all systems"""
        try:
            # Stop connection manager
            if hasattr(self, 'connection_manager') and self.connection_manager:
                self.connection_manager.disconnect_all()
        
            # Stop GOOSE manager  
            if hasattr(self, 'goose_manager') and self.goose_manager:
                self.goose_manager.stop_publisher()
                self.goose_manager.stop_subscriber()
        except Exception as e:
            print(f"Error in stop_all: {e}")
    
    def parse_scl_to_tree(self, scl_data: dict) -> IEDElement:
        """Parse SCL data to tree structure"""
        return self.tree_manager.parse_scl_to_tree(scl_data)
    
    def get_iedscout_sections(self, tree_root: IEDElement) -> Dict[str, List[IEDElement]]:
        """Get IEDScout-style sections"""
        return self.tree_manager.get_iedscout_sections(tree_root)

# ==================== Test Functions ====================

if __name__ == "__main__":
    print("PyIEC61850 Enhanced Wrapper Test")
    print("================================")
    
    # Test Tree Management
    print("\n1. Testing Tree Management:")
    scl_data = {
        'SCL': {
            'IED': [{
                '@name': 'TestIED',
                '@manufacturer': 'TestManuf',
                'AccessPoint': {
                    'Server': {
                        'LDevice': {
                            '@inst': 'LD0',
                            'LN0': {
                                '@lnClass': 'LLN0',
                                'DOI': [{
                                    '@name': 'Mod',
                                    'DAI': [{
                                        '@name': 'stVal',
                                        'Val': [{'#text': '1'}]
                                    }]
                                }]
                            }
                        }
                    }
                }
            }]
        }
    }
    
    tree_mgr = IEC61850TreeManager()
    root = tree_mgr.parse_scl_to_tree(scl_data)
    print(f"   Tree root: {root.name} ({root.element_type})")
    print(f"   Children: {len(root.children)}")
    
    # Test MMS Client
    print("\n2. Testing MMS Client:")
    client = MMSClient()
    if client.connect("localhost"):
        try:
            devices = client.get_logical_devices()
            print(f"   Found {len(devices)} logical devices: {devices}")
        except Exception as e:
            print(f"   Error: {e}")
        finally:
            client.disconnect()
    
    # Test GOOSE Publisher
    print("\n3. Testing GOOSE Publisher:")
    publisher = GOOSEPublisher("eth0")
    if publisher.create():
        publisher.set_dataset([
            {'value': True, 'type': 'boolean'},
            {'value': 42, 'type': 'integer'},
            {'value': "Test", 'type': 'visible-string'}
        ])
        
        if publisher.publish(increase_stnum=True):
            print("   ✅ GOOSE published successfully")
        else:
            print("   ❌ GOOSE publish failed")
        
        publisher.destroy()
    
    print("\n✅ Enhanced wrapper test completed")

