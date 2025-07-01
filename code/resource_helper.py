import sys
import os
from pathlib import Path

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_ui_path(ui_filename):
    """Get UI file path"""
    return resource_path(f"QTDesigner/{ui_filename}")

def get_icon_path(icon_filename):
    """Get icon file path"""
    return resource_path(f"icon/{icon_filename}")