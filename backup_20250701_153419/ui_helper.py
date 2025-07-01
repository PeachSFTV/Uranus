"""
UI Helper for Uranus - ใน code/ directory
จัดการ UI file paths สำหรับทั้ง development และ PyInstaller executable
"""

import os
import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QDir

class UIHelper:
    """Helper class for UI file management"""
    
    @staticmethod
    def get_base_path():
        """Get the base path for resources"""
        if hasattr(sys, '_MEIPASS'):
            # Running in PyInstaller bundle
            return sys._MEIPASS
        else:
            # Running in development - กลับไป parent directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir.endswith('/code'):
                return os.path.dirname(current_dir)  # ไปที่ Uranus/ directory
            return current_dir
    
    @staticmethod
    def get_ui_path(ui_filename):
        """Get full path to UI file"""
        base_path = UIHelper.get_base_path()
        
        # ลำดับความสำคัญของ path ที่จะหา
        possible_paths = [
            # Development mode
            os.path.join(base_path, 'code', 'QTDesigner', ui_filename),
            os.path.join(base_path, 'QTDesigner', ui_filename),
            
            # PyInstaller mode
            os.path.join(base_path, 'QTDesigner', ui_filename),
            os.path.join(base_path, ui_filename),
            
            # Fallback paths
            os.path.join(os.path.dirname(__file__), 'QTDesigner', ui_filename),
            os.path.join(os.path.dirname(__file__), '..', 'QTDesigner', ui_filename),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ Found UI file: {ui_filename} -> {path}")
                return path
        
        # Debug info ถ้าไม่เจอ
        print(f"❌ UI file not found: {ui_filename}")
        print(f"   Base path: {base_path}")
        print(f"   Current file: {__file__}")
        print(f"   Searched paths:")
        for path in possible_paths:
            exists = os.path.exists(path)
            print(f"     - {path} ({'EXISTS' if exists else 'NOT FOUND'})")
        
        # List available files ใน QTDesigner
        qtdesigner_paths = [
            os.path.join(base_path, 'code', 'QTDesigner'),
            os.path.join(base_path, 'QTDesigner'),
        ]
        
        for qtd_path in qtdesigner_paths:
            if os.path.exists(qtd_path):
                files = [f for f in os.listdir(qtd_path) if f.endswith('.ui')]
                print(f"   Available UI files in {qtd_path}: {files}")
                break
        
        return None
    
    @staticmethod
    def load_ui_safe(ui_filename, parent=None):
        """Safely load UI file with comprehensive error handling"""
        print(f"🔄 Loading UI: {ui_filename}")
        
        ui_path = UIHelper.get_ui_path(ui_filename)
        
        if ui_path is None:
            print(f"⚠️  Cannot find UI file: {ui_filename}")
            return UIHelper.create_fallback_widget(ui_filename, parent)
        
        try:
            # Load the UI file
            if parent:
                widget = uic.loadUi(ui_path, parent)
                print(f"✅ Successfully loaded UI: {ui_filename} (with parent)")
            else:
                widget = uic.loadUi(ui_path)
                print(f"✅ Successfully loaded UI: {ui_filename} (standalone)")
            
            return widget
            
        except Exception as e:
            print(f"❌ Error loading UI file {ui_filename}: {e}")
            print(f"   UI path: {ui_path}")
            print(f"   Error type: {type(e).__name__}")
            
            return UIHelper.create_fallback_widget(ui_filename, parent)
    
    @staticmethod
    def create_fallback_widget(ui_filename, parent=None):
        """Create a fallback widget when UI loading fails"""
        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QApplication
        from PyQt6.QtCore import Qt
        
        # Ensure QApplication exists
        app = QApplication.instance()
        if app is None:
            print(f"⚠️  Creating QApplication for fallback widget")
            app = QApplication([])
        
        if parent:
            widget = QWidget(parent)
        else:
            widget = QWidget()
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"UI Loading Error: {ui_filename}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Message
        message = QLabel("The UI file could not be loaded.\nUsing fallback interface.")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(widget.close)
        layout.addWidget(close_btn)
        
        widget.setLayout(layout)
        widget.setWindowTitle(f"Uranus - {ui_filename} (Fallback)")
        widget.resize(400, 200)
        
        return widget

    @staticmethod 
    def setup_paths():
        """Setup paths for the application"""
        base_path = UIHelper.get_base_path()
        
        # Add code directory to Python path if not already there
        code_path = os.path.join(base_path, 'code')
        if os.path.exists(code_path) and code_path not in sys.path:
            sys.path.insert(0, code_path)
            print(f"📁 Added to Python path: {code_path}")
        
        # Setup Qt search paths
        QDir.addSearchPath("ui", os.path.join(base_path, "code", "QTDesigner"))
        QDir.addSearchPath("ui", os.path.join(base_path, "QTDesigner"))
        QDir.addSearchPath("icons", os.path.join(base_path, "code", "icon"))
        QDir.addSearchPath("icons", os.path.join(base_path, "icon"))
        
        print(f"🔧 UI paths setup completed")
        print(f"   Base: {base_path}")
        print(f"   UI search paths configured")

# Convenience functions
def load_ui_safe(ui_filename, parent=None):
    """Convenience function for safe UI loading"""
    return UIHelper.load_ui_safe(ui_filename, parent)

def get_ui_path_safe(ui_filename):
    """Convenience function for getting UI path"""
    return UIHelper.get_ui_path(ui_filename)

# Auto-setup on import
UIHelper.setup_paths()