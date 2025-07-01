from Uranus.code.iec61850_system.time_sync_utils import check_time_synchronization, get_synchronized_timestamp_ms

# ตรวจสอบ sync status
is_synced, accuracy_us = check_time_synchronization()
print(f"Synchronized: {is_synced}")
print(f"Accuracy: {accuracy_us:.1f} µs")

# ดึง timestamp
ts = get_synchronized_timestamp_ms()
print(f"Timestamp: {ts}")