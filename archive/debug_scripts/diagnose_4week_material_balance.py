"""
Diagnose material balance deficit in 4-week test.

This script loads the 4-week scenario, solves it, and produces detailed
material flow analysis to identify where the -20,704 unit deficit comes from.

Run: /home/sverzijl/planning_latest/venv/bin/python diagnose_4week_material_balance.py
"""

from datetime import date, timedelta
from pathlib import Path
import sys
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

# Load data files
data_dir = Path(__file__).parent / "data" / "examples"
forecast_file = data_dir / "Gfree Forecast.xlsm"
network_file = data_dir / "Network_Config.xlsx"
inventory_file = data_dir / "inventory.xlsx"

print("Loading data...")
parser = MultiFileParser(
    forecast_file=forecast_file,
    network_file=network_file,
    inventory_file=inventory_file if inventory_file.exists() else None,
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]

manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Create model with 4-week horizon
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=27)  # 4 weeks

print("="*80)
print("4-WEEK MATERIAL BALANCE DIAGNOSTIC")
print("="*80)
print(f"Planning horizon: {start_date} to {end_date}")
print(f"Solving with CBC...")

model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    start_date=start_date,
    end_date=end_date,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
    initial_inventory=None,
)

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    tee=False,
)

print(f"Solved in {result.solve_time_seconds:.1f}s ({result.termination_condition})")

# Get solution
solution = model.get_solution()

# Calculate metrics
prod_by_date_product = solution.get('production_by_date_product', {})
total_production = sum(prod_by_date_product.values())

cohort_inventory = solution.get('cohort_inventory', {})
cohort_demand = solution.get('cohort_demand_consumption', {})
cohort_shipments = solution.get('shipment_leg_cohort', {})

shortages = solution.get('shortages_by_dest_product_date', {})
total_shortage = sum(shortages.values())

# First and last day inventory
first_day_inv = sum(
    qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
    if cd == start_date
)

last_day_inv = sum(
    qty for (loc, prod, pd, cd, state), qty in cohort_inventory.items()
    if cd == end_date
)

actual_consumption = sum(cohort_demand.values())
total_shipments = sum(cohort_shipments.values())

print("\n" + "="*80)
print("MATERIAL FLOW SUMMARY")
print("="*80)

print(f"\nProduction:")
print(f"  Total produced: {total_production:,.0f} units")

print(f"\nShipments:")
print(f"  Total shipped (all legs): {total_shipments:,.0f} units")

print(f"\nDemand:")
print(f"  Total consumption: {actual_consumption:,.0f} units")
print(f"  Total shortage: {total_shortage:,.0f} units")

print(f"\nInventory:")
print(f"  Day 1 inventory: {first_day_inv:,.0f} units")
print(f"  Day 28 inventory: {last_day_inv:,.0f} units")
print(f"  Net change: {last_day_inv - first_day_inv:+,.0f} units")

print("\n" + "="*80)
print("MATERIAL BALANCE")
print("="*80)

supply = first_day_inv + total_production
usage = actual_consumption + last_day_inv
balance = supply - usage

print(f"\nSupply: {first_day_inv:,.0f} (initial) + {total_production:,.0f} (production) = {supply:,.0f}")
print(f"Usage: {actual_consumption:,.0f} (consumed) + {last_day_inv:,.0f} (final inv) = {usage:,.0f}")
print(f"Balance: {balance:+,.0f} units")

if abs(balance) > 100:
    print(f"\n❌ MATERIAL BALANCE DEFICIT: {abs(balance):,.0f} units")

    # Detailed breakdown by location
    print("\n" + "="*80)
    print("LOCATION-LEVEL ANALYSIS")
    print("="*80)

    # Group inventory by location
    inv_by_loc = {}
    for (loc, prod, pd, cd, state), qty in cohort_inventory.items():
        if loc not in inv_by_loc:
            inv_by_loc[loc] = {'first_day': 0, 'last_day': 0}
        if cd == start_date:
            inv_by_loc[loc]['first_day'] += qty
        if cd == end_date:
            inv_by_loc[loc]['last_day'] += qty

    # Group shipments by leg
    shipments_by_leg = {}
    for (leg, prod, pd, dd), qty in cohort_shipments.items():
        if leg not in shipments_by_leg:
            shipments_by_leg[leg] = 0
        shipments_by_leg[leg] += qty

    # Group demand by location
    demand_by_loc = {}
    for (loc, prod, pd, dd), qty in cohort_demand.items():
        if loc not in demand_by_loc:
            demand_by_loc[loc] = 0
        demand_by_loc[loc] += qty

    print("\nInventory by location:")
    for loc, inv in sorted(inv_by_loc.items(), key=lambda x: x[1]['last_day'], reverse=True):
        print(f"  {loc}: Day 1={inv['first_day']:,.0f}, Day 28={inv['last_day']:,.0f}, Change={inv['last_day']-inv['first_day']:+,.0f}")

    print("\nShipments by leg (top 15):")
    for leg, qty in sorted(shipments_by_leg.items(), key=lambda x: x[1], reverse=True)[:15]:
        origin, dest = leg
        print(f"  {origin} → {dest}: {qty:,.0f} units")

    print("\nDemand consumption by location:")
    for loc, qty in sorted(demand_by_loc.items(), key=lambda x: x[1], reverse=True):
        print(f"  {loc}: {qty:,.0f} units")

    # Check hub locations specifically
    print("\n" + "="*80)
    print("HUB LOCATION ANALYSIS")
    print("="*80)

    hub_locations = ['6104', '6125']  # NSW/ACT and VIC/TAS/SA hubs

    for hub in hub_locations:
        print(f"\nHub {hub}:")

        # Inventory at hub
        hub_inv = inv_by_loc.get(hub, {'first_day': 0, 'last_day': 0})
        print(f"  Inventory: Day 1={hub_inv['first_day']:,.0f}, Day 28={hub_inv['last_day']:,.0f}")

        # Inbound shipments
        inbound = [(leg, qty) for leg, qty in shipments_by_leg.items() if leg[1] == hub]
        total_inbound = sum(qty for _, qty in inbound)
        print(f"  Inbound: {total_inbound:,.0f} units")
        for leg, qty in sorted(inbound, key=lambda x: x[1], reverse=True):
            print(f"    {leg[0]} → {hub}: {qty:,.0f}")

        # Outbound shipments
        outbound = [(leg, qty) for leg, qty in shipments_by_leg.items() if leg[0] == hub]
        total_outbound = sum(qty for _, qty in outbound)
        print(f"  Outbound: {total_outbound:,.0f} units")
        for leg, qty in sorted(outbound, key=lambda x: x[1], reverse=True):
            print(f"    {hub} → {leg[1]}: {qty:,.0f}")

        # Hub balance
        hub_balance = hub_inv['first_day'] + total_inbound - total_outbound - hub_inv['last_day']
        demand_at_hub = demand_by_loc.get(hub, 0)
        hub_balance -= demand_at_hub

        print(f"  Demand at hub: {demand_at_hub:,.0f} units")
        print(f"  Hub flow balance: {hub_balance:+,.0f} units")
        if abs(hub_balance) > 10:
            print(f"    ⚠ Hub has flow imbalance!")

else:
    print(f"\n✓ Material balance OK!")

print("\n" + "="*80)
