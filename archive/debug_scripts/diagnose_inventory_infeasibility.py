"""
Diagnose inventory-based truck loading infeasibility.
Test with progressively higher initial inventory levels.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("INVENTORY INFEASIBILITY DIAGNOSIS")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

# Parse all data
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Filter to 3 weeks
start_date = date(2025, 10, 13)  # Monday
end_date = date(2025, 11, 2)     # Sunday (3 weeks)
filtered_entries = [e for e in forecast.entries
                   if start_date <= e.forecast_date <= end_date]
forecast.entries = filtered_entries

# Get unique products
product_ids = sorted(set(e.product_id for e in forecast.entries))

print(f"Filtered to {start_date} - {end_date}: {len(filtered_entries)} forecast entries")
print(f"Products: {len(product_ids)}")
print(f"Locations: {len(locations)}")

# Test different initial inventory levels
initial_inventory_levels = [
    0,       # No initial inventory
    10000,   # 10k per product (original test)
    50000,   # 50k per product
    100000,  # 100k per product
]

for inv_level in initial_inventory_levels:
    print(f"\n{'=' * 80}")
    print(f"TESTING WITH INITIAL INVENTORY: {inv_level:,} units per product")
    print(f"Total initial inventory: {inv_level * len(product_ids):,} units")
    print("=" * 80)

    # Create initial inventory
    initial_inv = {}
    for pid in product_ids:
        initial_inv[('6122', pid, 'ambient')] = float(inv_level)

    print("\nBuilding optimization model...")
    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
        initial_inventory=initial_inv
    )

    print(f"Model built:")
    print(f"  Planning dates: {len(model.production_dates)} days")
    print(f"  Routes: {len(model.enumerated_routes)} routes")

    # Write LP file for first iteration only
    if inv_level == initial_inventory_levels[0]:
        print("\nWriting LP file for examination...")
        lp_filename = "inventory_model_debug.lp"
        try:
            from pyomo.environ import ConcreteModel
            # Build Pyomo model
            pyomo_model = model._build_optimization_model()
            pyomo_model.write(lp_filename, io_options={'symbolic_solver_labels': True})
            print(f"✓ LP file written to: {lp_filename}")
        except Exception as e:
            print(f"✗ Failed to write LP file: {e}")

    print("\nSolving...")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,  # Quick test
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False
    )

    print(f"\nResult: {result.termination_condition}")

    if result.success:
        print(f"✓ FEASIBLE with {inv_level:,} units initial inventory")
        print(f"  Objective value: ${result.objective_value:,.2f}")
        print(f"  Solve time: {result.solve_time_seconds:.2f}s")
        print("\n🎉 SUCCESS: Found feasible initial inventory level!")
        break
    else:
        print(f"✗ INFEASIBLE with {inv_level:,} units initial inventory")

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)
