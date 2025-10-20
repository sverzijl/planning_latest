"""Smoke test for warmstart functionality - verifies basic integration works."""

import sys
from datetime import date, timedelta

# Test warmstart generator import
print("Testing warmstart generator import...")
try:
    from src.optimization.warmstart_generator import (
        generate_campaign_warmstart,
        create_default_warmstart,
        validate_warmstart_hints,
    )
    print("✓ Warmstart generator imports successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test basic warmstart generation
print("\nTesting warmstart generation...")
try:
    # Simple test data
    test_date = date(2025, 10, 20)  # Monday
    products = ['PROD_001', 'PROD_002', 'PROD_003']

    # Create demand forecast
    demand = {}
    for i in range(7):  # One week
        d = test_date + timedelta(days=i)
        for product in products:
            demand[('6122', product, d)] = 1000.0  # Uniform demand

    # Generate warmstart
    hints = create_default_warmstart(
        demand_forecast=demand,
        manufacturing_node_id='6122',
        products=products,
        start_date=test_date,
        end_date=test_date + timedelta(days=6),
        max_daily_production=19600,
    )

    print(f"✓ Generated {len(hints)} warmstart hints")

    # Check structure
    assert isinstance(hints, dict), "Hints should be a dictionary"
    assert len(hints) > 0, "Should generate some hints"

    # Check values are binary
    non_binary = [v for v in hints.values() if v not in [0, 1]]
    assert len(non_binary) == 0, f"All values should be 0 or 1, found: {non_binary}"

    print(f"✓ All {len(hints)} hints are binary (0 or 1)")

    # Validate hints
    validate_warmstart_hints(hints, products, test_date, test_date + timedelta(days=6))
    print("✓ Hints pass validation")

except Exception as e:
    print(f"✗ Warmstart generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test UnifiedNodeModel has warmstart methods
print("\nTesting UnifiedNodeModel warmstart integration...")
try:
    from src.optimization.unified_node_model import UnifiedNodeModel

    # Check methods exist
    assert hasattr(UnifiedNodeModel, '_generate_warmstart'), "Missing _generate_warmstart method"
    assert hasattr(UnifiedNodeModel, '_apply_warmstart'), "Missing _apply_warmstart method"

    print("✓ UnifiedNodeModel has warmstart methods")

    # Check solve() signature accepts warmstart parameters
    import inspect
    sig = inspect.signature(UnifiedNodeModel.solve)
    params = list(sig.parameters.keys())

    assert 'use_warmstart' in params, "solve() missing use_warmstart parameter"
    assert 'warmstart_hints' in params, "solve() missing warmstart_hints parameter"

    print("✓ solve() method has warmstart parameters")
    print(f"  Parameters: {params}")

except Exception as e:
    print(f"✗ UnifiedNodeModel integration check failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("✅ ALL SMOKE TESTS PASSED")
print("="*70)
print("\nWarmstart functionality is properly integrated:")
print("  - warmstart_generator.py: Working")
print("  - UnifiedNodeModel._generate_warmstart(): Present")
print("  - UnifiedNodeModel._apply_warmstart(): Present")
print("  - UnifiedNodeModel.solve(use_warmstart=True): Supported")
print("\nNext steps:")
print("  1. Run integration test with warmstart enabled")
print("  2. Measure solve time improvement")
print("  3. Validate SKU reduction behavior")
print("="*70)
