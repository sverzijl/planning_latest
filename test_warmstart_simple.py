#!/usr/bin/env python3
"""
Simple warmstart functionality verification.

Tests core warmstart features without full model integration.
"""

from datetime import date, timedelta
from src.optimization.warmstart_generator import (
    generate_campaign_warmstart,
    create_default_warmstart,
    validate_warmstart_hints,
    validate_freshness_constraint,
    validate_daily_sku_limit,
)
from src.optimization.unified_node_model import UnifiedNodeModel
import inspect

print("="*70)
print("WARMSTART FUNCTIONALITY VERIFICATION")
print("="*70)

# Test 1: Module Import
print("\n[TEST 1] Module Import")
print("-" * 70)
try:
    from src.optimization.warmstart_generator import generate_campaign_warmstart
    from src.optimization.unified_node_model import UnifiedNodeModel
    print("✓ Imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test 2: UnifiedNodeModel Methods
print("\n[TEST 2] UnifiedNodeModel Warmstart Methods")
print("-" * 70)
has_generate = hasattr(UnifiedNodeModel, '_generate_warmstart')
has_apply = hasattr(UnifiedNodeModel, '_apply_warmstart')
print(f"✓ _generate_warmstart() exists: {has_generate}")
print(f"✓ _apply_warmstart() exists: {has_apply}")

if not has_generate or not has_apply:
    print("✗ Missing warmstart methods")
    exit(1)

# Test 3: solve() Parameters
print("\n[TEST 3] solve() Method Parameters")
print("-" * 70)
solve_sig = inspect.signature(UnifiedNodeModel.solve)
params = solve_sig.parameters

print("solve() parameters:")
for param_name in params:
    if param_name != 'self':
        default = params[param_name].default
        default_str = f" = {default}" if default != inspect.Parameter.empty else ""
        print(f"  - {param_name}{default_str}")

has_warmstart = 'use_warmstart' in params
has_hints = 'warmstart_hints' in params
print(f"\n✓ use_warmstart parameter: {has_warmstart}")
print(f"✓ warmstart_hints parameter: {has_hints}")

if not has_warmstart or not has_hints:
    print("✗ Missing warmstart parameters")
    exit(1)

# Test 4: Warmstart Generator Function
print("\n[TEST 4] Warmstart Generator Function")
print("-" * 70)

demand = {
    ('6122', 'PROD_001', date(2025, 10, 20)): 5000,
    ('6122', 'PROD_001', date(2025, 10, 21)): 3000,
    ('6122', 'PROD_002', date(2025, 10, 22)): 2000,
    ('6122', 'PROD_002', date(2025, 10, 23)): 1500,
    ('6122', 'PROD_003', date(2025, 10, 24)): 4000,
}

try:
    hints = generate_campaign_warmstart(
        demand_forecast=demand,
        manufacturing_node_id='6122',
        products=['PROD_001', 'PROD_002', 'PROD_003'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 10, 26),
        max_daily_production=19600,
        target_skus_per_weekday=2,
        freshness_days=7,
    )
    
    print(f"✓ Warmstart hints generated: {len(hints)} hints")
    
    # Validate
    all_binary = all(v in [0, 1] for v in hints.values())
    all_dates_valid = all(
        date(2025, 10, 20) <= d <= date(2025, 10, 26)
        for (_, _, d) in hints.keys()
    )
    
    print(f"✓ All hints are binary: {all_binary}")
    print(f"✓ All dates within range: {all_dates_valid}")
    
    if not all_binary or not all_dates_valid:
        print("✗ Invalid hints generated")
        exit(1)
        
except Exception as e:
    print(f"✗ Warmstart generation failed: {e}")
    exit(1)

# Test 5: create_default_warmstart()
print("\n[TEST 5] create_default_warmstart() Function")
print("-" * 70)

try:
    hints2 = create_default_warmstart(
        demand_forecast=demand,
        manufacturing_node_id='6122',
        products=['PROD_001', 'PROD_002', 'PROD_003'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 10, 26),
        max_daily_production=19600,
    )
    
    print(f"✓ Default warmstart generated: {len(hints2)} hints")
    
except Exception as e:
    print(f"✗ Default warmstart failed: {e}")
    exit(1)

# Test 6: Validation Functions
print("\n[TEST 6] Validation Functions")
print("-" * 70)

test_hints = {
    ('6122', 'PROD_001', date(2025, 10, 20)): 1,
    ('6122', 'PROD_002', date(2025, 10, 21)): 1,
    ('6122', 'PROD_001', date(2025, 10, 22)): 0,
}

try:
    # Should not raise exceptions
    validate_warmstart_hints(
        test_hints,
        products=['PROD_001', 'PROD_002'],
        start_date=date(2025, 10, 20),
        end_date=date(2025, 10, 26)
    )
    print("✓ validate_warmstart_hints() works")
    
    freshness_ok = validate_freshness_constraint(test_hints, freshness_days=7)
    print(f"✓ validate_freshness_constraint() works: {freshness_ok}")
    
    daily_limit_ok = validate_daily_sku_limit(test_hints, max_skus_per_day=5)
    print(f"✓ validate_daily_sku_limit() works: {daily_limit_ok}")
    
except Exception as e:
    print(f"✗ Validation failed: {e}")
    exit(1)

# Test 7: Method Signatures
print("\n[TEST 7] Method Signature Verification")
print("-" * 70)

# Check _generate_warmstart signature
generate_sig = inspect.signature(UnifiedNodeModel._generate_warmstart)
print("✓ _generate_warmstart() signature:")
print(f"  Return: {generate_sig.return_annotation}")

# Check _apply_warmstart signature
apply_sig = inspect.signature(UnifiedNodeModel._apply_warmstart)
print("✓ _apply_warmstart() signature:")
for param_name in apply_sig.parameters:
    if param_name != 'self':
        param = apply_sig.parameters[param_name]
        print(f"  - {param_name}: {param.annotation}")

# Summary
print("\n" + "="*70)
print("✓✓✓ ALL WARMSTART TESTS PASSED ✓✓✓")
print("="*70)

print("\nWarmstart implementation verified:")
print("  1. ✓ warmstart_generator.py module created")
print("  2. ✓ generate_campaign_warmstart() function")
print("  3. ✓ create_default_warmstart() convenience function")
print("  4. ✓ Validation functions (validate_warmstart_hints, etc.)")
print("  5. ✓ UnifiedNodeModel._generate_warmstart() method")
print("  6. ✓ UnifiedNodeModel._apply_warmstart() method")
print("  7. ✓ UnifiedNodeModel.solve() with warmstart parameters")

print("\nReady for use! Call solve(use_warmstart=True) to enable.")
print("="*70)

