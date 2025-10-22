"""Check if Lineage is doing same-day flow-through (violating storage constraint).

If arrivals on day D lead to departures on day D, this violates the rule:
"Storage locations cannot ship same-day arrivals, only pre-existing stock"
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

# [Same data loading code as before - abbreviated for clarity]
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
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=phase1_cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
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

# Analyze same-day flow-through
print("="*80)
print("SAME-DAY FLOW-THROUGH ANALYSIS AT LINEAGE")
print("="*80)

# Get shipment_cohort structure
if hasattr(pyomo_model_phase1, 'shipment_cohort'):
    # Track arrivals and departures by date
    arrivals_by_date = defaultdict(float)
    departures_by_date = defaultdict(float)

    for index in pyomo_model_phase1.shipment_cohort:
        if len(index) == 6:
            origin, dest, prod, prod_date, curr_date, state = index

            try:
                qty = pyo_value(pyomo_model_phase1.shipment_cohort[index])

                if qty > 0.01:
                    # Inbound to Lineage
                    if dest == 'Lineage':
                        arrivals_by_date[curr_date] += qty

                    # Outbound from Lineage
                    if origin == 'Lineage':
                        # CRITICAL: When does this shipment DEPART Lineage?
                        # curr_date is ARRIVAL date at destination
                        # Need to calculate departure date

                        # Get route to find transit days
                        route = None
                        for r in unified_routes:
                            if r.origin_node_id == 'Lineage' and r.destination_node_id == dest:
                                route = r
                                break

                        if route:
                            # Departure date = Arrival date - transit days
                            departure_date = curr_date - timedelta(days=route.transit_days)
                            departures_by_date[departure_date] += qty
            except:
                pass

    print("\nLineage Flow by Date:")
    print(f"{'Date':<12} {'Arrivals':>12} {'Departures':>12} {'EOD Inventory':>15} {'Same-Day?':>12}")
    print("-"*65)

    # Get inventory by date for comparison
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

    # Check for same-day flow-through violations
    same_day_violations = []

    all_dates = sorted(set(list(arrivals_by_date.keys()) + list(departures_by_date.keys())))
    for date_val in all_dates[:20]:  # First 20 days
        arr = arrivals_by_date.get(date_val, 0)
        dep = departures_by_date.get(date_val, 0)
        inv = inventory_by_date.get(date_val, 0)

        same_day = "YES" if (arr > 0 and dep > 0) else ""

        if arr > 0 and dep > 0:
            same_day_violations.append(date_val)

        print(f"{date_val}   {arr:>10.0f}   {dep:>10.0f}   {inv:>13.0f}   {same_day:>10}")

    print("\n" + "="*80)
    print("DIAGNOSIS")
    print("="*80)

    if same_day_violations:
        print(f"\n❌ FOUND {len(same_day_violations)} SAME-DAY FLOW-THROUGH VIOLATIONS!")
        print(f"   Dates with both arrivals AND departures on same day:")
        for d in same_day_violations[:5]:
            print(f"     {d}: {arrivals_by_date[d]:.0f} in, {departures_by_date[d]:.0f} out")

        print(f"\n   This violates the constraint:")
        print(f"   'Storage nodes cannot ship same-day arrivals, only pre-existing stock'")
        print(f"\n   MODEL BUG: Missing constraint limiting departures to beginning-of-day inventory")
        print(f"\n   Suggested fix:")
        print(f"     For non-truck nodes (like Lineage):")
        print(f"       departures[date] ≤ prev_inventory[date-1] + arrivals[date-1]")
        print(f"       (Cannot ship arrivals until next day)")
    else:
        print(f"\n✓ No same-day flow-through violations found")
        print(f"   Model correctly enforces storage delay")

    # But if there are no violations, why is inventory zero?
    if not same_day_violations and max(inventory_by_date.values()) == 0:
        print(f"\n❓ Inventory is zero but no same-day violations...")
        print(f"   Possible explanations:")
        print(f"     1. Arrivals happen on day D, departures on day D+1 or later")
        print(f"     2. End-of-day inventory is calculated AFTER departures")
        print(f"     3. My timing calculation is wrong")

print("\n" + "="*80)
