"""
Verify mass balance with CORRECTED outflow calculation.

The previous diagnostic was calculating outflows wrong - it summed shipment_leg
by delivery date, but shipment_leg is indexed by ARRIVAL date. To get departures,
we need to account for transit time.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value
from datetime import timedelta

print("=" * 80)
print("MASS BALANCE VERIFICATION (CORRECTED OUTFLOW CALCULATION)")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=False,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

print("\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

if not result.success:
    print("\n❌ Solve failed")
    sys.exit(1)

pyomo_model = model.model

print(f"\n{'=' * 80}")
print("HUB FLOW VERIFICATION (CORRECTED)")
print("=" * 80)

# Check hub inventories throughout planning horizon
hubs = {'6104', '6125'}

for hub in sorted(hubs):
    print(f"\n{hub}:")

    # Get hub demand
    hub_demand = sum(v for (loc, p, d), v in model.demand.items() if loc == hub)
    print(f"  Total demand at hub: {hub_demand:,.0f} units")

    # Get total inflows (arrivals at hub - indexed by delivery date, which is correct)
    hub_inflow = 0
    for (origin, dest) in model.leg_keys:
        if dest == hub:
            for p in pyomo_model.products:
                for d in pyomo_model.dates:
                    hub_inflow += value(pyomo_model.shipment_leg[(origin, dest), p, d])

    print(f"  Total inflows:       {hub_inflow:,.0f} units")

    # Get total outflows (CORRECTED: sum by DEPARTURE date, not arrival date)
    hub_outflow = 0
    legs_from_hub = model.legs_from_location.get(hub, [])

    for departure_date in pyomo_model.dates:
        for (origin, dest) in legs_from_hub:
            if model.leg_arrival_state.get((origin, dest)) == 'ambient':
                transit_days = model.leg_transit_days[(origin, dest)]
                arrival_date = departure_date + timedelta(days=transit_days)

                # Only count if arrival is within planning horizon
                if arrival_date in pyomo_model.dates:
                    for p in pyomo_model.products:
                        qty = value(pyomo_model.shipment_leg[(origin, dest), p, arrival_date])
                        hub_outflow += qty

    print(f"  Total outflows:      {hub_outflow:,.0f} units (CORRECTED)")

    # Check inventory
    final_date = max(pyomo_model.dates)
    hub_final_inv = 0
    for p in pyomo_model.products:
        if (hub, p, final_date) in pyomo_model.inventory_ambient:
            hub_final_inv += value(pyomo_model.inventory_ambient[hub, p, final_date])

    print(f"  Final inventory:     {hub_final_inv:,.0f} units")

    # Check balance
    # Inflow should equal: Demand + Outflow + Final Inventory
    expected_inflow = hub_demand + hub_outflow + hub_final_inv
    diff = abs(hub_inflow - expected_inflow)

    print(f"  Balance check:")
    print(f"    Inflow = Demand + Outflow + Final Inv?")
    print(f"    {hub_inflow:,.0f} = {hub_demand:,.0f} + {hub_outflow:,.0f} + {hub_final_inv:,.0f}")
    print(f"    {hub_inflow:,.0f} vs {expected_inflow:,.0f} (diff: {diff:,.0f})")

    if diff < 1.0:
        print(f"    ✅ Hub balance correct!")
    else:
        print(f"    ⚠️  Hub balance error!")

print(f"\n{'=' * 80}")
