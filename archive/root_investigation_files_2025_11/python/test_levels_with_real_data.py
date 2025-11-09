#!/usr/bin/env python3
"""
Test incremental levels with REAL data to find performance bottleneck.

Strategy:
- Start with simple levels (1-4)
- Test with real data (11 nodes, 5 products, 4 weeks)
- Measure solve time for each
- Identify which level suddenly becomes slow

This will pinpoint the EXACT feature causing the slow solve!
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyomo.environ as pyo
from pyomo.environ import ConcreteModel, Var, Constraint, Objective, NonNegativeReals, minimize, quicksum, value

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser


def load_real_data():
    """Load real data files."""
    print("Loading real data...")

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

    # Get demand in horizon
    demand_by_loc_prod_date = {}
    for entry in forecast.entries:
        if planning_start <= entry.forecast_date <= planning_end:
            key = (entry.location_id, entry.product_id, entry.forecast_date)
            demand_by_loc_prod_date[key] = demand_by_loc_prod_date.get(key, 0) + entry.quantity

    # Get products
    product_ids = sorted(set(k[1] for k in demand_by_loc_prod_date.keys()))

    # Get dates
    dates = [planning_start + timedelta(days=i) for i in range((planning_end - planning_start).days + 1)]

    # Get nodes with demand
    demand_nodes = sorted(set(k[0] for k in demand_by_loc_prod_date.keys()))
    manufacturing_node = '6122'

    print(f"  Dates: {len(dates)}")
    print(f"  Products: {len(product_ids)}")
    print(f"  Demand nodes: {len(demand_nodes)}")
    print(f"  Total demand: {sum(demand_by_loc_prod_date.values()):,.0f} units")

    return {
        'dates': dates,
        'products': product_ids,
        'demand_nodes': demand_nodes,
        'manufacturing_node': manufacturing_node,
        'demand': demand_by_loc_prod_date,
        'routes': routes,
    }


def test_level1_with_real_data(data):
    """Level 1: Basic production-demand with REAL DATA scale"""
    print("\n" + "="*80)
    print("LEVEL 1 WITH REAL DATA: Basic production-demand")
    print("="*80)

    dates = data['dates'][:7]  # Start with 1 week
    products = data['products'][:2]  # Start with 2 products
    demand = data['demand']

    # Filter demand to test scope
    test_demand = {k: v for k, v in demand.items()
                   if k[2] in dates and k[1] in products}

    total_demand = sum(test_demand.values())

    print(f"Test scope: {len(dates)} days, {len(products)} products")
    print(f"Total demand: {total_demand:,.0f} units")

    if total_demand == 0:
        print("No demand in test scope, skipping")
        return None

    # Build simple model
    model = ConcreteModel(name="Level1_RealData")
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)

    # Variables: production and shortage per product per date
    prod_index = [(p, t) for p in products for t in dates]

    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    # Constraint: production + shortage = demand (aggregated across all nodes for simplicity)
    def demand_rule(model, prod, t):
        demand_qty = sum(v for (n, p, d), v in test_demand.items() if p == prod and d == t)
        if demand_qty == 0:
            return Constraint.Skip
        return model.production[prod, t] + model.shortage[prod, t] == demand_qty

    model.demand_con = Constraint(prod_index, rule=demand_rule)

    # Objective
    production_cost = 1.30 * quicksum(model.production[p, t] for (p, t) in prod_index)
    shortage_cost = 10.00 * quicksum(model.shortage[p, t] for (p, t) in prod_index)

    model.obj = Objective(expr=production_cost + shortage_cost, sense=minimize)

    # Solve and measure time
    print(f"Solving...")
    solver = pyo.SolverFactory('appsi_highs')

    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    print(f"  Status: {result.solver.termination_condition}")
    print(f"  Solve time: {solve_time:.2f}s")

    # Extract
    total_prod = sum(value(model.production[k]) for k in prod_index if value(model.production[k]) > 0.01)
    total_short = sum(value(model.shortage[k]) for k in prod_index if value(model.shortage[k]) > 0.01)

    print(f"  Production: {total_prod:,.0f}")
    print(f"  Shortage: {total_short:,.0f}")

    return solve_time


def test_level4_with_real_data(data):
    """Level 4: Add sliding window with REAL DATA"""
    print("\n" + "="*80)
    print("LEVEL 4 WITH REAL DATA: + Sliding window")
    print("="*80)

    dates = data['dates'][:7]  # 1 week
    products = data['products'][:2]  # 2 products
    demand = data['demand']

    test_demand = {k: v for k, v in demand.items()
                   if k[2] in dates and k[1] in products}

    total_demand = sum(test_demand.values())
    print(f"Test scope: {len(dates)} days, {len(products)} products, {total_demand:,.0f} units")

    if total_demand == 0:
        print("No demand, skipping")
        return None

    # Build model with material balance + sliding window
    model = ConcreteModel(name="Level4_RealData")
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    # Variables
    prod_index = [(p, t) for p in products for t in dates]
    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.inventory = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shipment = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    # Material balance
    def balance_rule(model, prod, t):
        prev_date = date_to_prev[t]
        prev_inv = model.inventory[prod, prev_date] if prev_date else 0
        return model.inventory[prod, t] == prev_inv + model.production[prod, t] - model.shipment[prod, t]

    model.balance_con = Constraint(prod_index, rule=balance_rule)

    # Demand satisfaction
    def demand_rule(model, prod, t):
        demand_qty = sum(v for (n, p, d), v in test_demand.items() if p == prod and d == t)
        if demand_qty == 0:
            return Constraint.Skip
        return model.shipment[prod, t] + model.shortage[prod, t] == demand_qty

    model.demand_con = Constraint(prod_index, rule=demand_rule)

    # Sliding window (5-day for testing)
    def sliding_window_rule(model, prod, t):
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 4)
        window_dates = date_list[window_start:t_idx+1]

        Q = quicksum(model.production[prod, tau] for tau in window_dates)
        O = quicksum(model.shipment[prod, tau] for tau in window_dates)

        return O <= Q

    model.sliding_con = Constraint(prod_index, rule=sliding_window_rule)

    # Objective
    model.obj = Objective(
        expr=1.30 * quicksum(model.production[p,t] for (p,t) in prod_index) +
             10.00 * quicksum(model.shortage[p,t] for (p,t) in prod_index),
        sense=minimize
    )

    # Solve
    print(f"Solving...")
    solver = pyo.SolverFactory('appsi_highs')

    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    print(f"  Status: {result.solver.termination_condition}")
    print(f"  Solve time: {solve_time:.2f}s")

    total_prod = sum(value(model.production[k]) for k in prod_index)
    total_short = sum(value(model.shortage[k]) for k in prod_index)

    print(f"  Production: {total_prod:,.0f}")
    print(f"  Shortage: {total_short:,.0f}")

    return solve_time


def test_level4_scaled(data, days, num_products):
    """Test Level 4 with different scales."""
    dates = data['dates'][:days]
    products = data['products'][:num_products]
    demand = data['demand']

    test_demand = {k: v for k, v in demand.items()
                   if k[2] in dates and k[1] in products}

    total_demand = sum(test_demand.values())

    print(f"\nLevel 4: {days} days, {num_products} products, demand={total_demand:,.0f}")

    if total_demand == 0:
        return None

    # Same as test_level4_with_real_data but parameterized
    model = ConcreteModel()
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    prod_index = [(p, t) for p in products for t in dates]
    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.inventory = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shipment = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    def balance_rule(model, prod, t):
        prev_date = date_to_prev[t]
        prev_inv = model.inventory[prod, prev_date] if prev_date else 0
        return model.inventory[prod, t] == prev_inv + model.production[prod, t] - model.shipment[prod, t]

    model.balance_con = Constraint(prod_index, rule=balance_rule)

    def demand_rule(model, prod, t):
        demand_qty = sum(v for (n, p, d), v in test_demand.items() if p == prod and d == t)
        if demand_qty == 0:
            return Constraint.Skip
        return model.shipment[prod, t] + model.shortage[prod, t] == demand_qty

    model.demand_con = Constraint(prod_index, rule=demand_rule)

    def sliding_window_rule(model, prod, t):
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 4)
        window_dates = date_list[window_start:t_idx+1]
        Q = quicksum(model.production[prod, tau] for tau in window_dates)
        O = quicksum(model.shipment[prod, tau] for tau in window_dates)
        return O <= Q

    model.sliding_con = Constraint(prod_index, rule=sliding_window_rule)

    model.obj = Objective(
        expr=1.30 * quicksum(model.production[p,t] for (p,t) in prod_index) +
             10.00 * quicksum(model.shortage[p,t] for (p,t) in prod_index),
        sense=minimize
    )

    solver = pyo.SolverFactory('appsi_highs')
    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    total_prod = sum(value(model.production[k]) for k in prod_index)

    print(f"  Solve time: {solve_time:.2f}s, Production: {total_prod:,.0f}")

    return solve_time


def main():
    """Run incremental tests with real data at different scales."""
    print("\n" + "="*80)
    print("INCREMENTAL PERFORMANCE TEST WITH REAL DATA")
    print("="*80)

    data = load_real_data()

    print("\n" + "="*80)
    print("SCALING TEST: Find where performance degrades")
    print("="*80)

    # Test different scales
    scales = [
        (7, 2, "1 week, 2 products"),
        (14, 2, "2 weeks, 2 products"),
        (29, 2, "4 weeks, 2 products"),
        (7, 5, "1 week, 5 products"),
        (14, 5, "2 weeks, 5 products"),
        (29, 5, "4 weeks, 5 products (FULL SCALE)"),
    ]

    times = {}
    for days, prods, desc in scales:
        try:
            t = test_level4_scaled(data, days, prods)
            times[desc] = t

            if t and t > 60:
                print(f"\n⚠️ SLOW SOLVE AT: {desc}")
                print(f"   This is where performance degrades!")
                break
        except KeyboardInterrupt:
            print(f"\n⚠️ INTERRUPTED AT: {desc}")
            break

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    for desc, t in times.items():
        if t:
            print(f"{desc:40s} {t:6.2f}s")


if __name__ == "__main__":
    main()
