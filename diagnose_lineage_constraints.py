"""Diagnose Lineage frozen inventory constraints to find phantom inventory bug.

The systematic test proved:
- Test 5 (1 product, WA via Lineage, 1 week): -700 unit deficit
- Production: 0, Consumption: 400, Day 1 phantom: 100, Last day: 400

This script examines:
1. Does Lineage have frozen inventory balance constraints?
2. Does the constraint count arrivals from 6122?
3. Does the constraint count departures to 6130?
4. Is there a missing term in the balance equation?
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

# Parse real configuration
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

_, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manuf_locs = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = ManufacturingSite(
    id=manuf_locs[0].id, name=manuf_locs[0].name, storage_mode=manuf_locs[0].storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Minimal forecast: 1 product, WA only (forces Lineage route)
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=6)

forecast_entries = []
for day_offset in range(4, 7):  # Days 4-6 (allows 3.5-day transit via Lineage)
    forecast_entries.append(
        ForecastEntry(
            location_id="6130",  # WA - MUST go through Lineage
            product_id="HELGAS GFREE WHOLEM 500G",
            forecast_date=start_date + timedelta(days=day_offset),
            quantity=100.0,
        )
    )

forecast = Forecast(name="Lineage Diagnostic", entries=forecast_entries)

print("="*80)
print("LINEAGE ROUTE CONSTRAINT DIAGNOSTIC")
print("="*80)
print(f"Demand: 300 units at 6130 (WA) - must use Lineage frozen route")
print(f"Planning: {start_date} to {end_date}")
print()

# Create model
model = IntegratedProductionDistributionModel(
    forecast=forecast, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
    cost_structure=cost_structure, locations=locations, routes=routes,
    truck_schedules=truck_schedules, start_date=start_date, end_date=end_date,
    allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
    initial_inventory=None,
)

print("MODEL CONFIGURATION:")
print(f"  Routes enumerated: {len(model.enumerated_routes)}")

# Check Lineage configuration
print(f"\\nLineage configuration:")
print(f"  In inventory_locations: {'Lineage' in model.inventory_locations}")
print(f"  In intermediate_storage: {'Lineage' in model.intermediate_storage}")
print(f"  In locations_frozen_storage: {'Lineage' in model.locations_frozen_storage}")

# Check Lineage legs
print(f"\\nLineage legs:")
legs_to_lineage = model.legs_to_location.get('Lineage', [])
legs_from_lineage = model.legs_from_location.get('Lineage', [])

print(f"  Inbound legs: {len(legs_to_lineage)}")
for leg in legs_to_lineage:
    mode = model.leg_transport_mode.get(leg)
    arr_state = model.leg_arrival_state.get(leg)
    print(f"    {leg}: mode={mode}, arrival_state={arr_state}")

print(f"  Outbound legs: {len(legs_from_lineage)}")
for leg in legs_from_lineage:
    mode = model.leg_transport_mode.get(leg)
    arr_state = model.leg_arrival_state.get(leg)
    print(f"    {leg}: mode={mode}, arrival_state={arr_state}")

# Build Pyomo model to check constraints
print(f"\\nBuilding Pyomo model to inspect constraints...")
pyomo_model = model.build_model()

# Check if frozen inventory balance constraint exists for Lineage
print(f"\\nChecking frozen inventory balance for Lineage:")

if hasattr(pyomo_model, 'inventory_frozen_cohort_balance_con'):
    print(f"  ✓ Frozen cohort balance constraint exists")

    # Check if Lineage has frozen cohorts
    lineage_frozen_cohorts = [key for key in model.cohort_frozen_index_set if key[0] == 'Lineage']
    print(f"  Frozen cohorts at Lineage: {len(lineage_frozen_cohorts)}")

    if lineage_frozen_cohorts:
        print(f"    Sample (first 3): {list(lineage_frozen_cohorts)[:3]}")
    else:
        print(f"    ❌ NO frozen cohorts at Lineage!")
        print(f"       Lineage can't store frozen inventory → bug!")

elif hasattr(pyomo_model, 'inventory_frozen_balance_con'):
    print(f"  ✓ Frozen aggregate balance constraint exists")

    # Check if Lineage is in the index
    if hasattr(pyomo_model, 'inventory_frozen_index'):
        lineage_in_index = any(loc == 'Lineage' for (loc, prod, date) in pyomo_model.inventory_frozen_index)
        print(f"  Lineage in frozen inventory index: {lineage_in_index}")
else:
    print(f"  ❌ NO frozen inventory balance constraint found!")

# Solve to see the bug
print(f"\\nSolving...")
result = model.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())
    shortage = sum(solution.get('shortages_by_dest_product_date', {}).values())

    cohort_inv = solution.get('cohort_inventory', {})

    # First day inventory at Lineage
    lineage_day1 = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if loc == 'Lineage' and cd == start_date and state == 'frozen')

    # Check shipments
    shipments_by_leg = solution.get('shipments_by_leg_product_date', {})

    # Arrivals at Lineage
    arrivals_to_lineage = {(leg, prod, dd): qty for (leg, prod, dd), qty in shipments_by_leg.items() if leg[1] == 'Lineage' and qty > 0.01}

    # Departures from Lineage
    departures_from_lineage = {(leg, prod, dd): qty for (leg, prod, dd), qty in shipments_by_leg.items() if leg[0] == 'Lineage' and qty > 0.01}

    print("="*80)
    print("LINEAGE FLOW ANALYSIS")
    print("="*80)

    print(f"Production at 6122: {production:,.0f} units")
    print(f"Demand satisfied at 6130: {consumption:,.0f} units")
    print(f"Shortage: {shortage:,.0f} units")
    print()

    print(f"Day 1 frozen inventory at Lineage: {lineage_day1:,.0f} units")
    if lineage_day1 > 0:
        print(f"  ❌ PHANTOM INVENTORY! Lineage has inventory without receiving it")
    print()

    print(f"Arrivals TO Lineage: {len(arrivals_to_lineage)}")
    total_arrivals = sum(arrivals_to_lineage.values())
    print(f"  Total: {total_arrivals:,.0f} units")
    for (leg, prod, dd), qty in list(arrivals_to_lineage.items())[:5]:
        print(f"    {leg} delivers {dd}: {qty:,.0f} units")

    print()
    print(f"Departures FROM Lineage: {len(departures_from_lineage)}")
    total_departures = sum(departures_from_lineage.values())
    print(f"  Total: {total_departures:,.0f} units")
    for (leg, prod, dd), qty in list(departures_from_lineage.items())[:5]:
        print(f"    {leg} delivers {dd}: {qty:,.0f} units")

    print()
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)

    if production == 0 and total_arrivals == 0 and total_departures > 0:
        print("❌ SMOKING GUN FOUND:")
        print(f"   Lineage DEPARTS {total_departures:,.0f} units")
        print(f"   But NEVER RECEIVES anything (arrivals = {total_arrivals})")
        print(f"   And 6122 NEVER PRODUCES")
        print()
        print("   This proves Lineage frozen inventory balance is broken:")
        print("   - Either departures are NOT being subtracted")
        print("   - Or arrivals are required but not being enforced")
        print("   - Or constraint doesn't exist for Lineage")

    elif production > 0 and total_arrivals == 0 and total_departures > 0:
        print("❌ BUG:")
        print(f"   Production: {production}")
        print(f"   Lineage never receives from 6122 (arrivals = 0)")
        print(f"   Yet Lineage ships {total_departures} to 6130")
        print()
        print("   Frozen shipments from 6122→Lineage are missing!")

    elif production > 0 and total_arrivals > 0 and abs(total_arrivals - total_departures) > 10:
        print("❌ BUG:")
        print(f"   Lineage receives: {total_arrivals}")
        print(f"   Lineage ships: {total_departures}")
        print(f"   Imbalance: {total_departures - total_arrivals:+,.0f}")
        print()
        print("   Lineage inventory balance not conserving flows!")

    else:
        print("✓ Lineage flows look balanced")
        print("   Bug must be elsewhere")
