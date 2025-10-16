"""Quick sparse indexing test - incremental saves."""

import json
from datetime import date, timedelta
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

print("="*70)
print("QUICK SPARSE INDEXING TEST")
print("="*70)

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

results = []

for weeks in [1, 2]:
    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(name=f"{weeks}W", entries=filtered_entries, creation_date=date.today())

    print(f"\n{weeks} WEEKS ({start_date} to {end_date})")
    print(f"  Entries: {len(filtered_entries)}")

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
    truck_load_vars = sum(1 for v in pyomo_model.component_data_objects(Var) if 'truck_load' in str(v))

    print(f"  Variables: {num_vars:,} total, {truck_load_vars:,} truck_load")
    print(f"  Solving...")

    result = model_obj.solve(solver_name='cbc', time_limit_seconds=30, mip_gap=0.01, tee=False)

    print(f"  Status: {result.termination_condition}")
    print(f"  Time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")

    results.append({
        'weeks': weeks,
        'time': result.solve_time_seconds,
        'vars': num_vars,
        'truck_load_vars': truck_load_vars,
        'status': str(result.termination_condition),
        'objective': result.objective_value
    })

# Save
with open('sparse_quick_results.json', 'w') as f:
    json.dump({'results': results}, f, indent=2, default=str)

# Load baseline for comparison
try:
    with open('solver_performance_results.json', 'r') as f:
        baseline = json.load(f)['results']

    print(f"\n{'='*70}")
    print("COMPARISON WITH BASELINE")
    print(f"{'='*70}")
    print(f"\n{'Weeks':<8} {'Dense Time':<12} {'Sparse Time':<12} {'Speedup':<10} {'Dense Vars':<12} {'Sparse Vars':<12} {'Reduction':<10}")
    print("-"*80)

    for r in results:
        b = next((x for x in baseline if x.get('horizon_weeks') == r['weeks']), None)
        if b:
            speedup = b['solve_time_seconds'] / r['time'] if r['time'] > 0 else 0
            var_reduction = (1 - r['vars'] / b['num_variables']) * 100 if b['num_variables'] > 0 else 0
            print(f"{r['weeks']:<8} {b['solve_time_seconds']:<12.2f} {r['time']:<12.2f} {speedup:<9.2f}x {b['num_variables']:<12,} {r['vars']:<12,} {var_reduction:<9.1f}%")

except FileNotFoundError:
    print("\nNo baseline found")

print(f"\n✅ Results saved to sparse_quick_results.json")
