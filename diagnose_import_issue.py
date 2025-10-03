"""
COMPREHENSIVE IMPORT DIAGNOSTIC SCRIPT

This script diagnoses import issues with render_truck_loadings_table.
Run this from the planning_latest directory on Windows.

Usage:
    cd C:\Users\simeon.verzijl\Downloads\WPy64-31311b1\planning_latest\planning_latest
    python diagnose_import_issue.py
"""

import sys
import os
from pathlib import Path
import hashlib

print("=" * 80)
print("COMPREHENSIVE IMPORT DIAGNOSTIC FOR render_truck_loadings_table")
print("=" * 80)

# Check Python version
print(f"\n[1] PYTHON ENVIRONMENT")
print(f"  Python version: {sys.version}")
print(f"  Platform: {sys.platform}")
print(f"  Executable: {sys.executable}")

# Check working directory
print(f"\n[2] WORKING DIRECTORY")
cwd = Path.cwd()
print(f"  Current: {cwd}")
print(f"  Absolute: {cwd.absolute()}")

# Check if we're in the right directory
if not (cwd / "ui" / "components" / "__init__.py").exists():
    print("  ERROR: Not in planning_latest directory!")
    print("  Please cd to the planning_latest directory first")
    sys.exit(1)
else:
    print("  OK: Correct directory")

# Check file existence and sizes
print(f"\n[3] FILE EXISTENCE CHECK")
critical_files = [
    "ui/components/__init__.py",
    "ui/components/data_tables.py",
    "src/distribution/__init__.py",
    "src/distribution/truck_loader.py",
]

