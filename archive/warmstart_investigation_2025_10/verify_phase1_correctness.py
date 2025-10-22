"""Systematic verification of Phase 1 model correctness.

Following Pyomo best practices to verify:
1. Phase 1 model has correct constraints (6130 must receive from Lineage)
2. Input data is correct (routes exist, demand exists)
3. Extraction method is correct (proper use of pyo.value())

Using Pyomo Example 2: Accessing Variable Values After Solving
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import copy

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import value as pyo_value, Var, Constraint, Binary
import pyomo.environ as pyo


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


print_section("PHASE 1 MODEL CORRECTNESS VERIFICATION")
print("\nUsing Pyomo best practices to verify model and extraction")

# Load data
print_section("1. Loading Input Data")

parser = MultiFileParser(
    forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
    network_file="data/examples/Network_Config.xlsx",
    inventory_file="data/examples/inventory.XLSX",
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
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

# Convert to unified
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

inventory_snapshot = parser.parse_inventory(snapshot_date=None)
initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

print(f"  Nodes: {len(nodes)}")
print(f"  Routes: {len(unified_routes)}")
print(f"  Forecast entries: {len(forecast.entries)}")

# VERIFY INPUT DATA
print_section("2. Verifying Input Data for 6130 (WA)")

# Check if 6130 exists
node_6130 = [n for n in nodes if n.id == '6130']
print(f"\n  Node 6130 exists: {len(node_6130) > 0}")
if node_6130:
    print(f"    Name: {node_6130[0].name}")
    print(f"    Can demand: {node_6130[0].capabilities.has_demand}")

# Check routes to 6130
routes_to_6130 = [r for r in unified_routes if r.destination_node_id == '6130']
print(f"\n  Routes to 6130: {len(routes_to_6130)}")
for r in routes_to_6130:
    print(f"    {r.origin_node_id} → {r.destination_node_id} ({r.transport_mode}, {r.transit_days} days)")

# Check if Lineage → 6130 route exists
lineage_to_6130 = [r for r in unified_routes if r.origin_node_id == 'Lineage' and r.destination_node_id == '6130']
print(f"\n  Lineage → 6130 route exists: {len(lineage_to_6130) > 0}")
if lineage_to_6130:
    r = lineage_to_6130[0]
    print(f"    Transport mode: {r.transport_mode}")
    print(f"    Transit days: {r.transit_days}")

# Check demand for 6130
demand_6130 = [e for e in forecast.entries if e.location_id == '6130']
print(f"\n  Demand entries for 6130: {len(demand_6130)}")
if demand_6130:
    total_demand = sum(e.quantity for e in demand_6130)
    print(f"    Total demand: {total_demand:,.0f} units")
    print(f"    Date range: {min(e.forecast_date for e in demand_6130)} to {max(e.forecast_date for e in demand_6130)}")

# VERIFY: 6130 should have NO other supply routes (only from Lineage)
other_routes_to_6130 = [r for r in unified_routes if r.destination_node_id == '6130' and r.origin_node_id != 'Lineage']
print(f"\n  Other routes to 6130 (should be 0): {len(other_routes_to_6130)}")
if other_routes_to_6130:
    print(f"    ⚠️  WARNING: Found unexpected routes:")
    for r in other_routes_to_6130:
        print(f"      {r.origin_node_id} → {r.destination_node_id}")

# Build and solve Phase 1
print_section("3. Building and Solving Phase 1 Model")

start_date = date(2025, 10, 20)
end_date = start_date + timedelta(days=6*7 - 1)

# Create Phase 1 cost structure (with unit-based costs)
phase1_cost_structure = copy.copy(cost_structure)

if (getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0) > 0 or
    getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0) > 0):

    pallet_var_cost = getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0)
    pallet_fixed_cost = getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0)

    amortization_days = 7.0
    units_per_pallet = 320.0

    equivalent_unit_cost_frozen = (
        pallet_var_cost + pallet_fixed_cost / amortization_days
    ) / units_per_pallet

    phase1_cost_structure.storage_cost_frozen_per_unit_day = equivalent_unit_cost_frozen
    phase1_cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    phase1_cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0

print(f"  Horizon: {start_date} to {end_date} (42 days)")

model_phase1_obj = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=phase1_cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_date,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print("\nBuilding Phase 1 model...")
pyomo_model_phase1 = model_phase1_obj.build_model()

# Add weekly pattern variables
products = sorted(set(e.product_id for e in forecast.entries))
pattern_index = [(prod, wd) for prod in products for wd in range(5)]
pyomo_model_phase1.product_weekday_pattern = Var(pattern_index, within=Binary)

print("Solving Phase 1...")
from pyomo.contrib import appsi
solver_phase1 = appsi.solvers.Highs()
solver_phase1.config.time_limit = 120
solver_phase1.config.mip_gap = 0.06
solver_phase1.highs_options['presolve'] = 'on'
solver_phase1.highs_options['parallel'] = 'on'

results_phase1 = solver_phase1.solve(pyomo_model_phase1)
print(f"  Result: {results_phase1.termination_condition}")

# VERIFY: Check constraints for demand satisfaction at 6130
print_section("4. Verifying Demand Satisfaction for 6130")

# Using Pyomo Example 2 pattern for accessing variables correctly
if hasattr(pyomo_model_phase1, 'demand_from_cohort'):
    demand_satisfied_6130 = 0.0

    # demand_from_cohort is 4-tuple: (node_id, prod, prod_date, demand_date)
    for index in pyomo_model_phase1.demand_from_cohort:
        node_id, prod, prod_date, demand_date = index
        if node_id == '6130':
            try:
                qty = pyo_value(pyomo_model_phase1.demand_from_cohort[index])
                if qty > 0.01:
                    demand_satisfied_6130 += qty
            except:
                pass

    print(f"\n  Demand satisfied at 6130: {demand_satisfied_6130:,.0f} units")

    if demand_satisfied_6130 > 0:
        print(f"  ✓ 6130 is receiving product")
    else:
        print(f"  ❌ 6130 receiving ZERO units (shortage or error!)")

# VERIFY: Check shipments from Lineage to 6130
print_section("5. Verifying Shipments from Lineage to 6130")

if hasattr(pyomo_model_phase1, 'shipment_cohort'):
    shipments_lineage_to_6130 = 0.0
    shipment_count = 0

    # Using Pyomo best practice: iterate through component indices
    for index in pyomo_model_phase1.shipment_cohort:
        try:
            # shipment_cohort[origin, dest, product, prod_date, curr_date, state]
            if len(index) == 6:
                origin, dest, prod, prod_date, curr_date, state = index
                if origin == 'Lineage' and dest == '6130':
                    qty = pyo_value(pyomo_model_phase1.shipment_cohort[index])
                    if qty > 0.01:
                        shipments_lineage_to_6130 += qty
                        shipment_count += 1
        except:
            pass

    print(f"\n  Shipments Lineage → 6130: {shipments_lineage_to_6130:,.0f} units ({shipment_count} shipment cohorts)")

    if shipments_lineage_to_6130 > 0:
        print(f"  ✓ Lineage is shipping to 6130")
    else:
        print(f"  ❌ Lineage shipping ZERO to 6130 (this would violate network structure!)")

# VERIFY: Check inventory at Lineage
print_section("6. Verifying Inventory at Lineage (CRITICAL)")

if hasattr(pyomo_model_phase1, 'inventory_cohort'):
    lineage_inventory_frozen = 0.0
    lineage_inventory_ambient = 0.0
    lineage_cohort_count_frozen = 0
    lineage_cohort_count_ambient = 0

    # Properly iterate using Pyomo pattern (Example 2)
    for index in pyomo_model_phase1.inventory_cohort:
        node_id, prod, prod_date, curr_date, state = index

        if node_id == 'Lineage':
            try:
                qty = pyo_value(pyomo_model_phase1.inventory_cohort[index])

                if state == 'frozen':
                    lineage_cohort_count_frozen += 1
                    if qty > 0.01:
                        lineage_inventory_frozen += qty
                elif state == 'ambient':
                    lineage_cohort_count_ambient += 1
                    if qty > 0.01:
                        lineage_inventory_ambient += qty
            except Exception as e:
                print(f"  Error extracting {index}: {e}")
                pass

    print(f"\n  Lineage Inventory:")
    print(f"    Frozen cohorts:  {lineage_cohort_count_frozen} total")
    print(f"    Frozen units:    {lineage_inventory_frozen:,.2f}")
    print(f"    Ambient cohorts: {lineage_cohort_count_ambient} total")
    print(f"    Ambient units:   {lineage_inventory_ambient:,.2f}")

    if lineage_inventory_frozen > 0:
        print(f"\n  ✓ Lineage has {lineage_inventory_frozen:,.0f} frozen units")
        print(f"    This should provide pallet hints!")
    else:
        print(f"\n  ❌ Lineage has ZERO frozen inventory")
        print(f"     This is WRONG if 6130 has demand!")

    # Sample some Lineage inventory cohorts
    print(f"\n  Sample Lineage frozen cohorts:")
    count = 0
    for index in pyomo_model_phase1.inventory_cohort:
        node_id, prod, prod_date, curr_date, state = index
        if node_id == 'Lineage' and state == 'frozen' and count < 5:
            try:
                qty = pyo_value(pyomo_model_phase1.inventory_cohort[index])
                print(f"    {index}: {qty:.2f} units")
                count += 1
            except Exception as e:
                print(f"    {index}: ERROR - {e}")
                count += 1

# VERIFY: Alternative extraction method
print_section("7. Alternative Extraction Method Verification")

print("\nMethod 1: Direct iteration (what I used):")
frozen_count_method1 = 0
for key in pyomo_model_phase1.inventory_cohort:
    node_id, prod, prod_date, curr_date, state = key
    if node_id == 'Lineage' and state == 'frozen':
        try:
            units = pyo_value(pyomo_model_phase1.inventory_cohort[key])
            if units > 0.01:
                frozen_count_method1 += 1
        except:
            pass
print(f"  Frozen inventory cohorts with units > 0.01: {frozen_count_method1}")

print("\nMethod 2: Using component_data_objects (Pyomo best practice):")
frozen_count_method2 = 0
for v in pyomo_model_phase1.component_data_objects(Var, active=True):
    if hasattr(v, 'name') and 'inventory_cohort' in str(v.name):
        # Parse the variable name to get indices
        # This is more robust
        try:
            val = pyo_value(v)
            if val > 0.01 and 'Lineage' in str(v.name) and 'frozen' in str(v.name):
                frozen_count_method2 += 1
        except:
            pass

print(f"  Frozen inventory cohorts with units > 0.01: {frozen_count_method2}")

# VERIFY: Check if variable has a value at all
print_section("8. Checking Variable State")

print("\nChecking if inventory_cohort variables have values:")
sample_lineage_frozen = None
for index in pyomo_model_phase1.inventory_cohort:
    node_id, prod, prod_date, curr_date, state = index
    if node_id == 'Lineage' and state == 'frozen':
        sample_lineage_frozen = index
        break

if sample_lineage_frozen:
    var = pyomo_model_phase1.inventory_cohort[sample_lineage_frozen]
    print(f"  Sample variable: inventory_cohort{sample_lineage_frozen}")
    print(f"    Has value: {var.value is not None}")
    print(f"    Value: {var.value}")
    print(f"    Using pyo.value(): {pyo_value(var)}")
    print(f"    Lower bound: {var.lb}")
    print(f"    Upper bound: {var.ub}")
    print(f"    Is fixed: {var.is_fixed()}")

# FINAL DIAGNOSIS
print_section("9. Diagnosis")

if lineage_inventory_frozen == 0 and demand_satisfied_6130 > 0:
    print("\n🚨 CONTRADICTION FOUND!")
    print(f"   6130 demand satisfied: {demand_satisfied_6130:,.0f} units")
    print(f"   Lineage frozen inventory: 0 units")
    print(f"   This is IMPOSSIBLE if 6130 can only receive from Lineage!")
    print(f"\nPossible causes:")
    print(f"   1. Extraction method error (not using pyo.value() correctly)")
    print(f"   2. Variables not loaded with solution (solver issue)")
    print(f"   3. Wrong variable being checked")
    print(f"   4. Lineage inventory in different state (not frozen)")
elif lineage_inventory_frozen > 0:
    print("\n✓ Model is correct:")
    print(f"   Lineage has {lineage_inventory_frozen:,.0f} frozen units")
    print(f"   This should provide pallet hints for Phase 2")
else:
    print("\n❓ Both Lineage inventory and 6130 demand are zero")
    print(f"   Check if 6130 demand exists in forecast")

print("\n" + "="*80)
