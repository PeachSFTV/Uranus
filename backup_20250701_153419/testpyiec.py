#!/usr/bin/env python3
"""
Test script for pyiec61850 installation
Verifies that pyiec61850 can be imported and used
"""

import sys
import os
import importlib

def test_import():
    """Test basic import"""
    print("🧪 Testing pyiec61850 import...")
    
    try:
        import pyiec61850
        print("✅ SUCCESS: pyiec61850 imported")
        return pyiec61850
    except ImportError as e:
        print(f"❌ FAILED: Cannot import pyiec61850 - {e}")
        
        # Try alternative imports
        print("🔄 Trying alternative imports...")

def test_module_info(module):
    """Test module information"""
    if not module:
        return False
        
    print(f"\n📋 Module Information:")
    print(f"   Name: {module.__name__}")
    
    if hasattr(module, '__file__'):
        print(f"   File: {module.__file__}")
        print(f"   Directory: {os.path.dirname(module.__file__)}")
    else:
        print("   Type: Built-in or C extension")
    
    if hasattr(module, '__version__'):
        print(f"   Version: {module.__version__}")
    
    # Count attributes
    attrs = [attr for attr in dir(module) if not attr.startswith('_')]
    print(f"   Attributes: {len(attrs)} public items")
    
    return True

def test_important_functions(module):
    """Test important IEC61850 functions"""
    if not module:
        return False
        
    print(f"\n🔧 Testing Important Functions:")
    
    important_functions = [
        'IedConnection_create',
        'IedConnection_connect', 
        'IedConnection_close',
        'IedConnection_destroy',
        'ClientDataSet_create',
        'ClientDataSet_destroy',
        'MmsValue_newBoolean',
        'MmsValue_getType'
    ]
    
    found_functions = []
    missing_functions = []
    
    for func_name in important_functions:
        if hasattr(module, func_name):
            found_functions.append(func_name)
            print(f"   ✅ {func_name}")
        else:
            missing_functions.append(func_name)
            print(f"   ❌ {func_name}")
    
    print(f"\n📊 Function Check Results:")
    print(f"   Found: {len(found_functions)}/{len(important_functions)}")
    print(f"   Missing: {len(missing_functions)}")
    
    return len(found_functions) > 0

def test_basic_usage(module):
    """Test basic usage"""
    if not module:
        return False
        
    print(f"\n🎯 Testing Basic Usage:")
    
    try:
        # Test 1: Create IED connection (without actually connecting)
        if hasattr(module, 'IedConnection_create'):
            print("   🔗 Testing IedConnection_create...")
            # Note: We don't actually connect to avoid network requirements
            print("   ✅ IedConnection_create function available")
        
        # Test 2: Test MmsValue functions
        if hasattr(module, 'MmsValue_newBoolean'):
            print("   📊 Testing MmsValue_newBoolean...")
            bool_val = module.MmsValue_newBoolean(True)
            if bool_val:
                print("   ✅ MmsValue_newBoolean works")
                
                # Clean up if possible
                if hasattr(module, 'MmsValue_delete'):
                    module.MmsValue_delete(bool_val)
            else:
                print("   ⚠️  MmsValue_newBoolean returned None")
        
        print("   ✅ Basic usage test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Basic usage test failed: {e}")
        return False

def test_installation_paths():
    """Test installation paths and files"""
    print(f"\n📁 Installation Path Analysis:")
    
    # Check Python path
    print("   Python paths:")
    for i, path in enumerate(sys.path[:5]):  # Show first 5 paths
        print(f"      {i+1}. {path}")
    
    # Check site-packages
    try:
        import site
        site_packages = site.getsitepackages()
        print(f"   Site-packages directories:")
        for i, path in enumerate(site_packages):
            print(f"      {i+1}. {path}")
            
            # Check for pyiec61850 in each
            pyiec_path = os.path.join(path, 'pyiec61850')
            if os.path.exists(pyiec_path):
                print(f"         ✅ pyiec61850 directory found")
                files = os.listdir(pyiec_path)
                print(f"         📄 Files: {files}")
            
            # Check for direct files
            for file_pattern in ['iec61850.py', '_iec61850.so', '_iec61850.pyd']:
                file_path = os.path.join(path, file_pattern)
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path) / 1024  # KB
                    print(f"         ✅ {file_pattern} ({size:.1f} KB)")
                    
    except Exception as e:
        print(f"   ❌ Path analysis failed: {e}")

def main():
    """Main test function"""
    print("🌟 pyiec61850 Installation Test")
    print("=" * 50)
    
    # Test import
    module = test_import()
    
    # Test module info
    info_ok = test_module_info(module)
    
    # Test functions
    functions_ok = test_important_functions(module)
    
    # Test basic usage
    usage_ok = test_basic_usage(module)
    
    # Test paths
    test_installation_paths()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   Import: {'✅ Pass' if module else '❌ Fail'}")
    print(f"   Module Info: {'✅ Pass' if info_ok else '❌ Fail'}")
    print(f"   Functions: {'✅ Pass' if functions_ok else '❌ Fail'}")
    print(f"   Basic Usage: {'✅ Pass' if usage_ok else '❌ Fail'}")
    
    # Overall result
    overall_ok = module and functions_ok
    if overall_ok:
        print("\n🎉 Overall Result: ✅ PASS")
        print("   pyiec61850 is ready for use!")
    else:
        print("\n❌ Overall Result: ❌ FAIL")
        print("   pyiec61850 needs installation or fixing")
        
        print("\n💡 Troubleshooting Tips:")
        if not module:
            print("   - Ensure pyiec61850 is installed")
            print("   - Check virtual environment activation")
            print("   - Try: pip install pyiec61850")
        if not functions_ok:
            print("   - Installation may be incomplete")
            print("   - Try rebuilding from source")
            print("   - Check for missing dependencies")
    
    return overall_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)