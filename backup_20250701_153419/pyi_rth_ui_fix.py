# PyInstaller runtime hook for UI file path fixes
# This hook ensures UI files can be found in the executable

import os
import sys

def fix_ui_paths():
    """Fix UI file paths for PyInstaller executable"""
    
    # Get the directory where the executable is running
    if hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle
        base_path = sys._MEIPASS
        print(f"PyInstaller mode: base_path = {base_path}")
    else:
        # Running in development
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(f"Development mode: base_path = {base_path}")
    
    # Set environment variables for UI paths
    os.environ['UI_BASE_PATH'] = base_path
    os.environ['QTDESIGNER_PATH'] = os.path.join(base_path, 'QTDesigner')
    os.environ['ICON_PATH'] = os.path.join(base_path, 'icon')
    os.environ['UPLOAD_PATH'] = os.path.join(base_path, 'upload_file')
    
    # Add paths to sys.path for module imports
    code_path = os.path.join(base_path, 'code')
    if code_path not in sys.path:
        sys.path.insert(0, code_path)
    
    iec_path = os.path.join(base_path, 'iec61850_system')
    if iec_path not in sys.path:
        sys.path.insert(0, iec_path)
    
    # Print debug info
    print("UI Paths configured:")
    print(f"  QTDesigner: {os.environ.get('QTDESIGNER_PATH')}")
    print(f"  Icons: {os.environ.get('ICON_PATH')}")
    print(f"  Upload: {os.environ.get('UPLOAD_PATH')}")
    
    # Check if UI files exist
    ui_dir = os.environ.get('QTDESIGNER_PATH')
    if ui_dir and os.path.exists(ui_dir):
        ui_files = [f for f in os.listdir(ui_dir) if f.endswith('.ui')]
        print(f"  Found UI files: {ui_files}")
    else:
        print(f"  WARNING: QTDesigner directory not found at {ui_dir}")

# Apply the fix
fix_ui_paths()