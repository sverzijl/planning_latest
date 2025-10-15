"""
Diagnostic script to investigate phantom inventory issue.

The model shows ~843 units of phantom inventory appearing on day 1 at 6122_Storage,
even though no initial inventory was provided.

This script will:
1. Create the model with the same settings as the test
2. Inspect the cohort_shipment_index to see if phantom shipments are included
3. Check if the no_phantom_cohort_shipments constraint is being created correctly
4. Examine the first-day inventory balance equations
"""

from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel

# Load data
data_dir = Path('data/examples')
parser = MultiFileParser(
    forecast_file=data_dir / 'Gfree Forecast.xlsm',
    network_file=data_dir / 'Network_Config.xlsx',
    inventory_file=None
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]

manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0,
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

# Convert truck schedules
from src.models.truck_schedule import TruckScheduleCollection
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create model with same settings as test
planning_start_date = date(2025, 10, 7)
planning_end_date = planning_start_date + timedelta(weeks=4)

print("Creating model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=None,  # NO INITIAL INVENTORY
    inventory_snapshot_date=None,
    start_date=planning_start_date,
    end_date=planning_end_date,
    use_batch_tracking=True,
)

print(f"\nModel created successfully")
print(f"Start date: {model.start_date}")
print(f"End date: {model.end_date}")
print(f"Initial inventory dict: {model.initial_inventory}")
print(f"Initial inventory empty: {len(model.initial_inventory) == 0}")

# Build the Pyomo model
print("\nBuilding Pyomo model...")
model.build_model()
print("Pyomo model built successfully")

# Check cohort_shipment_index for phantom shipments on day 1
print("\n" + "="*80)
print("CHECKING FOR PHANTOM SHIPMENT COHORTS ON DAY 1")
print("="*80)

day1 = model.start_date
phantom_shipments = []

for (leg, prod, prod_date, delivery_date) in model.cohort_shipment_index_set:
    if delivery_date == day1:
        origin, dest = leg
        transit_days = model.leg_transit_days.get(leg, 0)
        departure_date = delivery_date - timedelta(days=transit_days)

        if departure_date < model.start_date:
            phantom_shipments.append({
                'leg': leg,
                'product': prod,
                'prod_date': prod_date,
                'delivery_date': delivery_date,
                'departure_date': departure_date,
                'transit_days': transit_days,
            })

print(f"\nFound {len(phantom_shipments)} phantom shipment cohorts delivering on day 1")

