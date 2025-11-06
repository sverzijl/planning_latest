#!/usr/bin/env python3
"""
Pre-Push Verification Script

Run this BEFORE pushing any optimization model changes.
Prevents pushing code with unrealistic solutions.

Usage:
    python verify_before_push.py

Exit codes:
    0 = All checks pass (safe to push)
    1 = Verification failed (DO NOT PUSH)
"""

import subprocess
import sys

print("="*80)
print("PRE-PUSH VERIFICATION")
print("="*80)

exit_code = 0

# Check 1: Solution Reasonableness Tests
print("\n1. Running solution reasonableness tests...")
print("   Command: pytest tests/test_solution_reasonableness.py -v")
result = subprocess.run(
    ['pytest', 'tests/test_solution_reasonableness.py', '-v', '--tb=short'],
    capture_output=False
)

if result.returncode != 0:
    print("\n❌ SOLUTION REASONABLENESS TESTS FAILED")
    print("   Solutions are economically nonsensical")
    print("   DO NOT PUSH - Fix formulation bugs first")
    exit_code = 1
else:
    print("\n✅ Solution reasonableness tests passed")

# Check 2: Integration Tests
print("\n2. Running integration tests...")
print("   Command: pytest tests/test_validation_integration.py -v")
result = subprocess.run(
    ['pytest', 'tests/test_validation_integration.py', '-v', '--tb=line'],
    capture_output=False
)

if result.returncode != 0:
    print("\n❌ INTEGRATION TESTS FAILED")
    print("   DO NOT PUSH")
    exit_code = 1
else:
    print("\n✅ Integration tests passed")

# Check 3: Pallet Tests
print("\n3. Running pallet tests...")
print("   Command: pytest tests/test_pallet_entry_costs.py -v")
result = subprocess.run(
    ['pytest', 'tests/test_pallet_entry_costs.py', '-v', '--tb=line'],
    capture_output=False
)

if result.returncode != 0:
    print("\n❌ PALLET TESTS FAILED")
    print("   DO NOT PUSH")
    exit_code = 1
else:
    print("\n✅ Pallet tests passed")

# Summary
print("\n" + "="*80)
if exit_code == 0:
    print("✅ ALL VERIFICATION PASSED - SAFE TO PUSH")
    print("="*80)
else:
    print("❌ VERIFICATION FAILED - DO NOT PUSH")
    print("="*80)
    print("\nFix the failing tests before pushing.")
    print("This protects users from broken code.")

sys.exit(exit_code)
