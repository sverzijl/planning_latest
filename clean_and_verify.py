"""Clean Python cache and verify installation.

This script removes cached .pyc files and verifies code is working.
"""

import sys
import shutil
from pathlib import Path

print("="*80)
print("CLEANING PYTHON CACHE")
print("="*80)

# Find and remove __pycache__ directories
root = Path.cwd()
pycache_dirs = list(root.rglob('__pycache__'))

print(f"\nFound {len(pycache_dirs)} __pycache__ directories")

for pycache_dir in pycache_dirs:
    try:
        shutil.rmtree(pycache_dir)
        print(f"  Removed: {pycache_dir.relative_to(root)}")
    except Exception as e:
        print(f"  Failed to remove {pycache_dir}: {e}")

# Remove .pyc files
pyc_files = list(root.rglob('*.pyc'))
print(f"\nFound {len(pyc_files)} .pyc files")
for pyc_file in pyc_files:
    try:
        pyc_file.unlink()
        print(f"  Removed: {pyc_file.relative_to(root)}")
    except Exception as e:
        print(f"  Failed to remove {pyc_file}: {e}")

print("\n" + "="*80)
print("VERIFYING INSTALLATION")
print("="*80)

# Test import
sys.path.insert(0, str(root))

try:
    # Import validation_utils
    from src.optimization import validation_utils
    print("\n✅ validation_utils imported")

    # Check functions exist
    expected_functions = [
        'validate_dict_has_string_keys',
        'validate_fefo_return_structure',
        'validate_solution_dict_for_pydantic',
        'validate_optimization_solution_complete',
    ]

    for func_name in expected_functions:
        has_func = hasattr(validation_utils, func_name)
        print(f"  {'✅' if has_func else '❌'} {func_name}")

except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("NEXT STEPS:")
print("="*80)
print("1. Restart Streamlit: streamlit run ui/app.py")
print("2. Run a NEW solve (don't use cached results)")
print("3. Check if data appears correctly")
print("="*80)
