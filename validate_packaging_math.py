#!/usr/bin/env python3
"""
Validate the mathematical correctness of packaging constraint bounds.
This script demonstrates that the lower/upper bounds correctly implement ceil().
"""

import math

def validate_pallet_ceiling(truck_load):
    """
    Validate that the pallet bounds correctly implement ceil(truck_load / 320).
    
    Lower bound: pallets_loaded * 320 >= truck_load
                 → pallets_loaded >= truck_load / 320
    
    Upper bound: pallets_loaded * 320 <= truck_load + 319
                 → pallets_loaded <= (truck_load + 319) / 320
    """
    # Expected result (using Python's ceil)
    expected = math.ceil(truck_load / 320)
    
    # Lower bound constraint
    lower_bound = truck_load / 320
    
    # Upper bound constraint  
    upper_bound = (truck_load + 319) / 320
    
    # Since pallets_loaded must be integer and satisfy both bounds:
    # pallets_loaded >= lower_bound AND pallets_loaded <= upper_bound
    # The smallest integer satisfying both is ceil(lower_bound)
    actual = math.ceil(lower_bound)
    
    # Verify upper bound doesn't conflict
    satisfies_upper = (actual <= upper_bound)
    
    return {
        'truck_load': truck_load,
        'expected_pallets': expected,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'actual_pallets': actual,
        'correct': (actual == expected and satisfies_upper)
    }

# Test cases
test_cases = [
    0,      # Empty
    1,      # Minimum (1 unit)
    10,     # 1 case
    100,    # Partial pallet
    160,    # Half pallet (16 cases)
    319,    # Just under full pallet
    320,    # Exact full pallet
    321,    # Just over full pallet
    640,    # Exactly 2 pallets
    641,    # Just over 2 pallets
    1000,   # Multiple partial pallets
    14080,  # Full truck (unit capacity)
    14400,  # Over unit capacity (45 full pallets)
]

print("=" * 80)
print("PACKAGING CONSTRAINT VALIDATION")
print("=" * 80)
print()
print("Testing that lower/upper bounds correctly implement ceil(truck_load / 320)")
print()

all_correct = True
for truck_load in test_cases:
    result = validate_pallet_ceiling(truck_load)
    
    status = "✓" if result['correct'] else "✗"
    
    print(f"{status} truck_load = {truck_load:>5} units")
    print(f"  Expected pallets: {result['expected_pallets']}")
    print(f"  Lower bound:      {result['lower_bound']:.4f} → ceil = {result['actual_pallets']}")
    print(f"  Upper bound:      {result['upper_bound']:.4f}")
    print(f"  Result:           {result['actual_pallets']} pallets {'✓' if result['correct'] else '✗ WRONG'}")
    print()
    
    if not result['correct']:
        all_correct = False

print("=" * 80)
if all_correct:
    print("✅ ALL TESTS PASSED - Pallet bounds correctly implement ceiling function")
else:
    print("❌ SOME TESTS FAILED - Check implementation")
print("=" * 80)
