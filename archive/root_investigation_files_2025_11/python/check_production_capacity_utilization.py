"""
Check if production capacity is fully utilized on early days.

MIP Hypothesis: If early days have spare capacity but model doesn't produce,
something is PREVENTING early production (wrong constraint or cost).
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Solve
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                 forecast_date=e.demand_date, quantity=e.quantity)
    for e in validated.demand_entries
]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser(
    'data/examples/Gluten Free Forecast - Latest.xlsm',
    'data/examples/Network_Config.xlsx',
    'data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
if not result.success:
    exit(1)

model = model_builder.model

# Check capacity utilization
print("="*100)
print("PRODUCTION CAPACITY UTILIZATION (First 14 Days)")
print("="*100)

production_rate = 1400  # units/hour
max_hours_weekday = 14  # 12 fixed + 2 OT
max_hours_weekend = 14  # No fixed, just OT
max_capacity_weekday = production_rate * max_hours_weekday  # 19,600 units
max_capacity_weekend = production_rate * max_hours_weekend  # 19,600 units

print(f"\nProduction rate: {production_rate:,} units/hour")
print(f"Max capacity: {max_capacity_weekday:,} units/day\n")

print(f"{'Date':<12} {'Day#':>4} {'DayType':<8} {'Production':>12} {'Capacity':>12} {'Util%':>7} {'Labor':>8}")
print("-"*100)

dates = sorted(list(model.dates))[:14]  # First 2 weeks

for i, t in enumerate(dates, 1):
    # Day type
    day_name = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][t.weekday()]
    labor_day = next((ld for ld in model_builder.labor_calendar.days if ld.date == t), None)

    is_weekend = t.weekday() in [5, 6]
    is_holiday = labor_day and labor_day.fixed_hours == 0 if labor_day else False

    if is_weekend or is_holiday:
        day_type = "Weekend"
        capacity = max_capacity_weekend
    else:
        day_type = "Weekday"
        capacity = max_capacity_weekday

    # Production
    production = 0
    for (node_id, prod, date) in model.production:
        if date == t:
            try:
                production += value(model.production[node_id, prod, date])
            except:
                pass

    # Labor
    labor = 0
    if hasattr(model, 'labor_hours_used'):
        for (node_id, date) in model.labor_hours_used:
            if date == t:
                try:
                    labor += value(model.labor_hours_used[node_id, date])
                except:
                    pass

    util = production / capacity * 100 if capacity > 0 else 0

    marker = ""
    if util < 50 and not (is_weekend or is_holiday):
        marker = " ← SPARE CAPACITY!"

    print(f"{t} {i:>4} {day_type:<8} {production:>12,.0f} {capacity:>12,.0f} {util:>6.1f}% {labor:>7.1f}h{marker}")

print("-"*100)

# Summary
print(f"\n\n{'='*100}")
print(f"MIP DIAGNOSIS:")
print(f"{'='*100}")

print(f"\nIf early days have SPARE CAPACITY but shortages exist:")
print(f"  → Model is choosing NOT to produce early (despite shortages)")
print(f"  → Something makes early production expensive or impossible")
print(f"\nIf early days are at FULL CAPACITY:")
print(f"  → Production bottleneck causes early shortages")
print(f"  → Late production becomes waste (demand already gone)")

print(f"\n{'='*100}")
