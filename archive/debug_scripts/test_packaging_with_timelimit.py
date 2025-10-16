"""
Test packaging constraints with real data and strict time limit.
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
PLANNING_WEEKS = 4


def validate_case_multiples(solution):
    """Check that all production is in 10-unit case multiples."""
    violations = []
    production_data = solution.metadata.get('production_by_date_product', {})
    for (d, p), qty in production_data.items():
        if qty > 0:
            remainder = qty % 10
            if remainder > 0.01 and remainder < 9.99:  # Floating point tolerance
                violations.append({
                    'date': d,
                    'product': p,
                    'quantity': qty,
                    'remainder': remainder,
                })
    return violations


def calculate_final_inventory(solution):
    """Calculate inventory at end of planning horizon."""
    inventory_frozen = solution.metadata.get('inventory_frozen_by_loc_product_date', {})
    inventory_ambient = solution.metadata.get('inventory_ambient_by_loc_product_date', {})

    all_inventory = {**inventory_frozen, **inventory_ambient}
    if not all_inventory:
        return None

    last_date = max(date for (loc, prod, date) in all_inventory.keys())

    final_inv = {}
    for (loc, prod, date), qty in all_inventory.items():
        if date == last_date and qty > 1e-6:
            key = (loc, prod)
            final_inv[key] = final_inv.get(key, 0) + qty

    return final_inv


print("=" * 80)
print("PACKAGING CONSTRAINTS TEST - 4 WEEKS WITH TIME LIMIT")
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

# Filter to 4 weeks from START_DATE
print(f"Filtering to {PLANNING_WEEKS} weeks from {START_DATE}...")
end_date = START_DATE + timedelta(days=PLANNING_WEEKS * 7 - 1)  # 28 days (4 weeks)
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
    allow_shortages=True,  # Allow shortages for feasibility (we'll validate production doesn't exceed demand)
    enforce_shelf_life=False,
    validate_feasibility=False,
    use_batch_tracking=True,
    initial_inventory=initial_inventory_dict,
    inventory_snapshot_date=START_DATE,
)
print("✓ Model built")
print()

# Solve with 10-minute time limit and 1% MIP gap tolerance
print("Solving with CBC (10 min time limit, 1% MIP gap)...")
solution = model.solve(solver_name='cbc', time_limit_seconds=600, mip_gap=0.01, tee=False)

if not solution.is_feasible():
    print(f"✗ FAILED: No feasible solution found")
    print(f"Status: {solution.termination_condition}")
    sys.exit(1)

status_str = "OPTIMAL" if solution.is_optimal() else "FEASIBLE"
print(f"✓ Solution: {status_str}")
print(f"✓ Total cost: ${solution.objective_value:,.2f}")
print()

# Validation 1: Case multiples
print("-" * 80)
print("VALIDATION 1: Case Multiple Constraints (10 units)")
print("-" * 80)

violations = validate_case_multiples(solution)

if violations:
    print(f"✗ FAILED: {len(violations)} violations")
    for v in violations[:10]:
        print(f"  {v['date']} / {v['product']}: {v['quantity']} units (remainder: {v['remainder']})")
else:
    print("✓ PASSED: All production in exact case multiples")
    production_data = solution.metadata.get('production_by_date_product', {})
    if production_data:
        print("\nSample production:")
        for i, ((d, p), qty) in enumerate(sorted(production_data.items())):
            if qty > 0 and i < 5:
                print(f"  {d} / {p}: {qty:,.0f} units = {int(qty/10)} cases")
print()

# Validation 2: Final inventory
print("-" * 80)
print("VALIDATION 2: Final Inventory (Overproduction Check)")
print("-" * 80)

final_inv = calculate_final_inventory(solution)

if final_inv is None:
    print("⚠ WARNING: No inventory data in solution")
else:
    total_final = sum(final_inv.values())
    print(f"Total final inventory: {total_final:,.0f} units")

    if total_final > 0:
        print("\nBy location:")
        for (loc, prod), qty in sorted(final_inv.items()):
            if qty > 0:
                print(f"  {loc} / {prod}: {qty:,.0f} units")

    production_data = solution.metadata.get('production_by_date_product', {})
    if production_data:
        total_prod = sum(production_data.values())
        inv_pct = (total_final / total_prod * 100) if total_prod > 0 else 0

        print(f"\nTotal production: {total_prod:,.0f} units")
        print(f"Final inventory: {inv_pct:.2f}% of production")

        if inv_pct < 1.0:
            print("✓ PASSED: Minimal overproduction (< 1%)")
        elif inv_pct < 5.0:
            print("✓ PASSED: Acceptable overproduction (< 5%)")
        else:
            print(f"⚠ WARNING: High overproduction ({inv_pct:.1f}%)")
print()

# Validation 3: Demand satisfaction
print("-" * 80)
print("VALIDATION 3: Demand Satisfaction")
print("-" * 80)

shortage = solution.metadata.get('total_shortage_units', 0.0)
print(f"Total shortage: {shortage:,.0f} units")
if shortage < 1.0:
    print("✓ PASSED: All demand satisfied")
else:
    print(f"⚠ WARNING: {shortage:,.0f} units unmet")
print()

# Validation 4: Production vs Demand (Supply Balance Check)
print("-" * 80)
print("VALIDATION 4: Supply Balance (Production + Initial Inventory vs Demand)")
print("-" * 80)

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

# Calculate total demand from filtered forecast
total_demand = sum(entry.quantity for entry in filtered_forecast.entries)
print(f"Total demand: {total_demand:,.0f} units")

# Calculate difference
supply_minus_demand = total_supply - total_demand
print(f"Supply - Demand: {supply_minus_demand:,.0f} units")

# Validate production doesn't exceed demand (some buffer acceptable for packaging)
# Allow small buffer for rounding to case/pallet multiples
acceptable_buffer = total_demand * 0.02  # 2% buffer for packaging constraints
if supply_minus_demand <= acceptable_buffer:
    print(f"✓ PASSED: Production within acceptable range (≤ 2% buffer)")
    if supply_minus_demand < 0:
        print(f"  Note: Supply deficit of {-supply_minus_demand:,.0f} units (shortage occurred)")
else:
    excess_pct = (supply_minus_demand / total_demand * 100)
    print(f"⚠ WARNING: Excess supply of {excess_pct:.2f}% (expected ≤ 2%)")
print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
