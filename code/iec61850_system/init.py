# iec61850_system/__init__.py
"""
IEC 61850 System Package
========================
Core modules for IEC 61850 protocol handling
"""

# Import all existing modules with error handling for PyInstaller
try:
    from .IEC61850_DO_DA_Config import iec61850_config, StatusValue
except ImportError as e:
    print(f"Warning: Could not import IEC61850_DO_DA_Config: {e}")
    iec61850_config = None
    StatusValue = None

try:
    from .time_sync_utils import get_synchronized_timestamp_ms, get_synchronized_timestamp_us, check_time_synchronization
except ImportError as e:
    print(f"Warning: Could not import time_sync_utils: {e}")
    import time
    
    def get_synchronized_timestamp_ms():
        return int(time.time() * 1000)
    
    def get_synchronized_timestamp_us():
        return int(time.time() * 1_000_000)
    
    def check_time_synchronization():
        return False, None

try:
    from .goose_handler import GOOSEHandler
except ImportError as e:
    print(f"Warning: Could not import goose_handler: {e}")
    GOOSEHandler = None

try:
    from .ied_connection_manager import IEDConnectionManager, IEDConnection
except ImportError as e:
    print(f"Warning: Could not import ied_connection_manager: {e}")
    IEDConnectionManager = None
    IEDConnection = None

try:
    from .test_executor import TestExecutor
except ImportError as e:
    print(f"Warning: Could not import test_executor: {e}")
    TestExecutor = None

try:
    from .report_generator import ReportGenerator
except ImportError as e:
    print(f"Warning: Could not import report_generator: {e}")
    ReportGenerator = None

try:
    from .commissioning_widget import CommissioningWidget
except ImportError as e:
    print(f"Warning: Could not import commissioning_widget: {e}")
    CommissioningWidget = None

# Additional modules that might be needed
try:
    from .iedscout_view_manager import IEDScoutViewManager, IEDScoutItem
except ImportError as e:
    print(f"Warning: Could not import iedscout_view_manager: {e}")
    IEDScoutViewManager = None
    IEDScoutItem = None

try:
    from .da_value_editor_dialog import DAValueEditorDialog
except ImportError as e:
    print(f"Warning: Could not import da_value_editor_dialog: {e}")
    DAValueEditorDialog = None

try:
    from .address_editor_dialog import AddressEditorDialog
except ImportError as e:
    print(f"Warning: Could not import address_editor_dialog: {e}")
    AddressEditorDialog = None

# Export all available modules
__all__ = [
    # Core configuration
    'iec61850_config',
    'StatusValue',
    
    # Time synchronization utilities
    'get_synchronized_timestamp_ms',
    'get_synchronized_timestamp_us',
    'check_time_synchronization',
    
    # Main handlers and managers
    'GOOSEHandler',
    'IEDConnectionManager', 
    'IEDConnection',
    'TestExecutor',
    'ReportGenerator',
    'CommissioningWidget',
    
    # UI components
    'IEDScoutViewManager',
    'IEDScoutItem', 
    'DAValueEditorDialog',
    'AddressEditorDialog',
]

# Version information
__version__ = "1.0.0"
__author__ = "IEC 61850 Tools"
__description__ = "IEC 61850 System Package for Uranus Application"

# Utility function to check what's available
def get_available_modules():
    """Return dict of available modules for debugging"""
    return {
        'iec61850_config': iec61850_config is not None,
        'StatusValue': StatusValue is not None,
        'GOOSEHandler': GOOSEHandler is not None,
        'IEDConnectionManager': IEDConnectionManager is not None,
        'IEDConnection': IEDConnection is not None,
        'TestExecutor': TestExecutor is not None,
        'ReportGenerator': ReportGenerator is not None,
        'CommissioningWidget': CommissioningWidget is not None,
        'IEDScoutViewManager': IEDScoutViewManager is not None,
        'IEDScoutItem': IEDScoutItem is not None,
        'DAValueEditorDialog': DAValueEditorDialog is not None,
        'AddressEditorDialog': AddressEditorDialog is not None,
    }

# Debug function (uncomment if needed)
# def print_available_modules():
#     """Print available modules status"""
#     modules = get_available_modules()
#     print("\n=== IEC 61850 System Modules ===")
#     for name, available in modules.items():
#         status = "✅" if available else "❌"
#         print(f"  {status} {name}")
#     print("=" * 35)

# print_available_modules()  # Uncomment for debugging