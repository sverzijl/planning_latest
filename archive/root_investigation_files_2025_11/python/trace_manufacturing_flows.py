"""
Trace all flows FROM manufacturing node (6122).

This will reveal if departures exceed available supply.
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

print(f"Solved successfully!\n")
model = model_builder.model

# Analyze manufacturing flows
print("="*80)
print("MANUFACTURING NODE (6122) FLOW ANALYSIS")
print("="*80)

mfg_node = '6122'

# 1. Available supply
init_inv_6122 = sum(model_builder.initial_inventory.get((mfg_node, prod, state), 0)
                    for prod in model.products
                    for state in ['ambient', 'frozen'])

production_6122 = 0
if hasattr(model, 'production'):
    for (node_id, prod, t) in model.production:
        if node_id == mfg_node:
            try:
                production_6122 += value(model.production[node_id, prod, t])
            except:
                pass

available_supply = init_inv_6122 + production_6122

print(f"\nAVAILABLE SUPPLY:")
print(f"  Initial inventory: {init_inv_6122:>12,.0f} units")
print(f"  Production:        {production_6122:>12,.0f} units")
print(f"  ────────────────────────────────")
print(f"  TOTAL AVAILABLE:   {available_supply:>12,.0f} units")

# 2. Departures (all in_transit flows FROM 6122)
print(f"\n\nDEPARTURES (in_transit flows FROM {mfg_node}):")
print(f"{'Date':<12} {'Destination':<10} {'Product':<35} {'State':<8} {'Quantity':>10}")
print("-"*80)

total_departures = 0
departures_by_dest = {}
departures_by_date = {}

if hasattr(model, 'in_transit'):
    for (origin, dest, prod, t, state) in model.in_transit:
        if origin == mfg_node:
            try:
                qty = value(model.in_transit[origin, dest, prod, t, state])
                if qty > 0.01:
                    total_departures += qty
                    departures_by_dest[dest] = departures_by_dest.get(dest, 0) + qty
                    departures_by_date[t] = departures_by_date.get(t, 0) + qty

                    print(f"{t} {dest:<10} {prod[:35]:<35} {state:<8} {qty:>10,.0f}")
            except:
                pass

print("-"*80)
print(f"{'TOTAL DEPARTURES':<58} {total_departures:>10,.0f} units")

# 3. End inventory at manufacturing
end_inv_6122 = 0
last_date = max(model.dates)

if hasattr(model, 'inventory'):
    for (node_id, prod, state, t) in model.inventory:
        if node_id == mfg_node and t == last_date:
            try:
                end_inv_6122 += value(model.inventory[node_id, prod, state, t])
            except:
                pass

print(f"\n\nEND INVENTORY:")
print(f"  At {mfg_node} on {last_date}: {end_inv_6122:>12,.0f} units")

# 4. Material balance check
print(f"\n\n{'='*80}")
print(f"MANUFACTURING MATERIAL BALANCE CHECK")
print(f"{'='*80}")

expected_usage = total_departures + end_inv_6122
balance = available_supply - expected_usage

print(f"\nSupply: {available_supply:>12,.0f} units (init_inv + production)")
print(f"Usage:  {expected_usage:>12,.0f} units (departures + end_inv)")
print(f"        {total_departures:>12,.0f}   departures")
print(f"        {end_inv_6122:>12,.0f}   end_inv")
print(f"Balance: {balance:>11,.0f} units")

if abs(balance) < 100:
    print(f"\n✓ Material balance HOLDS at manufacturing!")
else:
    print(f"\n❌ Material balance VIOLATED at manufacturing!")
    print(f"   Departures + end_inv EXCEEDS available supply by {abs(balance):,.0f} units!")

# 5. Summary by destination
print(f"\n\n{'='*80}")
print(f"DEPARTURES BY DESTINATION")
print(f"{'='*80}")
print(f"\n{'Destination':<15} {'Total Shipped':>15}")
print("-"*35)
for dest in sorted(departures_by_dest.keys()):
    print(f"{dest:<15} {departures_by_dest[dest]:>15,.0f}")
print("-"*35)
print(f"{'TOTAL':<15} {sum(departures_by_dest.values()):>15,.0f}")

# 6. CRITICAL: Compare to arrivals at demand nodes
print(f"\n\n{'='*80}")
print(f"ARRIVALS AT DEMAND NODES (from in_transit)")
print(f"{'='*80}")

arrivals_by_node = {}

if hasattr(model, 'in_transit'):
    for (origin, dest, prod, dep_date, state) in model.in_transit:
        if origin == mfg_node:  # Only shipments FROM manufacturing
            # Find route to get transit time
            route = next((r for r in model_builder.routes
                         if r.origin_node_id == origin and r.destination_node_id == dest), None)

            if route:
                delivery_date = dep_date + timedelta(days=route.transit_days)

                try:
                    qty = value(model.in_transit[origin, dest, prod, dep_date, state])
                    if qty > 0.01:
                        arrivals_by_node[dest] = arrivals_by_node.get(dest, 0) + qty
                except:
                    pass

print(f"\n{'Node':<15} {'Arrivals from 6122':>20}")
print("-"*40)
for node in sorted(arrivals_by_node.keys()):
    print(f"{node:<15} {arrivals_by_node[node]:>20,.0f}")
print("-"*40)
print(f"{'TOTAL':<15} {sum(arrivals_by_node.values()):>20,.0f}")

print(f"\n\nSHOULD MATCH: Departures = Arrivals (within rounding)")
print(f"  Departures: {total_departures:,.0f}")
print(f"  Arrivals:   {sum(arrivals_by_node.values()):,.0f}")
print(f"  Difference: {abs(total_departures - sum(arrivals_by_node.values())):,.0f}")

print(f"\n{'='*80}")
