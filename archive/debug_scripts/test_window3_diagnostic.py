"""Diagnostic test for Window 3 infeasibility."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from src.parsers.excel_parser import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models import Forecast

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

from src.models.truck_schedule import TruckScheduleCollection

data = {
    'locations': network_parser.parse_locations(),
    'routes': network_parser.parse_routes(),
    'labor_calendar': network_parser.parse_labor_calendar(),
    'truck_schedules': TruckScheduleCollection(schedules=network_parser.parse_truck_schedules()),
    'cost_structure': network_parser.parse_cost_structure(),
    'forecast': forecast_parser.parse_forecast(),
}

data['manufacturing_site'] = next((loc for loc in data['locations'] if loc.type == 'manufacturing'), None)

# Test Window 2 (feasible) vs Window 3 (infeasible)
print("=" * 70)
print("WINDOW 2: Jun 6-12 (Expected: FEASIBLE)")
print("=" * 70)

forecast_w2 = Forecast(
    name="window_2",
    entries=[e for e in data['forecast'].entries if date(2025, 6, 6) <= e.forecast_date <= date(2025, 6, 12)],
    creation_date=data['forecast'].creation_date
)

print(f"Demand entries: {len(forecast_w2.entries)}")
print(f"Date range: {min(e.forecast_date for e in forecast_w2.entries)} to {max(e.forecast_date for e in forecast_w2.entries)}")

model_w2 = IntegratedProductionDistributionModel(
    forecast=forecast_w2,
    labor_calendar=data['labor_calendar'],
    manufacturing_site=data['manufacturing_site'],
    cost_structure=data['cost_structure'],
    locations=data['locations'],
    routes=data['routes'],
    truck_schedules=data['truck_schedules'],
    max_routes_per_destination=5,
    allow_shortages=False,
)

print(f"Planning horizon (auto-extended): {model_w2.start_date} to {model_w2.end_date}")
print(f"Production dates: {len(model_w2.production_dates)} days")

result_w2 = model_w2.solve('cbc', time_limit_seconds=300)
print(f"\nResult: {result_w2.success}")
if result_w2.success:
    solution_w2 = model_w2.get_solution()
    print(f"Total cost: ${solution_w2['total_cost']:,.2f}")

    # Check ending inventory at Jun 12 (window_end_date for Window 2)
    inventory = solution_w2.get('inventory_by_dest_prod_date', {})
    jun12_inventory = {k: v for k, v in inventory.items() if k[2] == date(2025, 6, 12) and v > 1e-6}
    print(f"\nEnding inventory at Jun 12 (window_end_date): {len(jun12_inventory)} SKUs")
    if jun12_inventory:
        total = sum(jun12_inventory.values())
        print(f"  Total units: {total:,.0f}")
        for (dest, prod, d), qty in list(jun12_inventory.items())[:5]:
            print(f"    {dest}/{prod}: {qty:,.0f} units")
else:
    print(f"Infeasibility: {result_w2.infeasibility_message}")

print("\n" + "=" * 70)
print("WINDOW 3: Jun 10-16 (Expected: NOW FEASIBLE with fix)")
print("=" * 70)

forecast_w3 = Forecast(
    name="window_3",
    entries=[e for e in data['forecast'].entries if date(2025, 6, 10) <= e.forecast_date <= date(2025, 6, 16)],
    creation_date=data['forecast'].creation_date
)

print(f"Demand entries: {len(forecast_w3.entries)}")
print(f"Date range: {min(e.forecast_date for e in forecast_w3.entries)} to {max(e.forecast_date for e in forecast_w3.entries)}")

# Use inventory from Window 2 (from window_end_date = Jun 12)
initial_inventory_w3 = {(dest, prod): qty for (dest, prod, d), qty in jun12_inventory.items()} if result_w2.success else {}
print(f"\nInitial inventory: {len(initial_inventory_w3)} SKUs, {sum(initial_inventory_w3.values()):,.0f} total units")

model_w3 = IntegratedProductionDistributionModel(
    forecast=forecast_w3,
    labor_calendar=data['labor_calendar'],
    manufacturing_site=data['manufacturing_site'],
    cost_structure=data['cost_structure'],
    locations=data['locations'],
    routes=data['routes'],
    truck_schedules=data['truck_schedules'],
    max_routes_per_destination=5,
    allow_shortages=False,
    initial_inventory=initial_inventory_w3,
)

print(f"Planning horizon (auto-extended): {model_w3.start_date} to {model_w3.end_date}")
print(f"Production dates: {len(model_w3.production_dates)} days")

result_w3 = model_w3.solve('cbc', time_limit_seconds=300)
print(f"\nResult: {result_w3.success}")
if result_w3.success:
    solution_w3 = model_w3.get_solution()
    print(f"Total cost: ${solution_w3['total_cost']:,.2f}")
else:
    print(f"Infeasibility: {result_w3.infeasibility_message}")

print("\n" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
