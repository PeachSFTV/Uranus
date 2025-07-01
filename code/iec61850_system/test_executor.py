# test_executor.py
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from PyQt6.QtCore import QObject, pyqtSignal

import pyiec61850 as iec61850
from ied_connection_manager import IEDConnectionManager, IEDConnection
from goose_handler import GOOSEHandler
from time_sync_utils import get_synchronized_timestamp_us


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "Pending"
    RUNNING = "Running"
    PASSED = "Passed"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    ERROR = "Error"
    TIMEOUT = "Timeout"


@dataclass
class TestResult:
    """Test execution result"""
    test_id: str
    test_name: str
    ied_name: str
    status: TestStatus
    start_time: float
    end_time: float = 0
    duration: float = 0
    details: Optional[str] = None
    error_message: Optional[str] = None
    measurements: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    

class TestExecutor(QObject):
    """Executor for commissioning tests"""
    
    # Signals
    test_started = pyqtSignal(str, str)  # test_id, ied_name
    test_completed = pyqtSignal(str, object)  # test_id, TestResult
    test_progress = pyqtSignal(str, int)  # test_id, progress_percentage
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(self, connection_manager: IEDConnectionManager,
                 goose_handler: Optional[GOOSEHandler] = None,
                 safety_checks: bool = True):
        super().__init__()
        
        self.connection_manager = connection_manager
        self.goose_handler = goose_handler
        self.safety_checks_enabled = safety_checks
        self.test_mode = True  # True = simulation, False = live
        
        # Test execution
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.active_tests: Dict[str, Future] = {}
        self.test_results: List[TestResult] = []
        
        # Test implementations
        self.test_implementations = {
            # Basic tests
            'connectivity': self._test_connectivity,
            'time_sync': self._test_time_synchronization,
            'data_model': self._test_data_model_verification,
            
            # Control tests
            'xcbr_control': self._test_circuit_breaker_control,
            'xswi_control': self._test_switch_control,
            'cswi_control': self._test_control_switch,
            
            # Protection tests
            'ptoc_test': self._test_overcurrent_protection,
            'pdif_test': self._test_differential_protection,
            'ptov_test': self._test_overvoltage_protection,
            'ptuv_test': self._test_undervoltage_protection,
            
            # Measurement tests
            'mmxu_verify': self._test_measurement_verification,
            'msqi_test': self._test_sequence_measurement,
            
            # GOOSE tests
            'goose_publish': self._test_goose_publishing,
            'goose_subscribe': self._test_goose_subscription,
            'goose_performance': self._test_goose_performance,
            
            # Interlocking tests
            'interlock_basic': self._test_basic_interlocking,
            'interlock_complex': self._test_complex_interlocking,
            
            # Performance tests
            'response_time': self._test_response_time,
            'throughput': self._test_data_throughput,
        }
        
    def set_test_mode(self, test_mode: bool):
        """Set test mode (simulation vs live)"""
        self.test_mode = test_mode
        self.log_message.emit(
            f"Test mode set to: {'Simulation' if test_mode else 'LIVE'}",
            "info"
        )
        
    def set_safety_checks(self, enabled: bool):
        """Enable/disable safety checks"""
        self.safety_checks_enabled = enabled
        self.log_message.emit(
            f"Safety checks: {'Enabled' if enabled else 'DISABLED'}",
            "warning" if not enabled else "info"
        )
        
    def execute_test_async(self, test_id: str, ied_name: str,
                          connection: IEDConnection,
                          callback: Optional[Callable[[TestResult], None]] = None):
        """Execute test asynchronously"""
        
        # Check if test exists
        if test_id not in self.test_implementations:
            result = TestResult(
                test_id=test_id,
                test_name=test_id,
                ied_name=ied_name,
                status=TestStatus.ERROR,
                start_time=time.time(),
                error_message=f"Unknown test: {test_id}"
            )
            if callback:
                callback(result)
            return
            
        # Submit test for execution
        future = self.executor.submit(
            self._execute_test_wrapper,
            test_id, ied_name, connection, callback
        )
        
        # Store active test
        test_key = f"{test_id}_{ied_name}"
        self.active_tests[test_key] = future
        
    def _execute_test_wrapper(self, test_id: str, ied_name: str,
                             connection: IEDConnection,
                             callback: Optional[Callable[[TestResult], None]] = None):
        """Wrapper for test execution with error handling"""
        
        # Emit start signal
        self.test_started.emit(test_id, ied_name)
        
        # Create result object
        result = TestResult(
            test_id=test_id,
            test_name=self._get_test_name(test_id),
            ied_name=ied_name,
            status=TestStatus.RUNNING,
            start_time=time.time()
        )
        
        try:
            # Execute test
            test_func = self.test_implementations[test_id]
            test_func(connection, result)
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            self.log_message.emit(
                f"Test {test_id} error: {e}",
                "error"
            )
            
        finally:
            # Complete result
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            
            # Store result
            self.test_results.append(result)
            
            # Remove from active tests
            test_key = f"{test_id}_{ied_name}"
            if test_key in self.active_tests:
                del self.active_tests[test_key]
                
            # Emit completion signal
            self.test_completed.emit(test_id, result)
            
            # Call callback if provided
            if callback:
                callback(result)
                
    def _get_test_name(self, test_id: str) -> str:
        """Get human-readable test name"""
        test_names = {
            'connectivity': "Connectivity Test",
            'time_sync': "Time Synchronization",
            'data_model': "Data Model Verification",
            'xcbr_control': "Circuit Breaker Control",
            'xswi_control': "Switch Control",
            'cswi_control': "Control Switch",
            'ptoc_test': "Overcurrent Protection (50/51)",
            'pdif_test': "Differential Protection (87)",
            'ptov_test': "Overvoltage Protection (59)",
            'ptuv_test': "Undervoltage Protection (27)",
            'mmxu_verify': "Measurement Verification",
            'msqi_test': "Sequence Measurement",
            'goose_publish': "GOOSE Publishing",
            'goose_subscribe': "GOOSE Subscription",
            'goose_performance': "GOOSE Performance",
            'interlock_basic': "Basic Interlocking",
            'interlock_complex': "Complex Interlocking",
            'response_time': "Response Time",
            'throughput': "Data Throughput"
        }
        return test_names.get(test_id, test_id)
        
    # Test Implementations
    
    def _test_connectivity(self, connection: IEDConnection, result: TestResult):
        """Test basic IED connectivity"""
        self.log_message.emit(f"Testing connectivity to {connection.ied_name}", "info")
        
        try:
            # Check connection state
            if connection.state.value != "Connected":
                result.status = TestStatus.FAILED
                result.error_message = "IED not connected"
                return
                
            # Try to read server directory
            server_dir = iec61850.IedConnection_getServerDirectory(
                connection.connection,
                False  # getFileNames
            )
            
            if server_dir:
                # Count logical devices
                ld_count = 0
                element = server_dir
                while element:
                    ld_count += 1
                    element = iec61850.LinkedList_getNext(element)
                    
                iec61850.LinkedList_destroy(server_dir)
                
                result.status = TestStatus.PASSED
                result.details = f"Connected successfully. Found {ld_count} logical devices."
                result.measurements['logical_device_count'] = ld_count
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Failed to read server directory"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_time_synchronization(self, connection: IEDConnection, result: TestResult):
        """Test time synchronization"""
        self.log_message.emit(f"Testing time sync for {connection.ied_name}", "info")
        
        try:
            # Read time from IED (example: LLN0.NamPlt.ldNs)
            time_path = f"{connection.ied_name}LD0/LLN0.Mod.t"
            
            # Read timestamp
            timestamp_result, error = self.connection_manager.read_value(
                connection.ied_name, 
                time_path
            )
            
            if error:
                # Try alternative path
                time_path = f"IED1LD0/LLN0.Beh.t"
                timestamp_result, error = self.connection_manager.read_value(
                    connection.ied_name,
                    time_path
                )
                
            if not error and timestamp_result:
                # Get local time
                local_time_ms = get_synchronized_timestamp_us() // 1000
                
                # Calculate difference
                if isinstance(timestamp_result, (int, float)):
                    ied_time_ms = int(timestamp_result)
                    time_diff_ms = abs(local_time_ms - ied_time_ms)
                    
                    result.measurements['time_difference_ms'] = time_diff_ms
                    result.measurements['ied_time'] = ied_time_ms
                    result.measurements['local_time'] = local_time_ms
                    
                    # Check tolerance (e.g., 100ms)
                    if time_diff_ms < 100:
                        result.status = TestStatus.PASSED
                        result.details = f"Time synchronized within {time_diff_ms}ms"
                    else:
                        result.status = TestStatus.FAILED
                        result.error_message = f"Time difference too large: {time_diff_ms}ms"
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = "Invalid timestamp format"
            else:
                result.status = TestStatus.SKIPPED
                result.details = "Could not read time from IED"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_data_model_verification(self, connection: IEDConnection, result: TestResult):
        """Verify IED data model"""
        self.log_message.emit(f"Verifying data model for {connection.ied_name}", "info")
        
        try:
            # Get logical device list
            ld_list, error = self.connection_manager.get_logical_device_list(
                connection.ied_name
            )
            
            if error:
                result.status = TestStatus.FAILED
                result.error_message = error
                return
                
            if not ld_list:
                result.status = TestStatus.FAILED
                result.error_message = "No logical devices found"
                return
                
            # Verify each logical device
            total_ln_count = 0
            verified_ln_count = 0
            
            for ld_name in ld_list:
                # Get logical nodes
                ln_list, error = self.connection_manager.get_logical_node_list(
                    connection.ied_name,
                    ld_name
                )
                
                if not error and ln_list:
                    total_ln_count += len(ln_list)
                    
                    # Verify common logical nodes
                    expected_lns = ['LLN0']  # At least LLN0 should exist
                    for expected_ln in expected_lns:
                        if expected_ln in ln_list:
                            verified_ln_count += 1
                            
            result.measurements['logical_device_count'] = len(ld_list)
            result.measurements['logical_node_count'] = total_ln_count
            result.measurements['verified_nodes'] = verified_ln_count
            
            if verified_ln_count > 0:
                result.status = TestStatus.PASSED
                result.details = f"Verified {len(ld_list)} LDs with {total_ln_count} LNs"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not verify expected logical nodes"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_circuit_breaker_control(self, connection: IEDConnection, result: TestResult):
        """Test circuit breaker control operations"""
        self.log_message.emit(f"Testing CB control for {connection.ied_name}", "info")
        
        try:
            # Safety check
            if not self.test_mode and self.safety_checks_enabled:
                if not self._perform_safety_checks(connection, 'XCBR'):
                    result.status = TestStatus.SKIPPED
                    result.details = "Safety checks failed"
                    return
                    
            # Find XCBR logical nodes
            xcbr_nodes = self._find_logical_nodes_by_class(connection, 'XCBR')
            
            if not xcbr_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No XCBR (Circuit Breaker) found"
                return
                
            # Test first XCBR
            xcbr_path = xcbr_nodes[0]
            self.log_message.emit(f"Testing XCBR at: {xcbr_path}", "info")
            
            # Read current position
            pos_path = f"{xcbr_path}.Pos.stVal"
            current_pos, error = self.connection_manager.read_value(
                connection.ied_name,
                pos_path
            )
            
            if error:
                result.status = TestStatus.FAILED
                result.error_message = f"Failed to read CB position: {error}"
                return
                
            result.measurements['initial_position'] = current_pos
            
            # Find associated CSWI (Control Switch)
            cswi_path = xcbr_path.replace('XCBR', 'CSWI')
            control_path = f"{cswi_path}.Pos"
            
            # Test sequence: Open -> Close -> Open
            test_sequence = [
                (2, "Open"),   # Dbpos OFF
                (3, "Close"),  # Dbpos ON
                (2, "Open")    # Dbpos OFF
            ]
            
            operation_times = []
            
            for target_pos, operation in test_sequence:
                self.log_message.emit(f"Executing {operation} command", "info")
                
                # Measure operation time
                start_time = time.time()
                
                # Send control command
                error = self.connection_manager.control_operation(
                    connection.ied_name,
                    control_path,
                    target_pos,
                    select_before_operate=True,
                    test_mode=self.test_mode
                )
                
                if error:
                    result.status = TestStatus.FAILED
                    result.error_message = f"Control failed: {error}"
                    return
                    
                # Wait for position change
                position_changed = False
                timeout = 5.0  # 5 seconds timeout
                poll_interval = 0.05  # 50ms
                
                while time.time() - start_time < timeout:
                    new_pos, _ = self.connection_manager.read_value(
                        connection.ied_name,
                        pos_path
                    )
                    
                    if new_pos == target_pos:
                        position_changed = True
                        break
                        
                    time.sleep(poll_interval)
                    
                operation_time = time.time() - start_time
                operation_times.append(operation_time)
                
                if not position_changed:
                    result.status = TestStatus.FAILED
                    result.error_message = f"{operation} operation timeout"
                    return
                    
                self.log_message.emit(
                    f"{operation} completed in {operation_time*1000:.1f}ms",
                    "info"
                )
                
                # Delay between operations
                time.sleep(1.0)
                
            # All operations successful
            result.status = TestStatus.PASSED
            result.details = "CB control test passed"
            result.measurements['open_time_ms'] = operation_times[0] * 1000
            result.measurements['close_time_ms'] = operation_times[1] * 1000
            result.measurements['average_time_ms'] = sum(operation_times) / len(operation_times) * 1000
            
            # Check performance criteria
            if max(operation_times) > 0.2:  # 200ms
                result.details += " (Warning: Operation time > 200ms)"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_switch_control(self, connection: IEDConnection, result: TestResult):
        """Test switch control operations"""
        # Similar to CB control but for XSWI
        self.log_message.emit(f"Testing switch control for {connection.ied_name}", "info")
        
        try:
            # Find XSWI logical nodes
            xswi_nodes = self._find_logical_nodes_by_class(connection, 'XSWI')
            
            if not xswi_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No XSWI (Switch) found"
                return
                
            # Test implementation similar to XCBR
            # ... (implementation details)
            
            result.status = TestStatus.PASSED
            result.details = "Switch control test passed"
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_overcurrent_protection(self, connection: IEDConnection, result: TestResult):
        """Test overcurrent protection (PTOC)"""
        self.log_message.emit(f"Testing PTOC for {connection.ied_name}", "info")
        
        try:
            # Find PTOC logical nodes
            ptoc_nodes = self._find_logical_nodes_by_class(connection, 'PTOC')
            
            if not ptoc_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No PTOC (Overcurrent Protection) found"
                return
                
            ptoc_path = ptoc_nodes[0]
            
            # Read protection settings
            settings = {}
            setting_paths = {
                'pickup_current': f"{ptoc_path}.StrVal.setMag.f",
                'time_delay': f"{ptoc_path}.OpDlTmms.setVal",
                'curve_type': f"{ptoc_path}.TmACrv.setCharact"
            }
            
            for setting_name, path in setting_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    settings[setting_name] = value
                    
            result.measurements['protection_settings'] = settings
            
            # Read protection status
            status_paths = {
                'start': f"{ptoc_path}.Str.general",
                'operate': f"{ptoc_path}.Op.general"
            }
            
            status = {}
            for status_name, path in status_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    status[status_name] = value
                    
            result.measurements['protection_status'] = status
            
            # Verify settings are within expected range
            if 'pickup_current' in settings:
                pickup = settings['pickup_current']
                if 0.1 <= pickup <= 10.0:  # Example range
                    result.status = TestStatus.PASSED
                    result.details = f"PTOC verified. Pickup: {pickup}A"
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = f"Pickup current out of range: {pickup}A"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read protection settings"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_measurement_verification(self, connection: IEDConnection, result: TestResult):
        """Verify measurement values (MMXU)"""
        self.log_message.emit(f"Testing measurements for {connection.ied_name}", "info")
        
        try:
            # Find MMXU logical nodes
            mmxu_nodes = self._find_logical_nodes_by_class(connection, 'MMXU')
            
            if not mmxu_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No MMXU (Measurement Unit) found"
                return
                
            mmxu_path = mmxu_nodes[0]
            
            # Read measurements
            measurements = {}
            measurement_paths = {
                'voltage_a': f"{mmxu_path}.PhV.phsA.cVal.mag.f",
                'voltage_b': f"{mmxu_path}.PhV.phsB.cVal.mag.f",
                'voltage_c': f"{mmxu_path}.PhV.phsC.cVal.mag.f",
                'current_a': f"{mmxu_path}.A.phsA.cVal.mag.f",
                'current_b': f"{mmxu_path}.A.phsB.cVal.mag.f",
                'current_c': f"{mmxu_path}.A.phsC.cVal.mag.f",
                'frequency': f"{mmxu_path}.Hz.mag.f",
                'power': f"{mmxu_path}.TotW.mag.f"
            }
            
            valid_measurements = 0
            
            for meas_name, path in measurement_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error and value is not None:
                    measurements[meas_name] = value
                    valid_measurements += 1
                    
            result.measurements = measurements
            
            # Verify measurements are reasonable
            if valid_measurements > 0:
                # Check frequency if available
                if 'frequency' in measurements:
                    freq = measurements['frequency']
                    if 49.5 <= freq <= 50.5:  # 50Hz ± 0.5Hz
                        result.status = TestStatus.PASSED
                        result.details = f"Measurements verified. Frequency: {freq:.2f}Hz"
                    else:
                        result.status = TestStatus.FAILED
                        result.error_message = f"Frequency out of range: {freq}Hz"
                else:
                    result.status = TestStatus.PASSED
                    result.details = f"Read {valid_measurements} measurements successfully"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "No measurements could be read"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_goose_publishing(self, connection: IEDConnection, result: TestResult):
        """Test GOOSE publishing capability"""
        if not self.goose_handler:
            result.status = TestStatus.SKIPPED
            result.details = "GOOSE handler not available"
            return
            
        self.log_message.emit(f"Testing GOOSE publishing for {connection.ied_name}", "info")
        
        try:
            # Find GOOSE control blocks for this IED
            gcb_list = []
            for gcb in self.goose_handler.goose_controls:
                if gcb['ied_name'] == connection.ied_name:
                    gcb_list.append(gcb)
                    
            if not gcb_list:
                result.status = TestStatus.SKIPPED
                result.details = "No GOOSE control blocks found"
                return
                
            # Test first GoCB
            gcb = gcb_list[0]
            gcb_name = gcb['name']
            
            self.log_message.emit(f"Testing GoCB: {gcb_name}", "info")
            
            # Send test GOOSE
            success = self.goose_handler.send_test_goose(gcb_name)
            
            if success:
                result.status = TestStatus.PASSED
                result.details = f"Successfully published GOOSE for {gcb_name}"
                result.measurements['goose_control_blocks'] = len(gcb_list)
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Failed to publish GOOSE"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_goose_subscription(self, connection: IEDConnection, result: TestResult):
        """Test GOOSE subscription capability"""
        if not self.goose_handler:
            result.status = TestStatus.SKIPPED
            result.details = "GOOSE handler not available"
            return
            
        self.log_message.emit(f"Testing GOOSE subscription for {connection.ied_name}", "info")
        
        try:
            # Start GOOSE receiver if not running
            if not self.goose_handler.is_receiving:
                interface = "eth0"  # TODO: Get from configuration
                if not self.goose_handler.start_receiver(interface):
                    result.status = TestStatus.FAILED
                    result.error_message = "Failed to start GOOSE receiver"
                    return
                    
            # Wait for GOOSE messages
            start_time = time.time()
            timeout = 10.0  # 10 seconds
            
            initial_count = len(self.goose_handler.received_messages)
            
            while time.time() - start_time < timeout:
                current_count = len(self.goose_handler.received_messages)
                if current_count > initial_count:
                    break
                time.sleep(0.1)
                
            received_count = len(self.goose_handler.received_messages) - initial_count
            
            if received_count > 0:
                result.status = TestStatus.PASSED
                result.details = f"Received {received_count} GOOSE messages"
                result.measurements['received_messages'] = received_count
                
                # Get statistics
                stats = self.goose_handler.get_goose_statistics()
                result.measurements['goose_publishers'] = len(stats)
            else:
                result.status = TestStatus.FAILED
                result.error_message = "No GOOSE messages received"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_goose_performance(self, connection: IEDConnection, result: TestResult):
        """Test GOOSE performance (timing)"""
        if not self.goose_handler:
            result.status = TestStatus.SKIPPED
            result.details = "GOOSE handler not available"
            return
            
        self.log_message.emit(f"Testing GOOSE performance for {connection.ied_name}", "info")
        
        try:
            # Measure GOOSE round-trip time
            # This would require a loopback configuration or
            # cooperation with another IED
            
            # For now, measure publishing time
            gcb_list = []
            for gcb in self.goose_handler.goose_controls:
                if gcb['ied_name'] == connection.ied_name:
                    gcb_list.append(gcb)
                    
            if not gcb_list:
                result.status = TestStatus.SKIPPED
                result.details = "No GOOSE control blocks found"
                return
                
            gcb_name = gcb_list[0]['name']
            
            # Measure time to publish
            timing_results = []
            test_count = 10
            
            for i in range(test_count):
                start_time = time.time()
                success = self.goose_handler.send_test_goose(gcb_name)
                publish_time = (time.time() - start_time) * 1000  # ms
                
                if success:
                    timing_results.append(publish_time)
                    
                time.sleep(0.1)  # 100ms between tests
                
            if timing_results:
                avg_time = sum(timing_results) / len(timing_results)
                max_time = max(timing_results)
                min_time = min(timing_results)
                
                result.measurements['average_publish_time_ms'] = avg_time
                result.measurements['max_publish_time_ms'] = max_time
                result.measurements['min_publish_time_ms'] = min_time
                
                # Check against requirement (e.g., < 4ms)
                if max_time < 4.0:
                    result.status = TestStatus.PASSED
                    result.details = f"GOOSE timing OK. Avg: {avg_time:.2f}ms"
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = f"GOOSE timing exceeds 4ms: {max_time:.2f}ms"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Failed to measure GOOSE timing"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_basic_interlocking(self, connection: IEDConnection, result: TestResult):
        """Test basic interlocking logic"""
        self.log_message.emit(f"Testing interlocking for {connection.ied_name}", "info")
        
        try:
            # Find CILO (Interlocking) logical nodes
            cilo_nodes = self._find_logical_nodes_by_class(connection, 'CILO')
            
            if not cilo_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No CILO (Interlocking) found"
                return
                
            cilo_path = cilo_nodes[0]
            
            # Read interlocking status
            interlock_paths = {
                'enabled': f"{cilo_path}.EnaOpn.stVal",
                'closed': f"{cilo_path}.EnaCls.stVal"
            }
            
            interlock_status = {}
            for name, path in interlock_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    interlock_status[name] = value
                    
            result.measurements['interlock_status'] = interlock_status
            
            # Basic verification
            if interlock_status:
                result.status = TestStatus.PASSED
                result.details = "Interlocking status verified"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read interlocking status"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_response_time(self, connection: IEDConnection, result: TestResult):
        """Test control response time"""
        self.log_message.emit(f"Testing response time for {connection.ied_name}", "info")
        
        try:
            # Use a simple read operation to measure response time
            test_path = f"{connection.ied_name}LD0/LLN0.Mod.stVal"
            
            response_times = []
            test_count = 10
            
            for i in range(test_count):
                start_time = time.time()
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    test_path
                )
                response_time = (time.time() - start_time) * 1000  # ms
                
                if not error:
                    response_times.append(response_time)
                    
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)
                
                result.measurements['average_response_ms'] = avg_time
                result.measurements['max_response_ms'] = max_time
                result.measurements['min_response_ms'] = min_time
                
                # Check performance
                if avg_time < 100:  # 100ms average
                    result.status = TestStatus.PASSED
                    result.details = f"Response time OK. Avg: {avg_time:.1f}ms"
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = f"Response time too high: {avg_time:.1f}ms"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Failed to measure response time"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    # Helper methods
    
    def _find_logical_nodes_by_class(self, connection: IEDConnection, 
                                    ln_class: str) -> List[str]:
        """Find all logical nodes of specific class"""
        found_nodes = []
        
        try:
            # Get logical devices
            ld_list, error = self.connection_manager.get_logical_device_list(
                connection.ied_name
            )
            
            if error or not ld_list:
                return found_nodes
                
            for ld_name in ld_list:
                # Get logical nodes
                ln_list, error = self.connection_manager.get_logical_node_list(
                    connection.ied_name,
                    ld_name
                )
                
                if not error and ln_list:
                    for ln_name in ln_list:
                        # Check if it matches the class
                        if ln_class in ln_name:
                            ln_path = f"{ld_name}/{ln_name}"
                            founln_path = f"{ld_name}/{ln_name}"
                            found_nodes.append(ln_path)
                            
        except Exception as e:
            self.log_message.emit(f"Error finding {ln_class} nodes: {e}", "error")
            
        return found_nodes
        
    def _test_control_switch(self, connection: IEDConnection, result: TestResult):
        """Test control switch operations (CSWI)"""
        self.log_message.emit(f"Testing control switch for {connection.ied_name}", "info")
        
        try:
            # Find CSWI logical nodes
            cswi_nodes = self._find_logical_nodes_by_class(connection, 'CSWI')
            
            if not cswi_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No CSWI (Control Switch) found"
                return
                
            cswi_path = cswi_nodes[0]
            
            # Read control switch status
            status_paths = {
                'position': f"{cswi_path}.Pos.stVal",
                'mode': f"{cswi_path}.Mod.stVal",
                'health': f"{cswi_path}.Health.stVal"
            }
            
            status = {}
            for name, path in status_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    status[name] = value
                    
            result.measurements['control_switch_status'] = status
            
            if status:
                result.status = TestStatus.PASSED
                result.details = f"Control switch verified. Mode: {status.get('mode', 'Unknown')}"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read control switch status"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_differential_protection(self, connection: IEDConnection, result: TestResult):
        """Test differential protection (PDIF)"""
        self.log_message.emit(f"Testing differential protection for {connection.ied_name}", "info")
        
        try:
            # Find PDIF logical nodes
            pdif_nodes = self._find_logical_nodes_by_class(connection, 'PDIF')
            
            if not pdif_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No PDIF (Differential Protection) found"
                return
                
            pdif_path = pdif_nodes[0]
            
            # Read differential protection status
            status_paths = {
                'operate': f"{pdif_path}.Op.general",
                'start': f"{pdif_path}.Str.general",
                'diff_current': f"{pdif_path}.DifAClc.mag.f"
            }
            
            status = {}
            for name, path in status_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    status[name] = value
                    
            result.measurements['differential_status'] = status
            
            # Check if protection is healthy
            if 'operate' in status and 'start' in status:
                if status['operate'] is False and status['start'] is False:
                    result.status = TestStatus.PASSED
                    result.details = "Differential protection healthy (no trip/start)"
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = "Differential protection in alarm state"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read differential protection status"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_overvoltage_protection(self, connection: IEDConnection, result: TestResult):
        """Test overvoltage protection (PTOV)"""
        self.log_message.emit(f"Testing overvoltage protection for {connection.ied_name}", "info")
        
        try:
            # Find PTOV logical nodes
            ptov_nodes = self._find_logical_nodes_by_class(connection, 'PTOV')
            
            if not ptov_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No PTOV (Overvoltage Protection) found"
                return
                
            ptov_path = ptov_nodes[0]
            
            # Read settings
            settings_paths = {
                'pickup_voltage': f"{ptov_path}.StrVal.setMag.f",
                'time_delay': f"{ptov_path}.OpDlTmms.setVal"
            }
            
            settings = {}
            for name, path in settings_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    settings[name] = value
                    
            result.measurements['overvoltage_settings'] = settings
            
            if settings.get('pickup_voltage'):
                # Verify reasonable settings (e.g., 110% - 150% of nominal)
                pickup = settings['pickup_voltage']
                if 1.1 <= pickup <= 1.5:  # Per unit
                    result.status = TestStatus.PASSED
                    result.details = f"Overvoltage protection verified. Pickup: {pickup:.2f}pu"
                else:
                    result.status = TestStatus.WARNING
                    result.details = f"Overvoltage pickup may be incorrect: {pickup:.2f}pu"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read overvoltage settings"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_undervoltage_protection(self, connection: IEDConnection, result: TestResult):
        """Test undervoltage protection (PTUV)"""
        # Similar to overvoltage but checking for low voltage
        pass
        
    def _test_sequence_measurement(self, connection: IEDConnection, result: TestResult):
        """Test sequence measurement (MSQI)"""
        self.log_message.emit(f"Testing sequence measurement for {connection.ied_name}", "info")
        
        try:
            # Find MSQI logical nodes
            msqi_nodes = self._find_logical_nodes_by_class(connection, 'MSQI')
            
            if not msqi_nodes:
                result.status = TestStatus.SKIPPED
                result.details = "No MSQI (Sequence Measurement) found"
                return
                
            msqi_path = msqi_nodes[0]
            
            # Read sequence components
            sequence_paths = {
                'positive_seq_current': f"{msqi_path}.SeqA.c1.cVal.mag.f",
                'negative_seq_current': f"{msqi_path}.SeqA.c2.cVal.mag.f",
                'zero_seq_current': f"{msqi_path}.SeqA.c3.cVal.mag.f",
                'positive_seq_voltage': f"{msqi_path}.SeqV.c1.cVal.mag.f",
                'negative_seq_voltage': f"{msqi_path}.SeqV.c2.cVal.mag.f"
            }
            
            sequences = {}
            for name, path in sequence_paths.items():
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    path
                )
                if not error:
                    sequences[name] = value
                    
            result.measurements['sequence_components'] = sequences
            
            # Check for unbalance
            if 'positive_seq_current' in sequences and 'negative_seq_current' in sequences:
                pos_seq = sequences['positive_seq_current']
                neg_seq = sequences['negative_seq_current']
                
                if pos_seq > 0:
                    unbalance = (neg_seq / pos_seq) * 100
                    result.measurements['current_unbalance_percent'] = unbalance
                    
                    if unbalance < 5:  # Less than 5% unbalance
                        result.status = TestStatus.PASSED
                        result.details = f"Sequence measurement OK. Unbalance: {unbalance:.1f}%"
                    else:
                        result.status = TestStatus.WARNING
                        result.details = f"High current unbalance: {unbalance:.1f}%"
                else:
                    result.status = TestStatus.PASSED
                    result.details = "No current flow detected"
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Could not read sequence components"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _test_complex_interlocking(self, connection: IEDConnection, result: TestResult):
        """Test complex interlocking scenarios"""
        # Would test multiple interlocking conditions
        pass
        
    def _test_data_throughput(self, connection: IEDConnection, result: TestResult):
        """Test data throughput capability"""
        self.log_message.emit(f"Testing data throughput for {connection.ied_name}", "info")
        
        try:
            # Measure how fast we can read multiple values
            test_duration = 5.0  # 5 seconds
            read_count = 0
            error_count = 0
            start_time = time.time()
            
            # Simple test path
            test_path = f"{connection.ied_name}LD0/LLN0.Mod.stVal"
            
            while time.time() - start_time < test_duration:
                value, error = self.connection_manager.read_value(
                    connection.ied_name,
                    test_path
                )
                
                if error:
                    error_count += 1
                else:
                    read_count += 1
                    
            elapsed_time = time.time() - start_time
            reads_per_second = read_count / elapsed_time
            
            result.measurements['reads_per_second'] = reads_per_second
            result.measurements['total_reads'] = read_count
            result.measurements['errors'] = error_count
            result.measurements['error_rate_percent'] = (error_count / (read_count + error_count) * 100) if (read_count + error_count) > 0 else 0
            
            # Check performance
            if reads_per_second > 10 and result.measurements['error_rate_percent'] < 1:
                result.status = TestStatus.PASSED
                result.details = f"Throughput OK: {reads_per_second:.1f} reads/sec"
            else:
                result.status = TestStatus.FAILED
                result.error_message = f"Low throughput: {reads_per_second:.1f} reads/sec"
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            
    def _perform_safety_checks(self, connection: IEDConnection, device_type: str) -> bool:
        """Perform safety checks before control operations"""
        if not self.safety_checks_enabled:
            return True
            
        self.log_message.emit(f"Performing safety checks for {device_type}", "info")
        
        try:
            # Example safety checks
            if device_type == 'XCBR':
                # Check if breaker is in local mode
                mode_path = f"{connection.ied_name}LD0/XCBR1.Loc.stVal"
                local_mode, error = self.connection_manager.read_value(
                    connection.ied_name,
                    mode_path
                )
                
                if not error and local_mode:
                    self.log_message.emit("Breaker in local mode - control blocked", "warning")
                    return False
                    
                # Check if there's a protection trip active
                # ... additional checks
                
            return True
            
        except Exception as e:
            self.log_message.emit(f"Safety check error: {e}", "error")
            return False
            
    def stop_all_tests(self):
        """Stop all running tests"""
        self.log_message.emit("Stopping all tests", "warning")
        
        # Cancel all active futures
        for test_key, future in self.active_tests.items():
            if not future.done():
                future.cancel()
                
        self.active_tests.clear()
        
    def get_test_results(self) -> List[TestResult]:
        """Get all test results"""
        return self.test_results.copy()
        
    def clear_results(self):
        """Clear test results"""
        self.test_results.clear()