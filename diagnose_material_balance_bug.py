"""
Diagnose material balance bug by tracing all flows.
"""

import sys
import os
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.parsers import MultiFileParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.location import LocationType
from src.models.manufacturing import ManufacturingSite
from src.models.forecast import Forecast

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'examples')
NETWORK_CONFIG_PATH = os.path.join(DATA_DIR, 'Network_Config.xlsx')
FORECAST_PATH = os.path.join(DATA_DIR, 'Gfree Forecast_Converted.xlsx')

# Minimal test configuration
START_DATE = date(2025, 10, 13)
PLANNING_WEEKS = 1  # Just 1 week for fast solve

print("=" * 80)
print("MATERIAL BALANCE DIAGNOSTIC - 1 WEEK TEST")
print("=" * 80)
print()

# Load data
print("Loading data...")
parser = MultiFileParser(
    network_file=NETWORK_CONFIG_PATH,
    forecast_file=FORECAST_PATH
)
forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()
truck_schedules = TruckScheduleCollection(schedules=trucks_list)

# Get manufacturing site
manufacturing_site = None
for loc in locations:
    if loc.type == LocationType.MANUFACTURING:
        manufacturing_site = ManufacturingSite(
            id=loc.id, name=loc.name, type=loc.type, storage_mode=loc.storage_mode,
            capacity=loc.capacity, latitude=loc.latitude, longitude=loc.longitude,
            production_rate=1400.0, labor_calendar=labor, changeover_time_hours=0.5,
        )
        break

# Filter to 1 week
print(f"Filtering to {PLANNING_WEEKS} weeks from {START_DATE}...")
end_date = START_DATE + timedelta(days=PLANNING_WEEKS * 7 - 1)
filtered_entries = [f for f in forecast.entries if START_DATE <= f.forecast_date <= end_date]
filtered_forecast = Forecast(name="Test", entries=filtered_entries)
print(f"✓ Using {len(filtered_entries)} entries from {START_DATE} to {end_date}")
print()

# Build model
print("Building model...")
model = IntegratedProductionDistributionModel(
    forecast=filtered_forecast,
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes,
    labor_calendar=labor,
    truck_schedules=truck_schedules,
    cost_structure=costs,
    allow_shortages=True,
    enforce_shelf_life=False,
    validate_feasibility=False,
    use_batch_tracking=True,
    initial_inventory=None,  # No initial inventory for cleaner debugging
)
print("✓ Model built")
print()

# Solve
print("Solving...")
solution = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.02, tee=False)

if not solution.is_feasible():
    print(f"✗ FAILED: No feasible solution found")
    sys.exit(1)

print(f"✓ Solution: {solution.termination_condition}")
print()

# Extract all flows by location
print("=" * 80)
print("FLOW ANALYSIS BY LOCATION")
print("=" * 80)
print()

cohort_inv = solution.metadata.get('cohort_inventory', {})
cohort_demand = solution.metadata.get('cohort_demand_consumption', {})
shipments = model.get_shipment_plan() or []
production_data = solution.metadata.get('production_by_date_product', {})

# Organize flows by location
location_flows = defaultdict(lambda: {
    'inflows': [],
    'outflows': [],
    'inventory_start': 0,
    'inventory_end': 0,
    'production': 0,
    'demand': 0,
})

# Track production at manufacturing
for (date, prod), qty in production_data.items():
    if qty > 0:
        location_flows['6122_Storage']['production'] += qty
        location_flows['6122_Storage']['inflows'].append(('production', prod, date, qty))

# Track shipments
for ship in shipments:
    location_flows[ship.origin_id]['outflows'].append(('shipment', ship.product_id, ship.departure_date, ship.quantity))
    location_flows[ship.destination_id]['inflows'].append(('shipment', ship.product_id, ship.delivery_date, ship.quantity))

# Track demand consumption
for (loc, prod, date), qty in cohort_demand.items():
    if qty > 0:
        location_flows[loc]['demand'] += qty
        location_flows[loc]['outflows'].append(('demand', prod, date, qty))

# Track inventory levels
for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
    if curr_date == model.start_date:
        location_flows[loc]['inventory_start'] += qty
    if curr_date == model.end_date:
        location_flows[loc]['inventory_end'] += qty

# Print flows for each location
for loc_id in sorted(location_flows.keys()):
    flows = location_flows[loc_id]

    print(f"Location: {loc_id}")
    print(f"  Production: {flows['production']:,.0f}")
    print(f"  Inventory Start: {flows['inventory_start']:,.0f}")
    print(f"  Inventory End: {flows['inventory_end']:,.0f}")
    print(f"  Demand: {flows['demand']:,.0f}")

    # Calculate total inflows and outflows
    total_inflows = flows['production'] + flows['inventory_start'] + sum(f[3] for f in flows['inflows'] if f[0] == 'shipment')
    total_outflows = flows['demand'] + flows['inventory_end'] + sum(f[3] for f in flows['outflows'] if f[0] == 'shipment')

    print(f"  Total Inflows (prod + start_inv + arrivals): {total_inflows:,.0f}")
    print(f"  Total Outflows (demand + end_inv + departures): {total_outflows:,.0f}")
    print(f"  Balance: {total_inflows - total_outflows:+,.0f}")

    if abs(total_inflows - total_outflows) > 1.0:
        print(f"  ⚠️ IMBALANCE at {loc_id}!")

    print()

# Global material balance
print("=" * 80)
print("GLOBAL MATERIAL BALANCE")
print("=" * 80)
print()

total_production = sum(production_data.values())
total_demand = sum(cohort_demand.values())
total_start_inv = sum(f['inventory_start'] for f in location_flows.values())
total_end_inv = sum(f['inventory_end'] for f in location_flows.values())

print(f"Initial Inventory: {total_start_inv:,.0f}")
print(f"Production: {total_production:,.0f}")
print(f"Total Supply: {total_start_inv + total_production:,.0f}")
print()
print(f"Demand Consumed: {total_demand:,.0f}")
print(f"Final Inventory: {total_end_inv:,.0f}")
print(f"Total Usage: {total_demand + total_end_inv:,.0f}")
print()
print(f"Material Balance: {(total_start_inv + total_production) - (total_demand + total_end_inv):+,.0f}")

if abs((total_start_inv + total_production) - (total_demand + total_end_inv)) < 1.0:
    print("✓ PERFECT BALANCE")
else:
    print("❌ IMBALANCE DETECTED")

print()
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
