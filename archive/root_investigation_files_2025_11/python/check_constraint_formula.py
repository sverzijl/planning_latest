"""
Check the formula of material balance constraints for manufacturing on Day 1 vs Day 2+.

Hypothesis: Maybe inventory[t-1] is missing from the constraints?
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load and solve model
print("Building model...")
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

print(f"Model solved!\n")
model = model_builder.model

# Check constraints for manufacturing
print("="*80)
print("MATERIAL BALANCE CONSTRAINT FORMULAS FOR MANUFACTURING (6122)")
print("="*80)

mfg_node = '6122'
prod = 'HELGAS GFREE MIXED GRAIN 500G'  # Pick one product

dates = sorted(list(model.dates))

print(f"\nNode: {mfg_node}")
print(f"Product: {prod}")
print(f"\nShowing constraints for Days 1, 2, and 3:\n")

for i, date in enumerate(dates[:3]):
    key = (mfg_node, prod, date)

    if key in model.ambient_balance_con:
        constraint = model.ambient_balance_con[key]

        print(f"DAY {i+1} ({date}):")
        print(f"  Constraint: {constraint.expr}")

        # Try to evaluate both sides
        try:
            # Get the expression as a string to analyze it
            expr_str = str(constraint.expr)

            # Check for key terms
            has_prev_inv = f"inventory['{mfg_node}',{prod}" in expr_str and str(dates[i-1]) in expr_str if i > 0 else False
            has_init_inv = any(str(val) in expr_str for val in [1280.0, 1280])  # Known init_inv value
            has_production = f"production['{mfg_node}'" in expr_str
            has_in_transit = "in_transit" in expr_str

            print(f"  Contains inventory[t-1]: {has_prev_inv}")
            print(f"  Contains init_inv (1280): {has_init_inv}")
            print(f"  Contains production: {has_production}")
            print(f"  Contains in_transit: {has_in_transit}")

        except Exception as e:
            print(f"  Error analyzing: {e}")

        print()

print("="*80)
print("ANALYSIS:")
print("="*80)
print("\nIf Day 1 uses init_inv but Day 2+ are MISSING inventory[t-1],")
print("that would cause phantom supply!")
print("\nExpected formulas:")
print("  Day 1: I[1] = init_inv + prod[1] - depart[1]")
print("  Day 2: I[2] = I[1] + prod[2] - depart[2]  ← Should link to Day 1!")
print("  Day 3: I[3] = I[2] + prod[3] - depart[3]  ← Should link to Day 2!")
print("\n" + "="*80)
