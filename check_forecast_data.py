"""Check what's in the forecast data."""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser

forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
forecast = forecast_parser.parse_forecast()

# Get unique values
products = set(e.product_id for e in forecast.entries)
locations = set(e.location_id for e in forecast.entries)
dates = set(e.forecast_date for e in forecast.entries)

print(f'Total entries: {len(forecast.entries)}')
print(f'\nProducts ({len(products)}): {sorted(products)}')
print(f'\nLocations ({len(locations)}): {sorted(locations)}')
print(f'\nDate range: {min(dates)} to {max(dates)}')

# Show first 10 entries
print(f'\nFirst 10 entries:')
for i, entry in enumerate(forecast.entries[:10]):
    print(f'  {entry.location_id} | {entry.product_id} | {entry.forecast_date} | {entry.quantity}')
