"""Simple test with initial inventory to reproduce UI infeasibility."""
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("SIMPLE INITIAL INVENTORY TEST")
print("=" * 80)

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=27)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Create dummy initial inventory (like UI scenario)
initial_inv = {
    ('6122', product_ids[0], 'ambient'): 1000,  # 1000 units at manufacturing
}

print(f"\nScenario: 4 weeks, with pallet tracking + initial inventory")
print(f"Initial inventory: {initial_inv}")

# Test
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print("\nBuilding...")
pyomo_model = model.build_model()

print("\nSolving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

print(f"\nResult: {result.termination_condition}")
print(f"Optimal: {result.is_optimal()}")

if not result.is_optimal():
    print(f"\n❌ INFEASIBLE with initial inventory!")
else:
    print(f"\n✅ FEASIBLE with initial inventory")
