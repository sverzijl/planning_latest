"""Verification that CBC -mipstart flag is now generated.

This directly tests the fix by running a simple solve with use_warmstart=True
and checking the CBC command line output for the -mipstart flag.
"""

import subprocess
import sys
from pathlib import Path

# Run the existing simple warmstart test
print("="*80)
print("VERIFYING CBC WARMSTART FIX")
print("="*80)

# First check if the test file exists
test_file = Path("test_warmstart_simple.py")
if not test_file.exists():
    print(f"ERROR: {test_file} not found")
    sys.exit(1)

print(f"\nRunning: {test_file}")
print("-"*80)

# Run the test and capture output
result = subprocess.run(
    [sys.executable, str(test_file)],
    capture_output=True,
    text=True,
    timeout=120
)

output = result.stdout + result.stderr

# Check for -mipstart in output
if "-mipstart" in output:
    print("\nSUCCESS: Found -mipstart flag in CBC command line!")
    print("\nRelevant output lines:")
    print("-"*80)
    for line in output.split('\n'):
        if 'command line' in line.lower() or 'mipstart' in line.lower():
            print(line)
    print("-"*80)
    print("\nWARMSTART FIX VERIFIED!")
    print("="*80)
    sys.exit(0)
else:
    print("\nFAILURE: -mipstart flag NOT found in CBC command line")
    print("\nSearching for 'command line' in output:")
    print("-"*80)
    found_cmdline = False
    for line in output.split('\n'):
        if 'command line' in line.lower():
            print(line)
            found_cmdline = True
    if not found_cmdline:
        print("(no command line found in output)")
    print("-"*80)
    print("\nWARMSTART FIX FAILED!")
    print("="*80)
    sys.exit(1)
