# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Uranus IEC 61850 Application
Supports both Linux and Windows builds
"""

import os
import sys
import platform
from pathlib import Path

block_cipher = None

# Get current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))
print(f"Build directory: {current_dir}")

# Detect platform
is_windows = platform.system() == 'Windows'
is_linux = platform.system() == 'Linux'

# Find pyiec61850 installation
def find_pyiec61850():
    """Auto-detect pyiec61850 installation"""
    pyiec_paths = []
    pyiec_files = []
    
    try:
        import pyiec61850
        if hasattr(pyiec61850, '__file__'):
            # Standard installation
            pyiec_dir = os.path.dirname(pyiec61850.__file__)
            pyiec_paths.append(pyiec_dir)
            print(f"Found pyiec61850 at: {pyiec_dir}")
            
            # Find related files
            if is_windows:
                extensions = ['*.pyd', '*.dll', '*.py']
            else:
                extensions = ['*.so', '*.py']
                
            for ext in extensions:
                import glob
                files = glob.glob(os.path.join(pyiec_dir, ext))
                pyiec_files.extend(files)
        else:
            print("pyiec61850 is built-in module")
            
    except ImportError:
        print("WARNING: pyiec61850 not found!")
        # Try to find in common locations
        import site
        for site_dir in site.getsitepackages():
            pyiec_file = os.path.join(site_dir, 'pyiec61850')
            if os.path.exists(pyiec_file):
                pyiec_paths.append(pyiec_file)
                # Find files in pyiec61850 directory
                if is_windows:
                    extensions = ['*.pyd', '*.dll', '*.py']
                else:
                    extensions = ['*.so', '*.py']
                    
                for ext in extensions:
                    import glob
                    files = glob.glob(os.path.join(pyiec_file, ext))
                    pyiec_files.extend(files)
                break
    
    return pyiec_paths, pyiec_files

# Get pyiec61850 info
pyiec_paths, pyiec_files = find_pyiec61850()

# Data files - Include project assets
# Data files - Include project assets
datas = [
    ('code/QTDesigner', 'QTDesigner'),
    ('code/upload_file', 'upload_file'),
    ('code/icon', 'icon'),
    ('code/iec61850_system', 'iec61850_system'),
]

# Add pyiec61850 Python files
for pyfile in pyiec_files:
    if pyfile.endswith('.py'):
        datas.append((pyfile, '.'))

# Binaries - Include shared libraries
binaries = []
for pyfile in pyiec_files:
    if pyfile.endswith(('.so', '.pyd', '.dll')):
        binaries.append((pyfile, '.'))

# Hidden imports - Comprehensive list
hiddenimports = [
    # PyQt6 Core
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.uic',
    'PyQt6.uic.load_ui',
    'PyQt6.uic.uiparser',
    'PyQt6.QtNetwork',
    'PyQt6.QtOpenGL',
    
    # Standard Library
    'json',
    'csv',
    'threading',
    'subprocess',
    'socket',
    'struct',
    'time',
    'datetime',
    'pathlib',
    'os',
    'sys',
    're',
    'typing',
    'logging',
    'argparse',
    'configparser',
    'xml.etree.ElementTree',
    
    # Scientific Computing
    'numpy',
    'pandas',
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_qt5agg',
    
    # Network
    'netifaces',
    'scapy',
    'scapy.all',
    
    # Project Modules
    'resource_helper',
    
    # IEC61850 System Modules
    'iec61850_system',
    'iec61850_system.address_editor_dialog',
    'iec61850_system.da_value_editor_dialog',
    'iec61850_system.iedscout_view_manager',
    'iec61850_system.IEC61850_DO_DA_Config',
    'iec61850_system.ied_connection_manager',
    'iec61850_system.time_sync_utils',
    
    # pyiec61850 Modules
    'iec61850',
    '_iec61850',
    'pyiec61850',
]

# Exclude unnecessary modules to reduce size
excludes = [
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'unittest',
    'test',
    'distutils',
    'setuptools',
    'pip',
    'scipy',  # Large scientific library
    'IPython',
    'jupyter',
    'notebook',
    'sympy',
]

# Analysis configuration
a = Analysis(
    ['code/MainWindow_Page.py'],  # Entry point
    pathex=[current_dir] + pyiec_paths,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_ui_fix.py'] if os.path.exists('pyi_rth_ui_fix.py') else [],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicates and optimize
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Platform-specific executable configuration
if is_windows:
    # Windows configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='Uranus',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,  # Enable compression
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # GUI mode
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='code/icon/UranusIcon.ico' if os.path.exists('code/icon/UranusIcon.ico') else None,
        version='version_info.txt' if os.path.exists('version_info.txt') else None,
        uac_admin=True,  # Request admin privileges for network access
        manifest='uranus.manifest' if os.path.exists('uranus.manifest') else None,
    )
else:
    # Linux configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='Uranus',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,  # Enable compression
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # GUI mode
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

print(f"Build configuration complete for {platform.system()}")
print(f"Entry point: code/MainWindow_Page.py")
print(f"Output: dist/Uranus{'exe' if is_windows else ''}")
print(f"pyiec61850 paths: {pyiec_paths}")
print(f"pyiec61850 files: {len(pyiec_files)}")