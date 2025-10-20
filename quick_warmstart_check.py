#!/usr/bin/env python
"""Quick check: Does -mipstart flag appear when we use UnifiedNodeModel?

Uses existing test fixture data to avoid file I/O issues.
"""

import subprocess
import sys

# Run an existing warmstart integration test that actually solves
test_cmd = [
    sys.executable, "-m", "pytest",
    "tests/test_baseline_labor_non_fixed.py",  # Known working test
    "-xvs", "--tb=short", "-k", "test_",
    "--capture=no"  # Show all output including solver output
]

print("="*80)
print("RUNNING INTEGRATION TEST WITH TEE=TRUE TO SEE CBC OUTPUT")
print("="*80)
print(f"\nCommand: {' '.join(test_cmd)}")
print("\n" + "-"*80)

result = subprocess.run(
    test_cmd,
    capture_output=True,
    text=True,
    timeout=120
)

output = result.stdout + result.stderr

# Check for -mipstart in output
if "-mipstart" in output:
    print("\n\nSUCCESS: -mipstart flag found!")
    print("="*80)
    print("CBC COMMAND LINE:")
    for line in output.split('\n'):
        if 'command line' in line.lower():
            print(line)
    print("="*80)
    print("\nMIPSTART MESSAGES:")
    for line in output.split('\n'):
        if 'mipstart' in line.lower():
            print(line)
    print("="*80)
else:
    print("\n\nNO -mipstart FLAG FOUND")
    print("="*80)
    print("Searching for CBC command line...")
    for line in output.split('\n'):
        if 'command line' in line.lower():
            print(line)
    print("="*80)

print(f"\nTest exit code: {result.returncode}")
sys.exit(result.returncode)
