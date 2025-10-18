"""
Simple material balance check on minimal test case.
"""

import sys
sys.path.insert(0, 'src')

from tests.test_minimal_material_balance import (
    test_minimal_single_product_single_destination,
    test_minimal_single_product_with_hub
)

print("=" * 80)
print("SIMPLE BALANCE CHECK ON MINIMAL TESTS")
print("=" * 80)
print()

print("TEST 1: Direct Route (6122 → 6110)")
print("-" * 80)
try:
    test_minimal_single_product_single_destination()
    print("✓ PASSED")
except AssertionError as e:
    print(f"✗ FAILED: {e}")
print()

print("TEST 2: Hub Route (6122 → 6125 → 6123)")
print("-" * 80)
try:
    test_minimal_single_product_with_hub()
    print("✓ PASSED")
except AssertionError as e:
    print(f"✗ FAILED: {e}")
print()

print("=" * 80)
print("TESTS COMPLETE")
print("=" * 80)
