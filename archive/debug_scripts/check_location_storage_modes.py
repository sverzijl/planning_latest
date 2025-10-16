"""Check storage modes for all locations."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser

parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = parser.parse_locations()

print("Location Storage Modes:")
print("="*70)

for loc in locations:
    print(f"{loc.id:15} {loc.name:30} {loc.type:15} {loc.storage_mode}")

# Identify intermediate storage locations
print("\n" + "="*70)
print("Intermediate Storage Locations (no demand):")
print("="*70)

# Load forecast to see which locations have demand
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
forecast = forecast_parser.parse_forecast()

locations_with_demand = set(entry.location_id for entry in forecast.entries)

for loc in locations:
    if loc.id not in locations_with_demand and loc.type == 'storage':
        print(f"{loc.id:15} {loc.name:30} {loc.storage_mode}")
