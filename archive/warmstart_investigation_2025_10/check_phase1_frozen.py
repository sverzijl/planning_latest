"""Quick diagnostic: Check if Phase 1 has frozen inventory.

This will tell us if pallet hints can be extracted from Phase 1.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import value as pyo_value, ConstraintList, Binary, Var
import math
import copy

# Load data
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

# Create Phase 1 cost structure (same as in solve_weekly_pattern_warmstart)
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

# Build and solve Phase 1
start_date = date(2025, 10, 20)
end_date = start_date + timedelta(days=6*7 - 1)

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

print("Building Phase 1 model...")
pyomo_model_phase1 = model_phase1_obj.build_model()

# Add weekly pattern (same as in solve_weekly_pattern_warmstart)
products = sorted(set(e.product_id for e in forecast.entries))
pattern_index = [(prod, wd) for prod in products for wd in range(5)]
pyomo_model_phase1.product_weekday_pattern = Var(pattern_index, within=Binary)

print("Solving Phase 1...")
from pyomo.contrib import appsi
solver_phase1 = appsi.solvers.Highs()
solver_phase1.config.time_limit = 120
solver_phase1.config.mip_gap = 0.06  # Relaxed
solver_phase1.highs_options['presolve'] = 'on'
solver_phase1.highs_options['parallel'] = 'on'

results_phase1 = solver_phase1.solve(pyomo_model_phase1)

print(f"Phase 1 solved: {results_phase1.termination_condition}")

# Check frozen inventory
print("\nAnalyzing Phase 1 frozen inventory:")

frozen_cohorts = [(n, p, pd, cd, s) for (n, p, pd, cd, s) in pyomo_model_phase1.inventory_cohort.keys() if s == 'frozen']
print(f"  Total frozen cohorts: {len(frozen_cohorts)}")

frozen_with_inventory = 0
frozen_lineage = 0
max_frozen_units = 0

for key in frozen_cohorts:
    try:
        units = pyo_value(pyomo_model_phase1.inventory_cohort[key])
        if units > 0.01:
            frozen_with_inventory += 1
            max_frozen_units = max(max_frozen_units, units)

            node_id = key[0]
            if node_id == 'Lineage':
                frozen_lineage += 1
    except:
        pass

print(f"  Frozen cohorts with inventory > 0.01: {frozen_with_inventory}")
print(f"  Lineage frozen cohorts: {frozen_lineage}")
print(f"  Max frozen inventory: {max_frozen_units:.1f} units")

if frozen_with_inventory == 0:
    print("\n❌ Phase 1 has NO frozen inventory!")
    print("   This explains why no pallet hints are extracted.")
    print("   Possible reasons:")
    print("   1. Phase 1 prefers ambient storage (cheaper with unit costs)")
    print("   2. Frozen routes not economical in Phase 1 solution")
    print("   3. Model can satisfy demand without using frozen buffer")
else:
    print(f"\n✓ Phase 1 has {frozen_with_inventory} frozen inventory cohorts")
    print(f"  These should provide pallet hints for Phase 2")
