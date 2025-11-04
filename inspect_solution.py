#!/usr/bin/env python3
"""
Inspect the solved model to understand zero production.

Checks:
1. Production variable values
2. Inventory variable values
3. Demand_consumed variable values
4. Material balance verification
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pyomo.environ import value
import pyomo.environ as pyo


def inspect_solution():
    """Inspect the last solved model."""

    # Access the model from the test
    # For now, let's create a simple inspection of what we know

    print("=" * 80)
    print("SOLUTION INSPECTION")
    print("=" * 80)

    print("\nKnown facts from test output:")
    print("  Total demand: 346,687 units")
    print("  Total production: 0 units (extracted)")
    print("  Total shortage: 0 units")
    print("  Fill rate: 100%")
    print("  Initial inventory: 49,581 units")

    print("\nMATHEMATICAL IMPOSSIBILITY:")
    print("  Demand (346,687) > Initial Inventory (49,581)")
    print("  But: Production (0) + Shortage (0)")
    print("  How is demand satisfied?")

    print("\nHYPOTHESES:")
    print("  1. Production extraction bug - production variables have values but not extracted")
    print("  2. Material balance bug - demand_consumed not linked to inventory")
    print("  3. Ghost inventory - initial inventory counted multiple times")
    print("  4. Disposal bug - disposing inventory that should be used")

    print("\nTO INVESTIGATE:")
    print("  1. Check if model.production variables have non-zero values")
    print("  2. Check demand_consumed values vs inventory values")
    print("  3. Check if material balance constraints are actually enforced")
    print("  4. Check disposal variable values")

    print("\n" + "=" * 80)
    print("RECOMMENDATION: Add diagnostic output to extract_solution()")
    print("=" * 80)

    print("\nAdd to sliding_window_model.py extract_solution():")
    print("""
# After extracting production:
print(f"DEBUG: Production variables in model: {len(model.production) if hasattr(model, 'production') else 0}")
if hasattr(model, 'production'):
    non_zero_prod = sum(1 for key in model.production if value(model.production[key]) > 0.01)
    print(f"DEBUG: Non-zero production variables: {non_zero_prod}")
    if non_zero_prod > 0:
        print(f"DEBUG: Sample production values:")
        count = 0
        for key in model.production:
            val = value(model.production[key])
            if val > 0.01:
                print(f"  production{key} = {val:.2f}")
                count += 1
                if count >= 5:
                    break
""")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    inspect_solution()
