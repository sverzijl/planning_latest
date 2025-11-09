"""
Check end-of-horizon state: inventory + in-transit.

User insight: Should be minimal (only mix rounding), not 15k+ units!
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

# Check end state
print("="*100)
print("END-OF-HORIZON STATE ANALYSIS")
print("="*100)

last_date = max(model.dates)
print(f"\nLast date: {last_date}")

# 1. End inventory
end_inv = 0
end_inv_by_node = {}

if hasattr(model, 'inventory'):
    for (node_id, prod, state, t) in model.inventory:
        if t == last_date:
            try:
                qty = value(model.inventory[node_id, prod, state, t])
                if qty > 0.01:
                    end_inv += qty
                    key = (node_id, state)
                    end_inv_by_node[key] = end_inv_by_node.get(key, 0) + qty
            except:
                pass

print(f"\nEND INVENTORY: {end_inv:,.0f} units")
print(f"\nBreakdown by node/state:")
for (node, state), qty in sorted(end_inv_by_node.items(), key=lambda x: -x[1]):
    print(f"  {node:<10} {state:<8}: {qty:>10,.0f} units")

# 2. End in-transit (deliveries after horizon)
end_in_transit = 0
post_horizon_shipments = []

if hasattr(model, 'in_transit'):
    for (origin, dest, prod, dep_date, state) in model.in_transit:
        var = model.in_transit[origin, dest, prod, dep_date, state]
        if hasattr(var, 'stale') and var.stale:
            continue

        route = next((r for r in model_builder.routes
                     if r.origin_node_id == origin and r.destination_node_id == dest), None)

        if route:
            delivery_date = dep_date + timedelta(days=route.transit_days)

            if delivery_date > last_date:
                try:
                    qty = value(var)
                    if qty > 0.01:
                        end_in_transit += qty
                        post_horizon_shipments.append({
                            'origin': origin,
                            'dest': dest,
                            'product': prod,
                            'depart': dep_date,
                            'deliver': delivery_date,
                            'qty': qty
                        })
                except:
                    pass

print(f"\n\nEND IN-TRANSIT (post-horizon deliveries): {end_in_transit:,.0f} units")
print(f"Post-horizon shipments: {len(post_horizon_shipments)}")

if len(post_horizon_shipments) > 0:
    print(f"\nFirst 10 post-horizon shipments:")
    for ship in post_horizon_shipments[:10]:
        print(f"  {ship['origin']} → {ship['dest']}: {ship['qty']:,.0f} units, delivers {ship['deliver']} (after {last_date})")

# 3. Total end state
total_end_state = end_inv + end_in_transit

print(f"\n\n{'='*100}")
print(f"TOTAL END STATE: {total_end_state:,.0f} units")
print(f"  End inventory:  {end_inv:,.0f}")
print(f"  End in-transit: {end_in_transit:,.0f}")
print(f"{'='*100}")

# 4. Check against mix rounding
print(f"\n\nMIX ROUNDING ANALYSIS:")
print(f"Mix sizes (units_per_mix):")

max_rounding = 0
for prod_id, prod in products_dict.items():
    units_per_mix = prod.units_per_mix if hasattr(prod, 'units_per_mix') else 0
    print(f"  {prod_id[:40]:<40}: {units_per_mix:>6} units/mix")
    max_rounding += units_per_mix

print(f"\nMaximum rounding (sum of all mix sizes): {max_rounding:,.0f} units")
print(f"  (If last production batch for each product was one mix)")

excess = total_end_state - max_rounding

if excess > 1000:
    print(f"\n❌ EXCESSIVE END STATE!")
    print(f"   End state: {total_end_state:,.0f}")
    print(f"   Max rounding: {max_rounding:,.0f}")
    print(f"   Excess: {excess:,.0f} units")
    print(f"\n   Model is overproducing or not minimizing waste properly!")
elif excess > 0:
    print(f"\n⚠️  End state slightly above rounding: +{excess:,.0f} units")
    print(f"   May be due to network effects or pallet rounding")
else:
    print(f"\n✓ End state within expected rounding")

# 5. Check waste cost in objective
print(f"\n\n{'='*100}")
print(f"WASTE COST VERIFICATION:")
print(f"{'='*100}")

waste_multiplier = model_builder.cost_structure.waste_cost_multiplier
prod_cost = model_builder.cost_structure.production_cost_per_unit
waste_cost_per_unit = waste_multiplier * prod_cost

expected_waste_cost = total_end_state * waste_cost_per_unit
total_cost = solution.total_cost

print(f"\nWaste cost multiplier: {waste_multiplier}")
print(f"Production cost: ${prod_cost:.2f}/unit")
print(f"Waste cost per unit: ${waste_cost_per_unit:.2f}/unit")
print(f"\nExpected waste cost: ${expected_waste_cost:,.0f} ({total_end_state:,.0f} units × ${waste_cost_per_unit:.2f})")
print(f"Total objective: ${total_cost:,.0f}")
print(f"Waste fraction: {expected_waste_cost / total_cost * 100:.1f}% of objective")

if expected_waste_cost > 100000:
    print(f"\n❌ HIGH WASTE COST: ${expected_waste_cost:,.0f}")
    print(f"   Model is paying ${expected_waste_cost:,.0f} in waste!")
    print(f"   This suggests overproduction or waste cost not properly penalizing")

print(f"\n{'='*100}")
