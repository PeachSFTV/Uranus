#!/usr/bin/env python3
"""
Fix Widget Loading Issues in UI Files
"""

import os
import re

def fix_mainwindow_widget_loading():
    """Fix MainWindow_Page.py widget loading"""
    
    file_path = "code/MainWindow_Page.py"
    
    print(f"🔧 Fixing widget loading in {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        new_lines = []
        
        for i, line in enumerate(lines):
            if 'self.findChild(QPushButton,' in line and 'upload_file_button' in line:
                # Add safety check for findChild
                new_lines.append(line)
                # Add the subsequent lines but with safety checks
                for j in range(i+1, min(i+6, len(lines))):
                    next_line = lines[j]
                    if 'self.findChild(QPushButton,' in next_line:
                        new_lines.append(next_line)
                    elif '.clicked.connect(' in next_line:
                        # Add safety check before connecting signals
                        widget_name = next_line.split('.clicked.connect')[0].strip()
                        safe_line = f"        if {widget_name}:"
                        new_lines.append(safe_line)
                        new_lines.append(f"    {next_line}")
                        break
                    else:
                        new_lines.append(next_line)
                        break
            elif 'self.findChild(QPushButton,' in line:
                new_lines.append(line)
            elif '.clicked.connect(' in line and 'self.' in line:
                # Add safety check for all button connections
                widget_name = line.split('.clicked.connect')[0].strip()
                indent = len(line) - len(line.lstrip())
                safe_line = ' ' * indent + f"if {widget_name}:"
                new_lines.append(safe_line)
                new_lines.append(' ' * (indent + 4) + line.strip())
            else:
                new_lines.append(line)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        print(f"   ✅ Fixed widget safety checks")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def fix_uploadfile_widget_approach():
    """Fix UploadFile_Page.py widget loading approach"""
    
    file_path = "code/UploadFile_Page.py"
    
    print(f"🔧 Fixing widget approach in {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the problematic widget copying approach
        old_approach = """        widget = load_ui_safe(ui_file)
        if widget:
            # Copy attributes from loaded widget
            for attr_name in dir(widget):
                if not attr_name.startswith("_") and hasattr(widget, attr_name):
                    attr_value = getattr(widget, attr_name)
                    if callable(attr_value) and hasattr(attr_value, "__self__"):
                        continue  # Skip bound methods
                    setattr(self, attr_name, attr_value)"""
        
        new_approach = """        # Load UI and set layout
        widget = load_ui_safe(ui_file)
        if widget:
            # Create layout and add loaded widget
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            
            # Get specific widgets we need
            self.uploadfile_button = widget.findChild(QPushButton, 'uploadfile_button')
            self.back_button = widget.findChild(QPushButton, 'back_button')
        else:
            # Fallback: create basic widgets
            from PyQt6.QtWidgets import QVBoxLayout, QLabel
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Failed to load UI file"))
            self.uploadfile_button = None
            self.back_button = None"""
        
        content = content.replace(old_approach, new_approach)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✅ Fixed widget loading approach")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def add_import_fixes():
    """Add missing imports"""
    
    files_to_fix = [
        ("code/UploadFile_Page.py", "from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox, QVBoxLayout, QPushButton, QLabel"),
        ("code/MainWindow_Page.py", "from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton")
    ]
    
    for file_path, import_line in files_to_fix:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if import_line.split('import')[1].strip() not in content:
                lines = content.split('\n')
                
                # Find where to insert import
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.startswith('from PyQt6.QtWidgets import'):
                        # Replace existing import
                        lines[i] = import_line
                        break
                    elif line.startswith('from PyQt6') and 'import' in line:
                        insert_pos = i + 1
                
                if insert_pos == 0:
                    # Add at beginning after first import
                    for i, line in enumerate(lines):
                        if 'import' in line:
                            insert_pos = i + 1
                            break
                
                if insert_pos > 0:
                    lines.insert(insert_pos, import_line)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                
                print(f"   ✅ Updated imports in {file_path}")
            
        except Exception as e:
            print(f"   ❌ Error updating {file_path}: {e}")

def create_qt_platform_fix():
    """Create Qt platform configuration fix"""
    
    runtime_hook = "pyi_rth_qt_fix.py"
    
    content = '''#!/usr/bin/env python3
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
'''
    
    try:
        with open(runtime_hook, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Created Qt platform fix: {runtime_hook}")
        return True
    except Exception as e:
        print(f"❌ Error creating platform fix: {e}")
        return False

def main():
    """Main fix function"""
    print("🔧 Fixing Widget Loading and Qt Platform Issues")
    print("=" * 60)
    
    # Fix widget loading
    print("\n1. Fixing widget loading issues:")
    fix_mainwindow_widget_loading()
    fix_uploadfile_widget_approach()
    
    # Fix imports
    print("\n2. Adding missing imports:")
    add_import_fixes()
    
    # Create Qt platform fix
    print("\n3. Creating Qt platform fix:")
    create_qt_platform_fix()
    
    print("\n✅ All fixes applied!")
    print("📋 Next steps:")
    print("   1. Install Qt dependencies: sudo apt install -y libxcb-cursor0")
    print("   2. Rebuild: pyinstaller --clean uranus.spec")
    print("   3. Test with: DISPLAY=:0 ./dist/Uranus")

if __name__ == "__main__":
    main()