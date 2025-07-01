#!/usr/bin/env python3
"""
PyInstaller Runtime Hook for Qt Platform Issues
"""

import os
import sys

def configure_qt_platform():
    """Configure Qt platform for PyInstaller"""
    
    # Set Qt platform plugin path
    if hasattr(sys, '_MEIPASS'):
        qt_plugin_path = os.path.join(sys._MEIPASS, 'PyQt6', 'Qt6', 'plugins')
        if os.path.exists(qt_plugin_path):
            os.environ['QT_PLUGIN_PATH'] = qt_plugin_path
    
    # Set platform based on available display
    if 'DISPLAY' not in os.environ:
        # No X11 display available
        if 'WAYLAND_DISPLAY' in os.environ:
            os.environ['QT_QPA_PLATFORM'] = 'wayland'
        else:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    else:
        # X11 display available
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
    
    # Enable debugging
    # os.environ['QT_DEBUG_PLUGINS'] = '1'
    
    print(f"🔧 Qt Platform: {os.environ.get('QT_QPA_PLATFORM', 'default')}")

# Execute configuration
configure_qt_platform()
