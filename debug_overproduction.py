"""
MIP Expert Debugging: Why is model overproducing by 16,756 units?

Systematic investigation following MIP debugging principles:
1. Verify objective coefficients are correct
2. Check for forcing constraints (lower bounds, minimums)
3. Analyze shadow prices/dual values
4. Test sensitivity (what happens if we force less production?)
"""

from datetime import datetime, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.models.location import LocationType
from pyomo.environ import value

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

planning_start = datetime(2025, 10, 17).date()
planning_end = planning_start + timedelta(weeks=1)

mfg = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(mfg, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_trucks = converter.convert_truck_schedules(trucks, mfg.id)

products = create_test_products(
    sorted(set(e.product_id for e in forecast.entries
              if planning_start <= e.forecast_date <= planning_end))
)

sliding_model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast, products=products,
    labor_calendar=labor_cal, cost_structure=costs,
    start_date=planning_start, end_date=planning_end,
    truck_schedules=unified_trucks, allow_shortages=True, use_pallet_tracking=False
)

result = sliding_model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.02)
solution = sliding_model.get_solution()
pyomo_model = sliding_model.model

print("="*80)
print("MIP OVERPRODUCTION DEBUGGING")
print("="*80)

# Calculate the overproduction
total_prod = solution.total_production
total_consumed = sum(solution.demand_consumed.values())
overproduction = total_prod - total_consumed

print(f"\nProduction: {total_prod:,.0f}")
print(f"Consumed: {total_consumed:,.0f}")
print(f"Overproduction: {overproduction:,.0f} units")

# Calculate economic impact
production_cost = 1.30
waste_multiplier = 10.0
waste_cost_per_unit = waste_multiplier * production_cost

cost_of_overproduction = (production_cost + waste_cost_per_unit) * overproduction
savings_from_shortage = 10.0 * overproduction

print(f"\nCost of overproducing {overproduction:,.0f} units:")
print(f"  Production: ${production_cost * overproduction:,.2f}")
print(f"  Waste: ${waste_cost_per_unit * overproduction:,.2f}")
print(f"  TOTAL COST: ${cost_of_overproduction:,.2f}")

print(f"\nCost of taking shortage instead:")
print(f"  Shortage penalty: ${savings_from_shortage:,.2f}")

print(f"\nNet waste from overproduction: ${cost_of_overproduction - savings_from_shortage:,.2f}")

print(f"\n{'❌ MODEL MAKING IRRATIONAL CHOICE' if cost_of_overproduction > savings_from_shortage else '✅ Economically rational'}")

# MIP DEBUGGING: Check for forcing constraints
print(f"\n" + "="*80)
print("CONSTRAINT INVESTIGATION")
print("="*80)

print(f"\nChecking for constraints that could FORCE production...")

# Check 1: Minimum production batch sizes
print(f"\n1. Mix-based production (integer batches):")
print(f"   units_per_mix = 415 units")
print(f"   Overproduction = {overproduction:,.0f} units = {overproduction/415:.1f} mixes")
print(f"   → Integer rounding could account for ~415 units, not {overproduction:,.0f}")

# Check 2: Truck loading
print(f"\n2. Truck capacity constraints:")
print(f"   Do truck constraints force MINIMUM loads?")
print(f"   Checking model...")

if hasattr(pyomo_model, 'truck_capacity_con'):
    print(f"   Found truck_capacity_con")
    # Sample a constraint to see its form
    sample_con = list(pyomo_model.truck_capacity_con.keys())[0] if len(pyomo_model.truck_capacity_con) > 0 else None
    if sample_con:
        con = pyomo_model.truck_capacity_con[sample_con]
        print(f"   Sample constraint: {con.expr}")
        # Check if it's <= (upper bound) or >= (lower bound - would force production!)

# Check 3: Material balance feedback
print(f"\n3. Material balance creating overproduction:")
print(f"   Hypothesis: Inventory needed at hubs to enable spoke deliveries")
print(f"   Even though spoke deliveries are post-horizon...")

# Check where the overproduction ends up
print(f"\n4. Location of overproduction (end inventory by location):")
end_inv_by_loc = {}
for (node, prod, state, date), qty in solution.inventory_state.items():
    if date == planning_end:
        end_inv_by_loc[node] = end_inv_by_loc.get(node, 0) + qty

for node in sorted(end_inv_by_loc.keys(), key=lambda x: -end_inv_by_loc[x])[:5]:
    node_type = "HUB" if node in ['6104', '6125'] else ("MFG" if node == '6122' else "DEMAND")
    print(f"   {node} ({node_type}): {end_inv_by_loc[node]:,.0f} units")

hub_inventory = sum(qty for node, qty in end_inv_by_loc.items() if node in ['6104', '6125', '6122'])
print(f"\n   Inventory at HUBS/MFG: {hub_inventory:,.0f}")
print(f"   Inventory at DEMAND nodes: {sum(end_inv_by_loc.values()) - hub_inventory:,.0f}")

if hub_inventory > overproduction * 0.5:
    print(f"\n   ❌ Most overproduction is at HUBS")
    print(f"      This suggests: Producing to position at hubs for post-horizon spoke deliveries")
    print(f"      But we filtered post-horizon shipments!")
    print(f"      → Material balance bug: Hub inventory has no outflow allowed")

print(f"\n" + "="*80)
print("ROOT CAUSE HYPOTHESIS")
print("="*80)

print(f"\nHub inventory at end: {hub_inventory:,.0f} units")
print(f"This inventory exists because:")
print(f"  A) Spoke deliveries would be post-horizon (we filtered them)")
print(f"  B) Material balance at hub requires inventory = arrivals - departures")
print(f"  C) Departures blocked (post-horizon), so arrivals accumulate as inventory")
print(f"\n→ Need to prevent ARRIVALS at hubs near end of horizon")
print(f"   If spoke delivery would be post-horizon, don't ship to hub either!")
