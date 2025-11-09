"""Minimal reproduction case for end-of-horizon inventory bug.

Tests progressively complex scenarios to identify which constraint causes
the model to produce excess inventory at end of planning horizon.
"""

import pytest
from datetime import date, timedelta
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products


def test_minimal_case_single_breadroom_single_day_demand():
    """
    MINIMAL CASE: Simplest possible scenario
    - 7-day horizon
    - 1 manufacturing, 1 breadroom
    - 1 product
    - 1-day transit
    - Demand ONLY on day 7

    Expected: Model produces ~1,000 units on day 6, end inventory ≈ 0
    """

    # Setup dates
    day_1 = date(2025, 1, 1)
    day_7 = date(2025, 1, 7)

    # Manufacturing node
    manufacturing = UnifiedNode(
        id='MFG',
        name='Manufacturing Site',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            has_demand=False,
            can_store=True,
            requires_trucks=False,
            storage_mode=StorageMode.AMBIENT,
            production_rate_per_hour=1400.0,
        ),
    )

    # Breadroom node
    breadroom = UnifiedNode(
        id='BR1',
        name='Breadroom 1',
        capabilities=NodeCapabilities(
            can_manufacture=False,
            has_demand=True,
            can_store=True,
            requires_trucks=False,
            storage_mode=StorageMode.AMBIENT,
            production_rate_per_hour=None,
        ),
    )

    # Route: MFG → BR1 (1-day transit)
    route = UnifiedRoute(
        id='MFG-BR1',
        origin_node_id='MFG',
        destination_node_id='BR1',
        transit_days=1.0,
        cost_per_unit=1.0,
        transport_mode=TransportMode.AMBIENT,
    )

    # Forecast: 1,000 units demand on day 7 ONLY
    forecast = Forecast(
        name='Minimal Test',
        entries=[
            ForecastEntry(
                location_id='BR1',
                product_id='PROD1',
                forecast_date=day_7,
                quantity=1000.0
            )
        ]
    )

    # Labor calendar: 12 hours/day, regular rate
    labor_days = []
    for day_offset in range(7):
        curr_date = day_1 + timedelta(days=day_offset)
        labor_days.append(LaborDay(
            date=curr_date,
            is_fixed_day=True,
            fixed_hours=12.0,
            overtime_hours=2.0,
            minimum_hours=4.0,
            regular_rate=25.0,
            overtime_rate=37.50,
            non_fixed_rate=50.0,
        ))

    labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

    # Cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=5.0,
        shortage_penalty_per_unit=10000.0,
    )

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=[manufacturing, breadroom],
        routes=[route],
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=day_1,
        end_date=day_7,
        truck_schedules=None,  # NO truck constraints (simplest)
        initial_inventory=None,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Solve
    print("\n" + "="*80)
    print("MINIMAL REPRODUCTION TEST")
    print("="*80)
    print(f"Horizon: {day_1} to {day_7} (7 days)")
    print(f"Nodes: 2 (MFG, BR1)")
    print(f"Routes: 1 (MFG → BR1, 1-day transit)")
    print(f"Demand: 1,000 units on day 7 ONLY")
    print(f"Truck constraints: NONE")
    print()

    result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

    print(f"Solved: {result.termination_condition} in {result.solve_time_seconds:.1f}s")

    # Extract solution
    solution = model.get_solution()

    # Get end-of-horizon inventory
    cohort_inv = solution.get('inventory_state', {})
    end_inventory = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == day_7 and qty > 0.01)

    # Get total production
    total_production = sum(solution.get('production_by_date_product', {}).values())

    # Get shortage
    total_shortage = solution.get('total_shortage_units', 0)

    # Get demand consumed
    total_consumed = sum(solution.get('cohort_demand_consumption', {}).values())

    print()
    print("RESULTS:")
    print(f"  Total production: {total_production:,.0f} units")
    print(f"  Demand (forecast): 1,000 units")
    print(f"  Demand consumed: {total_consumed:,.0f} units")
    print(f"  Shortage: {total_shortage:,.0f} units")
    print(f"  End-of-horizon inventory (day 7): {end_inventory:,.0f} units")
    print()

    # Calculate excess
    demand_on_day7 = 1000.0
    excess = end_inventory - (demand_on_day7 - total_consumed)

    print("VALIDATION:")
    print(f"  Expected end inventory: ~0 units (all consumed for day 7 demand)")
    print(f"  Actual end inventory: {end_inventory:,.0f} units")

    if end_inventory > 100:
        print(f"\n  ❌ BUG REPRODUCED IN MINIMAL CASE!")
        print(f"     {end_inventory:,.0f} units of excess inventory")
        print(f"     Cost: ${end_inventory * 5:,.0f} wasted")
        print(f"     This violates cost minimization with perfect foresight")

        # Show production by date
        prod_by_date = {}
        for (prod_date, product), qty in solution.get('production_by_date_product', {}).items():
            prod_by_date[prod_date] = prod_by_date.get(prod_date, 0) + qty

        print(f"\n  Production by date:")
        for prod_date in sorted(prod_by_date.keys()):
            print(f"    {prod_date}: {prod_by_date[prod_date]:,.0f} units")

        pytest.fail(f"Excess inventory {end_inventory:,.0f} units violates cost minimization")
    else:
        print(f"\n  ✓ NO BUG in minimal case (end inventory < 100 units)")
        print(f"     Bug requires more complex scenario")

    print("\n" + "="*80)


