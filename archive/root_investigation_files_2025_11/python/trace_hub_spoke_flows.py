"""
Trace hub-to-spoke flows to see if goods are double-counted.

Node 6104 departs 296 units on Day 1 to spokes.
Do those 296 units arrive at destination nodes?
Or are they lost/double-counted somewhere?
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

# Check hub-spoke flows on Day 1
print("="*100)
print("HUB-TO-SPOKE FLOW VERIFICATION - DAY 1")
print("="*100)

day1 = min(model.dates)
prod = 'HELGAS GFREE MIXED GRAIN 500G'

print(f"\nDate: {day1}")
print(f"Product: {prod}\n")

# Find all routes FROM 6104 (hub) to spokes
print("DEPARTURES FROM HUB 6104:")
total_departures = 0

for route in model_builder.routes:
    if route.origin_node_id == '6104':
        for state in ['ambient', 'frozen']:
            key = ('6104', route.destination_node_id, prod, day1, state)
            if key in model.in_transit:
                try:
                    qty = value(model.in_transit[key])
                    if qty > 0.01:
                        print(f"  6104 → {route.destination_node_id}: {qty:,.0f} units (state={state}, transit={route.transit_days}d)")
                        total_departures += qty

                        # Calculate arrival date
                        arrival_date = day1 + timedelta(days=route.transit_days)
                        print(f"    Should arrive on: {arrival_date}")

                        # Check if this arrival is counted at destination
                        if arrival_date in model.dates:
                            # Check material balance at destination on arrival date
                            dest = route.destination_node_id
                            if (dest, prod, 'ambient', arrival_date) in model.inventory:
                                # The arrival should be counted in the material balance
                                print(f"    Arrival date {arrival_date} is within horizon ✓")
                            else:
                                print(f"    ⚠️  No inventory variable for destination on arrival date")
                        else:
                            print(f"    ⚠️  Arrival date {arrival_date} is BEYOND HORIZON!")
                            print(f"       These units will NEVER arrive as far as model is concerned!")

                except:
                    pass

print(f"\nTotal departures from 6104 on {day1}: {total_departures:,.0f} units")

# Now check if these arrivals are counted at spoke nodes
print(f"\n\nARRIVALS AT SPOKE NODES (from 6104 shipments):")

total_arrivals_counted = 0

for route in model_builder.routes:
    if route.origin_node_id == '6104':
        arrival_date = day1 + timedelta(days=route.transit_days)

        if arrival_date in model.dates:
            dest = route.destination_node_id

            # Check if arrival is counted in material balance on arrival_date
            # Material balance should have: arrivals += in_transit[6104, dest, prod, day1, state]

            for state in ['ambient', 'frozen']:
                key = ('6104', dest, prod, day1, state)
                if key in model.in_transit:
                    try:
                        qty = value(model.in_transit[key])
                        if qty > 0.01:
                            print(f"  {dest} receives {qty:,.0f} on {arrival_date} (from 6104 shipment on {day1})")
                            total_arrivals_counted += qty
                    except:
                        pass

print(f"\nTotal arrivals counted: {total_arrivals_counted:,.0f} units")

print(f"\n\n{'='*100}")
print(f"VERIFICATION:")
print(f"{'='*100}")
print(f"\nDepartures from 6104: {total_departures:,.0f}")
print(f"Arrivals at spokes:   {total_arrivals_counted:,.0f}")
print(f"Difference:           {total_departures - total_arrivals_counted:,.0f}")

if abs(total_departures - total_arrivals_counted) < 1:
    print(f"\n✓ Hub-spoke flows balance (departures = arrivals)")
else:
    print(f"\n❌ MISMATCH! Goods leaving hub don't match arrivals at spokes!")

print(f"\n{'='*100}")
