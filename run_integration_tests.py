#!/usr/bin/env python
"""Run integration tests to verify labor calendar extension fixes."""

import subprocess
import sys
from datetime import datetime

def run_test(test_name):
    """Run a single test and return exit code."""
    cmd = [
        "pytest",
        f"tests/test_labor_validation_integration.py::{test_name}",
        "-v", "-s"
    ]

    print(f"\n{'='*70}")
    print(f"Running: {test_name}")
    print(f"{'='*70}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode

def main():
    print("="*70)
    print("PHASE 2A: Integration Test Verification")
    print("="*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nVerifying that labor calendar extension fixed 3 failing tests...")

    # Run the 3 previously failing tests
    tests = [
        ("Test 1", "test_example_data_with_normal_horizon"),
        ("Test 2", "test_example_data_with_extended_horizon"),
        ("Test 3", "test_labor_validation_distinguishes_weekdays_vs_weekends"),
    ]

    results = {}
    for label, test_name in tests:
        results[label] = run_test(test_name)

    # Summary
    print("\n" + "="*70)
    print("Test Results Summary:")
    print("="*70)

    all_passed = True
    for label, test_name in tests:
        status = "PASS ✓" if results[label] == 0 else "FAIL ✗"
        print(f"{label} ({test_name[:40]}...): {status}")
        if results[label] != 0:
            all_passed = False

    # Run full suite
    print("\n" + "="*70)
    print("Running full integration test suite...")
    print("="*70)

    cmd = ["pytest", "tests/test_labor_validation_integration.py", "-v"]
    full_result = subprocess.run(cmd, capture_output=False)

    # Final status
    print("\n" + "="*70)
    print("Final Status:")
    print("="*70)

    if all_passed:
        print("SUCCESS: All 3 previously failing tests now pass! ✓")
        return 0
    else:
        print("FAILURE: Some tests still failing ✗")
        return 1

if __name__ == "__main__":
    sys.exit(main())
