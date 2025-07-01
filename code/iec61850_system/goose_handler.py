# goose_handler.py
import time
import struct
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime
from collections import defaultdict
import pyiec61850 as iec61850

from time_sync_utils import get_synchronized_timestamp_us

class GOOSEMessage:
    """GOOSE message data structure"""
    
    def __init__(self):
        self.goose_id = ""
        self.gocb_ref = ""
        self.dataset = ""
        self.conf_rev = 0
        self.st_num = 0
        self.sq_num = 0
        self.timestamp = 0
        self.time_allowed_to_live = 0
        self.simulation = False
        self.needs_commission = False
        self.all_data = []
        self.src_mac = ""
        self.dst_mac = ""
        self.vlan_id = 0
        self.vlan_priority = 0
        self.app_id = 0
        

class GOOSEHandler:
    """Handler for GOOSE communication"""
    
    def __init__(self, scl_data: Dict):
        self.scl_data = scl_data
        self.goose_publishers = {}
        self.goose_subscribers = {}
        self.goose_receiver = None
        self.is_receiving = False
        
        # Statistics
        self.goose_statistics = defaultdict(dict)
        self.received_messages = []
        self.sent_messages = []
        
        # Callbacks
        self.message_callbacks = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Extract GOOSE configuration from SCL
        self.goose_controls = self._extract_goose_controls()
        
    def _extract_goose_controls(self) -> List[Dict]:
        """Extract GOOSE Control Blocks from SCL"""
        goose_controls = []
        
        if not self.scl_data:
            return goose_controls
            
        scl = self.scl_data.get('SCL', {})
        ieds = scl.get('IED', [])
        
        if isinstance(ieds, dict):
            ieds = [ieds]
            
        for ied in ieds:
            if not isinstance(ied, dict):
                continue
                
            ied_name = ied.get('@name', '')
            
            # Navigate through AccessPoint -> Server -> LDevice -> LN0
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
                    if not isinstance(ld, dict):
                        continue
                        
                    ld_inst = ld.get('@inst', '')
                    ln0 = ld.get('LN0', {})
                    
                    # Find GSEControl blocks
                    gse_controls = ln0.get('GSEControl', [])
                    if isinstance(gse_controls, dict):
                        gse_controls = [gse_controls]
                        
                    for gse in gse_controls:
                        if isinstance(gse, dict):
                            gcb_info = {
                                'name': gse.get('@name', ''),
                                'desc': gse.get('@desc', ''),
                                'datSet': gse.get('@datSet', ''),
                                'confRev': int(gse.get('@confRev', 1)),
                                'appID': gse.get('@appID', ''),
                                'ied_name': ied_name,
                                'ld_inst': ld_inst,
                                'type': gse.get('@type', 'GOOSE')
                            }
                            
                            # Get network configuration
                            network_config = self._get_goose_network_config(
                                ied_name, gse.get('@name', '')
                            )
                            gcb_info.update(network_config)
                            
                            # Get dataset information
                            dataset_ref = gse.get('@datSet', '')
                            if dataset_ref:
                                dataset = self._find_dataset(ln0, dataset_ref)
                                if dataset:
                                    gcb_info['dataset'] = dataset
                                    
                            goose_controls.append(gcb_info)
                            
        return goose_controls
        
    def _get_goose_network_config(self, ied_name: str, gse_name: str) -> Dict:
        """Get network configuration for GOOSE Control Block"""
        network_config = {}
        
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
                    # Find GSE
                    gses = cap.get('GSE', [])
                    if isinstance(gses, dict):
                        gses = [gses]
                        
                    for gse in gses:
                        if gse.get('@cbName') == gse_name:
                            # Extract addresses
                            address = gse.get('Address', {})
                            p_elements = address.get('P', [])
                            if not isinstance(p_elements, list):
                                p_elements = [p_elements]
                                
                            for p in p_elements:
                                if isinstance(p, dict):
                                    p_type = p.get('@type', '')
                                    p_value = p.get('#text', '')
                                    
                                    if p_type == 'MAC-Address':
                                        network_config['mac_address'] = p_value
                                    elif p_type == 'VLAN-ID':
                                        network_config['vlan_id'] = int(p_value, 16)
                                    elif p_type == 'VLAN-PRIORITY':
                                        network_config['vlan_priority'] = int(p_value)
                                    elif p_type == 'APPID':
                                        network_config['app_id'] = int(p_value, 16)
                                        
                            # Get timing parameters
                            min_time = gse.get('MinTime')
                            if min_time:
                                network_config['min_time'] = int(min_time.get('#text', 1000))
                                
                            max_time = gse.get('MaxTime')
                            if max_time:
                                network_config['max_time'] = int(max_time.get('#text', 3000))
                                
                            break
                            
        return network_config
        
    def _find_dataset(self, ln0: Dict, dataset_ref: str) -> Optional[Dict]:
        """Find dataset definition"""
        datasets = ln0.get('DataSet', [])
        if isinstance(datasets, dict):
            datasets = [datasets]
            
        for dataset in datasets:
            if isinstance(dataset, dict) and dataset.get('@name') == dataset_ref:
                # Extract FCDA (Functionally Constrained Data Attribute)
                fcdas = dataset.get('FCDA', [])
                if isinstance(fcdas, dict):
                    fcdas = [fcdas]
                    
                dataset_items = []
                for fcda in fcdas:
                    if isinstance(fcda, dict):
                        item = {
                            'ldInst': fcda.get('@ldInst', ''),
                            'prefix': fcda.get('@prefix', ''),
                            'lnClass': fcda.get('@lnClass', ''),
                            'lnInst': fcda.get('@lnInst', ''),
                            'doName': fcda.get('@doName', ''),
                            'daName': fcda.get('@daName', ''),
                            'fc': fcda.get('@fc', '')
                        }
                        dataset_items.append(item)
                        
                return {
                    'name': dataset_ref,
                    'desc': dataset.get('@desc', ''),
                    'items': dataset_items
                }
                
        return None
        
    def create_publisher(self, gcb_name: str, interface: str = "eth0") -> Optional[Any]:
        """Create GOOSE publisher for specific GoCB"""
        gcb_config = None
        for gcb in self.goose_controls:
            if gcb['name'] == gcb_name:
                gcb_config = gcb
                break
                
        if not gcb_config:
            print(f"❌ GOOSE Control Block '{gcb_name}' not found")
            return None
            
        try:
            # Create GOOSE publisher using pyiec61850
            publisher = iec61850.GoosePublisher_create(None, interface)
            
            if not publisher:
                print(f"❌ Failed to create GOOSE publisher on {interface}")
                return None
                
            # Configure publisher
            iec61850.GoosePublisher_setGoCbRef(publisher, gcb_config.get('gocb_ref', gcb_name))
            iec61850.GoosePublisher_setDataSetRef(publisher, gcb_config.get('datSet', ''))
            iec61850.GoosePublisher_setConfRev(publisher, gcb_config.get('confRev', 1))
            iec61850.GoosePublisher_setGoID(publisher, gcb_config.get('appID', gcb_name))
            iec61850.GoosePublisher_setTimeAllowedToLive(publisher, gcb_config.get('max_time', 3000))
            
            # Set simulation mode if in test mode
            iec61850.GoosePublisher_setSimulation(publisher, False)
            
            # Store publisher
            self.goose_publishers[gcb_name] = {
                'publisher': publisher,
                'config': gcb_config,
                'interface': interface
            }
            
            print(f"✅ Created GOOSE publisher for {gcb_name}")
            return publisher
            
        except Exception as e:
            print(f"❌ Error creating GOOSE publisher: {e}")
            return None
            
    def publish_goose(self, gcb_name: str, values: List[Any]) -> bool:
        """Publish GOOSE message"""
        if gcb_name not in self.goose_publishers:
            print(f"❌ Publisher for {gcb_name} not found")
            return False
            
        try:
            publisher_info = self.goose_publishers[gcb_name]
            publisher = publisher_info['publisher']
            
            # Create dataset values
            dataset = iec61850.LinkedList_create()
            
            for value in values:
                mms_value = self._python_to_mms_value(value)
                if mms_value:
                    iec61850.LinkedList_add(dataset, mms_value)
                    
            # Update timestamp
            timestamp_us = get_synchronized_timestamp_us()
            
            # Publish
            iec61850.GoosePublisher_publish(publisher, dataset)
            
            # Clean up dataset
            iec61850.LinkedList_destroyDeep(dataset, iec61850.MmsValue_delete)
            
            # Update statistics
            with self.lock:
                self.goose_statistics[gcb_name]['sent_count'] = \
                    self.goose_statistics[gcb_name].get('sent_count', 0) + 1
                self.goose_statistics[gcb_name]['last_sent'] = time.time()
                
            print(f"✅ Published GOOSE message for {gcb_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error publishing GOOSE: {e}")
            return False
            
    def _python_to_mms_value(self, value: Any):
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
        else:
            print(f"⚠️ Unsupported value type: {type(value)}")
            return None
            
    def start_receiver(self, interface: str = "eth0") -> bool:
        """Start GOOSE receiver"""
        if self.is_receiving:
            print("⚠️ GOOSE receiver already running")
            return True
            
        try:
            # Create GOOSE receiver
            self.goose_receiver = iec61850.GooseReceiver_create()
            
            if not self.goose_receiver:
                print("❌ Failed to create GOOSE receiver")
                return False
                
            # Set interface
            iec61850.GooseReceiver_setInterfaceId(self.goose_receiver, interface)
            
            # Add subscribers for each expected GOOSE
            for gcb in self.goose_controls:
                subscriber = self._create_subscriber(gcb)
                if subscriber:
                    iec61850.GooseReceiver_addSubscriber(self.goose_receiver, subscriber)
                    self.goose_subscribers[gcb['name']] = subscriber
                    
            # Start receiver
            iec61850.GooseReceiver_start(self.goose_receiver)
            self.is_receiving = True
            
            print(f"✅ GOOSE receiver started on {interface}")
            return True
            
        except Exception as e:
            print(f"❌ Error starting GOOSE receiver: {e}")
            return False
            
    def _create_subscriber(self, gcb_config: Dict):
        """Create GOOSE subscriber"""
        try:
            # Create subscriber
            subscriber = iec61850.GooseSubscriber_create(
                gcb_config.get('gocb_ref', ''),
                gcb_config.get('app_id', 0)
            )
            
            if not subscriber:
                return None
                
            # Set callback using Python wrapper
            callback = self._create_goose_callback(gcb_config['name'])
            iec61850.GooseSubscriber_setListener(
                subscriber,
                callback,
                None  # User parameter
            )
            
            return subscriber
            
        except Exception as e:
            print(f"❌ Error creating subscriber: {e}")
            return None
            
    def _create_goose_callback(self, gcb_name: str) -> Callable:
        """Create GOOSE message callback"""
        def callback(subscriber, user_param):
            try:
                # Get message details
                goose_msg = GOOSEMessage()
                goose_msg.goose_id = iec61850.GooseSubscriber_getGoId(subscriber)
                goose_msg.gocb_ref = iec61850.GooseSubscriber_getGoCbRef(subscriber)
                goose_msg.dataset = iec61850.GooseSubscriber_getDataSet(subscriber)
                goose_msg.conf_rev = iec61850.GooseSubscriber_getConfRev(subscriber)
                goose_msg.st_num = iec61850.GooseSubscriber_getStNum(subscriber)
                goose_msg.sq_num = iec61850.GooseSubscriber_getSqNum(subscriber)
                goose_msg.timestamp = iec61850.GooseSubscriber_getTimestamp(subscriber)
                goose_msg.time_allowed_to_live = iec61850.GooseSubscriber_getTimeAllowedToLive(subscriber)
                goose_msg.simulation = iec61850.GooseSubscriber_isTest(subscriber)
                goose_msg.needs_commission = iec61850.GooseSubscriber_needsCommission(subscriber)
                
                # Get network info
                src_mac = iec61850.GooseSubscriber_getSrcMac(subscriber)
                dst_mac = iec61850.GooseSubscriber_getDstMac(subscriber)
                goose_msg.src_mac = self._format_mac_address(src_mac)
                goose_msg.dst_mac = self._format_mac_address(dst_mac)
                
                if iec61850.GooseSubscriber_isVlanSet(subscriber):
                    goose_msg.vlan_id = iec61850.GooseSubscriber_getVlanId(subscriber)
                    goose_msg.vlan_priority = iec61850.GooseSubscriber_getVlanPrio(subscriber)
                
                goose_msg.app_id = iec61850.GooseSubscriber_getAppId(subscriber)
                
                # Get data values
                values = iec61850.GooseSubscriber_getDataSetValues(subscriber)
                if values:
                    goose_msg.all_data = self._parse_dataset_values(values)
                    
                # Update statistics
                with self.lock:
                    stats = self.goose_statistics[gcb_name]
                    stats['received_count'] = stats.get('received_count', 0) + 1
                    stats['last_received'] = time.time()
                    stats['stNum'] = goose_msg.st_num
                    stats['sqNum'] = goose_msg.sq_num
                    stats['publisher'] = goose_msg.src_mac
                    stats['status'] = 'Active'
                    stats['last_update'] = time.time()
                    
                    # Store message
                    self.received_messages.append(goose_msg)
                    
                    # Limit stored messages
                    if len(self.received_messages) > 1000:
                        self.received_messages = self.received_messages[-1000:]
                        
                # Call registered callbacks
                for callback_func in self.message_callbacks:
                    try:
                        callback_func(goose_msg)
                    except Exception as e:
                        print(f"⚠️ Error in GOOSE callback: {e}")
                        
            except Exception as e:
                print(f"❌ Error processing GOOSE message: {e}")
                
        return iec61850.GooseSubscriberForPython(callback)
        
    def _format_mac_address(self, mac_bytes: bytes) -> str:
        """Format MAC address bytes to string"""
        if mac_bytes and len(mac_bytes) == 6:
            return ':'.join(f'{b:02X}' for b in mac_bytes)
        return "00:00:00:00:00:00"
        
    def _parse_dataset_values(self, dataset_values) -> List[Any]:
        """Parse dataset values from MmsValue"""
        parsed_values = []
        
        if not dataset_values:
            return parsed_values
            
        try:
            # Get number of values
            num_values = iec61850.MmsValue_getArraySize(dataset_values)
            
            for i in range(num_values):
                element = iec61850.MmsValue_getElement(dataset_values, i)
                if element:
                    value = self._mms_value_to_python(element)
                    parsed_values.append(value)
                    
        except Exception as e:
            print(f"⚠️ Error parsing dataset values: {e}")
            
        return parsed_values
        
    def _mms_value_to_python(self, mms_value) -> Any:
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
            # Parse structure recursively
            struct_values = {}
            size = iec61850.MmsValue_getArraySize(mms_value)
            for i in range(size):
                element = iec61850.MmsValue_getElement(mms_value, i)
                struct_values[f"field_{i}"] = self._mms_value_to_python(element)
            return struct_values
        elif value_type == iec61850.MMS_ARRAY:
            # Parse array
            array_values = []
            size = iec61850.MmsValue_getArraySize(mms_value)
            for i in range(size):
                element = iec61850.MmsValue_getElement(mms_value, i)
                array_values.append(self._mms_value_to_python(element))
            return array_values
        else:
            return f"Unknown type: {value_type}"
            
    def stop_receiver(self):
        """Stop GOOSE receiver"""
        if not self.is_receiving:
            return
            
        try:
            if self.goose_receiver:
                iec61850.GooseReceiver_stop(self.goose_receiver)
                iec61850.GooseReceiver_destroy(self.goose_receiver)
                self.goose_receiver = None
                
            self.is_receiving = False
            print("✅ GOOSE receiver stopped")
            
        except Exception as e:
            print(f"❌ Error stopping GOOSE receiver: {e}")
            
    def add_message_callback(self, callback: Callable[[GOOSEMessage], None]):
        """Add callback for received GOOSE messages"""
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
            
    def remove_message_callback(self, callback: Callable[[GOOSEMessage], None]):
        """Remove message callback"""
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
            
    def get_goose_statistics(self) -> Dict[str, Dict]:
        """Get GOOSE statistics"""
        with self.lock:
            return dict(self.goose_statistics)
            
    def clear_statistics(self):
        """Clear GOOSE statistics"""
        with self.lock:
            self.goose_statistics.clear()
            self.received_messages.clear()
            self.sent_messages.clear()
            
    def get_received_messages(self, gcb_name: Optional[str] = None, 
                            limit: int = 100) -> List[GOOSEMessage]:
        """Get received GOOSE messages"""
        with self.lock:
            if gcb_name:
                messages = [msg for msg in self.received_messages 
                          if msg.gocb_ref == gcb_name]
            else:
                messages = self.received_messages.copy()
                
            return messages[-limit:]
            
    def send_test_goose(self, gcb_name: str, test_values: Optional[List[Any]] = None) -> bool:
        """Send test GOOSE message"""
        if gcb_name not in self.goose_controls:
            print(f"❌ Unknown GOOSE Control Block: {gcb_name}")
            return False
            
        # Create publisher if not exists
        if gcb_name not in self.goose_publishers:
            if not self.create_publisher(gcb_name):
                return False
                
        # Generate test values if not provided
        if test_values is None:
            gcb_config = next(gcb for gcb in self.goose_controls if gcb['name'] == gcb_name)
            dataset = gcb_config.get('dataset', {})
            dataset_items = dataset.get('items', [])
            
            test_values = []
            for item in dataset_items:
                # Generate test value based on type
                if 'stVal' in item.get('daName', ''):
                    test_values.append(True)  # Boolean
                elif 'mag' in item.get('daName', ''):
                    test_values.append(100.0)  # Float
                elif 'q' in item.get('daName', ''):
                    test_values.append(0x0000)  # Quality (Good)
                else:
                    test_values.append(0)  # Default integer
                    
        # Publish test message
        return self.publish_goose(gcb_name, test_values)
        
    def simulate_goose_burst(self, gcb_name: str, values: List[Any], 
                           burst_count: int = 5) -> bool:
        """Simulate GOOSE burst transmission (for testing)"""
        if gcb_name not in self.goose_publishers:
            if not self.create_publisher(gcb_name):
                return False
                
        try:
            publisher_info = self.goose_publishers[gcb_name]
            publisher = publisher_info['publisher']
            
            # Increase state number for new event
            iec61850.GoosePublisher_increaseStNum(publisher)
            
            # Send burst with decreasing intervals
            intervals = [0, 2, 4, 8, 16]  # milliseconds
            
            for i in range(min(burst_count, len(intervals))):
                if i > 0:
                    time.sleep(intervals[i] / 1000.0)
                    
                # Update sequence number
                iec61850.GoosePublisher_setSqNum(publisher, i)
                
                # Publish
                success = self.publish_goose(gcb_name, values)
                if not success:
                    return False
                    
            print(f"✅ Sent GOOSE burst ({burst_count} messages) for {gcb_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending GOOSE burst: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources"""
        # Stop receiver
        self.stop_receiver()
        
        # Destroy publishers
        for gcb_name, publisher_info in self.goose_publishers.items():
            try:
                iec61850.GoosePublisher_destroy(publisher_info['publisher'])
            except:
                pass
                
        self.goose_publishers.clear()
        self.goose_subscribers.clear()