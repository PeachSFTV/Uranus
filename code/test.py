# test_pyiec61850.py
import pyiec61850

# 1. ดู attributes และ functions ที่มี
print("=== pyiec61850 Attributes ===")
for attr in dir(pyiec61850):
    if not attr.startswith('_'):
        print(f"- {attr}")
        
# 2. ถ้ามี documentation
print("\n=== pyiec61850 Documentation ===")
if hasattr(pyiec61850, '__doc__'):
    print(pyiec61850.__doc__)

# 3. ลองดู specific modules ที่น่าจะมี
modules_to_check = ['goose', 'client', 'server', 'common', 'iec61850']
for module in modules_to_check:
    if hasattr(pyiec61850, module):
        print(f"\n=== {module} module ===")
        mod = getattr(pyiec61850, module)
        for attr in dir(mod):
            if not attr.startswith('_'):
                print(f"  - {attr}")

# 4. ถ้ามี example หรือ test
try:
    import pyiec61850.examples
    print("\n=== Examples available ===")
except:
    print("\n=== No examples module ===")