"""Test SlidingWindowModel with initial inventory (UI scenario).

The UI failure may be related to initial inventory handling.
"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("TEST: SlidingWindow with Initial Inventory (UI Scenario)")
print("=" * 80)

# Parse forecast and network
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Parse initial inventory
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()
print(f"\nInitial inventory snapshot: {inventory_snapshot}")
print(f"  Snapshot date: {inventory_snapshot.snapshot_date}")
print(f"  Entries: {len(inventory_snapshot.entries)}")

# Convert to unified
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Convert initial inventory to UnifiedNode format
initial_inv_dict = {}
for item in inventory_snapshot.entries:
    # Key format: (node_id, product_id, state)
    key = (item.location_id, item.product_id, 'ambient')  # Assume ambient for now
    initial_inv_dict[key] = initial_inv_dict.get(key, 0) + item.quantity

print(f"Converted initial inventory: {len(initial_inv_dict)} unique (location, product, state) combinations")
for k, v in list(initial_inv_dict.items())[:5]:
    print(f"  {k}: {v:.0f} units")

# Use snapshot date + 1 as start (standard UI pattern)
start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
end_date = start_date + timedelta(days=27)  # 4 weeks

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\nPlanning:")
print(f"  Start: {start_date}")
print(f"  End: {end_date}")
print(f"  Horizon: 4 weeks")

# Test WITH pallet tracking (like UI)
print(f"\n" + "=" * 80)
print("Building model with initial inventory + pallet tracking...")
print("=" * 80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start_date, end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,  # KEY: Initial inventory
    allow_shortages=True,
    use_pallet_tracking=True,  # KEY: Pallet tracking enabled
    use_truck_pallet_tracking=True  # KEY: Truck pallets enabled
)

pyomo_model = model.build_model()
print(f"✅ Model built")

# Check initial inventory constraints
print(f"\nModel details:")
if hasattr(pyomo_model, 'in_transit'):
    print(f"  in_transit variables: {len(list(pyomo_model.in_transit))}")

# Solve with verbose output
print(f"\n" + "=" * 80)
print("SOLVING...")
print("=" * 80)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.01, tee=True)

print(f"\n" + "=" * 80)
print("RESULT")
print("=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Optimal: {result.is_optimal()}")
print(f"Feasible: {result.is_feasible()}")

if not result.is_optimal() and not result.is_feasible():
    print(f"\n❌ INFEASIBILITY CONFIRMED with initial inventory + pallet tracking")
    print(f"\nThis is likely due to:")
    print(f"  1. Initial inventory state handling in material balance")
    print(f"  2. Initial pallet count calculation")
    print(f"  3. Interaction between initial inventory and in-transit variables")
else:
    print(f"\n✅ FEASIBLE with initial inventory + pallet tracking!")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")
