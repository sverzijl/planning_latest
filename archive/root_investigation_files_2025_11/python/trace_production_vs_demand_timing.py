"""
Trace production timing vs demand timing to identify if shelf life forces early production.

From MIP theory: If production happens too early relative to demand,
goods expire or accumulate as end inventory.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load and solve
print("Solving 4-week model...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=entry.node_id,
        product_id=entry.product_id,
        forecast_date=entry.demand_date,
        quantity=entry.quantity
    )
    for entry in validated.demand_entries
]
forecast = Forecast(name="Test Forecast", entries=forecast_entries)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

products_dict = {p.id: p for p in validated.products}

horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

model_builder = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=start,
    end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result.success:
    print(f"Solve failed!")
    exit(1)

print(f"Solved!\n")
model = model_builder.model

# Analyze production timing vs demand timing
print("="*100)
print("PRODUCTION VS DEMAND TIMING ANALYSIS")
print("="*100)

dates = sorted(list(model.dates))

# Extract daily production
production_by_date = {}
for t in dates:
    prod_today = 0
    if hasattr(model, 'production'):
        for (node_id, prod, date) in model.production:
            if date == t:
                try:
                    prod_today += value(model.production[node_id, prod, date])
                except:
                    pass
    production_by_date[t] = prod_today

# Extract daily demand
demand_by_date = {}
for t in dates:
    demand_today = sum(
        qty for (node_id, prod, date), qty in model_builder.demand.items()
        if date == t
    )
    demand_by_date[t] = demand_today

# Calculate cumulative
print(f"\n{'Date':<12} {'DayNum':>6} {'Production':>12} {'Demand':>12} {'CumProd':>12} {'CumDemand':>12} {'Gap':>12}")
print("-"*100)

cum_prod = 0
cum_demand = 0

for i, t in enumerate(dates, 1):
    prod = production_by_date[t]
    demand = demand_by_date[t]

    cum_prod += prod
    cum_demand += demand

    gap = cum_prod - cum_demand

    marker = ""
    if prod > 1000:
        marker = " ← PRODUCTION DAY"

    print(f"{t} {i:>6} {prod:>12,.0f} {demand:>12,.0f} {cum_prod:>12,.0f} {cum_demand:>12,.0f} {gap:>12,.0f}{marker}")

print("-"*100)

# Analysis
print(f"\n\n{'='*100}")
print(f"TIMING ANALYSIS:")
print(f"{'='*100}")

# When is most production?
total_prod = sum(production_by_date.values())
early_prod = sum(production_by_date[t] for t in dates[:7])  # First week
late_prod = sum(production_by_date[t] for t in dates[-7:])  # Last week

print(f"\nProduction distribution:")
print(f"  First week (days 1-7):  {early_prod:>10,.0f} ({early_prod/total_prod*100:.1f}%)")
print(f"  Last week (days 22-28): {late_prod:>10,.0f} ({late_prod/total_prod*100:.1f}%)")

# When is most demand?
total_demand = sum(demand_by_date.values())
early_demand = sum(demand_by_date[t] for t in dates[:7])
late_demand = sum(demand_by_date[t] for t in dates[-7:])

print(f"\nDemand distribution:")
print(f"  First week (days 1-7):  {early_demand:>10,.0f} ({early_demand/total_demand*100:.1f}%)")
print(f"  Last week (days 22-28): {late_demand:>10,.0f} ({late_demand/total_demand*100:.1f}%)")

# Diagnosis
if early_prod / total_prod > 0.5 and late_demand / total_demand > 0.3:
    print(f"\n❌ FRONT-LOADED PRODUCTION PATTERN!")
    print(f"   Production happens early (week 1: {early_prod/total_prod*100:.0f}%)")
    print(f"   Demand happens later (week 4: {late_demand/total_demand*100:.0f}%)")
    print(f"\n   With 17-day shelf life, early production expires before late demand!")
    print(f"   This forces end inventory (can't be consumed in time)")

print(f"\n{'='*100}")

# Check shelf life violations
print(f"\nSHELF LIFE CHECK:")
print(f"  Ambient shelf life: 17 days")
print(f"  Planning horizon: {len(dates)} days")
print(f"\n  Production on Day 1 expires: Day 18")
print(f"  Production on Day 12 expires: Day 29 (beyond horizon!)")
print(f"\n  If most production is Days 1-12 and demand is Days 15-28,")
print(f"  goods expire before they can be consumed → forced end inventory!")

print(f"\n{'='*100}")
