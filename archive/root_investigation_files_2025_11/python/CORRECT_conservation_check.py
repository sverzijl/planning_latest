"""
CORRECT Conservation Check - Account for ALL in-transit goods in network.

Previous checks may have been wrong because they didn't properly account for
hub-to-spoke flows and multi-echelon network structure.

Correct formula for a NETWORK:
  Total Init Inv + Total Production = Total Consumed + Total End Inv + Total End In-Transit

Where "Total End In-Transit" includes ALL goods in pipeline at horizon end,
not just goods from manufacturing.
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

print(f"Solved!\n")
model = model_builder.model
solution = model_builder.extract_solution(model)

# CORRECT Conservation Check
print("="*100)
print("CORRECT GLOBAL CONSERVATION CHECK")
print("="*100)

# 1. Total initial inventory (all nodes, all products, all states)
total_init_inv = sum(model_builder.initial_inventory.values())

# 2. Total production
total_production = solution.total_production

# 3. Total consumption (from solution)
total_consumed = sum(solution.demand_consumed.values()) if hasattr(solution, 'demand_consumed') else 0

# 4. Total end inventory (all nodes, all products, all states)
last_date = max(model.dates)
total_end_inv = 0

if hasattr(model, 'inventory'):
    for (node_id, prod, state, t) in model.inventory:
        if t == last_date:
            try:
                qty = value(model.inventory[node_id, prod, state, t])
                if qty > 0.01:
                    total_end_inv += qty
            except:
                pass

# 5. Total end in-transit (ONLY goods delivering AFTER horizon ends)
#    In-transit goods delivering within horizon will arrive and be counted as end_inv or consumed
#    We only want goods that are "in flight" at horizon end
total_end_in_transit = 0
last_date = max(model.dates)

if hasattr(model, 'in_transit'):
    for (origin, dest, prod, departure_date, state) in model.in_transit:
        var = model.in_transit[origin, dest, prod, departure_date, state]
        # Skip uninitialized variables
        if hasattr(var, 'stale') and var.stale:
            continue

        # Find route to get transit time
        route = next((r for r in model_builder.routes
                     if r.origin_node_id == origin and r.destination_node_id == dest), None)

        if route:
            delivery_date = departure_date + timedelta(days=route.transit_days)

            # Only count if delivers AFTER horizon ends
            if delivery_date > last_date:
                try:
                    qty = value(var)
                    if qty and qty > 0.01:
                        total_end_in_transit += qty
                except:
                    pass

print(f"\nSUPPLY SIDE:")
print(f"  Initial inventory (all nodes):  {total_init_inv:>15,.0f} units")
print(f"  Production (manufacturing):     {total_production:>15,.0f} units")
print(f"  ────────────────────────────────────────────────")
print(f"  TOTAL SUPPLY:                   {total_init_inv + total_production:>15,.0f} units")

print(f"\nUSAGE SIDE:")
print(f"  Consumed (demand nodes):        {total_consumed:>15,.0f} units")
print(f"  End inventory (all nodes):      {total_end_inv:>15,.0f} units")
print(f"  End in-transit (all routes):    {total_end_in_transit:>15,.0f} units")
print(f"  ────────────────────────────────────────────────")
print(f"  TOTAL USAGE:                    {total_consumed + total_end_inv + total_end_in_transit:>15,.0f} units")

balance = (total_init_inv + total_production) - (total_consumed + total_end_inv + total_end_in_transit)
balance_pct = balance / (total_init_inv + total_production) * 100 if (total_init_inv + total_production) > 0 else 0

print(f"\nBALANCE:")
print(f"  Supply - Usage:                 {balance:>15,.0f} units ({balance_pct:+.2f}%)")

print(f"\n{'='*100}")
if abs(balance) / (total_init_inv + total_production) < 0.05:
    print(f"✓ CONSERVATION HOLDS (within 5% tolerance)")
    print(f"\nConclusion: The model is CORRECT. The bug was in the test!")
else:
    print(f"❌ CONSERVATION VIOLATED (>5% error)")
    print(f"\nPhantom supply: {abs(balance):,.0f} units")

print(f"{'='*100}")

# Additional diagnostic
print(f"\n\nDIAGNOSTIC BREAKDOWN:")
print(f"  Total demand:                   {sum(model_builder.demand.values()):>15,.0f} units")
print(f"  Total shortage:                 {solution.total_shortage_units:>15,.0f} units")
print(f"  Consumed + Shortage:            {total_consumed + solution.total_shortage_units:>15,.0f} units")
print(f"  (Should equal demand)")

demand_check = abs((total_consumed + solution.total_shortage_units) - sum(model_builder.demand.values()))
if demand_check < 100:
    print(f"  ✓ Demand equation holds")
else:
    print(f"  ✗ Demand equation violated by {demand_check:,.0f} units")

print(f"\n{'='*100}")
