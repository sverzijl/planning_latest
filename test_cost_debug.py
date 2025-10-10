"""Debug cost calculation to understand the difference."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver

print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

print("\n" + "="*70)
print("Testing 14d/7d configuration WITH VERBOSE OUTPUT...")
print("="*70)

solver = RollingHorizonSolver(
    window_size_days=14,
    overlap_days=7,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    allow_shortages=True,
    enforce_shelf_life=True,
    time_limit_per_window=120,
)

result = solver.solve(
    forecast=full_forecast,
    granularity_config=None,
    solver_name='cbc',
    use_aggressive_heuristics=True,
    verbose=True  # Turn ON to see cost breakdown
)

print(f"\nFINAL RESULTS:")
print(f"  Total cost: ${result.total_cost:,.2f}")
print(f"  Windows: {result.num_windows}")
print(f"  Feasible: {result.all_feasible}")
