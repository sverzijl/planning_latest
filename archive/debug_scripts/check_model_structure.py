"""
Check model structure to diagnose infeasibility.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("MODEL STRUCTURE DIAGNOSIS")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

# Parse all data
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Filter to 3 weeks
start_date = date(2025, 10, 13)
end_date = date(2025, 11, 2)
filtered_entries = [e for e in forecast.entries
                   if start_date <= e.forecast_date <= end_date]
forecast.entries = filtered_entries

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Check manufacturing site storage mode
print(f"\nManufacturing site: {manufacturing_site.location_id}")
print(f"  Name: {manufacturing_site.name}")
print(f"  Storage mode: {manufacturing_site.storage_mode}")
print(f"  Location type: {manufacturing_site.location_type}")

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122', pid, 'ambient')] = 10000.0

print(f"\nInitial inventory: {len(initial_inv)} entries")
for key, val in list(initial_inv.items())[:3]:
    print(f"  {key}: {val}")

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print(f"\nModel structure:")
print(f"  Planning dates: {len(model.production_dates)} days")
print(f"    First: {min(model.production_dates)}")
print(f"    Last: {max(model.production_dates)}")
print(f"  Routes: {len(model.enumerated_routes)}")
print(f"  Products: {len(model.products)}")

print(f"\n  Inventory locations: {len(model.inventory_locations)}")
print(f"    {sorted(model.inventory_locations)}")

print(f"\n  Locations with ambient storage: {len(model.locations_ambient_storage)}")
print(f"    Manufacturing site (6122) in set: {manufacturing_site.location_id in model.locations_ambient_storage}")
print(f"    {sorted(model.locations_ambient_storage)}")

print(f"\n  Locations with frozen storage: {len(model.locations_frozen_storage)}")
print(f"    {sorted(model.locations_frozen_storage)}")

print(f"\n  Inventory ambient index set size: {len(model.inventory_ambient_index_set)}")
mfg_ambient_count = sum(1 for (loc, prod, date) in model.inventory_ambient_index_set
                         if loc == '6122')
print(f"    Entries for manufacturing site (6122): {mfg_ambient_count}")
if mfg_ambient_count > 0:
    print(f"    Sample entries:")
    for (loc, prod, date) in list(model.inventory_ambient_index_set)[:5]:
        if loc == '6122':
            print(f"      ('{loc}', '{prod}', {date})")

print(f"\n  Inventory frozen index set size: {len(model.inventory_frozen_index_set)}")

# Check truck schedules
print(f"\n  Truck schedules: {len(model.truck_schedules_list)}")
for i, truck in enumerate(model.truck_schedules_list[:3]):
    print(f"    Truck {i}: {truck.departure_type} to {truck.destination}")
    # Check first-day morning trucks
    for dest in model.destinations:
        for prod in product_ids[:1]:  # Just first product
            for delivery_date in list(model.production_dates)[:2]:  # First 2 days
                transit_days = model._get_truck_transit_days(i, dest)
                departure_date = delivery_date - timedelta(days=transit_days)
                if departure_date in model.production_dates:
                    if truck.departure_type == 'morning':
                        inv_date = departure_date - timedelta(days=1)
                        if inv_date not in model.production_dates:
                            print(f"      First-day morning truck: truck{i} to {dest}, prod {prod}")
                            print(f"        Departs {departure_date}, needs Day0 inventory")
                            print(f"        Initial inv for (6122, {prod}, ambient): {initial_inv.get(('6122', prod, 'ambient'), 0)}")

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE - Check if 6122 is in ambient storage locations")
print("=" * 80)
