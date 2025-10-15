"""
Quick script to check what's in the solution metadata.
"""

import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.parsers import MultiFileParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.optimization.solver_config import SolverConfig
from src.models.truck_schedule import TruckScheduleCollection
from src.models.location import LocationType
from src.models.manufacturing import ManufacturingSite
from src.models.forecast import Forecast

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'examples')
NETWORK_CONFIG_PATH = os.path.join(DATA_DIR, 'Network_Config.xlsx')
FORECAST_PATH = os.path.join(DATA_DIR, 'Gfree Forecast_Converted.xlsx')

# Load data
parser = MultiFileParser(
    network_file=NETWORK_CONFIG_PATH,
    forecast_file=FORECAST_PATH
)
forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()
truck_schedules = TruckScheduleCollection(schedules=trucks_list)

# Get manufacturing site
manufacturing_site = None
for loc in locations:
    if loc.type == LocationType.MANUFACTURING:
        manufacturing_site = ManufacturingSite(
            id=loc.id,
            name=loc.name,
            type=loc.type,
            storage_mode=loc.storage_mode,
            capacity=loc.capacity,
            latitude=loc.latitude,
            longitude=loc.longitude,
            production_rate=1400.0,
            labor_calendar=labor,
            changeover_time_hours=0.5,
        )
        break

# Filter to 14 days
min_date = min(f.forecast_date for f in forecast.entries)
max_date = min_date + timedelta(days=13)
filtered_forecast_entries = [f for f in forecast.entries if min_date <= f.forecast_date <= max_date]
filtered_forecast = Forecast(name="Test Forecast", entries=filtered_forecast_entries)

# Build model
model = IntegratedProductionDistributionModel(
    forecast=filtered_forecast,
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes,
    labor_calendar=labor,
    truck_schedules=truck_schedules,
    cost_structure=costs,
    allow_shortages=True,
    enforce_shelf_life=False,
    validate_feasibility=False,
)

# Solve
solver_config = SolverConfig()
best_solver = solver_config.get_best_available_solver()
solution = model.solve(solver_name=best_solver, time_limit_seconds=300, tee=False)

print("Solution metadata keys:")
for key in sorted(solution.metadata.keys()):
    value = solution.metadata[key]
    if isinstance(value, dict):
        print(f"  {key}: dict with {len(value)} entries")
        if len(value) > 0 and len(value) <= 5:
            for k, v in list(value.items())[:3]:
                print(f"    {k}: {v}")
    elif isinstance(value, (int, float)):
        print(f"  {key}: {value}")
    elif isinstance(value, list):
        print(f"  {key}: list with {len(value)} entries")
    else:
        print(f"  {key}: {type(value).__name__}")
