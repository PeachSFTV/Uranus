#!/usr/bin/env python3
"""
Enhanced GOOSE Raw Socket Sniffer Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alternative GOOSE capture using raw sockets with improved filtering
Enhanced version - รองรับ promiscuous mode และ IP filtering
"""

import socket
import struct
import time
from typing import Dict, List, Any, Optional, Callable
import select
import subprocess
import os
import sys
import re

# Socket constants
try:
    from socket import SOL_PACKET, PACKET_ADD_MEMBERSHIP, PACKET_MR_PROMISC
except ImportError:
    # Fallback constants for Linux
    SOL_PACKET = 263
    PACKET_ADD_MEMBERSHIP = 1
    PACKET_MR_PROMISC = 1

# Ethernet and GOOSE constants
ETH_P_ALL = 0x0003
ETH_P_GOOSE = 0x88B8
GOOSE_MULTICAST_PREFIX = b'\x01\x0c\xcd\x01'

class EnhancedGOOSERawSniffer:
    """Enhanced raw socket GOOSE sniffer with improved filtering and promiscuous mode"""
    
    def __init__(self, interface: str = "any"):
        self.interface = interface
        self.socket = None
        self.running = False
        self.callback = None
        self.promiscuous_interfaces = {}  # Track original promiscuous state
        self.packet_count = 0
        self.error_count = 0
    
    def set_callback(self, callback: Callable):
        """Set message callback"""
        self.callback = callback
    
    def _get_interface_list(self) -> List[str]:
        """Get list of network interfaces with enhanced detection"""
        interfaces = []
        
        try:
            # Method 1: Use ip command
            result = subprocess.run(['ip', '-o', 'link', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        # Format: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>"
                        parts = line.split(':')
                        if len(parts) >= 2:
                            iface = parts[1].strip()
                            if iface != 'lo' and not iface.startswith('docker'):
                                interfaces.append(iface)
                if interfaces:
                    return interfaces
        except:
            pass
        
        try:
            # Method 2: Use /sys/class/net
            net_dir = '/sys/class/net'
            if os.path.exists(net_dir):
                for iface in os.listdir(net_dir):
                    if iface != 'lo' and not iface.startswith('docker'):
                        # Check if interface is up
                        operstate_file = f'{net_dir}/{iface}/operstate'
                        if os.path.exists(operstate_file):
                            try:
                                with open(operstate_file, 'r') as f:
                                    state = f.read().strip()
                                    if state in ['up', 'unknown']:  # Include unknown state
                                        interfaces.append(iface)
                            except:
                                interfaces.append(iface)  # Add if can't read state
        except:
            pass
        
        try:
            # Method 3: Use ifconfig as fallback
            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line and not line.startswith(' ') and ':' in line:
                        iface = line.split(':')[0].strip()
                        if iface not in ['lo'] and not iface.startswith('docker'):
                            if iface not in interfaces:
                                interfaces.append(iface)
        except:
            pass
        
        return interfaces if interfaces else ['eth0', 'ens33', 'wlan0']  # Fallback list
    
    def _get_interface_index(self, interface: str) -> int:
        """Get interface index for promiscuous mode"""
        try:
            # Method 1: Use socket.if_nametoindex (most reliable)
            import socket
            return socket.if_nametoindex(interface)
        except:
            pass
        
        try:
            # Method 2: Use ioctl
            import socket
            import fcntl
            import struct
            
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # SIOCGIFINDEX = 0x8933
            ifreq = struct.pack('16sI', interface.encode('utf-8'), 0)
            res = fcntl.ioctl(s.fileno(), 0x8933, ifreq)
            s.close()
            
            return struct.unpack('16sI', res)[1]
        except:
            pass
        
        try:
            # Method 3: Read from /sys
            with open(f'/sys/class/net/{interface}/ifindex', 'r') as f:
                return int(f.read().strip())
        except:
            return 0
    
    def _check_promiscuous_mode(self, interface: str) -> bool:
        """Check if interface is in promiscuous mode"""
        try:
            # Method 1: Use ip command
            result = subprocess.run(['ip', 'link', 'show', interface], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return 'PROMISC' in result.stdout
        except:
            pass
        
        try:
            # Method 2: Read from /sys/class/net
            flags_file = f'/sys/class/net/{interface}/flags'
            if os.path.exists(flags_file):
                with open(flags_file, 'r') as f:
                    flags = int(f.read().strip(), 16)
                    # IFF_PROMISC = 0x100
                    return (flags & 0x100) != 0
        except:
            pass
        
        return False
    
    def _set_promiscuous_mode(self, interface: str, enable: bool = True) -> bool:
        """Enable/disable promiscuous mode with multiple methods"""
        try:
            # Save original state
            if interface not in self.promiscuous_interfaces:
                self.promiscuous_interfaces[interface] = self._check_promiscuous_mode(interface)
            
            # Method 1: Use ip command with sudo
            action = 'on' if enable else 'off'
            cmd = ['sudo', 'ip', 'link', 'set', interface, 'promisc', action]
            
            print(f"🔧 {'Enabling' if enable else 'Disabling'} promiscuous mode on {interface}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Verify the change
                time.sleep(0.2)  # Increased delay
                current_state = self._check_promiscuous_mode(interface)
                
                if enable and current_state:
                    print(f"✅ Promiscuous mode enabled on {interface}")
                    return True
                elif not enable and not current_state:
                    print(f"✅ Promiscuous mode disabled on {interface}")
                    return True
                else:
                    print(f"⚠️ Promiscuous mode state verification failed on {interface}")
                    return False
            else:
                print(f"⚠️ ip command failed: {result.stderr}")
                
                # Try alternative method
                return self._set_promiscuous_mode_alternative(interface, enable)
                
        except Exception as e:
            print(f"⚠️ Could not set promiscuous mode on {interface}: {e}")
            return self._set_promiscuous_mode_alternative(interface, enable)
    
    def _set_promiscuous_mode_alternative(self, interface: str, enable: bool) -> bool:
        """Alternative method using ifconfig"""
        try:
            if enable:
                cmd = ['sudo', 'ifconfig', interface, 'promisc']
            else:
                cmd = ['sudo', 'ifconfig', interface, '-promisc']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                time.sleep(0.2)
                current_state = self._check_promiscuous_mode(interface)
                
                if (enable and current_state) or (not enable and not current_state):
                    print(f"✅ Promiscuous mode {'enabled' if enable else 'disabled'} on {interface} (ifconfig)")
                    return True
            
            print(f"⚠️ ifconfig method also failed for {interface}")
            return False
            
        except:
            print(f"⚠️ Alternative promiscuous mode setting failed for {interface}")
            return False
    
    def start(self) -> bool:
        """Start enhanced capturing with promiscuous mode"""
        try:
            print("🚀 Starting Enhanced GOOSE Raw Socket Sniffer...")
            
            # Enable promiscuous mode on interfaces
            promisc_enabled = False
            
            if self.interface == "any":
                interfaces = self._get_interface_list()
                print(f"🔍 Found interfaces: {', '.join(interfaces)}")
                
                # Enable promiscuous on all interfaces
                success_count = 0
                for iface in interfaces:
                    if self._set_promiscuous_mode(iface, True):
                        success_count += 1
                
                if success_count > 0:
                    promisc_enabled = True
                    print(f"✅ Promiscuous mode enabled on {success_count}/{len(interfaces)} interfaces")
                else:
                    print("⚠️ Warning: Could not enable promiscuous mode via system commands")
            else:
                # Enable on specific interface
                if self._set_promiscuous_mode(self.interface, True):
                    promisc_enabled = True
                else:
                    print(f"⚠️ Warning: Could not enable promiscuous mode on {self.interface}")
            
            # Create raw socket with enhanced options
            try:
                self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
                print("✅ Raw socket created successfully")
            except PermissionError:
                print("❌ Permission denied creating raw socket")
                raise PermissionError("Raw socket requires root privileges")
            
            # Try socket-level promiscuous mode if system commands failed
            if not promisc_enabled:
                print("🔧 Trying socket-level promiscuous mode...")
                try:
                    self._enable_socket_promiscuous_mode()
                    promisc_enabled = True
                except Exception as e:
                    print(f"⚠️ Socket promiscuous mode failed: {e}")
            
            # Configure socket options
            try:
                # Set larger receive buffer (2MB)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
                
                # Set non-blocking mode
                self.socket.setblocking(False)
                
                # Set socket timeout
                self.socket.settimeout(0.1)
                
                print("✅ Socket options configured")
            except Exception as e:
                print(f"⚠️ Warning: Could not set socket options: {e}")
            
            # Bind to interface if specified
            try:
                if self.interface != "any":
                    self.socket.bind((self.interface, 0))
                    print(f"✅ Bound to interface: {self.interface}")
                else:
                    print("✅ Capturing on all interfaces")
            except Exception as e:
                print(f"⚠️ Warning: Could not bind to interface: {e}")
                # Continue anyway - might still work
            
            self.running = True
            self.packet_count = 0
            self.error_count = 0
            
            print("🟢 Enhanced raw socket sniffer started successfully")
            return True
            
        except PermissionError:
            print("❌ Failed to start raw socket: Permission denied")
            print("   Please run with sudo!")
            return False
        except Exception as e:
            print(f"❌ Failed to start enhanced raw socket: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _enable_socket_promiscuous_mode(self):
        """Enable promiscuous mode at socket level"""
        from socket import SOL_PACKET, PACKET_ADD_MEMBERSHIP, PACKET_MR_PROMISC
        
        if self.interface != "any":
            # For specific interface
            iface_index = self._get_interface_index(self.interface)
            if iface_index > 0:
                mreq = struct.pack("IHH8s", iface_index, PACKET_MR_PROMISC, 0, b'')
                self.socket.setsockopt(SOL_PACKET, PACKET_ADD_MEMBERSHIP, mreq)
                print(f"✅ Socket promiscuous mode enabled on {self.interface}")
        else:
            # For all interfaces
            interfaces = self._get_interface_list()
            success_count = 0
            for iface in interfaces:
                try:
                    iface_index = self._get_interface_index(iface)
                    if iface_index > 0:
                        mreq = struct.pack("IHH8s", iface_index, PACKET_MR_PROMISC, 0, b'')
                        self.socket.setsockopt(SOL_PACKET, PACKET_ADD_MEMBERSHIP, mreq)
                        success_count += 1
                except:
                    pass
            
            if success_count > 0:
                print(f"✅ Socket promiscuous mode enabled on {success_count} interfaces")
    
    def stop(self):
        """Stop capturing and restore interface settings"""
        print("🛑 Stopping enhanced raw socket sniffer...")
        self.running = False
        
        # Restore promiscuous mode to original state
        restored_count = 0
        for iface, original_state in self.promiscuous_interfaces.items():
            if not original_state:  # Was not promiscuous originally
                if self._set_promiscuous_mode(iface, False):
                    restored_count += 1
        
        if restored_count > 0:
            print(f"✅ Restored promiscuous mode on {restored_count} interfaces")
        
        self.promiscuous_interfaces.clear()
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
                print("✅ Socket closed")
            except:
                pass
            self.socket = None
        
        print(f"📊 Final stats: {self.packet_count} packets captured, {self.error_count} errors")
        print("✅ Enhanced raw socket sniffer stopped")
    
    def capture_single(self, timeout: float = 0.1) -> bool:
        """Capture single packet with enhanced error handling"""
        if not self.running or not self.socket:
            return False
            
        try:
            # Use select for timeout with multiple socket monitoring
            readable, _, exceptional = select.select([self.socket], [], [self.socket], timeout)
            
            if exceptional:
                print("⚠️ Socket exception detected")
                self.error_count += 1
                return False
            
            if readable:
                try:
                    packet, addr = self.socket.recvfrom(65536)
                    if packet:
                        self.packet_count += 1
                        self._process_packet(packet, addr)
                        return True
                except socket.timeout:
                    # Normal timeout
                    return False
                except socket.error as e:
                    if e.errno in [11, 35]:  # EAGAIN, EWOULDBLOCK
                        # Normal non-blocking behavior
                        return False
                    else:
                        print(f"⚠️ Socket error: {e}")
                        self.error_count += 1
                        return False
            
            return False  # Timeout
            
        except Exception as e:
            if self.running and "temporarily unavailable" not in str(e).lower():
                print(f"Capture error: {e}")
                self.error_count += 1
            return False
    
    def capture_loop(self):
        """Enhanced main capture loop with statistics"""
        print("🔄 Starting enhanced capture loop...")
        
        packet_count = 0
        goose_count = 0
        last_stats_time = time.time()
        last_goose_time = time.time()
        
        while self.running:
            try:
                # Capture with timeout
                if self.capture_single(0.1):
                    packet_count += 1
                    
                    # Check if it was a GOOSE packet (rough estimate)
                    if time.time() - last_goose_time < 0.1:
                        goose_count += 1
                        last_goose_time = time.time()
                
                # Print enhanced stats every 10 seconds
                current_time = time.time()
                if current_time - last_stats_time > 10:
                    if packet_count == 0:
                        print(f"⚠️ No packets captured in last 10 seconds")
                        print(f"   Check network activity and interface status")
                    else:
                        print(f"📊 Stats: {packet_count} total packets, ~{goose_count} GOOSE packets, {self.error_count} errors")
                    
                    # Reset counters
                    last_stats_time = current_time
                    packet_count = 0
                    goose_count = 0
                        
            except KeyboardInterrupt:
                print("\n🛑 Capture interrupted by user")
                break
            except Exception as e:
                if self.running:
                    print(f"Capture loop error: {e}")
                time.sleep(0.01)
        
        print("✅ Enhanced capture loop ended")
    
    def _process_packet(self, packet: bytes, addr: Any):
        """Process captured packet with enhanced validation"""
        try:
            # Basic packet validation
            if len(packet) < 14:
                return  # Too short for Ethernet header
                
            # Parse Ethernet header
            eth_header = packet[:14]
            try:
                eth_data = struct.unpack('!6s6sH', eth_header)
            except struct.error:
                return  # Invalid Ethernet header
            
            dst_mac = eth_data[0]
            src_mac = eth_data[1]
            eth_type = eth_data[2]
            
            # Check if GOOSE (0x88B8)
            if eth_type == ETH_P_GOOSE:
                # Validate GOOSE multicast MAC (01:0C:CD:01:xx:xx)
                if dst_mac[:4] == GOOSE_MULTICAST_PREFIX:
                    # Parse GOOSE with enhanced error handling
                    goose_data = self.parse_goose_enhanced(packet[14:], src_mac, dst_mac)
                    if goose_data and self.callback:
                        try:
                            self.callback(goose_data)
                        except Exception as e:
                            print(f"Callback error: {e}")
                            self.error_count += 1
                            
        except Exception as e:
            self.error_count += 1
            if self.error_count < 10:  # Limit error spam
                print(f"Packet processing error: {e}")
    
    def parse_goose_enhanced(self, data: bytes, src_mac: bytes, dst_mac: bytes) -> Optional[Dict]:
        """Enhanced GOOSE PDU parsing with better error handling and data extraction"""
        try:
            goose_info = {
                'src_mac': ':'.join(f'{b:02x}' for b in src_mac),
                'dst_mac': ':'.join(f'{b:02x}' for b in dst_mac),
                'timestamp': int(time.time() * 1000),
                'raw_data_length': len(data)
            }
            
            pos = 0
            
            # Parse APPID (first 2 bytes)
            if len(data) >= 2:
                goose_info['appId'] = struct.unpack('!H', data[0:2])[0]
                pos = 2
            else:
                goose_info['appId'] = 0
            
            # Parse Length (2 bytes)
            if len(data) >= pos + 2:
                length = struct.unpack('!H', data[pos:pos+2])[0]
                pos += 2
                goose_info['pdu_length'] = length
            
            # Skip Reserved fields (4 bytes)
            if len(data) >= pos + 4:
                reserved = data[pos:pos+4]
                pos += 4
                goose_info['reserved'] = reserved.hex()
            
            # Parse ASN.1 BER encoded GOOSE PDU
            if len(data) > pos and data[pos] == 0x61:  # GOOSE PDU tag
                pos += 1
                # Get length
                pos, pdu_length = self._parse_ber_length(data, pos)
                
                if pos + pdu_length <= len(data):
                    # Parse GOOSE PDU content
                    goose_content = self._parse_goose_pdu_enhanced(data[pos:pos+pdu_length])
                    goose_info.update(goose_content)
                else:
                    print(f"⚠️ Invalid PDU length: {pdu_length}, available: {len(data) - pos}")
            
            # Set intelligent defaults based on common patterns
            self._apply_intelligent_defaults(goose_info)
            
            # Validate parsed data
            if self._validate_goose_data(goose_info):
                return goose_info
            else:
                # Return basic info even if validation fails
                return self._create_fallback_goose_data(goose_info)
                
        except Exception as e:
            self.error_count += 1
            if self.error_count <= 5:  # Limit parsing error spam
                print(f"Enhanced GOOSE parsing error: {e}")
            
            # Return minimal valid data
            return {
                'src_mac': ':'.join(f'{b:02x}' for b in src_mac),
                'dst_mac': ':'.join(f'{b:02x}' for b in dst_mac),
                'timestamp': int(time.time() * 1000),
                'appId': 0,
                'goID': 'ParseError',
                'goCbRef': 'ParseError',
                'dataSet': 'ParseError',
                'stNum': 0,
                'sqNum': 0,
                'test': False,
                'ndsCom': False,
                'confRev': 0,
                'timeAllowedToLive': 0,
                'values': []
            }
    
    def _apply_intelligent_defaults(self, goose_info: Dict):
        """Apply intelligent defaults based on common GOOSE patterns"""
        # Generate reasonable defaults if not parsed
        if 'goID' not in goose_info or not goose_info['goID']:
            app_id = goose_info.get('appId', 0)
            goose_info['goID'] = f'GOOSE_{app_id:04X}'
        
        if 'goCbRef' not in goose_info or not goose_info['goCbRef']:
            go_id = goose_info.get('goID', 'GOOSE')
            goose_info['goCbRef'] = f'{go_id}/LLN0$GO'
        
        if 'dataSet' not in goose_info or not goose_info['dataSet']:
            go_id = goose_info.get('goID', 'GOOSE')
            goose_info['dataSet'] = f'{go_id}/LLN0$DS'
        
        # Set safe defaults for required fields
        goose_info.setdefault('stNum', 1)
        goose_info.setdefault('sqNum', 0)
        goose_info.setdefault('test', False)
        goose_info.setdefault('ndsCom', False)
        goose_info.setdefault('confRev', 1)
        goose_info.setdefault('timeAllowedToLive', 10000)
        goose_info.setdefault('values', [])
    
    def _validate_goose_data(self, goose_info: Dict) -> bool:
        """Validate parsed GOOSE data"""
        required_fields = ['src_mac', 'dst_mac', 'appId', 'goID', 'goCbRef', 'dataSet']
        
        for field in required_fields:
            if field not in goose_info:
                return False
        
        # Validate APP ID range
        app_id = goose_info.get('appId', 0)
        if not (0 <= app_id <= 0xFFFF):
            return False
        
        return True
    
    def _create_fallback_goose_data(self, partial_info: Dict) -> Dict:
        """Create fallback GOOSE data when parsing partially fails"""
        app_id = partial_info.get('appId', 0)
        
        return {
            'src_mac': partial_info.get('src_mac', '00:00:00:00:00:00'),
            'dst_mac': partial_info.get('dst_mac', '01:0C:CD:01:00:00'),
            'timestamp': partial_info.get('timestamp', int(time.time() * 1000)),
            'appId': app_id,
            'goID': f'Fallback_{app_id:04X}',
            'goCbRef': f'Fallback_{app_id:04X}/LLN0$GO',
            'dataSet': f'Fallback_{app_id:04X}/LLN0$DS',
            'stNum': 1,
            'sqNum': 0,
            'test': False,
            'ndsCom': False,
            'confRev': 1,
            'timeAllowedToLive': 10000,
            'values': []
        }
    
    def _parse_ber_length(self, data: bytes, pos: int) -> tuple:
        """Parse BER length encoding with bounds checking"""
        if pos >= len(data):
            return pos, 0
            
        first_byte = data[pos]
        pos += 1
        
        if first_byte & 0x80 == 0:
            # Short form
            return pos, first_byte
        else:
            # Long form
            num_octets = first_byte & 0x7F
            if num_octets == 0:
                # Indefinite length - not supported
                return pos, 0
            
            if pos + num_octets > len(data):
                return pos, 0
            
            length = 0
            for i in range(num_octets):
                length = (length << 8) | data[pos + i]
            
            return pos + num_octets, length
    
    def _parse_goose_pdu_enhanced(self, data: bytes) -> Dict:
        """Enhanced GOOSE PDU content parsing with better error handling"""
        result = {}
        pos = 0
        
        try:
            while pos < len(data) - 1:
                if pos >= len(data):
                    break
                    
                tag = data[pos]
                pos += 1
                
                if pos >= len(data):
                    break
                    
                pos, length = self._parse_ber_length(data, pos)
                
                if pos + length > len(data):
                    break
                
                # Parse based on context-specific tags
                try:
                    if tag == 0x80:  # gocbRef [0]
                        result['goCbRef'] = data[pos:pos+length].decode('utf-8', errors='replace')
                    elif tag == 0x81:  # timeAllowedtoLive [1]
                        if length <= 8:
                            result['timeAllowedToLive'] = int.from_bytes(data[pos:pos+length], 'big')
                    elif tag == 0x82:  # datSet [2]
                        result['dataSet'] = data[pos:pos+length].decode('utf-8', errors='replace')
                    elif tag == 0x83:  # goID [3]
                        result['goID'] = data[pos:pos+length].decode('utf-8', errors='replace')
                    elif tag == 0x84:  # t [4] - timestamp
                        result['timestamp'] = self._parse_timestamp_enhanced(data[pos:pos+length])
                    elif tag == 0x85:  # stNum [5]
                        if length <= 8:
                            result['stNum'] = int.from_bytes(data[pos:pos+length], 'big')
                    elif tag == 0x86:  # sqNum [6]
                        if length <= 8:
                            result['sqNum'] = int.from_bytes(data[pos:pos+length], 'big')
                    elif tag == 0x87:  # test [7]
                        result['test'] = length > 0 and data[pos] != 0
                    elif tag == 0x88:  # confRev [8]
                        if length <= 8:
                            result['confRev'] = int.from_bytes(data[pos:pos+length], 'big')
                    elif tag == 0x89:  # ndsCom [9]
                        result['ndsCom'] = length > 0 and data[pos] != 0
                    elif tag == 0x8A:  # numDatSetEntries [10]
                        if length <= 8:
                            result['numDatSetEntries'] = int.from_bytes(data[pos:pos+length], 'big')
                    elif tag == 0xAB:  # allData [11] - sequence of data values
                        result['values'] = self._parse_all_data_enhanced(data[pos:pos+length])
                except Exception as e:
                    # Skip problematic fields but continue parsing
                    pass
                
                pos += length
                
        except Exception as e:
            # Return what we managed to parse
            pass
        
        return result
    
    def _parse_timestamp_enhanced(self, data: bytes) -> int:
        """Enhanced timestamp parsing with multiple format support"""
        try:
            if len(data) >= 8:
                # Standard IEC 61850 timestamp
                seconds = int.from_bytes(data[0:4], 'big')
                fraction = int.from_bytes(data[4:7], 'big') if len(data) >= 7 else 0
                # Quality byte at data[7] if available
                
                # Convert to milliseconds
                ms = seconds * 1000 + (fraction * 1000 // 16777216)
                return ms
            elif len(data) >= 4:
                # Simple seconds timestamp
                seconds = int.from_bytes(data[0:4], 'big')
                return seconds * 1000
        except:
            pass
        
        # Fallback to current time
        return int(time.time() * 1000)
    
    def _parse_all_data_enhanced(self, data: bytes) -> List[Any]:
        """Enhanced data values parsing with comprehensive type support"""
        values = []
        pos = 0
        
        try:
            while pos < len(data) - 1:
                if pos >= len(data):
                    break
                    
                tag = data[pos]
                pos += 1
                
                if pos >= len(data):
                    break
                    
                pos, length = self._parse_ber_length(data, pos)
                
                if pos + length > len(data):
                    break
                
                try:
                    # Parse based on MMS data type tags
                    if tag == 0x83:  # boolean [3]
                        values.append(length > 0 and data[pos] != 0)
                    elif tag == 0x84:  # bit-string [4]
                        if length > 1:
                            unused_bits = data[pos]
                            bit_string = data[pos+1:pos+length]
                            # Convert to integer for easier handling
                            bit_value = int.from_bytes(bit_string, 'big')
                            values.append(f"0x{bit_value:0{(length-1)*2}X}")
                        else:
                            values.append("0x00")
                    elif tag == 0x85:  # integer [5]
                        if length <= 8:
                            values.append(int.from_bytes(data[pos:pos+length], 'big', signed=True))
                        else:
                            values.append(f"BigInt:{data[pos:pos+length].hex()}")
                    elif tag == 0x86:  # unsigned [6]
                        if length <= 8:
                            values.append(int.from_bytes(data[pos:pos+length], 'big'))
                        else:
                            values.append(f"BigUInt:{data[pos:pos+length].hex()}")
                    elif tag == 0x87:  # floating-point [7]
                        if length == 4:
                            values.append(struct.unpack('!f', data[pos:pos+length])[0])
                        elif length == 8:
                            values.append(struct.unpack('!d', data[pos:pos+length])[0])
                        else:
                            # Custom floating point format
                            values.append(f"Float:{data[pos:pos+length].hex()}")
                    elif tag == 0x89:  # octet-string [9]
                        values.append(f"0x{data[pos:pos+length].hex()}")
                    elif tag == 0x8A:  # visible-string [10]
                        values.append(data[pos:pos+length].decode('utf-8', errors='replace'))
                    elif tag == 0x8C:  # binary-time [12]
                        if length == 4:
                            timestamp = int.from_bytes(data[pos:pos+length], 'big')
                            values.append(f"BinTime:{timestamp}")
                        elif length == 6:
                            days = int.from_bytes(data[pos:pos+2], 'big')
                            ms = int.from_bytes(data[pos+2:pos+6], 'big')
                            values.append(f"BinTime:{days}d_{ms}ms")
                        else:
                            values.append(f"BinTime:{data[pos:pos+length].hex()}")
                    elif tag == 0x91:  # utc-time [17]
                        timestamp = self._parse_timestamp_enhanced(data[pos:pos+length])
                        values.append(timestamp)
                    else:
                        # Unknown type - store as hex with type info
                        values.append(f"Type{tag:02X}:{data[pos:pos+length].hex()}")
                        
                except Exception as e:
                    # Add error marker but continue
                    values.append(f"ParseError:{data[pos:pos+length].hex()}")
                
                pos += length
                
        except Exception as e:
            # Return what we managed to parse
            pass
        
        return values
    
    @staticmethod
    def mac_to_string(mac_bytes: bytes) -> str:
        """Convert MAC bytes to string"""
        return ':'.join(f'{b:02x}' for b in mac_bytes)

# Backward compatibility alias
GOOSERawSniffer = EnhancedGOOSERawSniffer

# ==================== Testing and Demo ====================

def test_enhanced_sniffer():
    """Test the enhanced sniffer"""
    print("🧪 Testing Enhanced GOOSE Raw Sniffer")
    
    def test_callback(goose_data):
        print(f"📦 GOOSE: {goose_data['goID']} | APP ID: 0x{goose_data['appId']:04X} | "
              f"ST: {goose_data['stNum']} | SQ: {goose_data['sqNum']} | "
              f"Values: {len(goose_data['values'])}")
    
    sniffer = EnhancedGOOSERawSniffer("any")
    sniffer.set_callback(test_callback)
    
    if sniffer.start():
        try:
            print("🔄 Capturing for 30 seconds... Press Ctrl+C to stop")
            start_time = time.time()
            while time.time() - start_time < 30:
                sniffer.capture_single(0.1)
                time.sleep(0.001)
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user")
        finally:
            sniffer.stop()
    else:
        print("❌ Failed to start sniffer")

if __name__ == "__main__":
    test_enhanced_sniffer()