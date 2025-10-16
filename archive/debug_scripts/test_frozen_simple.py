"""Simple frozen routing test to diagnose phantom inventory at Lineage.

This uses the SAME diagnostic strategy that worked for ambient hub routing.

Test scenario:
- 6122 produces frozen product
- Ships frozen to Lineage
- Lineage stores frozen
- Ships frozen to 6130
- 6130 thaws on arrival

Expected: Production = Consumption + Final Inventory
"""

from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel

# Setup
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=6)  # 7 days

print("="*80)
print("SIMPLE FROZEN ROUTING TEST")
print("="*80)
print(f"Route: 6122 (produces frozen) → Lineage (frozen storage) → 6130 (thaws)")
print(f"Planning: {start_date} to {end_date}")
print()

# Locations
manufacturing = Location(
    id="6122",
    name="Manufacturing",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.BOTH,
    production_rate=1400.0,
)

lineage = Location(
    id="Lineage",
    name="Lineage Frozen Storage",
    type=LocationType.STORAGE,
    storage_mode=StorageMode.BOTH,  # BOTH - can receive ambient and freeze it
    capacity=50000,
)

wa_destination = Location(
    id="6130",
    name="WA Thawing",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.AMBIENT,  # Thaws on arrival
    capacity=15000,
)

locations = [manufacturing, lineage, wa_destination]

# Routes - CORRECTED to match business process
route1 = Route(
    id="R1",
    origin_id="6122",
    destination_id="Lineage",
    transport_mode=StorageMode.AMBIENT,  # Ships AMBIENT, freezes at Lineage!
    transit_time_days=0.5,
    cost=0.05,
)

route2 = Route(
    id="R2",
    origin_id="Lineage",
    destination_id="6130",
    transport_mode=StorageMode.FROZEN,  # Frozen transit, thaws at 6130
    transit_time_days=3.0,
    cost=0.10,
)

routes = [route1, route2]

# Demand: 1000 units/day at 6130 for days 5-6 (allows 4-day lead time with rounding)
# Total transit: 0.5 + 3.0 = 3.5 days, so day 1 production arrives day 4.5
# Earliest achievable demand: day 5
forecast_entries = []
for day_offset in range(5, 7):  # Days 5-6 only
    forecast_entries.append(
        ForecastEntry(
            location_id="6130",
            product_id="FROZEN_PRODUCT",
            forecast_date=start_date + timedelta(days=day_offset),
            quantity=1000.0,
        )
    )

forecast = Forecast(name="Frozen Test", entries=forecast_entries)
total_demand = sum(e.quantity for e in forecast_entries)

print(f"Demand: {total_demand:,.0f} units at 6130 (days 4-6)")
print()

# Labor
labor_days = []
for i in range(7):
    labor_date = start_date + timedelta(days=i)
    labor_days.append(
        LaborDay(
            date=labor_date,
            fixed_hours=12.0 if labor_date.weekday() < 5 else 0.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=50.0,
            minimum_hours=4.0 if labor_date.weekday() >= 5 else 0.0,
        )
    )

labor_calendar = LaborCalendar(name="Test", days=labor_days)

manufacturing_site = ManufacturingSite(
    id="6122",
    name="Manufacturing",
    storage_mode=StorageMode.BOTH,
    production_rate=1400.0,
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=5.0,
)

cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    setup_cost=0.0,
    default_regular_rate=25.0,
    default_overtime_rate=37.5,
    default_non_fixed_rate=50.0,
    storage_cost_frozen_per_unit_day=0.10,
    storage_cost_ambient_per_unit_day=0.002,
    shortage_penalty_per_unit=1000.0,
    waste_cost_multiplier=1.5,
)

truck_schedules = TruckScheduleCollection(schedules=[])

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

print(f"✓ Model created")
print(f"  Routes enumerated: {len(model.enumerated_routes)}")
print(f"  Frozen storage locations: {model.locations_frozen_storage}")
print(f"  Intermediate storage: {model.intermediate_storage}")
print(f"  Inventory locations: {len(model.inventory_locations)}")
print()

# Check if Lineage is properly configured
print(f"Lineage configuration in model:")
print(f"  In inventory_locations: {'Lineage' in model.inventory_locations}")
print(f"  In intermediate_storage: {'Lineage' in model.intermediate_storage}")
print(f"  In locations_frozen_storage: {'Lineage' in model.locations_frozen_storage}")
print(f"  Has inbound legs: {len(model.legs_to_location.get('Lineage', []))} legs")
print(f"  Has outbound legs: {len(model.legs_from_location.get('Lineage', []))} legs")

if model.legs_to_location.get('Lineage'):
    print(f"  Inbound legs:")
    for (origin, dest) in model.legs_to_location.get('Lineage', []):
        print(f"    {origin} → {dest}")

if model.legs_from_location.get('Lineage'):
    print(f"  Outbound legs:")
    for (origin, dest) in model.legs_from_location.get('Lineage', []):
        print(f"    {origin} → {dest}")

print()
print("Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())
    cohort_inv = solution.get('cohort_inventory', {})

    # First and last day inventory
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    # Lineage inventory details
    lineage_inv_by_day = {}
    for (loc, prod, pd, cd, state), qty in cohort_inv.items():
        if loc == 'Lineage' and qty > 0.01:
            if cd not in lineage_inv_by_day:
                lineage_inv_by_day[cd] = 0.0
            lineage_inv_by_day[cd] += qty

    print("="*80)
    print("RESULTS")
    print("="*80)
    print(f"Production: {production:,.0f} units")
    print(f"Consumption: {consumption:,.0f} units")
    print(f"First day inventory: {first_day:,.0f} units")
    print(f"Last day inventory: {last_day:,.0f} units")
    print()

    if lineage_inv_by_day:
        print(f"Lineage inventory trajectory:")
        for day in sorted(lineage_inv_by_day.keys()):
            print(f"  {day}: {lineage_inv_by_day[day]:,.0f} units")
    else:
        print("Lineage inventory: 0 across all days")

    print()
    print("="*80)
    print("MATERIAL BALANCE")
    print("="*80)

    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    print(f"Supply: {first_day:,.0f} (day 1) + {production:,.0f} (production) = {supply:,.0f}")
    print(f"Usage: {consumption:,.0f} (consumed) + {last_day:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f} units")
    print()

    if abs(balance) <= 1:
        print("✓ MATERIAL BALANCE CORRECT")
    else:
        print("❌ MATERIAL BALANCE VIOLATION")
        if production == 0:
            print("  CRITICAL: No production but consumption occurred!")
            print("  This is the phantom inventory bug")
