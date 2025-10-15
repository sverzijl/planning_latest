#!/usr/bin/env python
"""Debug material balance violation in the optimization model."""

from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from datetime import date, timedelta

# Parse test data
print("Parsing test data...")
parser = ExcelParser('data/examples/Network_Config.xlsx')
parsed_data = parser.parse_all()

# Extract components
forecast = parsed_data['forecast']
locations = parsed_data['locations']
routes = parsed_data['routes']
labor_calendar = parsed_data['labor_calendar']
truck_schedules = parsed_data['truck_schedules']
cost_structure = parsed_data['cost_structure']
manufacturing_site = parsed_data['manufacturing_site']

# Set planning horizon (4 weeks from Oct 7)
planning_start_date = date(2025, 10, 7)
planning_end_date = planning_start_date + timedelta(weeks=4)

print(f"\nPlanning horizon: {planning_start_date} to {planning_end_date}")

# Create model
print("\nBuilding model...")
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
    inventory_snapshot_date=planning_start_date,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,
)

# Build model
pyomo_model = model.build_model()

print(f"\nModel built successfully!")
print(f"Start date: {model.start_date}")
print(f"End date: {model.end_date}")

# Check how many cohort shipment variables have departure before planning horizon
print("\n" + "="*80)
print("COHORT SHIPMENT INDEX ANALYSIS")
print("="*80)

pre_horizon_count = 0
within_horizon_count = 0

for (origin, dest, prod, prod_date, delivery_date) in model.cohort_shipment_index_set:
    leg = (origin, dest)
    transit_days = model.leg_transit_days.get(leg, 0)
    departure_date = delivery_date - timedelta(days=transit_days)

    if departure_date < model.start_date:
        pre_horizon_count += 1
        if pre_horizon_count <= 10:  # Show first 10
            print(f"  Pre-horizon: {origin} -> {dest}, prod={prod_date}, depart={departure_date}, deliver={delivery_date}")
    else:
        within_horizon_count += 1

print(f"\nPre-horizon shipments in index: {pre_horizon_count}")
print(f"Within-horizon shipments in index: {within_horizon_count}")
print(f"Total: {len(model.cohort_shipment_index_set)}")

print("\n" + "="*80)
print("NO_PHANTOM_COHORT_SHIPMENTS_CON ANALYSIS")
print("="*80)

# Check if the constraint exists and how many constraints are active
if hasattr(pyomo_model, 'no_phantom_cohort_shipments_con'):
    constraint = pyomo_model.no_phantom_cohort_shipments_con
    active_count = len([key for key in constraint if constraint[key].active])
    print(f"Constraint exists: Yes")
    print(f"Total constraint instances: {len(constraint)}")
    print(f"Active constraints: {active_count}")
    print(f"Expected pre-horizon constraints: {pre_horizon_count}")

    if active_count != pre_horizon_count:
        print(f"\n⚠ WARNING: Active constraints ({active_count}) != pre-horizon shipments ({pre_horizon_count})")
else:
    print("Constraint DOES NOT EXIST!")

print("\nDone!")
