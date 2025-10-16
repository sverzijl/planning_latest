"""Ultra-simple test with minimal real data subset.

Strategy: Start with 1 product, 1 week, real network config
Build up complexity step by step to find where phantom inventory appears.
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

print("="*80)
print("ULTRA-SIMPLE REAL DATA TEST")
print("="*80)
print("Test 1 product, 1 week, real network")
print()

# Parse real network configuration
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

# Get network configuration (locations, routes, labor, etc.)
_, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Create manufacturing site
manuf_locs = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manuf_locs[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create MINIMAL forecast: 1 product, 1 destination, 1 week
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=6)

# Choose simplest destination (direct route, no Lineage complexity)
# 6110 = QLD direct route from 6122
forecast_entries = []
product_id = "HELGAS GFREE WHOLEM 500G"  # One real product

for day_offset in range(2, 7):  # Days 2-6 (allow 1-day transit)
    forecast_entries.append(
        ForecastEntry(
            location_id="6110",
            product_id=product_id,
            forecast_date=start_date + timedelta(days=day_offset),
            quantity=1000.0,
        )
    )

forecast = Forecast(name="Ultra Simple Test", entries=forecast_entries)

total_demand = sum(e.quantity for e in forecast_entries)
print(f"Forecast: {total_demand:,.0f} units at 6110 (QLD direct)")
print(f"Planning: {start_date} to {end_date} (7 days)")
print()

print("Building model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    start_date=start_date,
    end_date=end_date,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
    initial_inventory=None,
)

print(f"✓ Model built")
print(f"  Routes enumerated: {len(model.enumerated_routes)}")
print(f"  Products: {len(model.products)}")
print(f"  Destinations: {len(model.destinations)}")
print()

print("Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    cohort_inventory = solution.get('cohort_inventory', {})
    cohort_demand = solution.get('cohort_demand_consumption', {})

    actual_consumption = sum(cohort_demand.values())

    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    # First and last day inventory
    first_day_inv = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items() if cd == start_date)
    last_day_inv = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items() if cd == end_date)

    print("="*80)
    print("RESULTS - REAL DATA, 1 PRODUCT, 1 WEEK")
    print("="*80)

    print(f"Production: {total_production:,.0f} units")
    print(f"Consumption: {actual_consumption:,.0f} units")
    print(f"Shortage: {total_shortage:,.0f} units")
    print(f"First day inventory: {first_day_inv:,.0f} units")
    print(f"Last day inventory: {last_day_inv:,.0f} units")
    print()

    # Material balance
    supply = first_day_inv + total_production
    usage = actual_consumption + last_day_inv
    balance = supply - usage

    print("="*80)
    print("MATERIAL BALANCE")
    print("="*80)
    print(f"Supply: {first_day_inv:,.0f} (day 1) + {total_production:,.0f} (prod) = {supply:,.0f}")
    print(f"Usage: {actual_consumption:,.0f} (consumed) + {last_day_inv:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f} units")
    print()

    if abs(balance) <= 1:
        print("✓ MATERIAL BALANCE PERFECT - Real data with 1 product works!")
    else:
        print("❌ MATERIAL BALANCE VIOLATION - Bug exists even with 1 product!")

        if first_day_inv > 1:
            print(f"\\n  Day 1 phantom inventory: {first_day_inv:,.0f} units")

            # Show where it is
            day1_by_loc = {}
            for (loc, prod, pd, cd, state), qty in cohort_inventory.items():
                if cd == start_date and qty > 0.01:
                    key = f"{loc} ({state})"
                    day1_by_loc[key] = day1_by_loc.get(key, 0.0) + qty

            print("  Location breakdown:")
            for loc_state, qty in sorted(day1_by_loc.items(), key=lambda x: x[1], reverse=True):
                print(f"    {loc_state}: {qty:,.0f} units")