if phantom_shipments:
    print("\nPhantom shipments by route:")
    route_counts = {}
    for ps in phantom_shipments:
        leg_str = f"{ps['leg'][0]} → {ps['leg'][1]}"
        if leg_str not in route_counts:
            route_counts[leg_str] = 0
        route_counts[leg_str] += 1

    for leg_str, count in sorted(route_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {leg_str}: {count} cohorts")

    # Show first few examples
    print("\nFirst 10 examples:")
    for ps in phantom_shipments[:10]:
        print(f"  {ps['leg'][0]} → {ps['leg'][1]}")
        print(f"    Product: {ps['product']}")
        print(f"    Prod date: {ps['prod_date']}")
        print(f"    Departure: {ps['departure_date']} (BEFORE horizon)")
        print(f"    Delivery: {ps['delivery_date']}")
        print(f"    Transit: {ps['transit_days']} days")
        print()

# Check if no_phantom_cohort_shipments constraint was created
print("=" * 80)
print("CHECKING NO_PHANTOM_SHIPMENTS CONSTRAINT")
print("=" * 80)

pm = model.model  # The Pyomo model is stored in model.model
if pm:
    if hasattr(pm, 'no_phantom_cohort_shipments_con'):
        constraint = pm.no_phantom_cohort_shipments_con
        print(f"\n✓ Constraint exists: {constraint}")
        print(f"  Number of constraints: {len(list(constraint.keys()))}")

        # Sample a few phantom shipments to see if they're constrained to zero
        print("\nChecking if phantom shipments are constrained to zero:")
        for ps in phantom_shipments[:5]:
            key = (ps['leg'][0], ps['leg'][1], ps['product'], ps['prod_date'], ps['delivery_date'])
            if key in constraint:
                con = constraint[key]
                print(f"\n  {ps['leg'][0]} → {ps['leg'][1]}, prod={ps['product']}, prod_date={ps['prod_date']}")
                print(f"    Constraint: {con.expr}")
            else:
                print(f"\n  ⚠ Phantom shipment NOT in constraint: {key}")
    else:
        print("\n⚠ no_phantom_cohort_shipments_con constraint NOT FOUND in model")
else:
    print("\n⚠ Pyomo model not built yet")

# Check ambient inventory balance for 6122_Storage on day 1
print("\n" + "="*80)
print("CHECKING 6122_STORAGE AMBIENT INVENTORY BALANCE ON DAY 1")
print("="*80)

if hasattr(model, 'cohort_ambient_index_set'):
    day1_cohorts_6122 = [
        (loc, prod, prod_date, curr_date)
        for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index_set
        if loc == '6122_Storage' and curr_date == day1
    ]

    print(f"\nFound {len(day1_cohorts_6122)} ambient cohorts at 6122_Storage on day 1")

    if day1_cohorts_6122:
        print("\nCohorts by production date:")
        prod_date_counts = {}
        for (loc, prod, prod_date, curr_date) in day1_cohorts_6122:
            if prod_date not in prod_date_counts:
                prod_date_counts[prod_date] = 0
            prod_date_counts[prod_date] += 1

        for pd, count in sorted(prod_date_counts.items()):
            marker = "← PHANTOM?" if pd < model.start_date else ""
            print(f"  {pd}: {count} cohorts {marker}")

# Solve the model to get actual solution values
print("\n" + "="*80)
print("SOLVING MODEL TO CHECK ACTUAL SOLUTION")
print("="*80)

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=120,
    mip_gap=0.01,
    tee=False
)

print(f"\nSolve status: {result.termination_condition}")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    # Check production on day 1
    production_by_date_product = solution.get('production_by_date_product', {})
    day1_production = {k: v for k, v in production_by_date_product.items() if k[0] == day1}

    print(f"\nProduction on day 1 ({day1}):")
    for (date, prod), qty in day1_production.items():
        print(f"  {prod}: {qty:,.0f} units")

    total_day1_prod = sum(day1_production.values())
    print(f"Total day 1 production: {total_day1_prod:,.0f} units")

    # Check inventory on day 1
    cohort_inv = solution.get('cohort_inventory', {})
    day1_inv_6122 = {}

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if loc == '6122_Storage' and curr_date == day1 and qty > 0.01:
            key = (prod, prod_date, state)
            if key not in day1_inv_6122:
                day1_inv_6122[key] = 0
            day1_inv_6122[key] += qty

    print(f"\nInventory at 6122_Storage on day 1 ({day1}):")
    for (prod, prod_date, state), qty in sorted(day1_inv_6122.items(), key=lambda x: x[1], reverse=True):
        marker = "← PHANTOM?" if prod_date < model.start_date else ""
        print(f"  {prod} (prod={prod_date}, {state}): {qty:,.0f} units {marker}")

    total_day1_inv = sum(day1_inv_6122.values())
    print(f"Total day 1 inventory at 6122_Storage: {total_day1_inv:,.0f} units")

    # Check departures from 6122_Storage on day 1
    shipments = model.get_shipment_plan() or []
    day1_shipments_from_6122 = [s for s in shipments if s.origin_id == '6122_Storage' and s.departure_date == day1]

    total_day1_shipped = sum(s.quantity for s in day1_shipments_from_6122)
    print(f"\nShipments FROM 6122_Storage on day 1: {total_day1_shipped:,.0f} units")

    # Material balance check for day 1 at 6122_Storage
    print(f"\nMaterial balance for 6122_Storage on day 1:")
    print(f"  Production: {total_day1_prod:,.0f}")
    print(f"  Departures: {total_day1_shipped:,.0f}")
    print(f"  End inventory: {total_day1_inv:,.0f}")
    print(f"  Balance: {total_day1_prod:,.0f} - {total_day1_shipped:,.0f} - {total_day1_inv:,.0f} = {total_day1_prod - total_day1_shipped - total_day1_inv:,.0f}")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
