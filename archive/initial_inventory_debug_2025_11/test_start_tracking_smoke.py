#!/usr/bin/env python3
"""Quick smoke test: Verify start tracking formulation works"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.unified_model_parser import UnifiedModelParser
from src.optimization.unified_node_model import UnifiedNodeModel

def test_start_tracking():
    """Verify start tracking variables and constraints are created."""

    # Parse data using unified parser
    parser = UnifiedModelParser(
        "data/examples/Network_Config_Unified.xlsx"
    )

    nodes, routes, trucks, forecast, labor_calendar, costs = parser.parse_all()

    # Build model (don't solve yet - just verify structure)
    start_date = date(2025, 10, 7)
    end_date = start_date + timedelta(days=6)

    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=trucks,
        use_batch_tracking=True,
        force_all_skus_daily=False,  # Binary SKU selection
    )

    # Build model (this will create product_start variables and start_detection_con)
    print("\n" + "="*80)
    print("Building model with start tracking formulation...")
    print("="*80)

    pyomo_model = model_wrapper.build_model()

    # Verify product_start variables exist
    assert hasattr(pyomo_model, 'product_start'), "Missing product_start variables!"
    print(f"✓ product_start variables created: {len(pyomo_model.product_start)} variables")

    # Verify start_detection_con constraints exist
    assert hasattr(pyomo_model, 'start_detection_con'), "Missing start_detection_con constraints!"
    print(f"✓ start_detection_con constraints created: {len(pyomo_model.start_detection_con)} constraints")

    # Verify production_day_linking_con exists
    assert hasattr(pyomo_model, 'production_day_linking_con'), "Missing production_day_linking_con!"
    print(f"✓ production_day_linking_con constraint created: {len(pyomo_model.production_day_linking_con)} constraints")

    # Verify num_products_produced is REMOVED
    assert not hasattr(pyomo_model, 'num_products_produced'), "Old num_products_produced still exists!"
    print(f"✓ num_products_produced correctly removed (replaced with product_start)")

    # Verify num_products_counting_con is REMOVED
    assert not hasattr(pyomo_model, 'num_products_counting_con'), "Old num_products_counting_con still exists!"
    print(f"✓ num_products_counting_con correctly removed")

    # Verify production_day_lower/upper_con are REMOVED
    assert not hasattr(pyomo_model, 'production_day_lower_con'), "Old production_day_lower_con still exists!"
    assert not hasattr(pyomo_model, 'production_day_upper_con'), "Old production_day_upper_con still exists!"
    print(f"✓ production_day_lower/upper_con correctly removed")

    print("\n" + "="*80)
    print("✅ ALL CHECKS PASSED - Start tracking formulation correctly implemented!")
    print("="*80)
    print("\nNext step: Run full test suite to verify no regressions")

    return True

if __name__ == "__main__":
    success = test_start_tracking()
    sys.exit(0 if success else 1)
