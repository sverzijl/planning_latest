"""
Check if any inventory variables are negative in the solved model.
Negative inventory would allow phantom supply!
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load and solve model (same as diagnostic)
print("Building and solving model...")
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
    print(f"Solve failed: {result.termination_condition}")
    exit(1)

print(f"Solved successfully!")
model = model_builder.model

# Check for negative inventory
print(f"\n" + "="*80)
print("CHECKING FOR NEGATIVE INVENTORY")
print("="*80)

negative_count = 0
negative_examples = []

if hasattr(model, 'inventory'):
    for (node_id, prod, state, t) in model.inventory:
        try:
            qty = value(model.inventory[node_id, prod, state, t])
            if qty < -0.01:  # Allow small numerical error
                negative_count += 1
                if len(negative_examples) < 10:
                    negative_examples.append((node_id, prod, state, t, qty))
        except:
            pass

print(f"\nNegative inventory variables found: {negative_count}")

if negative_count > 0:
    print(f"\n❌ FOUND NEGATIVE INVENTORY!")
    print(f"This allows phantom supply and violates material conservation!")
    print(f"\nFirst 10 examples:")
    for (node_id, prod, state, t, qty) in negative_examples:
        print(f"  {node_id}, {prod[:30]}, {state}, {t}: {qty:.2f}")
else:
    print(f"\n✓ No negative inventory found")
    print(f"All inventory variables are >= 0")

print("\n" + "="*80)
