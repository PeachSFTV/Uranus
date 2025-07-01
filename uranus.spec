# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Get current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

# Data files - ใช้ relative path
datas = [
    ('QTDesigner', 'QTDesigner'),
    ('upload_file', 'upload_file'), 
    ('icon', 'icon'),
    ('code/iec61850_system', 'iec61850_system'),  # เพิ่ม iec61850_system
]

# Hidden imports - รวม modules ทั้งหมดที่ใช้
hiddenimports = [
    # PyQt6
    'PyQt6.QtCore',
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets',
    'PyQt6.uic',
    'pyiec61850',
    'PyQt6.uic.load_ui',
    'PyQt6.uic.uiparser',
    
    # Standard libraries
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
    
    # Network
    'netifaces',
    
    # Project modules
    'resource_helper',
    
    # IEC61850 system modules
    'iec61850_system',
    'iec61850_system.address_editor_dialog',
    'iec61850_system.da_value_editor_dialog', 
    'iec61850_system.iedscout_view_manager',
    'iec61850_system.IEC61850_DO_DA_Config',
    'iec61850_system.ied_connection_manager',
    'iec61850_system.time_sync_utils',
    
    # Optional modules
    'pyiec61850',
    'scl_parser',
    'pyiec61850_wrapper',
]

# Analysis
a = Analysis(
    ['code/MainWindow_Page.py'],  # Entry point
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # ไม่ใช้ tkinter
        'matplotlib',  # ลดขนาดไฟล์
        'pandas',
        'numpy',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Uranus',
    debug=True,  # เปิด debug mode
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # ปิด UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # เปลี่ยนเป็น True เพื่อ debug
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon/UranusIcon.ico',
)