#!/usr/bin/env python3
"""
Test VerifiedSlidingWindowModel with REAL data.

This is THE test - if VerifiedModel produces > 0 with real data,
we've successfully replaced the buggy SlidingWindowModel!
"""

import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.optimization.verified_sliding_window_model import VerifiedSlidingWindowModel
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from tests.conftest import create_test_products


def main():
    print("=" * 80)
    print("TESTING VERIFIED MODEL WITH REAL DATA")
    print("=" * 80)

    # Load real data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    print(f"\nData loaded:")
    print(f"  Forecast entries: {len(forecast.entries)}")
    print(f"  Locations: {len(locations)}")
    print(f"  Routes: {len(routes)}")

    # Get inventory
    from src.parsers.inventory_parser import InventoryParser
    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()
    inventory_snapshot_date = inventory_snapshot.snapshot_date
    initial_inventory = inventory_snapshot.to_optimization_dict()

    print(f"  Initial inventory: {len(initial_inventory)} entries")
    print(f"  Snapshot date: {inventory_snapshot_date}")

    # Convert to unified format
    from src.models.location import LocationType

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)

    # Create products
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    print(f"  Nodes (unified): {len(nodes)}")
    print(f"  Products: {len(products)}")

    # Set planning horizon
    planning_start = inventory_snapshot_date
    planning_end = planning_start + timedelta(weeks=4)

    # Filter forecast to horizon
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start <= e.forecast_date <= planning_end
    )

    print(f"\nPlanning horizon: {planning_start} to {planning_end}")
    print(f"  Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"  Initial inventory: {sum(initial_inventory.values()):,.0f} units")

    # Build VerifiedSlidingWindowModel
    print(f"\nBuilding VerifiedSlidingWindowModel...")

    import time
    build_start = time.time()

    model = VerifiedSlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=[],  # Skip for now
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=False,
        use_truck_pallet_tracking=False
    )

    print(f"  Initialization took: {time.time() - build_start:.1f}s")
    print(f"  Now building Pyomo model...")

    build_model_start = time.time()
    pyomo_model = model.build_model()
    print(f"  Model building took: {time.time() - build_model_start:.1f}s")

    # Solve with optimized MIP settings
    print(f"\nSolving with optimized HiGHS MIP settings...")
    from pyomo.environ import SolverFactory
    solver = SolverFactory('appsi_highs')

    # Optimized settings for MIP (from HiGHS expert skill)
    solver.highs_options = {
        'presolve': 'on',
        'time_limit': 30.0,
        'parallel': 'on',
        'mip_rel_gap': 0.02,  # 2% gap
    }

    print(f"  Presolve: ON, Parallel: ON, MIP gap: 2%, Time: 30s")

    import time
    start_time = time.time()
    result = solver.solve(pyomo_model, tee=False, load_solutions=False)
    solve_time = time.time() - start_time

    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Status: {result.solver.termination_condition}")

    # Load solution variables
    try:
        solver.load_vars()
        print(f"  Solution loaded successfully")
    except Exception as e:
        print(f"  Warning loading solution: {e}")

    # Extract solution
    solution = model.extract_solution(pyomo_model)

    print(f"\n" + "="*80)
    print(f"RESULTS WITH REAL DATA")
    print(f"="*80)
    print(f"  Total demand: {demand_in_horizon:,.0f} units")
    print(f"  Total production: {solution['total_production']:,.0f} units")
    print(f"  Total shortage: {solution['total_shortage']:,.0f} units")

    fill_rate = ((demand_in_horizon - solution['total_shortage']) / demand_in_horizon * 100) if demand_in_horizon > 0 else 0
    print(f"  Fill rate: {fill_rate:.1f}%")

    print(f"\n" + "="*80)

    if solution['total_production'] > 0:
        print(f"✅ SUCCESS! VERIFIED MODEL PRODUCES WITH REAL DATA!")
        print(f"   Production: {solution['total_production']:,.0f} units")
        print(f"   Fill rate: {fill_rate:.1f}%")
        print(f"\n   The VerifiedSlidingWindowModel WORKS!")
        print(f"   Ready to replace buggy SlidingWindowModel!")
        return True
    else:
        print(f"❌ STILL ZERO PRODUCTION WITH REAL DATA")
        print(f"   Shortage: {solution['total_shortage']:,.0f} units")
        print(f"\n   Need to continue adding features...")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
