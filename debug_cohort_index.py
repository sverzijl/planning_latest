#!/usr/bin/env python
"""
Check if shipment cohort indices exist for Lineage outflows.
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

# Create model with batch tracking
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

# Build the model to create cohort indices
print("\nBuilding Pyomo model...")
pyomo_model = model_obj.build_model()
print("Model built successfully")

print("\n" + "="*80)
print("CHECKING SHIPMENT COHORT INDICES FOR LINEAGE")
print("="*80)

# Check if Lineage->6130 shipment cohorts exist for Oct 7 production
lineage_leg = ('Lineage', '6130')
oct_7 = date(2025, 10, 7)
oct_10 = date(2025, 10, 10)

print(f"\nLeg: {lineage_leg}")
print(f"Production date: {oct_7}")
print(f"Delivery date: {oct_10}")
print(f"Departure date (calculated): {oct_10 - timedelta(days=3)} = {oct_7}")

# Check for each product
products = model_obj.products
for prod in products:
    key = (lineage_leg, prod, oct_7, oct_10)
    exists = key in model_obj.cohort_shipment_index_set
    print(f"\n  Product: {prod}")
    print(f"    Cohort key: {key}")
    print(f"    Exists in index? {exists}")

# Check frozen inventory cohort for Lineage on Oct 7
print("\n" + "="*80)
print(f"FROZEN INVENTORY COHORTS AT LINEAGE ON {oct_7}")
print("="*80)

for prod in products:
    key = ('Lineage', prod, oct_7, oct_7)
    exists = key in model_obj.cohort_frozen_index_set
    print(f"\n  Product: {prod}")
    print(f"    Cohort key: {key}")
    print(f"    Exists in index? {exists}")

# Check ALL shipment cohorts involving Lineage
print("\n" + "="*80)
print("ALL SHIPMENT COHORTS INVOLVING LINEAGE")
print("="*80)

lineage_shipment_cohorts = [
    key for key in model_obj.cohort_shipment_index_set
    if key[0][0] == 'Lineage' or key[0][1] == 'Lineage'
]

print(f"\nFound {len(lineage_shipment_cohorts)} shipment cohorts involving Lineage")
print("\nFirst 20:")
for key in sorted(lineage_shipment_cohorts)[:20]:
    leg, prod, prod_date, delivery_date = key
    origin, dest = leg
    transit = model_obj.leg_transit_days.get(leg, 0)
    departure_date = delivery_date - timedelta(days=transit)
    print(f"  {origin} -> {dest}: prod={prod_date}, deliver={delivery_date}, depart={departure_date}")
