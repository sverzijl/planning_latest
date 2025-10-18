#!/usr/bin/env python
"""
Quick validation of labor calendar tests by running them directly.
"""

import sys
from datetime import date, timedelta
import pytest

# Run the specific test file
if __name__ == "__main__":
    print("=" * 70)
    print("Running Labor Calendar Regression Tests")
    print("=" * 70)
    print()

    # Run pytest programmatically
    exit_code = pytest.main([
        "tests/test_planning_ui_labor_calendar.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ])

    print()
    print("=" * 70)

    if exit_code == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ TESTS FAILED (exit code: {exit_code})")

    print("=" * 70)

    sys.exit(exit_code)
