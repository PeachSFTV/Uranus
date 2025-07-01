#!/usr/bin/env python3
"""
Fix UI Loading Issues - Convert uic.loadUi to load_ui_safe
"""

import os
import re
from pathlib import Path

def analyze_file(file_path):
    """Analyze Python file for UI loading patterns"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        lines = content.split('\n')
        
        print(f"\n🔍 Analyzing {file_path}:")
        
        # Check imports
        has_ui_helper = False
        has_uic_import = False
        
        # Find problematic lines
        uic_loadui_lines = []
        
        for i, line in enumerate(lines, 1):
            if 'from ui_helper import' in line:
                has_ui_helper = True
                print(f"   ✅ Line {i}: ui_helper import found")
                
            if 'from PyQt6 import uic' in line or 'import uic' in line:
                has_uic_import = True
                print(f"   📦 Line {i}: uic import found")
                
            if 'uic.loadUi' in line:
                uic_loadui_lines.append((i, line.strip()))
                print(f"   🎯 Line {i}: {line.strip()}")
        
        return content, lines, uic_loadui_lines, has_ui_helper, has_uic_import
        
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return None, None, [], False, False

def fix_mainwindow_page():
    """Fix MainWindow_Page.py"""
    file_path = "code/MainWindow_Page.py"
    
    print(f"🔧 Fixing {file_path}")
    
    content, lines, uic_lines, has_ui_helper, has_uic_import = analyze_file(file_path)
    
    if not content:
        return False
        
    # Make fixes
    new_lines = []
    modified = False
    
    for i, line in enumerate(lines):
        # Fix the specific uic.loadUi line (around line 72)
        if 'widget = uic.loadUi(ui_file)' in line:
            # Replace with load_ui_safe
            indent = len(line) - len(line.lstrip())
            new_line = ' ' * indent + 'widget = load_ui_safe(ui_file)'
            new_lines.append(new_line)
            modified = True
            print(f"   ✅ Fixed line {i+1}: {line.strip()} → {new_line.strip()}")
        else:
            new_lines.append(line)
    
    if modified:
        # Write back
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            print(f"   💾 Saved changes to {file_path}")
            return True
        except Exception as e:
            print(f"   ❌ Error saving {file_path}: {e}")
            return False
    else:
        print(f"   ℹ️  No changes needed in {file_path}")
        return True

def fix_uploadfile_page():
    """Fix UploadFile_Page.py"""
    file_path = "code/UploadFile_Page.py"
    
    print(f"🔧 Fixing {file_path}")
    
    content, lines, uic_lines, has_ui_helper, has_uic_import = analyze_file(file_path)
    
    if not content:
        return False
        
    # Make fixes
    new_lines = []
    modified = False
    
    for i, line in enumerate(lines):
        # Fix the specific uic.loadUi line (around line 24)
        if 'uic.loadUi(ui_file, self)' in line:
            # Replace with load_ui_safe approach
            indent = len(line) - len(line.lstrip())
            # For this case, we need to replace the widget loading approach
            new_line = ' ' * indent + 'widget = load_ui_safe(ui_file)'
            new_lines.append(new_line)
            # Add the widget assignment
            new_lines.append(' ' * indent + 'if widget:')
            new_lines.append(' ' * indent + '    # Copy attributes from loaded widget')
            new_lines.append(' ' * indent + '    for attr_name in dir(widget):')
            new_lines.append(' ' * indent + '        if not attr_name.startswith("_") and hasattr(widget, attr_name):')
            new_lines.append(' ' * indent + '            attr_value = getattr(widget, attr_name)')
            new_lines.append(' ' * indent + '            if callable(attr_value) and hasattr(attr_value, "__self__"):')
            new_lines.append(' ' * indent + '                continue  # Skip bound methods')
            new_lines.append(' ' * indent + '            setattr(self, attr_name, attr_value)')
            modified = True
            print(f"   ✅ Fixed line {i+1}: {line.strip()} → widget loading approach")
        else:
            new_lines.append(line)
    
    if modified:
        # Write back
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            print(f"   💾 Saved changes to {file_path}")
            return True
        except Exception as e:
            print(f"   ❌ Error saving {file_path}: {e}")
            return False
    else:
        print(f"   ℹ️  No changes needed in {file_path}")
        return True

def fix_other_pages():
    """Fix other page files that might have similar issues"""
    
    files_to_check = [
        "code/Login_Page.py",
        "code/Publisher_Page.py", 
        "code/Sniffer_Page.py",
        "code/EasyEditer_Page.py"
    ]
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"⏭️  Skipping {file_path} (not found)")
            continue
            
        print(f"\n🔧 Checking {file_path}")
        
        content, lines, uic_lines, has_ui_helper, has_uic_import = analyze_file(file_path)
        
        if not content:
            continue
            
        if not uic_lines:
            print(f"   ✅ No uic.loadUi found in {file_path}")
            continue
            
        # Apply generic fixes
        new_lines = []
        modified = False
        
        for i, line in enumerate(lines):
            # Generic uic.loadUi replacement
            if 'uic.loadUi(' in line and 'self)' in line:
                # Pattern: uic.loadUi(ui_file, self)
                indent = len(line) - len(line.lstrip())
                
                # Extract ui_file variable
                ui_file_match = re.search(r'uic\.loadUi\(([^,]+),', line)
                if ui_file_match:
                    ui_file_var = ui_file_match.group(1).strip()
                    
                    new_line = f"{' ' * indent}widget = load_ui_safe({ui_file_var})"
                    new_lines.append(new_line)
                    new_lines.append(f"{' ' * indent}if widget:")
                    new_lines.append(f"{' ' * indent}    # Copy widget attributes")
                    new_lines.append(f"{' ' * indent}    for attr in dir(widget):")
                    new_lines.append(f"{' ' * indent}        if not attr.startswith('_'):")
                    new_lines.append(f"{' ' * indent}            try:")
                    new_lines.append(f"{' ' * indent}                setattr(self, attr, getattr(widget, attr))")
                    new_lines.append(f"{' ' * indent}            except:")
                    new_lines.append(f"{' ' * indent}                pass")
                    
                    modified = True
                    print(f"   ✅ Fixed line {i+1}: uic.loadUi → load_ui_safe")
                else:
                    new_lines.append(line)
                    
            elif 'uic.loadUi(' in line and not 'self)' in line:
                # Pattern: widget = uic.loadUi(ui_file)
                indent = len(line) - len(line.lstrip())
                new_line = line.replace('uic.loadUi(', 'load_ui_safe(')
                new_lines.append(new_line)
                modified = True
                print(f"   ✅ Fixed line {i+1}: uic.loadUi → load_ui_safe")
            else:
                new_lines.append(line)
        
        if modified:
            # Write back
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                print(f"   💾 Saved changes to {file_path}")
            except Exception as e:
                print(f"   ❌ Error saving {file_path}: {e}")

def verify_fixes():
    """Verify that all fixes were applied correctly"""
    
    files_to_check = [
        "code/MainWindow_Page.py",
        "code/UploadFile_Page.py",
        "code/Login_Page.py",
        "code/Publisher_Page.py",
        "code/Sniffer_Page.py",
        "code/EasyEditer_Page.py"
    ]
    
    print(f"\n🧪 Verification:")
    print("=" * 50)
    
    all_good = True
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            has_ui_helper = 'from ui_helper import' in content
            has_load_ui_safe = 'load_ui_safe(' in content
            has_old_uic = 'uic.loadUi(' in content
            
            print(f"📄 {file_path}:")
            print(f"   ui_helper import: {'✅' if has_ui_helper else '❌'}")
            print(f"   load_ui_safe usage: {'✅' if has_load_ui_safe else '❌'}")
            print(f"   Old uic.loadUi: {'❌ STILL EXISTS' if has_old_uic else '✅ REMOVED'}")
            
            if has_old_uic:
                all_good = False
                # Show remaining instances
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'uic.loadUi(' in line:
                        print(f"      ⚠️  Line {i}: {line.strip()}")
                        
        except Exception as e:
            print(f"❌ Error checking {file_path}: {e}")
            all_good = False
    
    return all_good

def main():
    """Main fix function"""
    print("🔧 UI Loading Fix Script")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists("code"):
        print("❌ 'code' directory not found. Please run from project root.")
        return False
    
    # Make backup first
    print("💾 Creating backup...")
    import shutil
    import datetime
    
    backup_dir = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copytree("code", backup_dir)
        print(f"   ✅ Backup created: {backup_dir}")
    except Exception as e:
        print(f"   ⚠️  Backup failed: {e}")
        print("   Continuing without backup...")
    
    # Apply fixes
    print(f"\n🔧 Applying Fixes:")
    
    success1 = fix_mainwindow_page()
    success2 = fix_uploadfile_page()
    fix_other_pages()  # This handles other files
    
    # Verify fixes
    all_good = verify_fixes()
    
    # Summary
    print(f"\n📋 Summary:")
    if all_good:
        print("   ✅ All UI loading issues fixed!")
        print("   ✅ Ready for PyInstaller build")
    else:
        print("   ⚠️  Some issues may remain")
        print("   Check verification results above")
    
    return all_good

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)