file_hashes = {}
for filepath in critical_files:
    path = Path(filepath)
    if path.exists():
        size = path.stat().st_size
        # Calculate hash
        with open(path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        file_hashes[filepath] = file_hash
        print(f"  OK: {filepath} ({size} bytes, hash: {file_hash})")
    else:
        print(f"  ERROR: {filepath} NOT FOUND")
        sys.exit(1)

# Check for __pycache__ directories
print(f"\n[4] PYTHON CACHE DIRECTORIES")
cache_dirs = list(Path(".").rglob("__pycache__"))
if cache_dirs:
    print(f"  WARNING: Found {len(cache_dirs)} __pycache__ directories")
    print(f"  Run fix_import_error.ps1 to clear cache")
    for cache_dir in cache_dirs[:5]:
        print(f"    - {cache_dir}")
else:
    print("  OK: No __pycache__ directories found")

# Read and verify __init__.py content
print(f"\n[5] VERIFY ui/components/__init__.py CONTENT")
init_path = Path("ui/components/__init__.py")
with open(init_path, 'r', encoding='utf-8') as f:
    init_content = f.read()
    lines = init_content.split('\n')

# Check import line
print(f"  Checking imports from .data_tables:")
import_section_start = init_content.find("from .data_tables import")
if import_section_start == -1:
    print(f"    ERROR: 'from .data_tables import' not found!")
    sys.exit(1)

import_section_end = init_content.find("\nfrom", import_section_start + 10)
if import_section_end == -1:
    import_section_end = len(init_content)

import_section = init_content[import_section_start:import_section_end]

if "render_truck_loadings_table" in import_section:
    print(f"    OK: render_truck_loadings_table found in imports")
    for i, line in enumerate(lines, 1):
        if "render_truck_loadings_table" in line and not line.strip().startswith('#'):
            if "from .data_tables" in '\n'.join(lines[max(0,i-10):i]):
                print(f"       Line {i}: {line.strip()}")
                break
else:
    print(f"    ERROR: render_truck_loadings_table NOT in imports!")
    print(f"    Import section found:")
    for line in import_section.split('\n')[:15]:
        print(f"      {line}")
    print(f"\n    YOUR FILE IS OUT OF DATE!")
    print(f"    Run: git pull origin master")
    sys.exit(1)

# Check __all__ list
print(f"  Checking __all__ export list:")
if "'render_truck_loadings_table'" in init_content or '"render_truck_loadings_table"' in init_content:
    print(f"    OK: 'render_truck_loadings_table' found in __all__")
    for i, line in enumerate(lines, 1):
        if "render_truck_loadings_table" in line and "__all__" in '\n'.join(lines[max(0,i-30):i+5]):
            print(f"       Line {i}: {line.strip()}")
            break
else:
    print(f"    ERROR: 'render_truck_loadings_table' NOT in __all__!")
    print(f"    YOUR FILE IS OUT OF DATE!")
    print(f"    Run: git pull origin master")
    sys.exit(1)

# Read and verify data_tables.py content
print(f"\n[6] VERIFY ui/components/data_tables.py CONTENT")
data_tables_path = Path("ui/components/data_tables.py")
with open(data_tables_path, 'r', encoding='utf-8') as f:
    data_tables_content = f.read()
    dt_lines = data_tables_content.split('\n')

# Check for function definition
if "def render_truck_loadings_table" in data_tables_content:
    print(f"  OK: Function render_truck_loadings_table defined")
    for i, line in enumerate(dt_lines, 1):
        if "def render_truck_loadings_table" in line:
            print(f"     Line {i}: {line.strip()}")
            break
else:
    print(f"  ERROR: Function render_truck_loadings_table NOT FOUND!")
    print(f"  YOUR FILE IS OUT OF DATE!")
    print(f"  Run: git pull origin master")
    sys.exit(1)

# Test import chain step by step
print(f"\n[7] TEST IMPORT CHAIN")

# Clear any existing imports
modules_to_clear = [m for m in sys.modules.keys() if m.startswith('ui.components') or m.startswith('src.distribution')]
for module in modules_to_clear:
    del sys.modules[module]

# Test 1: Import ui.components module
print(f"  [7.1] Import ui.components module")
try:
    import ui.components
    print(f"    OK: ui.components imported successfully")
except Exception as e:
    print(f"    ERROR: Failed to import ui.components")
    print(f"       {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Import data_tables submodule
print(f"  [7.2] Import ui.components.data_tables")
try:
    from ui.components import data_tables
    print(f"    OK: data_tables imported successfully")
except Exception as e:
    print(f"    ERROR: Failed to import data_tables")
    print(f"       {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check if function exists in module
print(f"  [7.3] Check if render_truck_loadings_table exists in data_tables")
if hasattr(data_tables, 'render_truck_loadings_table'):
    print(f"    OK: Function exists in module")
else:
    print(f"    ERROR: Function NOT found in module!")
    available = [x for x in dir(data_tables) if not x.startswith('_')]
    print(f"    Available functions in data_tables:")
    for name in available[:20]:
        print(f"      - {name}")
    sys.exit(1)

# Test 4: Import from ui.components.__init__
print(f"  [7.4] Import render_truck_loadings_table from ui.components")
try:
    from ui.components import render_truck_loadings_table
    print(f"    OK: Import successful!")
except Exception as e:
    print(f"    ERROR: Import FAILED!")
    print(f"       {e}")
    import traceback
    traceback.print_exc()

    # Additional diagnostics
    print(f"\n    ADDITIONAL DIAGNOSTICS:")
    if hasattr(ui.components, '__all__'):
        all_list = ui.components.__all__
        print(f"    ui.components.__all__ has {len(all_list)} items")
        if 'render_truck_loadings_table' in all_list:
            print(f"    'render_truck_loadings_table' IS in __all__ at position {all_list.index('render_truck_loadings_table')}")
        else:
            print(f"    'render_truck_loadings_table' NOT in __all__!")
            print(f"    Items in __all__:")
            for item in all_list[:30]:
                print(f"      - {item}")

    sys.exit(1)

# Git status check
print(f"\n[8] GIT STATUS")
try:
    import subprocess
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        if result.stdout.strip():
            print(f"  WARNING: Modified files detected:")
            for line in result.stdout.strip().split('\n')[:10]:
                print(f"    {line}")
        else:
            print(f"  OK: Working directory clean")

        # Check if behind remote
        print(f"  Checking if local is up to date...")
        subprocess.run(['git', 'fetch'], capture_output=True, text=True, timeout=10)
        status_result = subprocess.run(['git', 'status', '-uno'], capture_output=True, text=True, timeout=5)
        if 'behind' in status_result.stdout.lower():
            print(f"  WARNING: LOCAL IS BEHIND REMOTE!")
            print(f"  Run: git pull origin master")
        elif 'up to date' in status_result.stdout.lower() or 'up-to-date' in status_result.stdout.lower():
            print(f"  OK: Up to date with remote")

    else:
        print(f"  WARNING: Not a git repository or git not available")
except Exception as e:
    print(f"  WARNING: Could not check git status: {e}")

print("\n" + "=" * 80)
print("SUCCESS: ALL DIAGNOSTICS PASSED!")
print("=" * 80)
print("\nThe import works correctly on this machine.")
print("\nIf Streamlit still shows errors:")
print("  1. Close all Streamlit/Python processes")
print("  2. Delete __pycache__: Get-ChildItem -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force")
print("  3. Restart your terminal")
print("  4. Run: streamlit run ui/app.py")
