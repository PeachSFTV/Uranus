#!/usr/bin/env python3
"""
Quick patch script สำหรับแก้ไข UI loading ใน MainWindow_Page.py และ UploadFile_Page.py
"""

import os
import re
import shutil

def patch_file(file_path):
    """Patch a single Python file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"🔧 Patching {file_path}...")
    
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Add ui_helper import (after PyQt6 imports)
    if 'from ui_helper import' not in content:
        # Find PyQt6 imports
        pyqt_import_pattern = r'(from PyQt6[^\n]*\n)'
        pyqt_imports = re.findall(pyqt_import_pattern, content)
        
        if pyqt_imports:
            # Add after last PyQt6 import
            last_import = pyqt_imports[-1]
            insert_pos = content.rfind(last_import) + len(last_import)
            
            ui_import = "from ui_helper import load_ui_safe, UIHelper\n"
            content = content[:insert_pos] + ui_import + content[insert_pos:]
            print(f"   ✅ Added ui_helper import")
    
    # 2. Replace uic.loadUi calls
    replacements = [
        # Replace: uic.loadUi("file.ui", self)
        (r'uic\.loadUi\("([^"]+\.ui)",\s*([^)]+)\)', r'load_ui_safe("\1", \2)'),
        
        # Replace: uic.loadUi('file.ui', self)  
        (r"uic\.loadUi\('([^']+\.ui)',\s*([^)]+)\)", r"load_ui_safe('\1', \2)"),
        
        # Replace: uic.loadUi(f"QTDesigner/{file}.ui", self)
        (r'uic\.loadUi\(f"QTDesigner/([^"]+\.ui)",\s*([^)]+)\)', r'load_ui_safe(f"\1", \2)'),
        
        # Replace: uic.loadUi("QTDesigner/file.ui", self)
        (r'uic\.loadUi\("QTDesigner/([^"]+\.ui)",\s*([^)]+)\)', r'load_ui_safe("\1", \2)'),
    ]
    
    total_replacements = 0
    for pattern, replacement in replacements:
        new_content, count = re.subn(pattern, replacement, content)
        if count > 0:
            content = new_content
            total_replacements += count
            print(f"   ✅ Replaced {count} uic.loadUi calls")
    
    # 3. Handle specific UI file references
    ui_mappings = {
        'MainWindowUi.ui': 'MainWindowUi.ui',
        'UploadFileUi.ui': 'UploadFileUi.ui',
        'LoginUi.ui': 'LoginUi.ui',
        'Sim_Page_test.ui': 'Sim_Page_test.ui',
        'Sniffer_Page.ui': 'Sniffer_Page.ui',
        'Publisher_Page.ui': 'Publisher_Page.ui',
        'Real_ied.ui': 'Real_ied.ui',
        'EasyEditer_Page.ui': 'EasyEditer_Page.ui',
        'File_list_Page.ui': 'File_list_Page.ui',
    }
    
    # Replace hardcoded paths
    for ui_file in ui_mappings.keys():
        # Replace "QTDesigner/file.ui" with just "file.ui" since load_ui_safe handles the path
        old_pattern = f'"QTDesigner/{ui_file}"'
        new_pattern = f'"{ui_file}"'
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)
            print(f"   ✅ Fixed path for {ui_file}")
    
    # 4. Add error handling for UI loading functions
    if 'def load_main_ui(' in content:
        content = re.sub(
            r'def load_main_ui\(self\):',
            '''def load_main_ui(self):
        """Load main UI with error handling"""
        try:''',
            content
        )
        print(f"   ✅ Added error handling to load_main_ui")
    
    if 'def load_uploadfile_ui(' in content:
        content = re.sub(
            r'def load_uploadfile_ui\(self\):',
            '''def load_uploadfile_ui(self):
        """Load upload file UI with error handling"""
        try:''',
            content
        )
        print(f"   ✅ Added error handling to load_uploadfile_ui")
    
    # Save if changed
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ Saved patched file: {file_path}")
        return True
    else:
        print(f"   ℹ️  No changes needed: {file_path}")
        return False

def main():
    """Main patching function"""
    print("🚀 Quick UI Patch Script")
    print("=" * 30)
    
    # Files to patch
    files_to_patch = [
        'code/MainWindow_Page.py',
        'code/UploadFile_Page.py'
    ]
    
    # Check if we're in the right directory
    if not os.path.exists('code'):
        print("❌ Please run from Uranus project root directory")
        return False
    
    # Check if ui_helper exists
    if not os.path.exists('code/ui_helper.py'):
        print("❌ code/ui_helper.py not found!")
        print("   Please create it first with the ui_helper.py content")
        return False
    
    patched_count = 0
    
    # Patch each file
    for file_path in files_to_patch:
        if os.path.exists(file_path):
            # Create backup
            backup_path = f"{file_path}.backup"
            if not os.path.exists(backup_path):
                shutil.copy2(file_path, backup_path)
                print(f"📁 Backup created: {backup_path}")
            
            # Patch file
            if patch_file(file_path):
                patched_count += 1
        else:
            print(f"⚠️  File not found: {file_path}")
    
    print(f"\n📋 Summary:")
    print(f"   Files patched: {patched_count}")
    print(f"   Next steps:")
    print(f"   1. Test: python code/MainWindow_Page.py")
    print(f"   2. Update uranus.spec")
    print(f"   3. Rebuild: pyinstaller uranus.spec")
    
    return patched_count > 0

if __name__ == "__main__":
    main()