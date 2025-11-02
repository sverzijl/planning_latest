"""Force test with EXACT snapshot date user specified: 2025-10-16"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("FORCED TEST: Snapshot 2025-10-16, 4-week horizon")
print("=" * 80)

# Parse
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
inventory_snapshot = inv_parser.parse()

print(f"\nInventory file snapshot date: {inventory_snapshot.snapshot_date}")

# FORCE snapshot date to what user specified
FORCED_SNAPSHOT_DATE = date(2025, 10, 16)
print(f"FORCING snapshot date to: {FORCED_SNAPSHOT_DATE}")

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Use FORCED date
start_date = FORCED_SNAPSHOT_DATE + timedelta(days=1)  # 2025-10-17
end_date = start_date + timedelta(days=27)  # 4 weeks

print(f"\nPlanning horizon:")
print(f"  Start: {start_date}")
print(f"  End: {end_date}")
print(f"  Duration: 4 weeks")

# Check forecast data availability
forecast_dates = set(e.forecast_date for e in forecast.entries)
forecast_min = min(forecast_dates)
forecast_max = max(forecast_dates)
print(f"\nForecast data range: {forecast_min} to {forecast_max}")

if start_date < forecast_min:
    print(f"  ⚠️  Planning starts BEFORE forecast data!")
    print(f"     This will cause zero demand on first days")

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert inventory
initial_inv_dict = {}
if hasattr(inventory_snapshot, 'to_optimization_dict'):
    initial_inv_dict = inventory_snapshot.to_optimization_dict()
else:
    for entry in inventory_snapshot.entries:
        key = (entry.location_id, entry.product_id, 'ambient')
        initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

print(f"\nInitial inventory: {len(initial_inv_dict)} entries, {sum(initial_inv_dict.values()):,.0f} units")

# Build model with EXACT user settings
print(f"\nBuilding model...")
model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inv_dict,
    inventory_snapshot_date=FORCED_SNAPSHOT_DATE,  # Use forced date
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

pyomo_model = model.build_model()

# Solve
from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.load_solution = False
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

results = solver.solve(pyomo_model)

print(f"\n" + "=" * 80)
print("RESULT WITH FORCED SNAPSHOT 2025-10-16")
print("=" * 80)
print(f"Termination: {results.termination_condition}")

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
if results.termination_condition == AppsiTC.infeasible:
    print(f"\n❌ INFEASIBLE - Issue REPLICATED!")
    print(f"\n   Now we can debug the real problem")
elif results.termination_condition == AppsiTC.optimal:
    print(f"\n✅ OPTIMAL")
    print(f"   Objective: ${results.best_feasible_objective:,.2f}")
