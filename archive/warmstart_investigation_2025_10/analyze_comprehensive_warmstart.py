"""Analyze comprehensive warmstart potential.

MIP Expert Analysis: What can we extract from Phase 1?

Phase 1 Variables:
- inventory_cohort[node, prod, prod_date, curr_date, state] - CONTINUOUS
- shipment_cohort[origin, dest, prod, prod_date, curr_date, state] - CONTINUOUS
- production[node, prod, date] - CONTINUOUS
- product_produced[node, prod, date] - BINARY
- labor variables - CONTINUOUS
- truck variables - BINARY/CONTINUOUS

Phase 2 Variables (that don't exist in Phase 1):
- pallet_count[node, prod, prod_date, curr_date, state] - INTEGER
  → Can derive from Phase 1 inventory_cohort: ceil(units / 320)

Question: Why are we only extracting 97 pallet hints when Phase 2 has 4,515 pallet variables?

Answer: We should extract ALL of them!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import value as pyo_value, Var
import copy
from datetime import date, timedelta

# Load data
parser = MultiFileParser(
    forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
    network_file="data/examples/Network_Config.xlsx",
    inventory_file="data/examples/inventory.XLSX",
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

inventory_snapshot = parser.parse_inventory(snapshot_date=None)
initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

# Create Phase 1 and Phase 2 models
phase1_cost_structure = copy.copy(cost_structure)
if (getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0) > 0 or
    getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0) > 0):
    pallet_var_cost = getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0)
    pallet_fixed_cost = getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0)
    equivalent_unit_cost_frozen = (pallet_var_cost + pallet_fixed_cost / 7.0) / 320.0
    phase1_cost_structure.storage_cost_frozen_per_unit_day = equivalent_unit_cost_frozen
    phase1_cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    phase1_cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0

start_date = date(2025, 10, 20)
end_date = start_date + timedelta(days=6*7 - 1)

print("="*80)
print("COMPREHENSIVE WARMSTART ANALYSIS")
print("="*80)

print("\nBuilding Phase 1 and Phase 2 models (no solve)...")

# Build Phase 1
model_phase1 = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=phase1_cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
)

pyomo_phase1 = model_phase1.build_model()

# Build Phase 2
model_phase2 = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,  # Original pallet costs
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
)

pyomo_phase2 = model_phase2.build_model()

print("\nAnalyzing variable overlap between Phase 1 and Phase 2...")

# Count variables in each model
def count_variables(model, model_name):
    """Count variables by type."""
    counts = {'binary': 0, 'integer': 0, 'continuous': 0}

    for v in model.component_data_objects(Var, active=True):
        if v.is_binary():
            counts['binary'] += 1
        elif v.is_integer():
            counts['integer'] += 1
        else:
            counts['continuous'] += 1

    print(f"\n{model_name}:")
    print(f"  Binary:     {counts['binary']:,}")
    print(f"  Integer:    {counts['integer']:,}")
    print(f"  Continuous: {counts['continuous']:,}")
    print(f"  TOTAL:      {sum(counts.values()):,}")

    return counts

counts_p1 = count_variables(pyomo_phase1, "Phase 1")
counts_p2 = count_variables(pyomo_phase2, "Phase 2")

# Analyze shared variable structure
print("\n" + "="*80)
print("WARMSTART POTENTIAL")
print("="*80)

# 1. Binary variables that exist in both
print("\n1. BINARY VARIABLES:")

phase1_binaries = set()
for v in pyomo_phase1.component_data_objects(Var, active=True):
    if v.is_binary():
        phase1_binaries.add(str(v.name).split('[')[0])

phase2_binaries = set()
for v in pyomo_phase2.component_data_objects(Var, active=True):
    if v.is_binary():
        phase2_binaries.add(str(v.name).split('[')[0])

shared_binaries = phase1_binaries.intersection(phase2_binaries)
print(f"   Phase 1 binary components: {sorted(phase1_binaries)}")
print(f"   Phase 2 binary components: {sorted(phase2_binaries)}")
print(f"   Shared: {sorted(shared_binaries)}")

# Check product_produced specifically
if hasattr(pyomo_phase1, 'product_produced') and hasattr(pyomo_phase2, 'product_produced'):
    p1_prod = len([1 for _ in pyomo_phase1.product_produced])
    p2_prod = len([1 for _ in pyomo_phase2.product_produced])
    print(f"   product_produced: {p1_prod} in P1, {p2_prod} in P2")
    print(f"   → Can warmstart {min(p1_prod, p2_prod)} binary variables (100% coverage)")

# 2. Integer variables
print("\n2. INTEGER VARIABLES:")

phase2_integers = {}
for v in pyomo_phase2.component_data_objects(Var, active=True):
    if v.is_integer():
        comp_name = str(v.name).split('[')[0]
        phase2_integers[comp_name] = phase2_integers.get(comp_name, 0) + 1

print(f"   Phase 2 integer components:")
for comp, count in sorted(phase2_integers.items()):
    print(f"     {comp}: {count:,} variables")

# Check if Phase 1 has equivalents
print(f"\n   Warmstart potential:")

# pallet_count: Derive from inventory_cohort
if hasattr(pyomo_phase2, 'pallet_count'):
    p2_pallet_count = len([1 for _ in pyomo_phase2.pallet_count])
    print(f"     pallet_count: {p2_pallet_count:,} in Phase 2")

    if hasattr(pyomo_phase1, 'inventory_cohort'):
        # Count how many Phase 1 inventory cohorts match Phase 2 pallet_count indices
        p1_inv_cohorts = set(pyomo_phase1.inventory_cohort.keys())
        p2_pallet_indices = set(pyomo_phase2.pallet_count.keys())

        matching = p1_inv_cohorts.intersection(p2_pallet_indices)
        print(f"       Phase 1 inventory_cohort: {len(p1_inv_cohorts):,}")
        print(f"       Matching Phase 2 pallet indices: {len(matching):,}")
        print(f"       → Can derive {len(matching):,} pallet hints ({len(matching)/p2_pallet_count*100:.1f}% coverage)")

# num_products_produced: Derive from product_produced
if hasattr(pyomo_phase2, 'num_products_produced'):
    p2_num_prods = len([1 for _ in pyomo_phase2.num_products_produced])
    print(f"     num_products_produced: {p2_num_prods:,} in Phase 2")

    if hasattr(pyomo_phase1, 'product_produced'):
        # Can count how many products produced on each date
        print(f"       → Can derive from Phase 1 product_produced (100% coverage)")

# 3. Continuous variables
print("\n3. CONTINUOUS VARIABLES:")

phase1_continuous_comps = set()
for v in pyomo_phase1.component_objects(Var, active=True):
    if any(vv.is_continuous() for vv in v.values()):
        phase1_continuous_comps.add(v.name)

phase2_continuous_comps = set()
for v in pyomo_phase2.component_objects(Var, active=True):
    if any(vv.is_continuous() for vv in v.values()):
        phase2_continuous_comps.add(v.name)

shared_continuous = phase1_continuous_comps.intersection(phase2_continuous_comps)

print(f"   Shared continuous components: {sorted(shared_continuous)}")

# Check sizes
for comp_name in sorted(shared_continuous):
    if hasattr(pyomo_phase1, comp_name) and hasattr(pyomo_phase2, comp_name):
        p1_comp = getattr(pyomo_phase1, comp_name)
        p2_comp = getattr(pyomo_phase2, comp_name)
        p1_size = len([1 for _ in p1_comp])
        p2_size = len([1 for _ in p2_comp])
        print(f"     {comp_name}: {p1_size:,} in P1, {p2_size:,} in P2")

# Summary
print("\n" + "="*80)
print("COMPREHENSIVE WARMSTART SUMMARY")
print("="*80)

total_p2_vars = counts_p2['binary'] + counts_p2['integer'] + counts_p2['continuous']
warmstartable_vars = 0

# Binary
warmstartable_vars += min(counts_p1['binary'], counts_p2['binary'])

# Integer (derivable from Phase 1)
if hasattr(pyomo_phase2, 'pallet_count'):
    warmstartable_vars += len([1 for _ in pyomo_phase2.pallet_count])

# Continuous (all shared components)
for comp_name in shared_continuous:
    if hasattr(pyomo_phase2, comp_name):
        warmstartable_vars += len([1 for _ in getattr(pyomo_phase2, comp_name)])

print(f"\nPhase 2 total variables: {total_p2_vars:,}")
print(f"Warmstartable variables: {warmstartable_vars:,}")
print(f"Coverage: {warmstartable_vars/total_p2_vars*100:.1f}%")

print(f"\nCURRENT IMPLEMENTATION:")
print(f"  Product binaries: 210 hints (100% coverage) ✓")
print(f"  Pallet integers: 97 hints (2% coverage) ❌")
print(f"  Continuous vars: 0 hints (0% coverage) ❌")

print(f"\nPOTENTIAL COMPREHENSIVE WARMSTART:")
print(f"  Product binaries: 210 hints (100%) ✓")
print(f"  Pallet integers: ALL ~4,515 hints (100%) ✓✓✓")
print(f"  inventory_cohort: ALL ~30,765 hints (100%) ✓✓✓")
print(f"  shipment_cohort: ALL ~41,690 hints (100%) ✓✓✓")
print(f"  production: ALL ~210 hints (100%) ✓✓✓")
print(f"  Other continuous: ALL remaining ✓✓✓")

print(f"\n💡 MIP EXPERT INSIGHT:")
print(f"   Providing complete warmstart (100% coverage) should dramatically")
print(f"   reduce Phase 2 solve time. Solver starts with a COMPLETE feasible")
print(f"   solution and only needs to refine it, not build from scratch!")

print("\n" + "="*80)
