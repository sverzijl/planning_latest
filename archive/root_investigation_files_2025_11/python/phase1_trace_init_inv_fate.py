"""
SYSTEMATIC DEBUGGING - PHASE 1: Root Cause Investigation

Trace EXACTLY what happens to initial inventory in both solutions.

Evidence to gather:
1. Where is init_inv on Day 1 (which nodes)?
2. How much is consumed each day?
3. How much is shipped each day?
4. When does it start accumulating (not flowing out)?
5. Which specific units end up disposed?
"""

from datetime import datetime, timedelta
from pyomo.core.base import value
from pyomo.environ import Constraint

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


def solve_and_trace_init_inv_daily(add_constraint=False):
    """Trace initial inventory day-by-day."""

    coordinator = DataCoordinator(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    validated = coordinator.load_and_validate()

    forecast_entries = [
        ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                     forecast_date=e.demand_date, quantity=e.quantity)
        for e in validated.demand_entries
    ]
    forecast = Forecast(name="Test", entries=forecast_entries)

    parser = MultiFileParser(
        'data/examples/Gluten Free Forecast - Latest.xlsm',
        'data/examples/Network_Config.xlsx',
        'data/examples/inventory_latest.XLSX'
    )
    _, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes_legacy)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
    products_dict = {p.id: p for p in validated.products}

    start = validated.planning_start_date
    end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

    model_builder = SlidingWindowModel(
        nodes, unified_routes, forecast, labor_calendar, cost_structure,
        products_dict, start, end, unified_truck_schedules,
        validated.get_inventory_dict(), validated.inventory_snapshot_date,
        True, True, True
    )

    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
    model = model_builder.model

    if add_constraint:
        last_date = max(model.dates)
        total_end_inv = sum(
            model.inventory[n, p, s, last_date]
            for (n, p, s, t) in model.inventory
            if t == last_date
        )
        model.force_low_end_inv = Constraint(expr=total_end_inv <= 2000)

        from pyomo.opt import SolverFactory
        solver = SolverFactory('appsi_highs')
        result = solver.solve(model, tee=False)

    # Trace inventory at nodes that HAD init_inv
    # Focus on one node that shows disposal: 6123
    trace_node = '6123'
    trace_product = 'HELGAS GFREE WHOLEM 500G'  # Had disposal in constrained

    # Get init_inv for this combination
    init_inv_qty = model_builder.initial_inventory.get((trace_node, trace_product, 'ambient'), 0)

    # Trace day by day
    daily_trace = []
    dates = sorted(list(model.dates))

    for t in dates:
        # Inventory at end of day
        inv = 0
        if (trace_node, trace_product, 'ambient', t) in model.inventory:
            inv = value(model.inventory[trace_node, trace_product, 'ambient', t])

        # Consumption
        cons = 0
        if (trace_node, trace_product, t) in model.demand_consumed_from_ambient:
            cons = value(model.demand_consumed_from_ambient[trace_node, trace_product, t])

        # Demand
        demand = model_builder.demand.get((trace_node, trace_product, t), 0)

        # Shortage
        shortage = 0
        if hasattr(model, 'shortage') and (trace_node, trace_product, t) in model.shortage:
            shortage = value(model.shortage[trace_node, trace_product, t])

        # Disposal
        disposal = 0
        if hasattr(model, 'disposal') and (trace_node, trace_product, 'ambient', t) in model.disposal:
            disposal = value(model.disposal[trace_node, trace_product, 'ambient', t])

        daily_trace.append({
            'date': t,
            'inventory': inv,
            'consumption': cons,
            'demand': demand,
            'shortage': shortage,
            'disposal': disposal
        })

    return trace_node, trace_product, init_inv_qty, daily_trace


print("="*120)
print("SYSTEMATIC DEBUGGING - PHASE 1: Root Cause Investigation")
print("="*120)
print("\nTracing initial inventory fate for ONE specific node/product...\n")

print("1. NATURAL solution...")
node, product, init_inv, trace_nat = solve_and_trace_init_inv_daily(False)