def test_minimal_with_multi_day_demand():
    """
    Add complexity: Demand on multiple days
    - 7-day horizon
    - Demand on days 1, 3, 5, 7 (500 units each = 2,000 total)

    Expected: Production matches demand, minimal end inventory
    """

    day_1 = date(2025, 1, 1)
    day_7 = date(2025, 1, 7)

    # Same nodes and route as minimal case
    manufacturing = UnifiedNode(
        id='MFG', name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True, has_demand=False, can_store=True,
            requires_trucks=False, storage_mode=StorageMode.AMBIENT,
            production_rate_per_hour=1400.0,
        ),
    )

    breadroom = UnifiedNode(
        id='BR1', name='Breadroom',
        capabilities=NodeCapabilities(
            can_manufacture=False, has_demand=True, can_store=True,
            requires_trucks=False, storage_mode=StorageMode.AMBIENT,
        ),
    )

    route = UnifiedRoute(
        id='MFG-BR1',
        origin_node_id='MFG', destination_node_id='BR1',
        transit_days=1.0, cost_per_unit=1.0,
        transport_mode=TransportMode.AMBIENT,
    )

    # Forecast: Demand on days 1, 3, 5, 7
    forecast = Forecast(name='Multi-day', entries=[
        ForecastEntry('BR1', 'PROD1', day_1 + timedelta(days=0), 500.0),  # Day 1
        ForecastEntry('BR1', 'PROD1', day_1 + timedelta(days=2), 500.0),  # Day 3
        ForecastEntry('BR1', 'PROD1', day_1 + timedelta(days=4), 500.0),  # Day 5
        ForecastEntry('BR1', 'PROD1', day_1 + timedelta(days=6), 500.0),  # Day 7
    ])

    # Labor calendar
    labor_days = [
        LaborDay(day_1 + timedelta(days=i), True, 12.0, 2.0, 4.0, 25.0, 37.5, 50.0)
        for i in range(7)
    ]
    labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

    cost_structure = CostStructure(
        production_cost_per_unit=5.0,
        shortage_penalty_per_unit=10000.0,
    )

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=[manufacturing, breadroom], routes=[route],
        forecast=forecast, labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=day_1, end_date=day_7,
        truck_schedules=None, initial_inventory=None,
        use_pallet_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    )

    print("\n" + "="*80)
    print("TEST: Multi-Day Demand")
    print("="*80)
    print("Demand: Days 1, 3, 5, 7 (500 units each = 2,000 total)")

    result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)
    solution = model.get_solution()

    cohort_inv = solution.get('inventory_state', {})
    end_inventory = sum(qty for (n, p, pd, cd, s), qty in cohort_inv.items() if cd == day_7)
    total_production = sum(solution.get('production_by_date_product', {}).values())

    print(f"\nResults:")
    print(f"  Production: {total_production:,.0f} units")
    print(f"  Total demand: 2,000 units")
    print(f"  End inventory: {end_inventory:,.0f} units")

    if end_inventory > 200:  # Allow some slack for solver precision
        print(f"\n  ❌ BUG REPRODUCED: {end_inventory:,.0f} excess units")
        pytest.fail(f"Excess inventory in multi-day case")
    else:
        print(f"\n  ✓ Minimal excess ({end_inventory:,.0f} units)")

    print("="*80)


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, '-v', '-s']))
