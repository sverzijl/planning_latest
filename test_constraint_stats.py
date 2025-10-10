"""Check constraint statistics."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import Constraint, Var

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

print('Building model WITH D-1/D0 timing constraints...')
model_with = IntegratedProductionDistributionModel(
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
)

# Build Pyomo model to get statistics
pyomo_model = model_with.build_model()

# Count constraints
num_constraints = sum(1 for _ in pyomo_model.component_data_objects(ctype=Constraint, active=True))
num_variables = sum(1 for _ in pyomo_model.component_data_objects(ctype=Var, active=True))

print(f'\n📊 MODEL STATISTICS:')
print(f'  Variables: {num_variables:,}')
print(f'  Constraints: {num_constraints:,}')
print(f'  Routes: {len(model_with.enumerated_routes)}')
print(f'  Production dates: {len(model_with.production_dates)}')
print(f'  Trucks: {len(model_with.truck_indices)}')
print(f'  Truck destinations: {len(model_with.truck_destinations) if hasattr(model_with, "truck_destinations") else "N/A"}')
print(f'  Products: {len(model_with.products)}')

# Calculate expected truck_production_timing constraints
# Should be: trucks × truck_destinations × products × dates
if hasattr(model_with, 'truck_destinations'):
    expected_timing_constraints = (
        len(model_with.truck_indices) *
        len(model_with.truck_destinations) *
        len(model_with.products) *
        len(model_with.production_dates)
    )
    print(f'\n🔍 Expected truck_production_timing constraints: {expected_timing_constraints:,}')
    print(f'  = {len(model_with.truck_indices)} trucks × {len(model_with.truck_destinations)} dests × {len(model_with.products)} products × {len(model_with.production_dates)} dates')

# Check truck info
print(f'\n🚚 TRUCK INFO:')
for truck_idx in list(model_with.truck_indices)[:5]:  # Show first 5
    truck = model_with.truck_by_index[truck_idx]
    print(f'  Truck {truck_idx}: {truck.truck_name} - {truck.departure_type} - dest:{truck.destination_id}')
