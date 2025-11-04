#!/usr/bin/env python3
"""
Test Levels 14-16 with real data to find exact performance bottleneck.

Level 14: demand_consumed in sliding window
Level 15: Dynamic arrivals
Level 16: Arrivals in sliding window Q

One of these likely causes the slow solve!
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


def load_real_data():
    """Load real data - use 2 weeks and 3 products."""
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    planning_start = inventory_snapshot.snapshot_date
    planning_end = planning_start + timedelta(weeks=4)  # 4 weeks - FULL SCALE

    demand = {}
    for entry in forecast.entries:
        if planning_start <= entry.forecast_date <= planning_end:
            key = (entry.location_id, entry.product_id, entry.forecast_date)
            demand[key] = demand.get(key, 0) + entry.quantity

    dates = [planning_start + timedelta(days=i) for i in range((planning_end - planning_start).days + 1)]
    product_ids = sorted(set(k[1] for k in demand.keys()))  # ALL 5 products

    demand = {k: v for k, v in demand.items() if k[1] in product_ids}

    print(f"Real data: {len(dates)} days, {len(product_ids)} products, {sum(demand.values()):,.0f} units demand")

    return {
        'dates': dates,
        'products': product_ids,
        'demand': demand,
        'routes': routes,
        'mfg_id': '6122',
        'demand_nodes': sorted(set(k[0] for k in demand.keys())),
    }


def test_level14_real(data):
    """Level 14: Multi-node with demand_consumed in sliding window."""
    print("\n" + "="*80)
    print("LEVEL 14: demand_consumed in sliding window")
    print("="*80)

    dates = data['dates']
    products = data['products']
    demand = data['demand']
    routes = data['routes']
    mfg_id = data['mfg_id']
    demand_nodes = data['demand_nodes']

    model = ConcreteModel()
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    # Simplified 2-node network for testing: MFG → DEMAND (aggregate all demand nodes)
    # This is like Level 14 but with real data scale

    prod_index = [(p, t) for p in products for t in dates]

    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.inventory_mfg = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.inventory_demand = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.in_transit = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))  # Simplified
    model.demand_consumed = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    # Material balances
    def mfg_balance_rule(model, prod, t):
        prev = date_to_prev[t]
        prev_inv = model.inventory_mfg[prod, prev] if prev else 0
        return model.inventory_mfg[prod, t] == prev_inv + model.production[prod, t] - model.in_transit[prod, t]

    model.mfg_balance_con = Constraint(prod_index, rule=mfg_balance_rule)

    def demand_balance_rule(model, prod, t):
        prev = date_to_prev[t]
        prev_inv = model.inventory_demand[prod, prev] if prev else 0
        t_idx = date_list.index(t)
        arrivals = model.in_transit[prod, date_list[t_idx-2]] if t_idx >= 2 else 0
        return model.inventory_demand[prod, t] == prev_inv + arrivals - model.demand_consumed[prod, t]

    model.demand_balance_con = Constraint(prod_index, rule=demand_balance_rule)

    # Demand satisfaction
    demand_agg = {}
    for (node, prod, t), qty in demand.items():
        demand_agg[(prod, t)] = demand_agg.get((prod, t), 0) + qty

    def demand_sat_rule(model, prod, t):
        demand_qty = demand_agg.get((prod, t), 0)
        if demand_qty == 0:
            return Constraint.Skip
        return model.demand_consumed[prod, t] + model.shortage[prod, t] == demand_qty

    model.demand_sat_con = Constraint(prod_index, rule=demand_sat_rule)

    # Sliding window at DEMAND with demand_consumed in O (KEY DIFFERENCE)
    def sliding_demand_rule(model, prod, t):
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 4)
        window_dates = date_list[window_start:t_idx+1]

        # Inflows: arrivals
        Q = 0
        for tau in window_dates:
            tau_idx = date_list.index(tau)
            if tau_idx >= 2:
                Q += model.in_transit[prod, date_list[tau_idx-2]]

        # Outflows: demand_consumed (THIS IS THE KEY!)
        O = quicksum(model.demand_consumed[prod, tau] for tau in window_dates)

        return O <= Q

    model.sliding_demand_con = Constraint(prod_index, rule=sliding_demand_rule)

    # Objective
    model.obj = Objective(
        expr=1.30 * quicksum(model.production[k] for k in prod_index) +
             0.10 * quicksum(model.in_transit[k] for k in prod_index) +
             10.00 * quicksum(model.shortage[k] for k in prod_index),
        sense=minimize
    )

    print(f"  Variables: {model.nvariables():,}, Constraints: {model.nconstraints():,}")

    solver = pyo.SolverFactory('appsi_highs')
    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    total_prod = sum(value(model.production[k]) for k in prod_index)

    print(f"  Solve time: {solve_time:.2f}s")
    print(f"  Production: {total_prod:,.0f}")

    return solve_time


def test_level16_real(data):
    """Level 16: Multi-node with FULL sliding window (arrivals in Q)."""
    print("\n" + "="*80)
    print("LEVEL 16: Multi-node with sliding window at all nodes")
    print("="*80)

    dates = data['dates']
    products = data['products']
    demand = data['demand']
    routes = data['routes']
    mfg_id = data['mfg_id']
    demand_nodes = data['demand_nodes']

    # Use ALL real nodes (not aggregated)
    all_nodes = [mfg_id] + demand_nodes  # Use ALL nodes - FULL SCALE TEST

    print(f"  Nodes: {len(all_nodes)} (testing subset)")
    print(f"  Routes: {len(routes)}")

    model = ConcreteModel()
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)
    model.nodes = pyo.Set(initialize=all_nodes)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    # Variables
    prod_index = [(p, t) for p in products for t in dates]
    inv_index = [(n, p, t) for n in all_nodes for p in products for t in dates]

    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.inventory = Var(inv_index, within=NonNegativeReals, bounds=(0, 100000))

    # in_transit for real routes (filtered to our test nodes)
    intransit_index = []
    for route in routes:
        if route.origin_id in all_nodes and route.destination_id in all_nodes:
            for prod in products:
                for t in dates:
                    intransit_index.append((route.origin_id, route.destination_id, prod, t))

    model.in_transit = Var(intransit_index, within=NonNegativeReals, bounds=(0, 100000))

    # Demand variables
    demand_filtered = {k: v for k, v in demand.items() if k[0] in all_nodes}
    demand_index = list(demand_filtered.keys())

    model.demand_consumed = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))

    # Material balance at each node
    def balance_rule(model, node, prod, t):
        prev = date_to_prev[t]
        prev_inv = model.inventory[node, prod, prev] if prev else 0

        production_inflow = model.production[prod, t] if node == mfg_id else 0

        # Arrivals
        arrivals = 0
        for route in routes:
            if route.destination_id == node and route.origin_id in all_nodes:
                dep_date = t - timedelta(days=route.transit_time_days)
                if dep_date in dates:
                    key = (route.origin_id, node, prod, dep_date)
                    if key in intransit_index:
                        arrivals += model.in_transit[key]

        # Departures
        departures = 0
        for route in routes:
            if route.origin_id == node and route.destination_id in all_nodes:
                key = (node, route.destination_id, prod, t)
                if key in intransit_index:
                    departures += model.in_transit[key]

        # Demand
        demand_consumption = 0
        if (node, prod, t) in demand_index:
            demand_consumption = model.demand_consumed[node, prod, t]

        return model.inventory[node, prod, t] == prev_inv + production_inflow + arrivals - departures - demand_consumption

    model.balance_con = Constraint(inv_index, rule=balance_rule)

    # Demand satisfaction
    def demand_rule(model, node, prod, t):
        if (node, prod, t) not in demand_filtered:
            return Constraint.Skip
        return model.demand_consumed[node, prod, t] + model.shortage[node, prod, t] == demand_filtered[node, prod, t]

    model.demand_con = Constraint(demand_index, rule=demand_rule)

    # Sliding window at EACH node (THIS IS THE KEY DIFFERENCE)
    def sliding_rule(model, node, prod, t):
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 4)
        window_dates = date_list[window_start:t_idx+1]

        # Inflows
        Q = 0
        if node == mfg_id:
            Q += quicksum(model.production[prod, tau] for tau in window_dates)
        else:
            # Arrivals
            for tau in window_dates:
                for route in routes:
                    if route.destination_id == node and route.origin_id in all_nodes:
                        dep_date = tau - timedelta(days=route.transit_time_days)
                        if dep_date in window_dates:
                            key = (route.origin_id, node, prod, dep_date)
                            if key in intransit_index:
                                Q += model.in_transit[key]

        # Outflows
        O = 0
        for tau in window_dates:
            # Departures
            for route in routes:
                if route.origin_id == node and route.destination_id in all_nodes:
                    key = (node, route.destination_id, prod, tau)
                    if key in intransit_index:
                        O += model.in_transit[key]

            # Demand consumed
            if (node, prod, tau) in demand_index:
                O += model.demand_consumed[node, prod, tau]

        return O <= Q

    model.sliding_con = Constraint(inv_index, rule=sliding_rule)

    # Objective
    model.obj = Objective(
        expr=1.30 * quicksum(model.production[k] for k in prod_index) +
             0.10 * quicksum(model.in_transit[k] for k in intransit_index) +
             10.00 * quicksum(model.shortage[k] for k in demand_index),
        sense=minimize
    )

    print(f"  Variables: {model.nvariables():,}, Constraints: {model.nconstraints():,}")

    solver = pyo.SolverFactory('appsi_highs')
    solve_start = time.time()

    # Set time limit
    solver.config.time_limit = 60.0

    result = solver.solve(model, tee=False, load_solutions=False)
    solve_time = time.time() - solve_start

    # Try to load if solved
    try:
        solver.load_vars()
        total_prod = sum(value(model.production[k]) for k in prod_index)
    except:
        total_prod = 0

    print(f"  Solve time: {solve_time:.2f}s")
    print(f"  Status: {result.solver.termination_condition}")
    print(f"  Production: {total_prod:,.0f}")

    return solve_time


def main():
    """Test Levels 14-16 with real data."""
    print("="*80)
    print("PERFORMANCE TEST: Levels 14-16 with real data")
    print("="*80)

    data = load_real_data()

    results = {}

    # Test Level 14
    results['Level 14'] = test_level14_real(data)

    # Test Level 16 (with sliding window at all nodes)
    results['Level 16'] = test_level16_real(data)

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    for level, t in results.items():
        if t:
            status = "⚠️ SLOW" if t > 10 else "✓ FAST"
            print(f"{level:20s} {t:8.2f}s  {status}")

    # Find the bottleneck
    if results.get('Level 14', 0) < 5 and results.get('Level 16', 0) > 30:
        print(f"\n🔍 BOTTLENECK FOUND!")
        print(f"   Level 14 is fast, Level 16 is slow")
        print(f"   The issue is in Level 16: Arrivals in sliding window Q")


if __name__ == "__main__":
    main()
