"""Analyze Lineage inventory flow to understand the zero-inventory contradiction.

Check:
1. Inbound shipments to Lineage
2. Outbound shipments from Lineage
3. Inventory balance at Lineage
4. Timing of shipments vs inventory
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
from pyomo.environ import value as pyo_value, Var, Binary
from collections import defaultdict


# Load and solve Phase 1 (same as before)
parser = MultiFileParser(
    forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
    network_file="data/examples/Network_Config.xlsx",
    inventory_file="data/examples/inventory.XLSX",
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

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

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

inventory_snapshot = parser.parse_inventory(snapshot_date=None)
initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

# Create Phase 1 cost structure
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

print("Building and solving Phase 1...")
pyomo_model_phase1 = model_phase1_obj.build_model()

products = sorted(set(e.product_id for e in forecast.entries))
pattern_index = [(prod, wd) for prod in products for wd in range(5)]
pyomo_model_phase1.product_weekday_pattern = Var(pattern_index, within=Binary)

from pyomo.contrib import appsi
solver_phase1 = appsi.solvers.Highs()
solver_phase1.config.time_limit = 120
solver_phase1.config.mip_gap = 0.06
solver_phase1.highs_options['presolve'] = 'on'
solver_phase1.highs_options['parallel'] = 'on'

results_phase1 = solver_phase1.solve(pyomo_model_phase1)
print(f"Solved: {results_phase1.termination_condition}\n")

# Analyze Lineage flow
print("="*80)
print("LINEAGE INVENTORY FLOW ANALYSIS")
print("="*80)

# Inbound to Lineage
print("\n1. INBOUND TO LINEAGE:")
inbound_by_date = defaultdict(float)

if hasattr(pyomo_model_phase1, 'shipment_cohort'):
    for index in pyomo_model_phase1.shipment_cohort:
        # shipment_cohort[origin, dest, product, prod_date, curr_date, state]
        if len(index) == 6:
            origin, dest, prod, prod_date, curr_date, state = index
            if dest == 'Lineage':
                try:
                    qty = pyo_value(pyomo_model_phase1.shipment_cohort[index])
                    if qty > 0.01:
                        inbound_by_date[curr_date] += qty
                except:
                    pass

for date_val in sorted(inbound_by_date.keys())[:10]:  # First 10 days
    print(f"  {date_val}: {inbound_by_date[date_val]:,.0f} units inbound")

total_inbound = sum(inbound_by_date.values())
print(f"  TOTAL INBOUND: {total_inbound:,.0f} units")

# Outbound from Lineage
print("\n2. OUTBOUND FROM LINEAGE:")
outbound_by_date = defaultdict(float)

if hasattr(pyomo_model_phase1, 'shipment_cohort'):
    for index in pyomo_model_phase1.shipment_cohort:
        if len(index) == 6:
            origin, dest, prod, prod_date, curr_date, state = index
            if origin == 'Lineage':
                try:
                    qty = pyo_value(pyomo_model_phase1.shipment_cohort[index])
                    if qty > 0.01:
                        outbound_by_date[curr_date] += qty
                except:
                    pass

for date_val in sorted(outbound_by_date.keys())[:10]:
    print(f"  {date_val}: {outbound_by_date[date_val]:,.0f} units outbound")

total_outbound = sum(outbound_by_date.values())
print(f"  TOTAL OUTBOUND: {total_outbound:,.0f} units")

# Inventory at Lineage by date
print("\n3. INVENTORY AT LINEAGE BY DATE:")
inventory_by_date = defaultdict(float)

if hasattr(pyomo_model_phase1, 'inventory_cohort'):
    for index in pyomo_model_phase1.inventory_cohort:
        node_id, prod, prod_date, curr_date, state = index
        if node_id == 'Lineage':
            try:
                qty = pyo_value(pyomo_model_phase1.inventory_cohort[index])
                inventory_by_date[curr_date] += qty
            except:
                pass

for date_val in sorted(inventory_by_date.keys())[:15]:
    print(f"  {date_val}: {inventory_by_date[date_val]:,.0f} units")

total_inventory_ever = sum(1 for v in inventory_by_date.values() if v > 0.01)
print(f"  Dates with inventory > 0: {total_inventory_ever}")
print(f"  Max inventory: {max(inventory_by_date.values()) if inventory_by_date else 0:,.0f} units")

# Flow balance check
print("\n4. FLOW BALANCE:")
print(f"  Total inbound:  {total_inbound:,.0f}")
print(f"  Total outbound: {total_outbound:,.0f}")
print(f"  Net:            {total_inbound - total_outbound:,.0f}")

if abs(total_inbound - total_outbound) < 100:
    print(f"\n  ✓ Flow-through node: Inbound ≈ Outbound (minimal storage)")
    print(f"    Lineage is NOT storing inventory - just passing through!")
    print(f"\n  💡 THIS EXPLAINS THE ZERO INVENTORY:")
    print(f"    - Model ships to Lineage on day D")
    print(f"    - Model ships from Lineage to 6130 on day D or D+1")
    print(f"    - End-of-day inventory at Lineage ≈ 0 (just in-transit)")
    print(f"\n  IMPLICATION FOR PALLET HINTS:")
    print(f"    - Can extract from shipment_cohort instead of inventory_cohort!")
    print(f"    - Pallet hints = ceil(shipment_from_lineage / 320)")
else:
    print(f"\n  ❌ Flow imbalance: {abs(total_inbound - total_outbound):,.0f} units difference")

print("\n" + "="*80)
