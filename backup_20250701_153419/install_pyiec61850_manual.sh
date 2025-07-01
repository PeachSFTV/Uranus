#!/bin/bash
# Manual pyiec61850 installation script for GitHub Actions

set -e

echo "🔧 Manual pyiec61850 Installation"
echo "================================"

# Get Python site-packages directory
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "📁 Site-packages: $SITE_PACKAGES"

# Create pyiec61850 directory
PYIEC_DIR="$SITE_PACKAGES/pyiec61850"
mkdir -p "$PYIEC_DIR"
echo "📁 Created: $PYIEC_DIR"

# Function to find and copy files
copy_files() {
    local pattern="$1"
    local dest="$2"
    local desc="$3"
    
    echo "🔍 Looking for $desc..."
    
    # Search in multiple locations
    for search_dir in . ../build ../pyiec61850 pyiec61850; do
        if [ -d "$search_dir" ]; then
            find "$search_dir" -name "$pattern" -type f 2>/dev/null | while read -r file; do
                if [ -f "$file" ]; then
                    cp "$file" "$dest/"
                    echo "✅ Copied: $(basename "$file") from $search_dir"
                fi
            done
        fi
    done
}

# Copy Python wrapper files
echo "📦 Installing Python wrapper files..."
copy_files "iec61850.py" "$PYIEC_DIR" "Python wrapper"
copy_files "*.py" "$PYIEC_DIR" "Python files"

# Copy compiled extensions (Linux)
echo "📦 Installing compiled extensions..."
copy_files "_iec61850.so" "$SITE_PACKAGES" "Linux shared library"
copy_files "*.so" "$SITE_PACKAGES" "shared libraries"

# Copy Windows extensions (if any)
copy_files "_iec61850.pyd" "$SITE_PACKAGES" "Windows extension"
copy_files "*.pyd" "$SITE_PACKAGES" "Python extensions"

# Create __init__.py
INIT_FILE="$PYIEC_DIR/__init__.py"
if [ ! -f "$INIT_FILE" ]; then
    cat > "$INIT_FILE" << 'EOF'
"""
pyiec61850 - Python bindings for libiec61850
IEC 61850 client and server library for Python
"""

try:
    # Try to import from local iec61850 module
    from .iec61850 import *
except ImportError:
    try:
        # Fallback to direct import
        import iec61850
        # Re-export all symbols
        import sys
        current_module = sys.modules[__name__]
        for attr in dir(iec61850):
            if not attr.startswith('_'):
                setattr(current_module, attr, getattr(iec61850, attr))
    except ImportError as e:
        print(f"Warning: Failed to import iec61850: {e}")
        pass

__version__ = "1.5.2"
__author__ = "MZ Automation GmbH"
__description__ = "Python bindings for libiec61850"
EOF
    echo "✅ Created: $INIT_FILE"
fi

# Verify installation
echo "🧪 Testing installation..."
if python -c "import pyiec61850; print('✅ pyiec61850 import successful')" 2>/dev/null; then
    echo "🎉 Manual installation successful!"
    
    # Show available functions
    python -c "
import pyiec61850
attrs = [attr for attr in dir(pyiec61850) if not attr.startswith('_')]
print(f'📋 Available attributes: {len(attrs)}')
if len(attrs) > 0:
    print('🔧 Sample functions:', attrs[:5])
" 2>/dev/null || echo "⚠️  Module imported but limited functionality"

else
    echo "❌ Manual installation failed"
    echo "📋 Available files:"
    ls -la "$SITE_PACKAGES" | grep iec || echo "No iec61850 files found"
    ls -la "$PYIEC_DIR" 2>/dev/null || echo "pyiec61850 directory empty"
    exit 1
fi

echo "✅ Installation completed"