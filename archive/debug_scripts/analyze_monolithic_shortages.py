"""Analyze which demand is not met in monolithic solve."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from collections import defaultdict

print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

print("\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=full_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory={},
)

print("\nSolving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

if not result.is_feasible():
    print("Model is infeasible!")
    sys.exit(1)

print("\nExtracting solution...")
solution = model.get_solution()

# Get shortage variables from solution
shortage_by_dest_product_date = solution.get('shortage_by_dest_product_date', {})

# Calculate total shortages
total_shortage = 0.0
shortages_by_date = defaultdict(float)
shortages_by_dest = defaultdict(float)

for key, value in shortage_by_dest_product_date.items():
    if value > 0:
        total_shortage += value
        if isinstance(key, tuple) and len(key) >= 3:
            dest, product, date = key[0], key[1], key[2]
            shortages_by_date[date] += value
            shortages_by_dest[dest] += value

print(f"\n{'='*70}")
print("SHORTAGE ANALYSIS")
print(f"{'='*70}")

if total_shortage == 0:
    print("\n✓ NO SHORTAGES DETECTED in solution variables")
    print("\nBut production (2,252,419) < demand (2,407,299)")
    print("Investigating where the difference comes from...")

    # Calculate actual deliveries from shipments
    shipments = solution.get('shipments', [])
    deliveries_by_dest_product_date = defaultdict(float)

    for shipment in shipments:
        dest = shipment.destination_id
        product = shipment.product_id
        delivery_date = shipment.delivery_date
        quantity = shipment.quantity
        deliveries_by_dest_product_date[(dest, product, delivery_date)] += quantity

    # Compare with forecast
    print(f"\n{'='*70}")
    print("DEMAND VS DELIVERY COMPARISON")
    print(f"{'='*70}")

    unmet_demand = []
    for entry in full_forecast.entries:
        dest = entry.location_id
        product = entry.product_id
        date = entry.forecast_date
        demand = entry.quantity
        delivery = deliveries_by_dest_product_date.get((dest, product, date), 0.0)

        if delivery < demand - 0.1:  # Allow small rounding errors
            unmet_demand.append({
                'dest': dest,
                'product': product,
                'date': date,
                'demand': demand,
                'delivery': delivery,
                'gap': demand - delivery
            })

    if unmet_demand:
        print(f"\nFound {len(unmet_demand)} forecast entries with unmet demand:")
        print(f"Total unmet: {sum(item['gap'] for item in unmet_demand):,.0f} units")

        # Show by date
        unmet_by_date = defaultdict(float)
        for item in unmet_demand:
            unmet_by_date[item['date']] += item['gap']

        print(f"\nUnmet demand by date:")
        for date in sorted(unmet_by_date.keys())[-14:]:  # Last 14 days
            print(f"  {date}: {unmet_by_date[date]:>10,.0f} units")

        # Show by destination
        unmet_by_dest = defaultdict(float)
        for item in unmet_demand:
            unmet_by_dest[item['dest']] += item['gap']

        print(f"\nUnmet demand by destination:")
        for dest in sorted(unmet_by_dest.keys()):
            print(f"  {dest}: {unmet_by_dest[dest]:>10,.0f} units")
    else:
        print("\n✓ All forecast demand is met in shipments!")
        print("\nThe 154,880 unit gap must be explained by:")
        print("  - Inventory buildup")
        print("  - Waste/spoilage")
        print("  - Accounting discrepancy")

        # Check inventory
        ending_inventory = solution.get('ending_inventory', {})
        total_ending_inventory = 0.0
        for key, value in ending_inventory.items():
            total_ending_inventory += value

        print(f"\nEnding inventory: {total_ending_inventory:,.0f} units")

        # Calculate total deliveries
        total_deliveries = sum(s.quantity for s in shipments)
        print(f"Total deliveries: {total_deliveries:,.0f} units")
        print(f"Total production: 2,252,419 units")
        print(f"Difference (production - deliveries): {2252419 - total_deliveries:,.0f} units")
else:
    print(f"\nTotal shortage: {total_shortage:,.0f} units")
    print(f"\nShortages by date (last 14 days):")
    for date in sorted(shortages_by_date.keys())[-14:]:
        print(f"  {date}: {shortages_by_date[date]:>10,.0f} units")

    print(f"\nShortages by destination:")
    for dest in sorted(shortages_by_dest.keys()):
        print(f"  {dest}: {shortages_by_dest[dest]:>10,.0f} units")
