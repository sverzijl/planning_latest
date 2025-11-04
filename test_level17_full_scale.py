#!/usr/bin/env python3
"""
Test Level 17 (frozen state + transitions) with FULL real data scale.

This should confirm if frozen state is the performance bottleneck.
"""

import sys
from pathlib import Path
from datetime import timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyomo.environ as pyo
from pyomo.environ import ConcreteModel, Var, Constraint, Objective, NonNegativeReals, minimize, quicksum, value

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser


def main():
    """Test Level 17 with frozen state at full scale."""
    print("="*80)
    print("LEVEL 17: Frozen state + transitions - FULL SCALE TEST")
    print("="*80)

    # Load real data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    planning_start = inventory_snapshot.snapshot_date
    planning_end = planning_start + timedelta(weeks=4)

    demand = {}
    for entry in forecast.entries:
        if planning_start <= entry.forecast_date <= planning_end:
            key = (entry.location_id, entry.product_id, entry.forecast_date)
            demand[key] = demand.get(key, 0) + entry.quantity

    dates = [planning_start + timedelta(days=i) for i in range((planning_end - planning_start).days + 1)]
    product_ids = sorted(set(k[1] for k in demand.keys()))
    demand_nodes = sorted(set(k[0] for k in demand.keys()))
    mfg_id = '6122'
    all_nodes = [mfg_id] + demand_nodes

    print(f"\nFULL SCALE:")
    print(f"  Days: {len(dates)}")
    print(f"  Products: {len(product_ids)}")
    print(f"  Nodes: {len(all_nodes)}")
    print(f"  Demand: {sum(demand.values()):,.0f} units")

    # Build Level 17 model (with ambient + frozen states)
    model = ConcreteModel(name="Level17_FullScale")
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=product_ids)
    model.nodes = pyo.Set(initialize=all_nodes)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    # Variables
    prod_index = [(p, t) for p in product_ids for t in dates]

    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    # ADD MIX-BASED PRODUCTION (integer variables) - Level 18!
    model.mix_count = Var(prod_index, within=pyo.NonNegativeIntegers, bounds=(0, 1000))
    print(f"  Mix count (INTEGER): {len(prod_index)}")

    # AMBIENT inventory at all nodes
    inv_ambient_index = [(n, p, t) for n in all_nodes for p in product_ids for t in dates]
    model.inventory_ambient = Var(inv_ambient_index, within=NonNegativeReals, bounds=(0, 100000))

    # FROZEN inventory at nodes with frozen capability (e.g., Lineage)
    # For simplicity, only at Lineage
    inv_frozen_index = [('Lineage', p, t) for p in product_ids for t in dates]
    model.inventory_frozen = Var(inv_frozen_index, within=NonNegativeReals, bounds=(0, 100000))

    # State transitions (only where both states exist)
    freeze_index = [('Lineage', p, t) for p in product_ids for t in dates]
    model.freeze = Var(freeze_index, within=NonNegativeReals, bounds=(0, 100000))
    model.thaw = Var(freeze_index, within=NonNegativeReals, bounds=(0, 100000))

    # in_transit (simplified - ambient only for now)
    intransit_index = []
    for route in routes:
        if route.origin_id in all_nodes and route.destination_id in all_nodes:
            for prod in product_ids:
                for t in dates:
                    intransit_index.append((route.origin_id, route.destination_id, prod, t, 'ambient'))
                    # Add frozen for frozen routes
                    if str(route.transport_mode).lower() == 'frozen':
                        intransit_index.append((route.origin_id, route.destination_id, prod, t, 'frozen'))

    model.in_transit = Var(intransit_index, within=NonNegativeReals, bounds=(0, 100000))

    demand_index = list(demand.keys())
    model.demand_consumed = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))

    print(f"\nVariables:")
    print(f"  Production: {len(prod_index)}")
    print(f"  Inventory (ambient): {len(inv_ambient_index)}")
    print(f"  Inventory (frozen): {len(inv_frozen_index)}")
    print(f"  Freeze/thaw: {len(freeze_index)} each")
    print(f"  In-transit: {len(intransit_index)}")

    # Material balance AMBIENT (all nodes)
    def ambient_balance_rule(model, node, prod, t):
        prev = date_to_prev[t]
        prev_inv = model.inventory_ambient[node, prod, prev] if prev else 0

        production = model.production[prod, t] if node == mfg_id else 0

        # Thaw inflow (only at Lineage)
        thaw_inflow = model.thaw['Lineage', prod, t] if node == 'Lineage' and ('Lineage', prod, t) in freeze_index else 0

        # Arrivals (ambient)
        arrivals = 0
        for route in routes:
            if route.destination_id == node and route.origin_id in all_nodes:
                if str(route.transport_mode).lower() != 'frozen':
                    dep_date = t - timedelta(days=route.transit_time_days)
                    if dep_date in dates:
                        key = (route.origin_id, node, prod, dep_date, 'ambient')
                        if key in intransit_index:
                            arrivals += model.in_transit[key]

        # Freeze outflow (only at Lineage)
        freeze_outflow = model.freeze['Lineage', prod, t] if node == 'Lineage' and ('Lineage', prod, t) in freeze_index else 0

        # Departures (ambient)
        departures = 0
        for route in routes:
            if route.origin_id == node and route.destination_id in all_nodes:
                if str(route.transport_mode).lower() != 'frozen':
                    key = (node, route.destination_id, prod, t, 'ambient')
                    if key in intransit_index:
                        departures += model.in_transit[key]

        # Demand
        demand_consumption = 0
        if (node, prod, t) in demand_index:
            demand_consumption = model.demand_consumed[node, prod, t]

        return model.inventory_ambient[node, prod, t] == (
            prev_inv + production + thaw_inflow + arrivals - freeze_outflow - departures - demand_consumption
        )

    # Mix production constraint (Level 18!)
    def mix_rule(model, prod, t):
        """production = mix_count × units_per_mix"""
        return model.production[prod, t] == model.mix_count[prod, t] * 415

    model.mix_con = Constraint(prod_index, rule=mix_rule)
    print(f"  Mix production constraints: {len(prod_index)}")

    model.ambient_balance_con = Constraint(inv_ambient_index, rule=ambient_balance_rule)

    # Material balance FROZEN (only Lineage)
    def frozen_balance_rule(model, node, prod, t):
        if node != 'Lineage':
            return Constraint.Skip

        prev = date_to_prev[t]
        prev_inv = model.inventory_frozen[node, prod, prev] if prev else 0

        freeze_inflow = model.freeze[node, prod, t]

        # Arrivals (frozen)
        arrivals = 0
        for route in routes:
            if route.destination_id == node and route.origin_id in all_nodes:
                if str(route.transport_mode).lower() == 'frozen':
                    dep_date = t - timedelta(days=route.transit_time_days)
                    if dep_date in dates:
                        key = (route.origin_id, node, prod, dep_date, 'frozen')
                        if key in intransit_index:
                            arrivals += model.in_transit[key]

        thaw_outflow = model.thaw[node, prod, t]

        # Departures (frozen)
        departures = 0
        for route in routes:
            if route.origin_id == node and route.destination_id in all_nodes:
                if str(route.transport_mode).lower() == 'frozen':
                    key = (node, route.destination_id, prod, t, 'frozen')
                    if key in intransit_index:
                        departures += model.in_transit[key]

        return model.inventory_frozen[node, prod, t] == (
            prev_inv + freeze_inflow + arrivals - thaw_outflow - departures
        )

    model.frozen_balance_con = Constraint(inv_frozen_index, rule=frozen_balance_rule)

    # Demand satisfaction
    def demand_rule(model, node, prod, t):
        if (node, prod, t) not in demand:
            return Constraint.Skip
        return model.demand_consumed[node, prod, t] + model.shortage[node, prod, t] == demand[node, prod, t]

    model.demand_con = Constraint(demand_index, rule=demand_rule)

    # ADD SLIDING WINDOW CONSTRAINTS (FIXED: Include arrivals in Q!)
    def sliding_ambient_rule(model, node, prod, t):
        """Sliding window for ambient state - CORRECT formulation"""
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 16)  # 17-day window
        window_dates = date_list[window_start:t_idx+1]

        # Inflows
        Q = 0

        # Production (if manufacturing node)
        if node == mfg_id:
            Q += quicksum(model.production[prod, tau] for tau in window_dates)

        # Arrivals in window (CRITICAL FIX!)
        for tau in window_dates:
            for route in routes:
                if route.destination_id == node and route.origin_id in all_nodes:
                    if str(route.transport_mode).lower() != 'frozen':
                        dep_date = tau - timedelta(days=route.transit_time_days)
                        # CORRECT: Check if departure in planning horizon (not window!)
                        if dep_date in date_list:
                            key = (route.origin_id, node, prod, dep_date, 'ambient')
                            if key in intransit_index:
                                Q += model.in_transit[key]

        # Outflows
        O = 0
        for tau in window_dates:
            # Departures
            for route in routes:
                if route.origin_id == node and route.destination_id in all_nodes:
                    if str(route.transport_mode).lower() != 'frozen':
                        key = (node, route.destination_id, prod, tau, 'ambient')
                        if key in intransit_index:
                            O += model.in_transit[key]

            # Demand consumed
            if (node, prod, tau) in demand_index:
                O += model.demand_consumed[node, prod, tau]

        return O <= Q

    model.sliding_ambient_con = Constraint(inv_ambient_index, rule=sliding_ambient_rule)

    print(f"  Adding sliding window constraints: {len(inv_ambient_index)}")

    # Objective
    model.obj = Objective(
        expr=1.30 * quicksum(model.production[k] for k in prod_index) +
             0.10 * quicksum(model.in_transit[k] for k in intransit_index) +
             10.00 * quicksum(model.shortage[k] for k in demand_index),
        sense=minimize
    )

    print(f"\nModel:")
    print(f"  Variables: {model.nvariables():,}")
    print(f"  Constraints: {model.nconstraints():,}")

    # Solve with optimized HiGHS settings
    print(f"\nSolving with optimized HiGHS MIP settings...")
    solver = pyo.SolverFactory('appsi_highs')

    # Set HiGHS options via highs_options dict
    solver.highs_options = {
        'presolve': 'on',  # Critical for MIP performance
        'time_limit': 30.0,
        'parallel': 'on',  # Use parallel branching
        'mip_rel_gap': 0.02,  # 2% gap tolerance
        'mip_heuristic_effort': 0.5,  # Increase heuristic effort
    }

    print(f"  Presolve: ON, Parallel: ON, MIP gap: 2%, Time: 30s")

    solve_start = time.time()
    result = solver.solve(model, tee=False, load_solutions=False)
    solve_time = time.time() - solve_start

    print(f"  Solve time: {solve_time:.2f}s")
    print(f"  Status: {result.solver.termination_condition}")

    # Try to load and extract
    try:
        solver.load_vars()
        total_prod = sum(value(model.production[k]) for k in prod_index)
        total_short = sum(value(model.shortage[k]) for k in demand_index)
        print(f"  Production: {total_prod:,.0f}")
        print(f"  Shortage: {total_short:,.0f}")

        if total_prod > 0:
            print(f"\n✅ LEVEL 17 WORKS AT FULL SCALE!")
            return solve_time
    except Exception as e:
        print(f"  Could not extract solution: {e}")

    if solve_time > 30:
        print(f"\n⚠️ LEVEL 17 IS SLOW AT FULL SCALE!")
        print(f"   Frozen state + transitions cause performance issues")

    return solve_time


if __name__ == "__main__":
    solve_time = main()

    print(f"\n" + "="*80)
    if solve_time < 30:
        print(f"✓ Level 17 is fast enough ({solve_time:.2f}s)")
    else:
        print(f"⚠️ Level 17 is too slow ({solve_time:.2f}s)")
        print(f"   Frozen state is the bottleneck!")
    print("="*80)
