"""Minimal test for freeze operation at a single location.

Test the freeze operation in isolation:
1. 6122 produces ambient inventory → 6122_Storage ambient
2. 6122_Storage freezes ambient → frozen
3. 6122_Storage ships frozen to destination

This tests if the freeze operation properly converts ambient to frozen inventory.
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

start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=3)  # 4 days total

print("="*80)
print("MINIMAL FREEZE OPERATION TEST")
print("="*80)
print("Test: Can 6122_Storage freeze ambient inventory and ship it frozen?")
print(f"Planning: {start_date} to {end_date} (4 days)")
print()

# Locations - just manufacturing and one destination
manufacturing = Location(
    id="6122",
    name="Manufacturing",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.BOTH,
    production_rate=1400.0,
)

# Destination that can receive frozen AND thaw for consumption
frozen_dest = Location(
    id="FROZEN_DEST",
    name="Frozen Destination",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.BOTH,  # Can receive frozen AND thaw it for demand
    capacity=10000,
)

locations = [manufacturing, frozen_dest]

# Route: 6122 → FROZEN_DEST (frozen transport, 1 day)
route = Route(
    id="R1",
    origin_id="6122",
    destination_id="FROZEN_DEST",
    transport_mode=StorageMode.FROZEN,  # Ships frozen
    transit_time_days=1.0,
    cost=0.10,
)

routes = [route]

# Forecast: 1000 units on day 2 (allows 1-day transit from day 1 production)
forecast_entries = [
    ForecastEntry(
        location_id="FROZEN_DEST",
        product_id="TEST_FREEZE",
        forecast_date=start_date + timedelta(days=2),
        quantity=1000.0,
    )
]

forecast = Forecast(name="Freeze Test", entries=forecast_entries)

print(f"Demand: 1,000 units at FROZEN_DEST on day 2")
print()

# Labor
labor_days = []
for i in range(4):
    labor_days.append(
        LaborDay(
            date=start_date + timedelta(days=i),
            fixed_hours=12.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=50.0,
            minimum_hours=0.0,
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

print("Building model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=[]),
    start_date=start_date,
    end_date=end_date,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
    initial_inventory=None,
)

print(f"✓ Model created")
print(f"  Routes enumerated: {len(model.enumerated_routes)}")
print(f"  6122_Storage in locations_with_freezing: {'6122_Storage' in model.locations_with_freezing}")
print(f"  6122_Storage in locations_frozen_storage: {'6122_Storage' in model.locations_frozen_storage}")
print(f"  6122_Storage in locations_ambient_storage: {'6122_Storage' in model.locations_ambient_storage}")
print()

# Check virtual leg
virtual_leg = ('6122_Storage', 'FROZEN_DEST')
if virtual_leg in model.leg_keys:
    print(f"✓ Virtual leg {virtual_leg} created")
    print(f"    transport_mode: {model.leg_transport_mode.get(virtual_leg)}")
    print(f"    departure_state: {model.leg_departure_state.get(virtual_leg)}")
    print(f"    arrival_state: {model.leg_arrival_state.get(virtual_leg)}")
    print(f"    transit_days: {model.leg_transit_days.get(virtual_leg)}")
else:
    print(f"❌ Virtual leg not created")

print()
print("Expected behavior:")
print("  Day 1: Produce 1000 units → 6122_Storage ambient")
print("  Day 1: Freeze 1000 units → 6122_Storage frozen")
print("  Day 1: Ship 1000 frozen units from 6122_Storage")
print("  Day 2: Deliver 1000 units to FROZEN_DEST")
print()

print("Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s ({result.termination_condition})")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    freeze_ops = solution.get('freeze_operations', {})
    thaw_ops = solution.get('thaw_operations', {})

    cohort_demand = solution.get('cohort_demand_consumption', {})
    total_consumption = sum(cohort_demand.values())

    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    print("="*80)
    print("RESULTS")
    print("="*80)

    print(f"Production: {total_production:,.0f} units")
    if production_by_date_product:
        for (d, p), qty in production_by_date_product.items():
            print(f"  {d}: {qty:,.0f} units")

    print(f"\\nFreeze operations: {len(freeze_ops)}")
    if freeze_ops:
        total_frozen = sum(freeze_ops.values())
        print(f"  Total frozen: {total_frozen:,.0f} units")
        for (loc, prod, pd, cd), qty in list(freeze_ops.items())[:5]:
            print(f"    {loc} on {cd} (prod_date={pd}): {qty:,.0f} units")
    else:
        print(f"  ❌ NO FREEZE OPERATIONS (this is the problem!)")

    print(f"\\nThaw operations: {len(thaw_ops)}")

    print(f"\\nConsumption: {total_consumption:,.0f} units")
    print(f"Shortage: {total_shortage:,.0f} units")

    # Check 6122_Storage inventory by state
    cohort_inv = solution.get('cohort_inventory', {})
    storage_amb = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if loc == '6122_Storage' and state == 'ambient')
    storage_frz = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if loc == '6122_Storage' and state == 'frozen')

    print(f"\\n6122_Storage inventory:")
    print(f"  Ambient: {storage_amb:,.0f} units")
    print(f"  Frozen: {storage_frz:,.0f} units")

    print()
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)

    if total_production == 0:
        print("❌ No production occurred")
        print("   Route is INFEASIBLE or freeze operation broken")
    elif len(freeze_ops) == 0:
        print("❌ No freeze operations occurred")
        print("   Freeze variables exist but model won't use them")
        print("   Possible causes:")
        print("     1. Freeze operation cost too high (but it's \$0!)")
        print("     2. Frozen departure constraint broken")
        print("     3. Missing constraint linking freeze to frozen shipments")
    elif total_consumption > 0:
        print("✓ Route works! Production → freeze → ship frozen → deliver")
    else:
        print("⚠️ Production and freeze occurred but no delivery")
else:
    print(f"❌ Solution not feasible: {result.termination_condition}")
