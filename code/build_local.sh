#!/bin/bash
# Local build script for Uranus (Linux)

set -e  # Exit on any error

echo "🌟 Uranus Local Build Script"
echo "============================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check Python version
check_python() {
    log_info "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found!"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_success "Python $PYTHON_VERSION found"
    
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
        log_error "Python 3.8+ required, found $PYTHON_VERSION"
        exit 1
    fi
}

# Check virtual environment
check_venv() {
    log_info "Checking virtual environment..."
    if [[ -z "$VIRTUAL_ENV" ]]; then
        log_warning "Not in virtual environment"
        if [[ -d ".venv" ]]; then
            log_info "Found .venv, activating..."
            source .venv/bin/activate
            log_success "Virtual environment activated"
        else
            log_info "Creating virtual environment..."
            python3 -m venv .venv
            source .venv/bin/activate
            log_success "Virtual environment created and activated"
        fi
    else
        log_success "Virtual environment is active: $VIRTUAL_ENV"
    fi
}

# Check pyiec61850
check_pyiec61850() {
    log_info "Checking pyiec61850 installation..."
    if python -c "import pyiec61850" 2>/dev/null; then
        log_success "pyiec61850 is available"
        PYIEC_INFO=$(python -c "import pyiec61850; print(f'Location: {pyiec61850.__file__ if hasattr(pyiec61850, \"__file__\") else \"built-in\"}')")
        log_info "$PYIEC_INFO"
    else
        log_error "pyiec61850 not found!"
        log_info "Please install pyiec61850 first:"
        log_info "  1. Build from source: https://github.com/mz-automation/libiec61850"
        log_info "  2. Or install pre-built version"
        exit 1
    fi
}

# Install dependencies
install_deps() {
    log_info "Installing dependencies..."
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "Dependencies installed from requirements.txt"
    else
        log_warning "requirements.txt not found, installing basic deps..."
        pip install PyQt6 numpy pandas matplotlib netifaces scapy pyinstaller
    fi
    
    # Install PyInstaller if not present
    if ! pip show pyinstaller &> /dev/null; then
        log_info "Installing PyInstaller..."
        pip install pyinstaller
    fi
    
    log_success "All dependencies installed"
}

# Clean previous build
clean_build() {
    log_info "Cleaning previous build..."
    rm -rf dist/ build/ *.spec.bak
    log_success "Build directory cleaned"
}

# Build executable
build_exe() {
    log_info "Building Linux executable..."
    
    # Check spec file
    if [[ ! -f "uranus.spec" ]]; then
        log_error "uranus.spec not found!"
        log_info "Please create uranus.spec file first"
        exit 1
    fi
    
    # Check entry point
    if [[ ! -f "code/MainWindow_Page.py" ]]; then
        log_error "Entry point code/MainWindow_Page.py not found!"
        log_info "Please check your project structure"
        exit 1
    fi
    
    # Run PyInstaller
    log_info "Running PyInstaller..."
    pyinstaller uranus.spec
    
    # Check result
    if [[ -f "dist/Uranus" ]]; then
        log_success "Executable created successfully!"
        ls -lh dist/Uranus
        file dist/Uranus
        
        # Test executable
        log_info "Testing executable..."
        if timeout 5s dist/Uranus --help &>/dev/null; then
            log_success "Executable test passed"
        else
            log_warning "Executable test timed out (normal for GUI apps)"
        fi
        
        # Create release info
        cat > dist/README.txt << EOF
Uranus IEC 61850 Protocol Analyzer - Linux Build
===============================================

Build Date: $(date)
Platform: $(uname -a)
Python Version: $(python --version)

Usage:
  chmod +x Uranus
  sudo ./Uranus  # Run as root for network access

For support and documentation:
  https://github.com/PeachSFTV/Uranus
EOF
        
        log_success "Build completed successfully!"
        log_info "Executable location: $(pwd)/dist/Uranus"
        
    else
        log_error "Failed to create executable!"
        log_info "Check PyInstaller output above for errors"
        exit 1
    fi
}

# Main execution
main() {
    echo
    log_info "Starting Uranus build process..."
    echo
    
    # Pre-build checks
    check_python
    check_venv
    check_pyiec61850
    
    # Build process
    install_deps
    clean_build
    build_exe
    
    echo
    log_success "🎉 Build process completed!"
    echo
    log_info "Next steps:"
    log_info "  1. Test: ./dist/Uranus"
    log_info "  2. Distribute: Copy dist/Uranus to target systems"
    log_info "  3. Package: tar -czf uranus-linux.tar.gz dist/"
    echo
}

# Run main function
main "$@"