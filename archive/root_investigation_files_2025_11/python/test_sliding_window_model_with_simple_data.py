#!/usr/bin/env python3
"""
Test the ACTUAL SlidingWindowModel class with simple test data.

This test uses the real SlidingWindowModel implementation (not a simplified version)
but with simple, controlled test data. This will reveal if the bug is in:
1. The SlidingWindowModel implementation itself
2. The real data

If this test produces > 0: Bug is in real data
If this test produces = 0: Bug is in SlidingWindowModel class
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.optimization.sliding_window_model import SlidingWindowModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.product import Product
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure


def test_real_sliding_window_model_simple_data():
    """Test REAL SlidingWindowModel class with simple data."""

    print("=" * 80)
    print("TEST: REAL SlidingWindowModel CLASS WITH SIMPLE DATA")
    print("=" * 80)

    # Simple network: MFG → HUB → DEMAND
    start_date = date(2025, 11, 3)
    end_date = start_date + timedelta(days=9)  # 10 days

    print(f"\nSetup:")
    print(f"  Using REAL SlidingWindowModel class")
    print(f"  Planning: {start_date} to {end_date}")

    # Create nodes
    mfg_node = UnifiedNode(
        id='MFG',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=1400,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=False
        )
    )

    hub_node = UnifiedNode(
        id='HUB',
        name='Hub',
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=False
        )
    )

    demand_node = UnifiedNode(
        id='DEMAND',
        name='Demand Node',
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=True
        )
    )

    nodes = [mfg_node, hub_node, demand_node]  # Pass as list, not dict

    # Create routes
    routes = [
        UnifiedRoute(
            id='R1',
            origin_node_id='MFG',
            destination_node_id='HUB',
            transit_days=1,
            transport_mode=TransportMode.AMBIENT,
            cost_per_unit=0.10
        ),
        UnifiedRoute(
            id='R2',
            origin_node_id='HUB',
            destination_node_id='DEMAND',
            transit_days=1,
            transport_mode=TransportMode.AMBIENT,
            cost_per_unit=0.10
        )
    ]

    # Create products
    products = {
        'PROD_A': Product(id='PROD_A', sku='PROD_A', name='Product A', units_per_mix=415),
        'PROD_B': Product(id='PROD_B', sku='PROD_B', name='Product B', units_per_mix=415),
    }

    # Create simple forecast
    forecast_entries = []
    for day_offset in range(10):
        demand_date = start_date + timedelta(days=day_offset)
        # Demand starts day 3 (after 2-day transit)
        qty = 200 if day_offset >= 2 else 0

        for prod_id in ['PROD_A', 'PROD_B']:
            forecast_entries.append(
                ForecastEntry(
                    location_id='DEMAND',
                    product_id=prod_id,
                    forecast_date=demand_date,
                    quantity=qty
                )
            )

    forecast = Forecast(name='Simple Test Forecast', entries=forecast_entries)

    total_demand = sum(e.quantity for e in forecast_entries)
    print(f"  Total demand: {total_demand} units")

    # Create labor calendar
    labor_days = []
    for day_offset in range(10):
        labor_date = start_date + timedelta(days=day_offset)
        is_weekend = labor_date.weekday() >= 5

        labor_days.append(LaborDay(
            date=labor_date,
            fixed_hours=0 if is_weekend else 12,
            overtime_hours=2 if not is_weekend else 8,
            regular_rate=20.0,
            overtime_rate=30.0,
            non_fixed_rate=40.0
        ))

    labor_calendar = LaborCalendar(name='Test Labor', labor_days=labor_days)

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=1.30,
        shortage_penalty_per_unit=10.00
    )

    # Initial inventory (distributed across network like real data)
    initial_inventory = {
        ('MFG', 'PROD_A', 'ambient'): 100,
        ('HUB', 'PROD_A', 'ambient'): 150,
        ('DEMAND', 'PROD_A', 'ambient'): 250,  # ← At demand node
        ('MFG', 'PROD_B', 'ambient'): 100,
    }

    total_init_inv = sum(initial_inventory.values())
    print(f"  Total init_inv: {total_init_inv} units")
    print(f"  Required production: ~{total_demand - total_init_inv} units")

    # Build model using REAL SlidingWindowModel class
    print(f"\n Building model with REAL SlidingWindowModel...")

    model = SlidingWindowModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=[],  # No trucks for simplicity
        initial_inventory=initial_inventory,
        inventory_snapshot_date=start_date,
        allow_shortages=True,
        use_pallet_tracking=False,  # Simplify
        use_truck_pallet_tracking=False
    )

    # Solve
    print(f"\nSolving...")
    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.02,
        tee=False
    )

    print(f"  Status: {result.termination_condition}")
    print(f"  Objective: ${result.objective_value:,.2f}")

    # Get solution
    solution = model.get_solution()

    total_production = solution.total_production
    total_shortage = solution.total_shortage_units

    print(f"\nRESULTS:")
    print(f"  Total demand: {total_demand}")
    print(f"  Total init_inv: {total_init_inv}")
    print(f"  Total production: {total_production:.0f}")
    print(f"  Total shortage: {total_shortage:.0f}")

    print(f"\n" + "="*80)

    # CRITICAL CHECK
    expected_min_production = total_demand - total_init_inv  # 3200 - 600 = 2600

    if total_production < expected_min_production - 500:
        print(f"❌ BUG FOUND IN SlidingWindowModel CLASS!")
        print(f"  Expected: ~{expected_min_production}")
        print(f"  Actual: {total_production:.0f}")
        print(f"\n  The SlidingWindowModel implementation has a bug!")
        print(f"  Even with simple data, it produces zero/low production.")
        print(f"  But our incremental tests (Levels 1-12) all work.")
        print(f"\n  This means the bug is in how SlidingWindowModel")
        print(f"  implements features differently than our tests.")
        return False
    else:
        print(f"✅ SlidingWindowModel produces correctly with simple data!")
        print(f"  Production: {total_production:.0f} (expected ~{expected_min_production})")
        print(f"\n  This means the bug is in the REAL DATA, not the model class!")
        return True


if __name__ == "__main__":
    success = test_real_sliding_window_model_simple_data()

    if success:
        print("\n" + "="*80)
        print("CONCLUSION: Bug is in REAL DATA, not SlidingWindowModel class")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("CONCLUSION: Bug is in SlidingWindowModel implementation")
        print("="*80)

    sys.exit(0 if success else 1)