print(f"\n2. CONSTRAINED solution...")
_, _, _, trace_con = solve_and_trace_init_inv_daily(True)

# Display comparison
print("\n\n" + "="*120)
print(f"DAILY TRACE: Node {node}, Product {product[:35]}")
print(f"Initial inventory: {init_inv:,.0f} units")
print("="*120)

print(f"\n{'Date':<12} {'Day':>3} {'Natural':<45} {'Constrained':<45}")
print(f"{'':12} {'':3} {'Inv':>8} {'Cons':>8} {'Demand':>8} {'Short':>8} {'Disp':>6} {'Inv':>8} {'Cons':>8} {'Demand':>8} {'Short':>8} {'Disp':>6}")
print("-"*120)

for i in range(len(trace_nat)):
    t = trace_nat[i]['date']
    nat = trace_nat[i]
    con = trace_con[i]

    # Highlight differences
    marker = ""
    if abs(nat['inventory'] - con['inventory']) > 50:
        marker = " ← INV DIFFERS"
    elif abs(nat['consumption'] - con['consumption']) > 50:
        marker = " ← CONS DIFFERS"
    elif con['disposal'] > 10:
        marker = " ← DISPOSAL!"

    print(f"{t} {i+1:>3} {nat['inventory']:>8,.0f} {nat['consumption']:>8,.0f} {nat['demand']:>8,.0f} {nat['shortage']:>8,.0f} {nat['disposal']:>6,.0f} {con['inventory']:>8,.0f} {con['consumption']:>8,.0f} {con['demand']:>8,.0f} {con['shortage']:>8,.0f} {con['disposal']:>6,.0f}{marker}")

print("\n\n" + "="*120)
print("EVIDENCE GATHERED:")
print("="*120)

# Find where they diverge
divergence_day = None
for i in range(len(trace_nat)):
    if abs(trace_nat[i]['inventory'] - trace_con[i]['inventory']) > 50:
        divergence_day = i + 1
        break

if divergence_day:
    print(f"\n→ Inventory levels DIVERGE starting Day {divergence_day}")
    print(f"  Date: {trace_nat[divergence_day-1]['date']}")
    print(f"  Natural inventory: {trace_nat[divergence_day-1]['inventory']:,.0f}")
    print(f"  Constrained inventory: {trace_con[divergence_day-1]['inventory']:,.0f}")

# Check total consumption
total_cons_nat = sum(t['consumption'] for t in trace_nat)
total_cons_con = sum(t['consumption'] for t in trace_con)

print(f"\n→ Total consumption over 28 days:")
print(f"  Natural: {total_cons_nat:,.0f} units")
print(f"  Constrained: {total_cons_con:,.0f} units")
print(f"  Difference: {total_cons_con - total_cons_nat:,.0f} units")

# Check disposal
total_disp_nat = sum(t['disposal'] for t in trace_nat)
total_disp_con = sum(t['disposal'] for t in trace_con)

print(f"\n→ Total disposal:")
print(f"  Natural: {total_disp_nat:,.0f} units")
print(f"  Constrained: {total_disp_con:,.0f} units")
print(f"  Difference: {total_disp_con - total_disp_nat:,.0f} units")

print(f"\n\n" + "="*120)
print(f"ROOT CAUSE HYPOTHESIS:")
print(f"={'='*120}")

if total_cons_nat > total_cons_con + 500:
    print(f"\n→ Constrained solution CONSUMES LESS over the horizon")
    print(f"  Reduction: {total_cons_nat - total_cons_con:,.0f} units")
    print(f"  This almost matches disposal increase: {total_disp_con:,.0f} units")
    print(f"\n  HYPOTHESIS: end_inv constraint prevents consumption of init_inv")
    print(f"  Need to identify WHICH constraint/mechanism blocks it")
else:
    print(f"\n→ Consumption levels similar")
    print(f"  Disposal increase not from reduced consumption")
    print(f"  Must be from different inventory positioning/routing")

print(f"\n{'='*120}")
print(f"NEXT: Identify the blocking constraint (Phase 2)")
print(f"{'='*120}")
