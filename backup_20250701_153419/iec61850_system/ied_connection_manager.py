# ied_connection_manager.py
import threading
import time
from typing import Dict, Optional, List, Any, Callable, Tuple
from enum import Enum

import pyiec61850 as iec61850 


class ConnectionState(Enum):
    """IED connection states"""
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    ERROR = "Error"


class IEDConnection:
    """Wrapper for IED connection"""
    
    def __init__(self, ied_name: str, ip_address: str, port: int = 102):
        self.ied_name = ied_name
        self.ip_address = ip_address
        self.port = port
        self.connection = None
        self.state = ConnectionState.DISCONNECTED
        self.error_message = ""
        self.model = None
        self.connected_time = None
        
        # Statistics
        self.request_count = 0
        self.error_count = 0
        self.last_activity = None
        

class IEDConnectionManager:
    """Manager for IED connections"""
    
    def __init__(self):
        self.connections: Dict[str, IEDConnection] = {}
        self.lock = threading.Lock()
        
        # Callbacks
        self.connection_callbacks: List[Callable] = []
        
    def connect_to_ied(self, ied_name: str, ip_address: str, 
                      port: int = 102, timeout: int = 10000) -> Optional[IEDConnection]:
        """Connect to an IED"""
        
        with self.lock:
            # Check if already connected
            if ied_name in self.connections:
                conn = self.connections[ied_name]
                if conn.state == ConnectionState.CONNECTED:
                    print(f"ℹ️ Already connected to {ied_name}")
                    return conn
                    
        # Create connection wrapper
        ied_conn = IEDConnection(ied_name, ip_address, port)
        ied_conn.state = ConnectionState.CONNECTING
        
        try:
            print(f"🔌 Connecting to {ied_name} at {ip_address}:{port}...")
            
            # Create IED connection
            connection = iec61850.IedConnection_create()
            
            if not connection:
                raise Exception("Failed to create IED connection object")
                
            # Set connection parameters
            iec61850.IedConnection_setConnectTimeout(connection, timeout)
            
            # Connect
            error = iec61850.IedConnection_connect(connection, ip_address, port)
            
            if error != iec61850.IED_ERROR_OK:
                error_msg = iec61850.IedClientError_toString(error)
                raise Exception(f"Connection failed: {error_msg}")
                
            # Connection successful
            ied_conn.connection = connection
            ied_conn.state = ConnectionState.CONNECTED
            ied_conn.connected_time = time.time()
            
            # Get device model
            print(f"📊 Retrieving device model from {ied_name}...")
            ied_conn.model = iec61850.IedConnection_getDeviceModelFromServer(connection)
            
            if not ied_conn.model:
                print(f"⚠️ Warning: Could not retrieve device model from {ied_name}")
                
            # Store connection
            with self.lock:
                self.connections[ied_name] = ied_conn
                
            # Notify callbacks
            self._notify_connection_change(ied_name, ConnectionState.CONNECTED)
            
            print(f"✅ Connected to {ied_name}")
            return ied_conn
            
        except Exception as e:
            print(f"❌ Error connecting to {ied_name}: {e}")
            ied_conn.state = ConnectionState.ERROR
            ied_conn.error_message = str(e)
            
            # Clean up
            if ied_conn.connection:
                try:
                    iec61850.IedConnection_destroy(ied_conn.connection)
                except:
                    pass
                    
            return None
            
    def disconnect_from_ied(self, ied_name: str):
        """Disconnect from an IED"""
        
        with self.lock:
            if ied_name not in self.connections:
                print(f"⚠️ {ied_name} not connected")
                return
                
            ied_conn = self.connections[ied_name]
            
        try:
            if ied_conn.connection:
                print(f"🔌 Disconnecting from {ied_name}...")
                
                # Close connection
                iec61850.IedConnection_close(ied_conn.connection)
                
                # Destroy connection object
                iec61850.IedConnection_destroy(ied_conn.connection)
                
            ied_conn.connection = None
            ied_conn.state = ConnectionState.DISCONNECTED
            
            # Remove from connections
            with self.lock:
                del self.connections[ied_name]
                
            # Notify callbacks
            self._notify_connection_change(ied_name, ConnectionState.DISCONNECTED)
            
            print(f"✅ Disconnected from {ied_name}")
            
        except Exception as e:
            print(f"❌ Error disconnecting from {ied_name}: {e}")
            
    def get_connection(self, ied_name: str) -> Optional[IEDConnection]:
        """Get IED connection"""
        with self.lock:
            return self.connections.get(ied_name)
            
    def is_connected(self, ied_name: str) -> bool:
        """Check if IED is connected"""
        conn = self.get_connection(ied_name)
        return conn is not None and conn.state == ConnectionState.CONNECTED
        
    def get_all_connections(self) -> Dict[str, IEDConnection]:
        """Get all connections"""
        with self.lock:
            return dict(self.connections)
            
    def read_value(self, ied_name: str, object_reference: str) -> Tuple[Optional[Any], Optional[str]]:
        """Read value from IED
        
        Returns:
            (value, error_message)
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return None, f"{ied_name} not connected"
            
        try:
            # Read value
            mms_value = iec61850.IedConnection_readObject(
                conn.connection, 
                object_reference,
                iec61850.IEC61850_FC_ST  # Functional constraint
            )
            
            if not mms_value:
                return None, "Failed to read value"
                
            # Convert to Python value
            python_value = self._mms_to_python(mms_value)
            
            # Delete MMS value
            iec61850.MmsValue_delete(mms_value)
            
            # Update statistics
            conn.request_count += 1
            conn.last_activity = time.time()
            
            return python_value, None
            
        except Exception as e:
            conn.error_count += 1
            return None, str(e)
            
    def write_value(self, ied_name: str, object_reference: str, 
                   value: Any, fc: int = iec61850.IEC61850_FC_ST) -> Optional[str]:
        """Write value to IED
        
        Returns:
            error_message if failed, None if successful
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return f"{ied_name} not connected"
            
        try:
            # Convert Python value to MMS
            mms_value = self._python_to_mms(value)
            if not mms_value:
                return "Failed to convert value"
                
            # Write value
            error = iec61850.IedConnection_writeObject(
                conn.connection,
                object_reference,
                fc,
                mms_value
            )
            
            # Clean up
            iec61850.MmsValue_delete(mms_value)
            
            if error != iec61850.IED_ERROR_OK:
                error_msg = iec61850.IedClientError_toString(error)
                conn.error_count += 1
                return error_msg
                
            # Update statistics
            conn.request_count += 1
            conn.last_activity = time.time()
            
            return None
            
        except Exception as e:
            conn.error_count += 1
            return str(e)
            
    def get_logical_device_list(self, ied_name: str) -> Tuple[Optional[List[str]], Optional[str]]:
        """Get list of logical devices
        
        Returns:
            (device_list, error_message)
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return None, f"{ied_name} not connected"
            
        try:
            # Get device list
            device_list = iec61850.IedConnection_getLogicalDeviceList(conn.connection)
            
            if not device_list:
                return [], None
                
            # Convert to Python list
            devices = []
            element = device_list
            while element:
                device_name = iec61850.LinkedList_getData(element)
                if device_name:
                    devices.append(device_name)
                element = iec61850.LinkedList_getNext(element)
                
            # Clean up
            iec61850.LinkedList_destroy(device_list)
            
            return devices, None
            
        except Exception as e:
            return None, str(e)
            
    def get_logical_node_list(self, ied_name: str, 
                            logical_device: str) -> Tuple[Optional[List[str]], Optional[str]]:
        """Get list of logical nodes in a logical device
        
        Returns:
            (node_list, error_message)
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return None, f"{ied_name} not connected"
            
        try:
            # Get logical node directory
            node_list = iec61850.IedConnection_getLogicalNodeDirectory(
                conn.connection,
                logical_device,
                iec61850.ACSI_CLASS_LOGICAL_NODE
            )
            
            if not node_list:
                return [], None
                
            # Convert to Python list
            nodes = []
            element = node_list
            while element:
                node_name = iec61850.LinkedList_getData(element)
                if node_name:
                    nodes.append(node_name)
                element = iec61850.LinkedList_getNext(element)
                
            # Clean up
            iec61850.LinkedList_destroy(node_list)
            
            return nodes, None
            
        except Exception as e:
            return None, str(e)
            
    def get_data_directory(self, ied_name: str, 
                          logical_node_path: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get data directory of a logical node
        
        Returns:
            (data_list, error_message)
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return None, f"{ied_name} not connected"
            
        try:
            # Get data directory
            data_attrs = iec61850.IedConnection_getDataDirectory(
                conn.connection,
                logical_node_path
            )
            
            if not data_attrs:
                return [], None
                
            # Parse data attributes
            data_list = []
            element = data_attrs
            while element:
                attr_name = iec61850.LinkedList_getData(element)
                if attr_name:
                    # Get attribute info
                    data_info = {
                        'name': attr_name,
                        'path': f"{logical_node_path}.{attr_name}"
                    }
                    data_list.append(data_info)
                    
                element = iec61850.LinkedList_getNext(element)
                
            # Clean up
            iec61850.LinkedList_destroy(data_attrs)
            
            return data_list, None
            
        except Exception as e:
            return None, str(e)
            
    def control_operation(self, ied_name: str, control_object: str,
                         control_value: Any, select_before_operate: bool = True,
                         test_mode: bool = False) -> Optional[str]:
        """Perform control operation
        
        Returns:
            error_message if failed, None if successful
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return f"{ied_name} not connected"
            
        try:
            # Create control object client
            control_client = iec61850.ControlObjectClient_create(
                control_object,
                conn.connection
            )
            
            if not control_client:
                return "Failed to create control client"
                
            # Set test mode
            iec61850.ControlObjectClient_setTestMode(control_client, test_mode)
            
            # Set control number
            iec61850.ControlObjectClient_setCtlNum(control_client, 1)
            
            # Set origin
            origin = iec61850.ControlObjectClient_setOrigin(
                control_client, 
                None,  # orIdent
                3      # orCat: remote-control
            )
            
            # Convert control value
            mms_value = self._python_to_mms(control_value)
            if not mms_value:
                iec61850.ControlObjectClient_destroy(control_client)
                return "Failed to convert control value"
                
            error = None
            
            if select_before_operate:
                # Select before operate
                print(f"🎮 Selecting control object: {control_object}")
                if not iec61850.ControlObjectClient_selectWithValue(control_client, mms_value):
                    error = iec61850.ControlObjectClient_getLastError(control_client)
                    error_msg = f"Select failed: {iec61850.IedClientError_toString(error)}"
                else:
                    # Operate
                    print(f"🎮 Operating control: {control_object}")
                    if not iec61850.ControlObjectClient_operate(control_client, mms_value, 0):
                        error = iec61850.ControlObjectClient_getLastError(control_client)
                        error_msg = f"Operate failed: {iec61850.IedClientError_toString(error)}"
                    else:
                        error_msg = None
            else:
                # Direct control
                print(f"🎮 Direct control: {control_object}")
                if not iec61850.ControlObjectClient_operate(control_client, mms_value, 0):
                    error = iec61850.ControlObjectClient_getLastError(control_client)
                    error_msg = f"Control failed: {iec61850.IedClientError_toString(error)}"
                else:
                    error_msg = None
                    
            # Clean up
            iec61850.MmsValue_delete(mms_value)
            iec61850.ControlObjectClient_destroy(control_client)
            
            # Update statistics
            conn.request_count += 1
            conn.last_activity = time.time()
            if error_msg:
                conn.error_count += 1
                
            return error_msg
            
        except Exception as e:
            conn.error_count += 1
            return str(e)
            
    def get_rcb_values(self, ied_name: str, rcb_reference: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get Report Control Block values
        
        Returns:
            (rcb_values, error_message)
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return None, f"{ied_name} not connected"
            
        try:
            # Create RCB object
            rcb = iec61850.pyWrap_IedConnection_getRCBValues(
                conn.connection,
                rcb_reference,
                None  # Client report
            )
            
            if not rcb:
                return None, "Failed to read RCB"
                
            # Extract RCB values
            rcb_values = {
                'rptID': iec61850.ClientReportControlBlock_getRptId(rcb),
                'rptEna': iec61850.ClientReportControlBlock_getRptEna(rcb),
                'bufTm': iec61850.ClientReportControlBlock_getBufTm(rcb),
                'datSet': iec61850.ClientReportControlBlock_getDataSetReference(rcb),
                'confRev': iec61850.ClientReportControlBlock_getConfRev(rcb),
                'trgOps': iec61850.ClientReportControlBlock_getTrgOps(rcb),
                'intgPd': iec61850.ClientReportControlBlock_getIntgPd(rcb),
                'gi': iec61850.ClientReportControlBlock_getGI(rcb),
                'sqNum': iec61850.ClientReportControlBlock_getSqNum(rcb),
                'owner': iec61850.ClientReportControlBlock_getOwner(rcb)
            }
            
            # Get optional fields
            opt_fields = iec61850.ClientReportControlBlock_getOptFlds(rcb)
            rcb_values['optFlds'] = {
                'seqNum': bool(opt_fields & iec61850.RPT_OPT_SEQ_NUM),
                'timeStamp': bool(opt_fields & iec61850.RPT_OPT_TIME_STAMP),
                'dataSet': bool(opt_fields & iec61850.RPT_OPT_DATA_SET),
                'reasonCode': bool(opt_fields & iec61850.RPT_OPT_REASON_FOR_INCLUSION),
                'dataRef': bool(opt_fields & iec61850.RPT_OPT_DATA_REFERENCE),
                'bufOvfl': bool(opt_fields & iec61850.RPT_OPT_BUFFER_OVERFLOW),
                'entryId': bool(opt_fields & iec61850.RPT_OPT_ENTRY_ID),
                'confRev': bool(opt_fields & iec61850.RPT_OPT_CONF_REV)
            }
            
            # Clean up
            iec61850.ClientReportControlBlock_destroy(rcb)
            
            return rcb_values, None
            
        except Exception as e:
            return None, str(e)
            
    def set_rcb_values(self, ied_name: str, rcb_reference: str,
                      rcb_values: Dict) -> Optional[str]:
        """Set Report Control Block values
        
        Returns:
            error_message if failed, None if successful
        """
        conn = self.get_connection(ied_name)
        if not conn or conn.state != ConnectionState.CONNECTED:
            return f"{ied_name} not connected"
            
        try:
            # Get current RCB
            rcb = iec61850.pyWrap_IedConnection_getRCBValues(
                conn.connection,
                rcb_reference,
                None
            )
            
            if not rcb:
                return "Failed to read RCB"
                
            # Update values
            parameter_mask = 0
            
            if 'rptID' in rcb_values:
                iec61850.ClientReportControlBlock_setRptId(rcb, rcb_values['rptID'])
                parameter_mask |= iec61850.RCB_ELEMENT_RPT_ID
                
            if 'rptEna' in rcb_values:
                iec61850.ClientReportControlBlock_setRptEna(rcb, rcb_values['rptEna'])
                parameter_mask |= iec61850.RCB_ELEMENT_RPT_ENA
                
            if 'datSet' in rcb_values:
                iec61850.ClientReportControlBlock_setDataSetReference(rcb, rcb_values['datSet'])
                parameter_mask |= iec61850.RCB_ELEMENT_DATSET
                
            if 'trgOps' in rcb_values:
                iec61850.ClientReportControlBlock_setTrgOps(rcb, rcb_values['trgOps'])
                parameter_mask |= iec61850.RCB_ELEMENT_TRG_OPS
                
            if 'intgPd' in rcb_values:
                iec61850.ClientReportControlBlock_setIntgPd(rcb, rcb_values['intgPd'])
                parameter_mask |= iec61850.RCB_ELEMENT_INTG_PD
                
            if 'gi' in rcb_values:
                iec61850.ClientReportControlBlock_setGI(rcb, rcb_values['gi'])
                parameter_mask |= iec61850.RCB_ELEMENT_GI
                
            # Write RCB values
            error = iec61850.pyWrap_IedConnection_setRCBValues(
                conn.connection,
                rcb,
                parameter_mask,
                True  # singleRequest
            )
            
            # Clean up
            iec61850.ClientReportControlBlock_destroy(rcb)
            
            if error != iec61850.IED_ERROR_OK:
                return iec61850.IedClientError_toString(error)
                
            return None
            
        except Exception as e:
            return str(e)
            
    def _python_to_mms(self, value: Any):
        """Convert Python value to MmsValue"""
        if isinstance(value, bool):
            return iec61850.MmsValue_newBoolean(value)
        elif isinstance(value, int):
            if -2147483648 <= value <= 2147483647:
                return iec61850.MmsValue_newIntegerFromInt32(value)
            else:
                return iec61850.MmsValue_newIntegerFromInt64(value)
        elif isinstance(value, float):
            return iec61850.MmsValue_newFloat(value)
        elif isinstance(value, str):
            return iec61850.MmsValue_newVisibleString(value)
        elif isinstance(value, bytes):
            return iec61850.MmsValue_newOctetString(value, len(value))
        elif isinstance(value, dict):
            # Handle Dbpos (double position)
            if 'stVal' in value:
                return iec61850.MmsValue_newIntegerFromInt32(value['stVal'])
        else:
            print(f"⚠️ Unsupported value type: {type(value)}")
            return None
            
    def _mms_to_python(self, mms_value) -> Any:
        """Convert MmsValue to Python value"""
        if not mms_value:
            return None
            
        value_type = iec61850.MmsValue_getType(mms_value)
        
        if value_type == iec61850.MMS_BOOLEAN:
            return iec61850.MmsValue_getBoolean(mms_value)
        elif value_type == iec61850.MMS_INTEGER:
            return iec61850.MmsValue_toInt32(mms_value)
        elif value_type == iec61850.MMS_UNSIGNED:
            return iec61850.MmsValue_toUint32(mms_value)
        elif value_type == iec61850.MMS_FLOAT:
            return iec61850.MmsValue_toFloat(mms_value)
        elif value_type == iec61850.MMS_VISIBLE_STRING:
            return iec61850.MmsValue_toString(mms_value)
        elif value_type == iec61850.MMS_OCTET_STRING:
            size = iec61850.MmsValue_getOctetStringSize(mms_value)
            buffer = iec61850.MmsValue_getOctetStringBuffer(mms_value)
            return bytes(buffer[:size])
        elif value_type == iec61850.MMS_UTC_TIME:
            return iec61850.MmsValue_getUtcTimeInMs(mms_value)
        elif value_type == iec61850.MMS_BIT_STRING:
            return iec61850.MmsValue_getBitStringAsInteger(mms_value)
        elif value_type == iec61850.MMS_STRUCTURE:
            # Handle structure (e.g., quality, timestamp)
            struct_dict = {}
            size = iec61850.MmsValue_getArraySize(mms_value)
            for i in range(size):
                element = iec61850.MmsValue_getElement(mms_value, i)
                # Simple indexing for now
                struct_dict[f"field_{i}"] = self._mms_to_python(element)
            return struct_dict
        elif value_type == iec61850.MMS_ARRAY:
            # Handle array
            array_list = []
            size = iec61850.MmsValue_getArraySize(mms_value)
            for i in range(size):
                element = iec61850.MmsValue_getElement(mms_value, i)
                array_list.append(self._mms_to_python(element))
            return array_list
        else:
            return f"Unknown type: {value_type}"
            
    def add_connection_callback(self, callback: Callable[[str, ConnectionState], None]):
        """Add connection state change callback"""
        if callback not in self.connection_callbacks:
            self.connection_callbacks.append(callback)
            
    def remove_connection_callback(self, callback: Callable[[str, ConnectionState], None]):
        """Remove connection state change callback"""
        if callback in self.connection_callbacks:
            self.connection_callbacks.remove(callback)
            
    def _notify_connection_change(self, ied_name: str, state: ConnectionState):
        """Notify callbacks of connection state change"""
        for callback in self.connection_callbacks:
            try:
                callback(ied_name, state)
            except Exception as e:
                print(f"⚠️ Error in connection callback: {e}")
                
    def get_connection_statistics(self, ied_name: str) -> Optional[Dict]:
        """Get connection statistics"""
        conn = self.get_connection(ied_name)
        if not conn:
            return None
            
        stats = {
            'state': conn.state.value,
            'connected_time': conn.connected_time,
            'request_count': conn.request_count,
            'error_count': conn.error_count,
            'last_activity': conn.last_activity,
            'error_rate': (conn.error_count / conn.request_count * 100) 
                         if conn.request_count > 0 else 0
        }
        
        if conn.connected_time:
            uptime = time.time() - conn.connected_time
            stats['uptime_seconds'] = uptime
            stats['uptime_str'] = self._format_uptime(uptime)
            
        return stats
        
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            hours = seconds / 3600
            minutes = (seconds % 3600) / 60
            return f"{hours:.0f}h {minutes:.0f}m"
            
    def disconnect_all(self):
        """Disconnect all IEDs"""
        ied_names = list(self.connections.keys())
        for ied_name in ied_names:
            self.disconnect_from_ied(ied_name)