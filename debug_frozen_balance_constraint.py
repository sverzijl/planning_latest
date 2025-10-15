#!/usr/bin/env python
"""
Inspect the frozen inventory balance constraint for Lineage on Oct 7.
"""

from pathlib import Path
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

# Parse data
data_dir = Path('data/examples')
parser = MultiFileParser(
    forecast_file=data_dir / 'Gfree Forecast.xlsm',
    network_file=data_dir / 'Network_Config.xlsx',
    inventory_file=None,
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
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

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Set planning horizon
planning_start = date(2025, 10, 7)
planning_end = planning_start + timedelta(weeks=4)

# Create model
model_obj = IntegratedProductionDistributionModel(
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
    start_date=planning_start,
    end_date=planning_end,
    use_batch_tracking=True,
)

# Build model
pyomo_model = model_obj.build_model()

print("="*80)
print("FROZEN INVENTORY BALANCE CONSTRAINT FOR LINEAGE ON OCT 7")
print("="*80)

# Manually calculate what the constraint should be for one product
loc = 'Lineage'
prod = 'HELGAS GFREE TRAD WHITE 470G'  # One of the products with inventory
prod_date = date(2025, 10, 7)
curr_date = date(2025, 10, 7)

print(f"\nLocation: {loc}")
print(f"Product: {prod}")
print(f"Production date: {prod_date}")
print(f"Current date: {curr_date}")

# Check legs TO Lineage (frozen arrivals)
legs_frozen_arrival = [
    (o, d) for (o, d) in model_obj.legs_to_location.get(loc, [])
    if model_obj.leg_arrival_state.get((o, d)) == 'frozen'
]

print(f"\nLegs with frozen arrivals to {loc}:")
for leg in legs_frozen_arrival:
    transit_days = model_obj.leg_transit_days.get(leg, 0)
    departure_date = curr_date - timedelta(days=transit_days)
    in_horizon = departure_date >= model_obj.start_date
    print(f"  {leg[0]} -> {leg[1]}: transit={transit_days}d, departure={departure_date}, in_horizon={in_horizon}")

# Check legs FROM Lineage (frozen departures)
legs_from_loc = model_obj.legs_from_location.get(loc, [])
frozen_legs_from = [leg for leg in legs_from_loc if model_obj.leg_arrival_state.get(leg) == 'frozen']

print(f"\nLegs with frozen departures from {loc}:")
for leg in frozen_legs_from:
    origin, dest = leg
    transit_days = model_obj.leg_transit_days.get(leg, 0)
    delivery_date = curr_date + timedelta(days=transit_days)
    in_horizon = delivery_date in model_obj.production_dates

    # Check if shipment cohort exists
    cohort_key = (leg, prod, prod_date, delivery_date)
    cohort_exists = cohort_key in model_obj.cohort_shipment_index_set

    print(f"  {origin} -> {dest}: transit={transit_days}d, delivery={delivery_date}")
    print(f"    Delivery in horizon? {in_horizon}")
    print(f"    Shipment cohort exists? {cohort_exists}")
    print(f"    Cohort key: {cohort_key}")

# Now check if initial inventory exists for prev_date
prev_date = model_obj.date_previous.get(curr_date)
print(f"\nPrevious date: {prev_date}")

if prev_date is None:
    init_inv_key = (loc, prod, prod_date, 'frozen')
    init_inv = model_obj.initial_inventory.get(init_inv_key, 0)
    print(f"  Initial inventory key: {init_inv_key}")
    print(f"  Initial inventory value: {init_inv}")
else:
    print(f"  Would use inventory from previous date")

print("\n" + "="*80)
print("EXPECTED CONSTRAINT FORMULA")
print("="*80)
print(f"\ninventory_frozen_cohort[{loc}, {prod}, {prod_date}, {curr_date}] ==")
print(f"  prev_inventory (0 for day 1)")
print(f"  + frozen_arrivals (from 6122_Storage->Lineage if departure >= start_date)")
print(f"  - frozen_departures (to 6130, delivery on {curr_date + timedelta(days=3)})")
print(f"  + freeze_input (0)")
print(f"  - thaw_output (0)")

print("\n" + "="*80)
print("THE BUG")
print("="*80)
print("If frozen_departures are NOT being subtracted, the constraint becomes:")
print(f"  inventory = 0 + arrivals - 0 = arrivals")
print(f"This matches the solution (inventory = 681 = arrivals)")
print("\nPossible causes:")
print("  1. Shipment cohort not in index set (but we verified it IS)")
print("  2. Constraint rule has a bug in the outflow calculation")
print("  3. The leg_arrival_state is wrong (not 'frozen')")

# Check leg arrival state
lineage_to_6130 = ('Lineage', '6130')
arrival_state = model_obj.leg_arrival_state.get(lineage_to_6130)
print(f"\nLeg {lineage_to_6130} arrival state: {arrival_state}")
