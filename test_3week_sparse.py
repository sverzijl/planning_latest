"""Test 3-week performance with sparse indexing."""

from datetime import date, timedelta
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

print("Testing 3-week performance with sparse indexing...")

network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

start_date = date(2025, 6, 2)
end_date = start_date + timedelta(days=20)  # 3 weeks

filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
horizon_forecast = Forecast(name="3W", entries=filtered_entries, creation_date=date.today())

print(f"Building model (3 weeks: {start_date} to {end_date})...")
print(f"Forecast entries: {len(filtered_entries)}")

model_obj = IntegratedProductionDistributionModel(
    forecast=horizon_forecast,
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

pyomo_model = model_obj.build_model()

num_vars = pyomo_model.nvariables()
num_cons = pyomo_model.nconstraints()
num_binary = sum(1 for v in pyomo_model.component_data_objects(Var) if v.is_binary())
truck_load_vars = sum(1 for v in pyomo_model.component_data_objects(Var) if 'truck_load' in str(v))

print(f"\nModel statistics:")
print(f"  Total variables: {num_vars:,}")
print(f"  Constraints: {num_cons:,}")
print(f"  Binary variables: {num_binary:,}")
print(f"  truck_load variables: {truck_load_vars:,}")

print(f"\nSolving with 30s timeout...")
result = model_obj.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=True)

print(f"\n{'='*70}")
print(f"RESULTS")
print(f"{'='*70}")
print(f"Status: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.2f}s")
if result.objective_value:
    print(f"Objective: ${result.objective_value:,.2f}")
if result.gap:
    print(f"Gap: {result.gap*100:.2f}%")

if result.solve_time_seconds >= 29:
    print("\n⚠️  HIT TIME LIMIT - 3-week problem still too slow!")
else:
    print("\n✅ Solved within time limit")

# Comparison
print(f"\nComparison:")
print(f"  Dense indexing (from summary): >120s timeout")
print(f"  Sparse indexing (this test): {result.solve_time_seconds:.2f}s")
