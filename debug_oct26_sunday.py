"""
Debug why Sunday Oct 26 has production when Friday/Monday have spare capacity.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel

# Load data
parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
data = {
    'forecast': parser.forecast,
    'labor_calendar': parser.labor_calendar,
    'manufacturing_site': parser.manufacturing_site,
    'cost_structure': parser.cost_structure,
    'locations': parser.locations,
    'routes': parser.routes,
    'truck_schedules': parser.truck_schedules,
}

print("=" * 80)
print("OCT 26 SUNDAY PRODUCTION DEBUG")
print("=" * 80)

# Focus on the weekend: Oct 24 (Fri) - Oct 27 (Mon)
oct24 = date(2025, 10, 24)  # Friday
oct25 = date(2025, 10, 25)  # Saturday
oct26 = date(2025, 10, 26)  # Sunday
oct27 = date(2025, 10, 27)  # Monday

print(f"\nWeekend dates:")
print(f"  Oct 24 (Fri): {oct24.strftime('%A')}")
print(f"  Oct 25 (Sat): {oct25.strftime('%A')}")
print(f"  Oct 26 (Sun): {oct26.strftime('%A')}")
print(f"  Oct 27 (Mon): {oct27.strftime('%A')}")

# Check labor calendar
print(f"\nLabor calendar:")
for d in [oct24, oct25, oct26, oct27]:
    labor_day = data['labor_calendar'].get_day_for_date(d)
    if labor_day:
        print(f"  {d} ({d.strftime('%a')}): Fixed={labor_day.is_fixed_day}, "
              f"Fixed_hours={labor_day.fixed_hours}, Max_hours={labor_day.max_hours}")

# Check demand around this period
print(f"\nDemand forecast (Oct 24-30):")
start = oct24
end = date(2025, 10, 30)
total_demand = {}
for entry in data['forecast'].entries:
    if start <= entry.forecast_date <= end:
        d = entry.forecast_date
        if d not in total_demand:
            total_demand[d] = 0
        total_demand[d] += entry.quantity

for d in sorted(total_demand.keys()):
    print(f"  {d} ({d.strftime('%a')}): {total_demand[d]:,.0f} units")

# Check truck schedules for Oct 27 (Monday)
print(f"\nTruck schedules for Monday Oct 27:")
monday_schedules = [s for s in data['truck_schedules'].schedules 
                   if s.departure_date.weekday() == 0]  # Monday = 0
if monday_schedules:
    print(f"  Morning trucks: {[s for s in monday_schedules if 'morning' in s.time_of_day.lower()]}")
    print(f"  Afternoon trucks: {[s for s in monday_schedules if 'afternoon' in s.time_of_day.lower()]}")

# Build and solve model with limited horizon
print(f"\n" + "=" * 80)
print("SOLVING MODEL (Oct 17-30, 2 weeks)")
print("=" * 80)

# Filter forecast to 2-week period around the issue
start_date = date(2025, 10, 17)
end_date = date(2025, 10, 30)
filtered_entries = [e for e in data['forecast'].entries 
                   if start_date <= e.forecast_date <= end_date]
data['forecast'].entries = filtered_entries

print(f"\nFiltered forecast: {len(filtered_entries)} entries")
print(f"Date range: {start_date} to {end_date}")

model = IntegratedProductionDistributionModel(
    forecast=data['forecast'],
    labor_calendar=data['labor_calendar'],
    manufacturing_site=data['manufacturing_site'],
    cost_structure=data['cost_structure'],
    locations=data['locations'],
    routes=data['routes'],
    truck_schedules=data['truck_schedules'],
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory={}
)

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

print(f"\nSolver status: {result.status}")
print(f"Total cost: ${result.objective_value:,.2f}")

# Analyze production and capacity for Oct 24-27
print(f"\n" + "=" * 80)
print("PRODUCTION AND CAPACITY ANALYSIS")
print("=" * 80)
print(f"{'Date':<12} {'Day':<10} {'Production':<12} {'Labor Hrs':<12} {'Capacity':<12} {'Labor Cost':<12}")
print("-" * 80)

for d in [oct24, oct25, oct26, oct27]:
    if d not in model.production_dates:
        continue
    
    day_name = d.strftime("%A")
    
    # Get production
    production = sum(result.production.get((d, p.id), 0.0) 
                    for p in data['forecast'].products)
    
    # Get labor hours
    labor_hours = result.labor_hours.get(d, 0.0)
    
    # Calculate capacity
    labor_day = data['labor_calendar'].get_day_for_date(d)
    max_hours = labor_day.max_hours if labor_day else 0
    capacity = max_hours * data['manufacturing_site'].production_rate_per_hour
    
    # Get labor cost
    labor_cost = result.labor_cost_by_date.get(d, 0.0)
    
    spare_capacity = capacity - production
    
    print(f"{d} {day_name:<10} {production:>10.0f} {labor_hours:>10.2f}h "
          f"{spare_capacity:>10.0f} ${labor_cost:>10.2f}")

print("-" * 80)

# Check what's being shipped on Monday
print(f"\n" + "=" * 80)
print("SHIPMENTS AFTER OCT 26 PRODUCTION")
print("=" * 80)

# Look for shipments departing Oct 26-27
for route_id, product_id, ship_date in sorted(result.shipments.keys()):
    qty = result.shipments[(route_id, product_id, ship_date)]
    if qty > 0 and ship_date >= oct26 and ship_date <= oct27:
        route = next((r for r in data['routes'] if r.route_id == route_id), None)
        if route:
            print(f"  {ship_date}: {route.origin} → {route.destination} "
                  f"(Product {product_id}): {qty:,.0f} units")

print("\n" + "=" * 80)
