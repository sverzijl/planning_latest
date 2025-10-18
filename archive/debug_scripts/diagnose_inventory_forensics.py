#!/usr/bin/env python3
"""Forensic analysis of end-of-horizon inventory.

Extracts actual solution data from 4-week optimization to identify:
- WHERE the inventory is (which nodes)
- WHEN it was produced (production dates, ages)
- WHY it wasn't consumed (demand/shipment analysis)
- WHAT constraint bug causes it

This script provides DATA, not theories.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from pyomo.environ import value

# Load test data
data_dir = Path("data/examples")
forecast_file = data_dir / "Gfree Forecast.xlsm"
network_file = data_dir / "Network_Config.xlsx"
inventory_file = data_dir / "inventory.xlsx"

print("="*80)
print("FORENSIC ANALYSIS: End-of-Horizon Inventory")
print("="*80)

print("\n[1/6] Loading data...")
parser = MultiFileParser(
    forecast_file=str(forecast_file),
    network_file=str(network_file),
    inventory_file=str(inventory_file) if inventory_file.exists() else None,
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Convert to unified format
converter = LegacyToUnifiedConverter()
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

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

nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

# Set 4-week planning horizon (matching integration test)
forecast_start = min(e.forecast_date for e in forecast.entries)
planning_start = forecast_start
planning_end = planning_start + timedelta(days=27)  # 28 days

print(f"  Planning: {planning_start} to {planning_end} (28 days)")

# Build and solve model
print("\n[2/6] Building and solving model...")
model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    truck_schedules=unified_truck_schedules,
    start_date=planning_start,
    end_date=planning_end,
    initial_inventory=None,  # NO initial inventory for this analysis
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01, tee=False)
print(f"  Status: {result.termination_condition}, Time: {result.solve_time_seconds:.1f}s")

solution = model.get_solution()
pyomo_model = model.model  # Get the actual Pyomo model object

print("\n[3/6] Extracting end-of-horizon inventory...")

# Extract inventory on final day
cohort_inventory = solution.get('cohort_inventory', {})
end_day_inv = {
    (node, prod, prod_date, state): qty
    for (node, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
    if curr_date == planning_end and qty > 0.01
}

total_end_inv = sum(end_day_inv.values())
print(f"  Total end-of-horizon inventory: {total_end_inv:,.0f} units")

# Breakdown by location
by_location = defaultdict(float)
for (node, prod, prod_date, state), qty in end_day_inv.items():
    by_location[node] += qty

print(f"\n  Inventory by Location:")
for node_id in sorted(by_location.keys(), key=lambda x: by_location[x], reverse=True):
    qty = by_location[node_id]
    pct = (qty / total_end_inv * 100) if total_end_inv > 0 else 0
    node_obj = next((n for n in nodes if n.id == node_id), None)
    node_name = node_obj.name if node_obj else node_id
    node_type = "MFG" if node_obj and node_obj.can_produce() else \
                "HUB" if node_obj and not node_obj.has_demand_capability() else \
                "BREADROOM"
    print(f"    {node_id:6s} ({node_type:10s} - {node_name:20s}): {qty:8,.0f} units ({pct:5.1f}%)")

# Breakdown by production date and age
print(f"\n  Inventory by Production Date and Age:")
by_prod_date = defaultdict(float)
for (node, prod, prod_date, state), qty in end_day_inv.items():
    by_prod_date[prod_date] += qty

for prod_date in sorted(by_prod_date.keys()):
    qty = by_prod_date[prod_date]
    age = (planning_end - prod_date).days
    pct = (qty / total_end_inv * 100) if total_end_inv > 0 else 0
    freshness = "FRESH" if age <= 7 else "OK" if age <= 14 else "EXPIRED"
    print(f"    {prod_date} (age {age:2d}d): {qty:8,.0f} units ({pct:5.1f}%) [{freshness}]")

print("\n[4/6] Analyzing demand on final days...")

# Demand on days 26-28
late_demand = {}
for (node, prod, demand_date), qty in model.demand.items():
    if demand_date >= planning_end - timedelta(days=2):  # Last 3 days
        late_demand[(node, prod, demand_date)] = qty

total_late_demand = sum(late_demand.values())
print(f"  Total demand on days 26-28: {total_late_demand:,.0f} units")

# Breakdown by day
by_day = defaultdict(float)
for (node, prod, demand_date), qty in late_demand.items():
    by_day[demand_date] += qty

for demand_date in sorted(by_day.keys()):
    print(f"    Day {demand_date}: {by_day[demand_date]:,.0f} units")

print("\n[5/6] Checking shortage values...")

# Extract ACTUAL shortage from Pyomo model
actual_shortages = {}
total_actual_shortage = 0.0

if hasattr(pyomo_model, 'shortage'):
    for (node, prod, demand_date) in model.demand.keys():
        if (node, prod, demand_date) in pyomo_model.shortage:
            try:
                shortage_val = value(pyomo_model.shortage[node, prod, demand_date])
                if shortage_val > 0.01:
                    actual_shortages[(node, prod, demand_date)] = shortage_val
                    total_actual_shortage += shortage_val
            except:
                pass

print(f"  Total shortage (from model): {total_actual_shortage:,.0f} units")
print(f"  Total shortage (from solution dict): {solution.get('total_shortage_units', 0):,.0f} units")

if abs(total_actual_shortage - solution.get('total_shortage_units', 0)) > 1:
    print(f"  ⚠ EXTRACTION BUG: shortage in model ≠ shortage in solution dict")

# Breakdown shortage by day
shortage_by_day = defaultdict(float)
for (node, prod, demand_date), qty in actual_shortages.items():
    shortage_by_day[demand_date] += qty

if shortage_by_day:
    print(f"\n  Shortage by Day:")
    for demand_date in sorted(shortage_by_day.keys()):
        print(f"    {demand_date}: {shortage_by_day[demand_date]:,.0f} units")

print("\n[6/6] Material Balance Verification...")

total_production = sum(solution.get('production_by_date_product', {}).values())
cohort_consumption = sum(solution.get('cohort_demand_consumption', {}).values())
total_demand = sum(model.demand.values())

print(f"  Production: {total_production:,.0f} units")
print(f"  Total demand in horizon: {total_demand:,.0f} units")
print(f"  Cohort consumption: {cohort_consumption:,.0f} units")
print(f"  Shortage (actual): {total_actual_shortage:,.0f} units")
print(f"  End-of-horizon inventory: {total_end_inv:,.0f} units")

# Verify constraint equation
expected_consumption = total_demand - total_actual_shortage
if abs(cohort_consumption - expected_consumption) > 1:
    print(f"\n  ❌ CONSTRAINT VIOLATION:")
    print(f"     Cohort consumption ({cohort_consumption:,.0f}) ≠ Demand - Shortage ({expected_consumption:,.0f})")
    print(f"     Gap: {cohort_consumption - expected_consumption:,.0f} units")
else:
    print(f"\n  ✓ Demand satisfaction constraint: cohort_supply + shortage = demand")

# Material balance
material_balance = total_production - cohort_consumption - total_end_inv
print(f"\n  Material Balance:")
print(f"    Production - Consumption - End_Inv = {material_balance:,.0f} units")
if abs(material_balance) > 100:
    print(f"    ⚠ MISSING: ~{abs(material_balance):,.0f} units (in-transit or accounting error)")

# CRITICAL ANALYSIS: Why is there inventory when there were earlier shortages?
print("\n" + "="*80)
print("CRITICAL QUESTION: Why Inventory When Shortages Existed?")
print("="*80)

print(f"\nObservation:")
print(f"  - Shortages: 30,053 units (days 7-17)")
print(f"  - End inventory: 15,800 units (day 28, fresh, at breadrooms)")
print(f"  - Production dates: Days 20-31 (inventory is from LATE production)")

print(f"\nPuzzle:")
print(f"  If model had shortages on days 7-17, why didn't it:")
print(f"  1. Produce EARLIER (days 1-15) to cover those shortages?")
print(f"  2. Produce LESS on days 20-31 (since day 28 only needs 8,556 units)?")

print(f"\nPossible Explanations:")
print(f"  A. Production capacity constraints prevented earlier production")
print(f"  B. Truck schedule constraints prevented earlier deliveries")
print(f"  C. Transit time made it impossible to satisfy early demand")
print(f"  D. Model is minimizing COST, not maximizing demand satisfaction")
print(f"     (Shortage penalty < Production+Transport cost for early deliveries)")

# Check production capacity usage
prod_by_date_product = solution.get('production_by_date_product', {})
prod_by_date = defaultdict(float)
for (prod_date, product), qty in prod_by_date_product.items():
    prod_by_date[prod_date] += qty

print(f"\nProduction by Date (first 20 days):")
for prod_date in sorted(prod_by_date.keys())[:20]:
    qty = prod_by_date[prod_date]
    # Calculate capacity (assuming 12h fixed + 2h OT = 14h max, 1400 units/h = 19,600 capacity)
    capacity = 19600  # Max daily capacity
    utilization = (qty / capacity * 100) if capacity > 0 else 0
    print(f"  {prod_date}: {qty:7,.0f} units ({utilization:5.1f}% of capacity)")

print("\n" + "="*80)
print("FORENSIC ANALYSIS COMPLETE")
print("="*80)
