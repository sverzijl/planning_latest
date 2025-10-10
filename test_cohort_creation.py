#!/usr/bin/env python3
"""
Diagnostic: Check if 6122_Storage cohorts are being created
"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

# Load data
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()

forecast_parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
forecast = forecast_parser.parse_forecast(sheet_name="G610_RET")

manufacturing_site = next((loc for loc in locations if loc.type == "manufacturing"), None)

data = {
    'forecast': forecast,
    'locations': locations,
    'routes': routes,
    'labor_calendar': labor_calendar,
    'truck_schedules': truck_schedules,
    'cost_structure': cost_structure,
    'manufacturing_site': manufacturing_site
}

# Create model
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=27)

model = IntegratedProductionDistributionModel(
    forecast=data['forecast'],
    labor_calendar=data['labor_calendar'],
    manufacturing_site=data['manufacturing_site'],
    cost_structure=data['cost_structure'],
    locations=data['locations'],
    routes=data['routes'],
    truck_schedules=TruckScheduleCollection(schedules=data['truck_schedules']),
    max_routes_per_destination=3,
    allow_shortages=True,
    enforce_shelf_life=True,
    start_date=start_date,
    end_date=end_date,
    use_batch_tracking=True,
    enable_production_smoothing=False
)

# Build model to trigger cohort index construction
print("Building model...")
pyomo_model = model.build_model()

# Check cohort indices
print("\n" + "="*70)
print("COHORT INDEX DIAGNOSTICS")
print("="*70)

# Count 6122_Storage cohorts
storage_ambient_cohorts = [c for c in model.cohort_ambient_index_set if c[0] == '6122_Storage']
print(f"\n6122_Storage ambient cohorts: {len(storage_ambient_cohorts)}")

# Show sample
print(f"\nSample (first 10):")
for cohort in sorted(storage_ambient_cohorts)[:10]:
    loc, prod, prod_date, curr_date = cohort
    age = (curr_date - prod_date).days
    print(f"  {cohort} (age: {age} days)")

# Check if production-date cohorts exist (prod_date == curr_date)
production_cohorts = [c for c in storage_ambient_cohorts if c[2] == c[3]]
print(f"\nProduction cohorts (prod_date == curr_date): {len(production_cohorts)}")
print(f"Sample (first 5):")
for cohort in sorted(production_cohorts)[:5]:
    print(f"  {cohort}")

# Verify locations_ambient_storage contains 6122_Storage
print(f"\n'6122_Storage' in locations_ambient_storage: {'6122_Storage' in model.locations_ambient_storage}")
print(f"'6122_Storage' in inventory_locations: {'6122_Storage' in model.inventory_locations}")

print("\n" + "="*70)
