#!/usr/bin/env python3
"""
Time Synchronization Utilities for IEC 61850
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-precision time functions with GPS synchronization monitoring
"""

import time
import subprocess
import re
from typing import Tuple, Optional
from datetime import datetime

class TimeSyncManager:
    """Manage time synchronization for IEC 61850"""
    
    def __init__(self):
        self.is_synchronized = False
        self.sync_accuracy_us = None
        self.last_check_time = 0
        self.check_interval = 60  # Check every 60 seconds
        
    def check_time_sync(self) -> Tuple[bool, Optional[float]]:
        """Check if system time is synchronized
        
        Returns:
            (is_synchronized, accuracy_in_microseconds)
        """
        try:
            # Run chronyc tracking
            result = subprocess.run(
                ['chronyc', 'tracking'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False, None
            
            output = result.stdout
            
            # Parse synchronization status
            is_synced = False
            accuracy_us = None
            
            # Check if synchronized
            if "Leap status     : Normal" in output:
                is_synced = True
                
                # Extract system time offset
                offset_match = re.search(
                    r'System time\s*:\s*([\d.]+)\s*seconds\s*(slow|fast)',
                    output
                )
                if offset_match:
                    offset_seconds = float(offset_match.group(1))
                    accuracy_us = offset_seconds * 1_000_000  # Convert to microseconds
                
                # Also check RMS offset
                rms_match = re.search(
                    r'RMS offset\s*:\s*([\d.]+)\s*seconds',
                    output
                )
                if rms_match:
                    rms_seconds = float(rms_match.group(1))
                    rms_us = rms_seconds * 1_000_000
                    
                    # Use the better accuracy
                    if accuracy_us is None or rms_us < accuracy_us:
                        accuracy_us = rms_us
            
            return is_synced, accuracy_us
            
        except Exception as e:
            print(f"⚠️ Error checking time sync: {e}")
            return False, None
    
    def get_precise_timestamp_ms(self) -> int:
        """Get high-precision timestamp in milliseconds
        
        Returns:
            Timestamp in milliseconds since epoch
        """
        # Check synchronization periodically
        current_time = time.time()
        if current_time - self.last_check_time > self.check_interval:
            self.is_synchronized, self.sync_accuracy_us = self.check_time_sync()
            self.last_check_time = current_time
            
            if self.is_synchronized:
                if self.sync_accuracy_us and self.sync_accuracy_us < 1000:
                    print(f"✅ Time synchronized: accuracy {self.sync_accuracy_us:.1f} µs")
                else:
                    print(f"✅ Time synchronized: accuracy {self.sync_accuracy_us:.1f} µs")
            else:
                print("⚠️ WARNING: System time not synchronized with GPS/NTP!")
        
        # Use high-precision time
        # time.time_ns() provides nanosecond precision (Python 3.7+)
        timestamp_ns = time.time_ns()
        timestamp_ms = timestamp_ns // 1_000_000
        
        return timestamp_ms
    
    def get_precise_timestamp_us(self) -> int:
        """Get high-precision timestamp in microseconds
        
        Returns:
            Timestamp in microseconds since epoch
        """
        timestamp_ns = time.time_ns()
        timestamp_us = timestamp_ns // 1_000
        
        return timestamp_us
    
    def get_utc_time_quality(self) -> Tuple[int, int]:
        """Get UTC timestamp and quality indicator
        
        Returns:
            (timestamp_ms, quality)
            quality: 0=Good, 0x40=Clock not synchronized, 0x80=Clock failure
        """
        timestamp_ms = self.get_precise_timestamp_ms()
        
        # Determine quality based on synchronization
        if not self.is_synchronized:
            quality = 0x40  # Clock not synchronized
        elif self.sync_accuracy_us and self.sync_accuracy_us > 10_000:  # > 10ms
            quality = 0x20  # Clock accuracy outside spec
        else:
            quality = 0x00  # Good quality
        
        return timestamp_ms, quality
    
    def format_timestamp_iso(self, timestamp_ms: int) -> str:
        """Format timestamp as ISO 8601 string with microseconds"""
        timestamp_s = timestamp_ms / 1000.0
        dt = datetime.fromtimestamp(timestamp_s)
        
        # Include microseconds
        microseconds = int((timestamp_ms % 1000) * 1000)
        return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{microseconds:06d}Z")

# Global instance
time_sync_manager = TimeSyncManager()

# Convenience functions
def get_synchronized_timestamp_ms() -> int:
    """Get synchronized timestamp in milliseconds"""
    return time_sync_manager.get_precise_timestamp_ms()

def get_synchronized_timestamp_us() -> int:
    """Get synchronized timestamp in microseconds"""
    return time_sync_manager.get_precise_timestamp_us()

def get_utc_time_with_quality() -> Tuple[int, int]:
    """Get UTC time with quality indicator"""
    return time_sync_manager.get_utc_time_quality()

def check_time_synchronization() -> Tuple[bool, Optional[float]]:
    """Check if time is synchronized"""
    return time_sync_manager.check_time_sync()