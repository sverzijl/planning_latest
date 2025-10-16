"""
Trace material flow to find the source of the ~32k unit deficit.

Material balance equation for the entire horizon:
    Production + Initial Inventory = Demand Satisfied + Final Inventory + Waste

Current observations:
- Production: 216,950 units
- Initial Inventory: 0 units (passed as None)
- Demand Satisfied: 237,149 units
- Final Inventory: 12,177 units
- Deficit: 216,950 - (237,149 + 12,177) = -32,376 units

This diagnostic will trace where the extra ~32k units are coming from.
"""

from datetime import date, timedelta
from pathlib import Path
from pyomo.environ import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

# Load data
data_dir = Path('data/examples')
parser = MultiFileParser(
    forecast_file=data_dir / 'Gfree Forecast.xlsm',
    network_file=data_dir / 'Network_Config.xlsx',
    inventory_file=None
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]

manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0,
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

# Convert truck schedules
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create model
planning_start_date = date(2025, 10, 7)
planning_end_date = planning_start_date + timedelta(weeks=4)

print("Creating and building model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=None,
    inventory_snapshot_date=None,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,
)

print("Solving model...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    tee=False
)

print(f"\nSolve status: {result.termination_condition}")

if not (result.is_optimal() or result.is_feasible()):
    print("ERROR: Solution not optimal/feasible")
    exit(1)

print("\n" + "="*80)
print("TRACING MATERIAL FLOW")
print("="*80)

pm = model.model  # Pyomo model

# Sum all production
total_prod = 0
for d in model.production_dates:
    for p in model.products:
        var = pm.production[d, p]
        if var.value is not None:
            qty = value(var)
            if qty > 0.01:
                total_prod += qty

print(f"\nTotal production: {total_prod:,.0f} units")

# Sum all demand satisfaction (from cohorts)
total_demand_satisfied = 0
if hasattr(pm, 'demand_from_cohort'):
    for (loc, prod, prod_date, demand_date) in pm.cohort_demand_index:
        var = pm.demand_from_cohort[loc, prod, prod_date, demand_date]
        if var.value is not None:
            qty = value(var)
            if qty > 0.01:
                total_demand_satisfied += qty

print(f"Total demand satisfied (from cohorts): {total_demand_satisfied:,.0f} units")

# Sum final day inventory (all locations, all states)
final_day = model.end_date
total_final_inv = 0

if hasattr(pm, 'inventory_ambient_cohort'):
    for (loc, prod, prod_date, curr_date) in pm.cohort_ambient_index:
        if curr_date == final_day:
            var = pm.inventory_ambient_cohort[loc, prod, prod_date, curr_date]
            if var.value is not None:
                qty = value(var)
                if qty > 0.01:
                    total_final_inv += qty

if hasattr(pm, 'inventory_frozen_cohort'):
    for (loc, prod, prod_date, curr_date) in pm.cohort_frozen_index:
        if curr_date == final_day:
            var = pm.inventory_frozen_cohort[loc, prod, prod_date, curr_date]
            if var.value is not None:
                qty = value(var)
                if qty > 0.01:
                    total_final_inv += qty

print(f"Total final day inventory: {total_final_inv:,.0f} units")

# Calculate material balance
supply = total_prod  # No initial inventory
usage = total_demand_satisfied + total_final_inv
deficit = supply - usage

print(f"\nMaterial Balance:")
print(f"  Supply (production): {supply:,.0f}")
print(f"  Usage (demand + final inv): {usage:,.0f}")
print(f"  Deficit: {deficit:+,.0f} units")

if abs(deficit) > 100:
    print(f"\n⚠ Material balance violation detected: {abs(deficit):,.0f} units")

    # The extra units must be coming from somewhere. Check for:
    # 1. Initial inventory on day 1 (even though we didn't provide any)
    # 2. Phantom arrivals from pre-horizon departures
    # 3. Other flow conservation bugs

    print("\n" + "="*80)
    print("INVESTIGATING SOURCE OF PHANTOM UNITS")
    print("="*80)

    # Check day 1 inventory at all locations
    day1 = model.start_date
    print(f"\nDay 1 ({day1}) inventory by location:")

    day1_inv_by_loc = {}

    if hasattr(pm, 'inventory_ambient_cohort'):
        for (loc, prod, prod_date, curr_date) in pm.cohort_ambient_index:
            if curr_date == day1:
                var = pm.inventory_ambient_cohort[loc, prod, prod_date, curr_date]
                if var.value is not None:
                    qty = value(var)
                    if qty > 0.01:
                        if loc not in day1_inv_by_loc:
                            day1_inv_by_loc[loc] = 0
                        day1_inv_by_loc[loc] += qty

    if hasattr(pm, 'inventory_frozen_cohort'):
        for (loc, prod, prod_date, curr_date) in pm.cohort_frozen_index:
            if curr_date == day1:
                var = pm.inventory_frozen_cohort[loc, prod, prod_date, curr_date]
                if var.value is not None:
                    qty = value(var)
                    if qty > 0.01:
                        if loc not in day1_inv_by_loc:
                            day1_inv_by_loc[loc] = 0
                        day1_inv_by_loc[loc] += qty

    for loc, qty in sorted(day1_inv_by_loc.items(), key=lambda x: x[1], reverse=True):
        print(f"  {loc}: {qty:,.0f} units")

    total_day1_inv = sum(day1_inv_by_loc.values())
    print(f"  TOTAL: {total_day1_inv:,.0f} units")

    if total_day1_inv > 1:
        print(f"\n⚠ Day 1 inventory found: {total_day1_inv:,.0f} units")
        print("  This is expected if production happens on day 1")

        # Check day 1 production
        day1_prod = 0
        for p in model.products:
            var = pm.production[day1, p]
            if var.value is not None:
                qty = value(var)
                if qty > 0.01:
                    day1_prod += qty

        print(f"  Day 1 production: {day1_prod:,.0f} units")

        if day1_prod < total_day1_inv - 1:
            print(f"\n  ⚠ Day 1 inventory ({total_day1_inv:,.0f}) > Day 1 production ({day1_prod:,.0f})")
            print("  This suggests phantom units appearing on day 1!")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
