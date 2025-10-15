"""
Test hub fix with 2-week real data test.
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path

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
INVENTORY_PATH = os.path.join(DATA_DIR, 'inventory.XLSX')

# Test configuration
START_DATE = date(2025, 10, 7)
PLANNING_WEEKS = 2  # Shorter for faster solve


print("=" * 80)
print("HUB FIX VERIFICATION TEST - 2 WEEKS")
print("=" * 80)
print()

# Load data
print("Loading data...")
parser = MultiFileParser(
    network_file=NETWORK_CONFIG_PATH,
    forecast_file=FORECAST_PATH,
    inventory_file=INVENTORY_PATH
)
forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()
truck_schedules = TruckScheduleCollection(schedules=trucks_list)

# Load initial inventory for start date
print(f"Loading initial inventory for {START_DATE}...")
initial_inventory_snapshot = parser.parse_inventory(snapshot_date=START_DATE)
initial_inventory_dict = initial_inventory_snapshot.to_optimization_dict()
print(f"✓ Loaded inventory snapshot with {len(initial_inventory_snapshot.entries)} entries")

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

print(f"✓ Loaded {len(forecast.entries)} forecast entries")
print()

# Filter to 2 weeks from START_DATE
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
    initial_inventory=initial_inventory_dict,
    inventory_snapshot_date=START_DATE,
)
print("✓ Model built")
print()

# Solve with 5-minute time limit and 2% MIP gap tolerance
print("Solving with CBC (5 min time limit, 2% MIP gap)...")
solution = model.solve(solver_name='cbc', time_limit_seconds=300, mip_gap=0.02, tee=False)

if not solution.is_feasible():
    print(f"✗ FAILED: No feasible solution found")
    print(f"Status: {solution.termination_condition}")
    sys.exit(1)

status_str = "OPTIMAL" if solution.is_optimal() else "FEASIBLE"
print(f"✓ Solution: {status_str}")
print(f"✓ Total cost: ${solution.objective_value:,.2f}")
print()

# Material Balance Check
print("=" * 80)
print("MATERIAL BALANCE VERIFICATION")
print("=" * 80)
print()

# Calculate total initial inventory
total_initial_inventory = sum(entry.quantity for entry in initial_inventory_snapshot.entries)
print(f"Initial inventory: {total_initial_inventory:,.0f} units")

# Calculate total production
production_data = solution.metadata.get('production_by_date_product', {})
total_production = sum(production_data.values())
print(f"Total production: {total_production:,.0f} units")

# Calculate total supply
total_supply = total_initial_inventory + total_production
print(f"Total supply: {total_supply:,.0f} units")
print()

# Calculate total demand consumed from cohort tracking
demand_cohort_data = solution.metadata.get('demand_from_cohort', {})
if demand_cohort_data:
    total_demand_consumed = sum(demand_cohort_data.values())
    print(f"Demand consumed (cohort tracking): {total_demand_consumed:,.0f} units")
else:
    print("⚠ WARNING: No cohort demand data available")
    total_demand_consumed = 0

# Calculate final inventory
inventory_frozen = solution.metadata.get('inventory_frozen_by_loc_product_date', {})
inventory_ambient = solution.metadata.get('inventory_ambient_by_loc_product_date', {})

all_inventory = {**inventory_frozen, **inventory_ambient}
if all_inventory:
    last_date = max(date for (loc, prod, date) in all_inventory.keys())

    final_inv = {}
    for (loc, prod, date), qty in all_inventory.items():
        if date == last_date and qty > 1e-6:
            key = (loc, prod)
            final_inv[key] = final_inv.get(key, 0) + qty

    total_final_inventory = sum(final_inv.values())
    print(f"Final inventory: {total_final_inventory:,.0f} units")
else:
    total_final_inventory = 0
    print(f"Final inventory: 0 units")

print()

# Calculate total usage
total_usage = total_demand_consumed + total_final_inventory
print(f"Total usage: {total_usage:,.0f} units")
print()

# Material balance
material_balance = total_supply - total_usage
print(f"MATERIAL BALANCE: {material_balance:+,.0f} units")

# Validate
if abs(material_balance) < 1.0:
    print("✓ PERFECT: Material balance within ±1 unit")
elif abs(material_balance) < 10.0:
    print("✓ EXCELLENT: Material balance within ±10 units")
elif abs(material_balance) < 100.0:
    print("✓ GOOD: Material balance within ±100 units")
else:
    print(f"✗ ISSUE: Material balance deficit of {abs(material_balance):,.0f} units")
    pct_error = abs(material_balance) / total_supply * 100 if total_supply > 0 else 0
    print(f"  ({pct_error:.2f}% of total supply)")

print()

# Additional diagnostics
shortage = solution.metadata.get('total_shortage_units', 0.0)
print(f"Shortage: {shortage:,.0f} units")

total_demand_forecast = sum(entry.quantity for entry in filtered_forecast.entries)
print(f"Forecast demand: {total_demand_forecast:,.0f} units")
print(f"Satisfied demand: {total_demand_consumed:,.0f} units ({total_demand_consumed/total_demand_forecast*100:.1f}%)")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
