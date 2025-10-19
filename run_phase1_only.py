#!/usr/bin/env python3
"""Quick validation of Phase 1 tests only (non-fixed day fix)."""

import subprocess
import sys
from pathlib import Path


def run_test(test_path, name):
    """Run a single test and return result."""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}\n")

    venv_python = Path("/home/sverzijl/planning_latest/venv/bin/python")
    cmd = [str(venv_python), "-m", "pytest", test_path, "-v", "-s"]

    try:
        result = subprocess.run(cmd, timeout=60)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: Test exceeded 60 seconds")
        return False


def main():
    """Run Phase 1 tests only."""
    print("="*80)
    print("PHASE 1 VALIDATION: NON-FIXED DAY FIX")
    print("="*80)
    print("\nRunning 3 critical tests that were previously INFEASIBLE...\n")

    tests = [
        ('tests/test_labor_cost_piecewise.py::test_piecewise_non_fixed_day_below_minimum',
         'Test 1: Weekend Production Below Minimum'),
        ('tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_included',
         'Test 2: Public Holiday Overhead (Above Minimum)'),
        ('tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_below_minimum',
         'Test 3: Public Holiday Overhead (Below Minimum)'),
    ]

    results = []
    for test_path, test_name in tests:
        passed = run_test(test_path, test_name)
        results.append((test_name, passed))

    # Summary
    print("\n" + "="*80)
    print("PHASE 1 RESULTS SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {test_name:50s}: {status}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print("\n" + "="*80)
    if passed_count == total_count:
        print(f"SUCCESS: All {total_count} tests PASSED!")
        print("The fix has resolved the non-fixed day infeasibility issue.")
        sys.exit(0)
    else:
        print(f"FAILURE: {passed_count}/{total_count} tests passed")
        print(f"The fix may not have fully resolved the issue.")
        sys.exit(1)


if __name__ == "__main__":
    main()
