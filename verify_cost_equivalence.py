"""Verify if 14d/7d and 21d/14d produce similar solutions."""
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

# Solve with both configurations
configs = [
    ('14d/7d', 14, 7),
    ('21d/14d', 21, 14),
]

for name, window, overlap in configs:
    print(f"\n{'='*60}")
    print(f"{name}: Solving...")
    print(f"{'='*60}")
    
    solver = RollingHorizonSolver(
        window_size_days=window,
        overlap_days=overlap,
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
        verbose=True
    )
    
    print(f"\nResults for {name}:")
    print(f"  Total cost: ${result.total_cost:,.2f}")
    print(f"  Windows: {result.num_windows}")
    print(f"  Feasible: {result.all_feasible}")
    
    # Check production totals
    total_production = sum(
        sum(products.values()) 
        for products in result.complete_production_plan.values()
    )
    print(f"  Total production: {total_production:,.0f} units")
    
    # Check number of production days
    production_days = len([
        date for date, products in result.complete_production_plan.items()
        if sum(products.values()) > 0
    ])
    print(f"  Production days: {production_days}")

print("\n" + "="*60)
print("CONCLUSION:")
print("="*60)
print("If production totals and patterns are similar,")
print("the cost difference is likely a prorating artifact.")
