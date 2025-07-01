#!/bin/bash
"""
Uranus Launcher Script with Qt Platform Detection
"""

echo "🚀 Uranus IEC 61850 Application Launcher"
echo "======================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URANUS_EXEC="$SCRIPT_DIR/dist/Uranus"

# Check if executable exists
if [ ! -f "$URANUS_EXEC" ]; then
    echo "❌ Uranus executable not found at: $URANUS_EXEC"
    echo "Please build first with: pyinstaller uranus.spec"
    exit 1
fi

# Qt Platform Detection and Configuration
echo "🔍 Detecting display environment..."

# Check for X11
if [ -n "$DISPLAY" ] && command -v xdpyinfo >/dev/null 2>&1 && xdpyinfo >/dev/null 2>&1; then
    echo "✅ X11 display detected: $DISPLAY"
    export QT_QPA_PLATFORM=xcb
elif [ -n "$WAYLAND_DISPLAY" ]; then
    echo "✅ Wayland display detected: $WAYLAND_DISPLAY"
    export QT_QPA_PLATFORM=wayland
else
    echo "⚠️  No display detected, using offscreen mode"
    export QT_QPA_PLATFORM=offscreen
fi

# Qt Library Path Configuration
if [ -d "$SCRIPT_DIR/dist/_internal" ]; then
    export LD_LIBRARY_PATH="$SCRIPT_DIR/dist/_internal:$LD_LIBRARY_PATH"
fi

# Qt Plugin Path
if [ -d "$SCRIPT_DIR/dist/_internal/PyQt6/Qt6/plugins" ]; then
    export QT_PLUGIN_PATH="$SCRIPT_DIR/dist/_internal/PyQt6/Qt6/plugins"
fi

# Root privileges check
check_root_needed() {
    echo "🔐 Checking privileges..."
    
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Some features require root privileges:"
        echo "   • GOOSE message capture (raw sockets)"
        echo "   • Network interface promiscuous mode" 
        echo "   • ARP table access for IP filtering"
        echo ""
        read -p "Run with sudo? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🔄 Restarting with sudo..."
            sudo -E "$0" "$@"
            exit $?
        else
            echo "ℹ️  Running without root (limited functionality)"
        fi
    else
        echo "✅ Running with root privileges"
    fi
}

# Enhanced error handling
run_uranus() {
    echo "🚀 Starting Uranus..."
    echo "   Platform: $QT_QPA_PLATFORM"
    echo "   Display: ${DISPLAY:-${WAYLAND_DISPLAY:-none}}"
    echo ""
    
    # Try to run with error capturing
    "$URANUS_EXEC" "$@" 2>&1 | while IFS= read -r line; do
        case "$line" in
            *"Could not load the Qt platform plugin"*)
                echo "❌ Qt Platform Error: $line"
                echo "💡 Trying alternative platforms..."
                ;;
            *"xcb-cursor0"*)
                echo "❌ Missing Qt dependency: $line"
                echo "💡 Install with: sudo apt install libxcb-cursor0"
                ;;
            *"Fatal Python error"*)
                echo "❌ Fatal Error: $line"
                ;;
            *"ERROR"*|*"Error"*|*"error"*)
                echo "⚠️  $line"
                ;;
            *)
                echo "$line"
                ;;
        esac
    done
    
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "❌ Uranus exited with error code: $exit_code"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   1. Check Qt dependencies: sudo apt install libxcb-cursor0"
        echo "   2. Try different platform: QT_QPA_PLATFORM=wayland $0"
        echo "   3. Check display: echo \$DISPLAY"
        echo "   4. Run with debug: QT_DEBUG_PLUGINS=1 $0"
        echo ""
        return $exit_code
    fi
}

# Platform fallback mechanism
try_platforms() {
    local platforms=("xcb" "wayland" "offscreen")
    
    for platform in "${platforms[@]}"; do
        echo "🔄 Trying Qt platform: $platform"
        export QT_QPA_PLATFORM=$platform
        
        if timeout 10s "$URANUS_EXEC" --help >/dev/null 2>&1; then
            echo "✅ Platform $platform works!"
            run_uranus "$@"
            return $?
        else
            echo "❌ Platform $platform failed"
        fi
    done
    
    echo "❌ All Qt platforms failed"
    return 1
}

# Main execution
main() {
    # Check root if needed
    if [[ "$1" == "--need-root" ]]; then
        check_root_needed
        shift
    fi
    
    # Try default platform first
    echo "🎯 Attempting default platform..."
    if ! timeout 5s "$URANUS_EXEC" --help >/dev/null 2>&1; then
        echo "⚠️  Default platform failed, trying alternatives..."
        try_platforms "$@"
    else
        run_uranus "$@"
    fi
}

# Help message
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --need-root    Check and request root privileges"
    echo "  --help, -h     Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  QT_QPA_PLATFORM    Force Qt platform (xcb/wayland/offscreen)"
    echo "  QT_DEBUG_PLUGINS   Enable Qt plugin debugging"
    echo ""
    echo "Examples:"
    echo "  $0                           # Normal run"
    echo "  $0 --need-root              # Check for root privileges"
    echo "  QT_QPA_PLATFORM=wayland $0  # Force Wayland"
    echo "  sudo $0                     # Run with full privileges"
    exit 0
fi

# Execute main function
main "$@"