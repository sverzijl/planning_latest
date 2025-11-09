"""
Analyze waste vs shortage trade-off using MIP theory.

If model pays $204k waste, what would it cost to avoid that waste?
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
solution = model_builder.extract_solution(model)

# Analyze trade-off
print("="*100)
print("WASTE VS SHORTAGE TRADE-OFF ANALYSIS (MIP Economics)")
print("="*100)

# Get end inventory
last_date = max(model.dates)
end_inv = sum(
    value(model.inventory[node_id, prod, state, t])
    for (node_id, prod, state, t) in model.inventory
    if t == last_date and value(model.inventory[node_id, prod, state, t]) > 0.01
)

# Costs
waste_cost_per_unit = model_builder.cost_structure.waste_cost_multiplier * model_builder.cost_structure.production_cost_per_unit
shortage_cost_per_unit = model_builder.cost_structure.shortage_penalty_per_unit

actual_waste_cost = end_inv * waste_cost_per_unit
actual_shortage_cost = solution.total_shortage_units * shortage_cost_per_unit

print(f"\nCURRENT SOLUTION:")
print(f"  End inventory:    {end_inv:>10,.0f} units")
print(f"  Shortage:         {solution.total_shortage_units:>10,.0f} units")
print(f"  Waste cost:       ${actual_waste_cost:>10,.0f} ({end_inv:,.0f} × ${waste_cost_per_unit:.2f})")
print(f"  Shortage cost:    ${actual_shortage_cost:>10,.0f} ({solution.total_shortage_units:,.0f} × ${shortage_cost_per_unit:.2f})")
print(f"  Total:            ${actual_waste_cost + actual_shortage_cost:>10,.0f}")

# Alternative: Take shortage instead of holding end inventory
alternative_shortage = solution.total_shortage_units + end_inv
alternative_waste = 0

alt_waste_cost = 0
alt_shortage_cost = alternative_shortage * shortage_cost_per_unit

print(f"\nALTERNATIVE (no end inventory, take shortages instead):")
print(f"  End inventory:    {alternative_waste:>10,.0f} units")
print(f"  Shortage:         {alternative_shortage:>10,.0f} units")
print(f"  Waste cost:       ${alt_waste_cost:>10,.0f}")
print(f"  Shortage cost:    ${alt_shortage_cost:>10,.0f}")
print(f"  Total:            ${alt_waste_cost + alt_shortage_cost:>10,.0f}")

# Comparison
savings = (actual_waste_cost + actual_shortage_cost) - (alt_waste_cost + alt_shortage_cost)

print(f"\n{'='*100}")
print(f"COMPARISON:")
print(f"{'='*100}")
print(f"  Current (waste + shortage):     ${actual_waste_cost + actual_shortage_cost:>10,.0f}")
print(f"  Alternative (all shortage):     ${alt_shortage_cost:>10,.0f}")
print(f"  Difference:                     ${savings:>10,.0f}")

if savings < 0:
    print(f"\n✅ Current solution is BETTER by ${abs(savings):,.0f}")
    print(f"   Model correctly chooses waste over shortage")
elif savings > 10000:
    print(f"\n❌ Alternative would save ${savings:,.0f}!")
    print(f"   Model should prefer shortage over end inventory!")
    print(f"\n   WHY ISN'T MODEL CHOOSING THIS?")
    print(f"   Possible reasons:")
    print(f"     1. Waste cost not actually in objective")
    print(f"     2. End inventory is 'forced' by other constraints")
    print(f"     3. Shelf life constraints require early production → can't be consumed")
else:
    print(f"\n≈ Solutions are economically similar (within $10k)")

# Check if waste cost is actually in objective expression
print(f"\n\n{'='*100}")
print(f"VERIFY WASTE COST IN OBJECTIVE:")
print(f"{'='*100}")

if hasattr(model, 'obj'):
    obj_expr = str(model.obj.expr)
    has_inventory_term = 'inventory' in obj_expr
    has_in_transit_term = 'in_transit' in obj_expr

    print(f"\nObjective expression contains:")
    print(f"  'inventory' term: {has_inventory_term}")
    print(f"  'in_transit' term: {has_in_transit_term}")

    if has_inventory_term or has_in_transit_term:
        print(f"\n✓ Waste cost appears to be in objective")
    else:
        print(f"\n❌ WARNING: Waste cost may NOT be in objective!")
        print(f"   (Check lines 2760-2790 in sliding_window_model.py)")

print(f"\n{'='*100}")
