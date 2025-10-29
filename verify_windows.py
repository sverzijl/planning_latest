"""Run this on Windows to verify code changes are present.

Usage:
    python verify_windows.py
"""

from pathlib import Path
import sys

print("="*80)
print("WINDOWS INSTALLATION VERIFICATION")
print("="*80)

print(f"\nPython: {sys.executable}")
print(f"Working dir: {Path.cwd()}")

# Check key files exist
files_to_check = [
    "src/optimization/validation_utils.py",
    "src/optimization/sliding_window_model.py",
    "tests/test_validation_utils.py",
]

print("\nChecking files:")
for file_path in files_to_check:
    p = Path(file_path)
    exists = p.exists()
    print(f"  {'✅' if exists else '❌'} {file_path}")

# Check for the specific fix in sliding_window_model.py
print("\nChecking sliding_window_model.py for fixes:")
sw_path = Path("src/optimization/sliding_window_model.py")
if sw_path.exists():
    content = sw_path.read_text()

    checks = {
        "Tuple→string conversion": "batch_inventory_serialized" in content,
        "FEFO validation": "validate_fefo_return_structure" in content,
        "Diagnostic logging": "Extracted {len(production_by_date_product)} production entries" in content,
        "Pre-validation": "validate_solution_dict_for_pydantic" in content,
    }

    for check_name, found in checks.items():
        print(f"  {'✅' if found else '❌'} {check_name}")

    if not all(checks.values()):
        print(f"\n  ⚠️  CODE CHANGES NOT FOUND!")
        print(f"  The git pull may not have updated the files.")
        print(f"  Try: git reset --hard origin/master")
else:
    print(f"  ❌ File not found!")

# Check git status
print("\nGit info:")
try:
    import subprocess
    result = subprocess.run(['git', 'log', '-1', '--oneline'],
                          capture_output=True, text=True, shell=True)
    print(f"  Latest commit: {result.stdout.strip()}")

    result = subprocess.run(['git', 'status', '--short'],
                          capture_output=True, text=True, shell=True)
    if result.stdout.strip():
        print(f"  Modified files:\n{result.stdout}")
    else:
        print(f"  No local modifications")
except Exception as e:
    print(f"  Could not check git: {e}")

print("\n" + "="*80)
print("If you see ❌, run: git reset --hard origin/master")
print("="*80)
