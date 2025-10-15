"""Debug script to diagnose phantom inventory on day 1."""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from parsers.excel_parser import ExcelParser
from optimization.integrated_model import IntegratedProductionDistributionModel

# Parse data
data_file = Path("/home/sverzijl/planning_latest/data/examples/Gfree Forecast.xlsm")
parser = ExcelParser(str(data_file))
parsed_data = parser.parse_all_sheets()

forecast = parsed_data['forecast']
locations = parsed_data['locations']
routes = parsed_data['routes']
labor_calendar = parsed_data['labor_calendar']
truck_schedules = parsed_data['truck_schedules']
cost_structure = parsed_data['cost_structure']
manufacturing_site = parsed_data['manufacturing_site']

# Calculate planning horizon (4 weeks from first forecast date)
inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)
planning_start_date = inventory_snapshot_date
planning_end_date = planning_start_date + timedelta(weeks=4)

print(f"Planning horizon: {planning_start_date} to {planning_end_date}")
print(f"No initial inventory provided")

# Create model
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
    initial_inventory=None,  # No initial inventory
    inventory_snapshot_date=inventory_snapshot_date,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,
)

print(f"\n{'='*80}")
print("COHORT SHIPMENT INDEX ANALYSIS")
print(f"{'='*80}")

# Check if any shipments in cohort_shipment_index_set have departure before start_date
day1 = model.start_date
pre_horizon_arrivals = []

for (leg, prod, prod_date, delivery_date) in model.cohort_shipment_index_set:
    transit_days = model.leg_transit_days.get(leg, 0)
    departure_date = delivery_date - timedelta(days=transit_days)

    # Check if this would arrive on day 1 but depart before start
    if delivery_date == day1 and departure_date < model.start_date:
        pre_horizon_arrivals.append({
            'leg': leg,
            'product': prod,
            'prod_date': prod_date,
            'delivery_date': delivery_date,
            'departure_date': departure_date,
            'transit_days': transit_days,
        })

if pre_horizon_arrivals:
    print(f"\n❌ FOUND {len(pre_horizon_arrivals)} PRE-HORIZON ARRIVALS ON DAY 1:")
    print(f"These would create phantom inventory!\n")
    for arr in pre_horizon_arrivals[:10]:  # Show first 10
        print(f"  Leg: {arr['leg'][0]} → {arr['leg'][1]}")
        print(f"  Product: {arr['product']}")
        print(f"  Production date: {arr['prod_date']}")
        print(f"  Departure: {arr['departure_date']} (BEFORE START: {model.start_date})")
        print(f"  Arrival: {arr['delivery_date']} (DAY 1)")
        print(f"  Transit: {arr['transit_days']} days")
        print()
else:
    print("\n✓ No pre-horizon arrivals found in cohort_shipment_index_set")

# Check if no_phantom_cohort_shipments constraint would catch these
print(f"\n{'='*80}")
print("CONSTRAINT VERIFICATION")
print(f"{'='*80}")

if pre_horizon_arrivals:
    print("\nThe no_phantom_cohort_shipments constraint should force these to 0.")
    print("But they shouldn't even be in the cohort_shipment_index_set!")
    print("\nBUG LOCATION: Cohort index creation logic (lines 1143-1161)")
    print("FIX NEEDED: Filter out shipments where departure_date < start_date")
else:
    print("\nCohort index creation appears correct.")
    print("Issue must be elsewhere (arrivals, departures, or production logic).")

# Check cohort_ambient_index_set for day 1 at 6122_Storage
print(f"\n{'='*80}")
print("DAY 1 AMBIENT COHORTS AT 6122_Storage")
print(f"{'='*80}")

day1_cohorts = []
for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index_set:
    if loc == '6122_Storage' and curr_date == day1:
        day1_cohorts.append({
            'location': loc,
            'product': prod,
            'prod_date': prod_date,
            'curr_date': curr_date,
        })

print(f"\nFound {len(day1_cohorts)} ambient cohorts at 6122_Storage on day 1")
if day1_cohorts:
    print("\nFirst 5 cohorts:")
    for cohort in day1_cohorts[:5]:
        print(f"  Product: {cohort['product']}, Prod date: {cohort['prod_date']}")

    # Check if any have prod_date < start_date
    pre_start = [c for c in day1_cohorts if c['prod_date'] < model.start_date]
    if pre_start:
        print(f"\n❌ FOUND {len(pre_start)} COHORTS WITH PROD_DATE BEFORE START!")
        print("This indicates pre-horizon production dates are being included.")
    else:
        print(f"\n✓ All cohorts have prod_date >= {model.start_date}")

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Start date: {model.start_date}")
print(f"Pre-horizon shipment arrivals on day 1: {len(pre_horizon_arrivals)}")
print(f"Day 1 cohorts at 6122_Storage: {len(day1_cohorts)}")
