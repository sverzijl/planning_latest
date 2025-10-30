"""Verify that the latest code changes are actually installed and working.

Run this to diagnose why UI isn't showing changes.
"""

import sys
from pathlib import Path

print("="*80)
print("INSTALLATION VERIFICATION")
print("="*80)

# 1. Check Python path
print(f"\n1. Python executable: {sys.executable}")
print(f"   Python version: {sys.version}")

# 2. Check working directory
print(f"\n2. Current directory: {Path.cwd()}")

# 3. Check if validation_utils exists
validation_utils_path = Path(__file__).parent / "src" / "optimization" / "validation_utils.py"
print(f"\n3. validation_utils.py exists: {validation_utils_path.exists()}")
if validation_utils_path.exists():
    print(f"   Path: {validation_utils_path}")
    # Read first few lines
    with open(validation_utils_path) as f:
        first_line = f.readline().strip()
        print(f"   First line: {first_line}")

# 4. Check if sliding_window_model has the fix
sliding_window_path = Path(__file__).parent / "src" / "optimization" / "sliding_window_model.py"
print(f"\n4. Checking sliding_window_model.py for fix...")
if sliding_window_path.exists():
    with open(sliding_window_path) as f:
        content = f.read()
        # Check for the fix
        has_string_serialization = "batch_inventory_serialized" in content
        has_validation_call = "validate_fefo_return_structure" in content
        has_diagnostic_logging = "Extracted {len(production_by_date_product)} production entries" in content

        print(f"   Has tuple→string conversion: {has_string_serialization}")
        print(f"   Has FEFO validation: {has_validation_call}")
        print(f"   Has diagnostic logging: {has_diagnostic_logging}")

        if not all([has_string_serialization, has_validation_call, has_diagnostic_logging]):
            print(f"\n   ⚠️  WARNING: Code changes not found in file!")
            print(f"   This means the files on disk don't have the latest changes.")

# 5. Try importing validation_utils
print(f"\n5. Testing imports...")
try:
    from src.optimization import validation_utils
    print(f"   ✅ validation_utils imported successfully")
    print(f"   Functions: {[name for name in dir(validation_utils) if not name.startswith('_')]}")
except ImportError as e:
    print(f"   ❌ Failed to import validation_utils: {e}")

# 6. Test logging configuration
print(f"\n6. Testing logging...")
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('test')
logger.info("This is a test INFO message")
logger.warning("This is a test WARNING message")
logger.error("This is a test ERROR message")

print(f"\n7. Git status...")
import subprocess
try:
    result = subprocess.run(['git', 'log', '-1', '--oneline'], capture_output=True, text=True, cwd=Path(__file__).parent)
    print(f"   Latest commit: {result.stdout.strip()}")
except:
    print(f"   Could not run git command")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)
print("\nIf everything shows ✅, the code is installed correctly.")
print("If you see ⚠️  warnings, the files don't have the latest changes.")
print("\nRun with: python verify_installation.py")
