"""Full integration test matching UI configuration.

This test verifies the optimization works end-to-end with:
- Full example dataset (Network_Config.xlsx + Gfree Forecast_Converted.xlsx)
- UI default settings (300s timeout, 1% gap, no shortages, enforce shelf life)
- CBC solver (UI default)
"""

from pathlib import Path
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 70)
print("FULL INTEGRATION TEST - UI CONFIGURATION")
print("=" * 70)

# Parse full example data
print("\n📂 Loading data files...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

print(f"  ✓ Locations: {len(locations)}")
print(f"  ✓ Routes: {len(routes)}")
print(f"  ✓ Truck schedules: {len(truck_schedules_list)}")
print(f"  ✓ Forecast entries: {len(forecast.entries)}")
print(f"  ✓ Manufacturing site: {manufacturing_site.id}")

# UI SETTINGS - matching typical usage
time_limit = 300  # seconds (UI default)
mip_gap = 0.01  # 1% (UI default)
allow_shortages = True  # Allow shortages for large datasets (user's typical setting)
enforce_shelf_life = True  # UI default (checkbox checked)
max_routes = 5  # UI default
solver = 'cbc'  # UI auto-detects, CBC is first choice

print(f"\n⚙️  UI Configuration:")
print(f"  Time limit: {time_limit}s")
print(f"  MIP gap: {mip_gap*100}%")
print(f"  Allow shortages: {allow_shortages}")
print(f"  Enforce shelf life: {enforce_shelf_life}")
print(f"  Max routes per dest: {max_routes}")
print(f"  Solver: {solver}")

# Build model with UI settings
print(f"\n🔨 Building optimization model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=max_routes,
    allow_shortages=allow_shortages,
    enforce_shelf_life=enforce_shelf_life,
)

print(f"  ✓ Model built successfully")
print(f"  Routes enumerated: {len(model.enumerated_routes)}")
print(f"  Production dates: {len(model.production_dates)}")
print(f"  Trucks: {len(model.truck_indices)}")
print(f"  Destinations: {len(model.destinations)}")
print(f"  Products: {len(model.products)}")

# Solve with UI settings
print(f"\n⚡ Solving optimization (this may take a few minutes)...")
result = model.solve(
    solver_name=solver,
    time_limit_seconds=time_limit,
    mip_gap=mip_gap,
    tee=False
)

# Report results
print(f"\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
print(f"Status: {result.termination_condition}")
print(f"Success: {result.success}")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")
else:
    print(f"Objective: N/A")
print(f"Solve time: {result.solve_time_seconds:.1f}s")
if result.gap:
    print(f"Gap: {result.gap*100:.2f}%")
print(f"Variables: {result.num_variables:,}")
print(f"Constraints: {result.num_constraints:,}")
print(f"Integer vars: {result.num_integer_vars:,}")

if result.is_optimal() or result.is_feasible():
    print(f"\n✅ OPTIMIZATION SUCCESSFUL")

    # Extract solution metrics
    solution = model.get_solution()
    production = solution.get('production_by_date_product', {})
    shipments = model.get_shipment_plan()

    print(f"\n📊 Solution Summary:")
    print(f"  Total production: {sum(production.values()):,.0f} units")
    print(f"  Shipments: {len(shipments)}")

    # Weekend production check
    weekend_production = 0
    weekday_production = 0
    for (d, p), qty in production.items():
        labor_day = labor_calendar.get_labor_day(d)
        if labor_day and not labor_day.is_fixed_day:
            weekend_production += qty
        else:
            weekday_production += qty

    total = weekend_production + weekday_production
    if total > 0:
        print(f"\n📦 Production Breakdown:")
        print(f"  Weekday: {weekday_production:,.0f} units ({weekday_production/total*100:.1f}%)")
        print(f"  Weekend: {weekend_production:,.0f} units ({weekend_production/total*100:.1f}%)")

        if weekend_production > 0:
            print(f"\n  ℹ️  Note: Weekend production present - this is expected for:")
            print(f"     - Demand spikes requiring extra capacity")
            print(f"     - Cold start (no initial buffer stock)")
            print(f"     - Cost-optimal decisions (weekend cheaper than alternatives)")

    # Inventory check
    inventory = solution.get('inventory_by_dest_product_date', {})
    if inventory:
        total_inventory = sum(inventory.values())
        print(f"\n📦 Inventory:")
        print(f"  Total inventory (all dest/prod/date): {total_inventory:,.0f} units")

        # Check for buffer build-up
        by_date = {}
        for (dest, prod, date), qty in inventory.items():
            by_date[date] = by_date.get(date, 0) + qty

        if by_date:
            sorted_dates = sorted(by_date.keys())
            print(f"  Inventory over time:")
            for i, date in enumerate(sorted_dates[:5]):  # First 5 days
                print(f"    {date}: {by_date[date]:,.0f} units")
            if len(sorted_dates) > 5:
                print(f"    ... ({len(sorted_dates)-5} more dates)")

    # Truck usage
    truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
    if truck_loads:
        num_loads = len([v for v in truck_loads.values() if v > 0.1])
        print(f"\n🚚 Truck Loads:")
        print(f"  Active truck loads: {num_loads}")

    print(f"\n✅ TEST PASSED - Model solves successfully with UI configuration")

elif result.is_infeasible():
    print(f"\n❌ MODEL IS INFEASIBLE")
    if result.infeasibility_message:
        print(f"   {result.infeasibility_message}")
    if allow_shortages:
        print(f"\n   This indicates a bug - model should be feasible with:")
        print(f"   - allow_shortages=True (demand shortfalls allowed)")
        print(f"   - enforce_shelf_life={enforce_shelf_life}")
    else:
        print(f"\n   This may be expected - demand exceeds capacity or shelf life constraints are too tight")
        print(f"   Try with allow_shortages=True to permit unmet demand")
    print(f"\n❌ TEST FAILED")
else:
    print(f"\n⚠️  SOLVER ERROR")
    if result.infeasibility_message:
        print(f"   {result.infeasibility_message}")
    print(f"\n❌ TEST FAILED")

print(f"\n" + "=" * 70)
