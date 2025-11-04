#!/usr/bin/env python3
"""
Test each incremental level with REAL DATA to find performance bottleneck.

We'll test critical levels:
- Level 1: Basic
- Level 4: + Sliding window
- Level 5: + Multi-node
- Level 13: + in_transit variables
- Level 16: + Dynamic arrivals in sliding window

Find where solve time suddenly increases!
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
    """Load real data - use 2 weeks and 2 products for faster testing."""
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    planning_start = inventory_snapshot.snapshot_date
    planning_end = planning_start + timedelta(weeks=2)  # 2 weeks for faster testing

    # Get demand
    demand = {}
    for entry in forecast.entries:
        if planning_start <= entry.forecast_date <= planning_end:
            key = (entry.location_id, entry.product_id, entry.forecast_date)
            demand[key] = demand.get(key, 0) + entry.quantity

    dates = [planning_start + timedelta(days=i) for i in range((planning_end - planning_start).days + 1)]
    product_ids = sorted(set(k[1] for k in demand.keys()))[:2]  # Just 2 products

    # Filter demand to 2 products
    demand = {k: v for k, v in demand.items() if k[1] in product_ids}

    print(f"Real data loaded:")
    print(f"  Dates: {len(dates)}")
    print(f"  Products: {len(product_ids)}")
    print(f"  Total demand: {sum(demand.values()):,.0f} units")
    print(f"  Locations: {len(locations)}")
    print(f"  Routes: {len(routes)}")

    return {
        'dates': dates,
        'products': product_ids,
        'demand': demand,
        'locations': locations,
        'routes': routes,
    }


def test_level4_real(data):
    """Level 4: Sliding window (single node)."""
    print("\n" + "="*80)
    print("LEVEL 4: Sliding window (single node)")
    print("="*80)

    dates = data['dates']
    products = data['products']
    demand = data['demand']

    # Aggregate demand across all locations
    demand_by_prod_date = {}
    for (loc, prod, d), qty in demand.items():
        demand_by_prod_date[(prod, d)] = demand_by_prod_date.get((prod, d), 0) + qty

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
        prev = date_to_prev[t]
        prev_inv = model.inventory[prod, prev] if prev else 0
        return model.inventory[prod, t] == prev_inv + model.production[prod, t] - model.shipment[prod, t]

    model.balance_con = Constraint(prod_index, rule=balance_rule)

    def demand_rule(model, prod, t):
        demand_qty = demand_by_prod_date.get((prod, t), 0)
        if demand_qty == 0:
            return Constraint.Skip
        return model.shipment[prod, t] + model.shortage[prod, t] == demand_qty

    model.demand_con = Constraint(prod_index, rule=demand_rule)

    def sliding_rule(model, prod, t):
        t_idx = date_list.index(t)
        window_start = max(0, t_idx - 4)
        window_dates = date_list[window_start:t_idx+1]
        Q = quicksum(model.production[prod, tau] for tau in window_dates)
        O = quicksum(model.shipment[prod, tau] for tau in window_dates)
        return O <= Q

    model.sliding_con = Constraint(prod_index, rule=sliding_rule)

    model.obj = Objective(
        expr=1.30 * quicksum(model.production[k] for k in prod_index) +
             10.00 * quicksum(model.shortage[k] for k in prod_index),
        sense=minimize
    )

    print(f"  Variables: {model.nvariables()}, Constraints: {model.nconstraints()}")

    solver = pyo.SolverFactory('appsi_highs')
    solve_start = time.time()
    result = solver.solve(model, tee=False)
    solve_time = time.time() - solve_start

    total_prod = sum(value(model.production[k]) for k in prod_index)

    print(f"  Solve time: {solve_time:.2f}s")
    print(f"  Production: {total_prod:,.0f}")

    return solve_time


def test_level13_real(data):
    """Level 13: Multi-node with in_transit variables - CRITICAL TEST."""
    print("\n" + "="*80)
    print("LEVEL 13: Multi-node with in_transit (CRITICAL)")
    print("="*80)

    dates = data['dates']
    products = data['products']
    demand = data['demand']
    routes = data['routes']
    locations = data['locations']

    # Get location IDs
    loc_ids = [loc.id for loc in locations]
    mfg_id = '6122'

    print(f"  Nodes: {len(loc_ids)}")
    print(f"  Routes: {len(routes)}")
    print(f"  Products: {len(products)}")
    print(f"  Days: {len(dates)}")

    model = ConcreteModel()
    model.dates = pyo.Set(initialize=dates, ordered=True)
    model.products = pyo.Set(initialize=products)
    model.nodes = pyo.Set(initialize=loc_ids)

    date_list = list(dates)
    date_to_prev = {date_list[i]: date_list[i-1] if i > 0 else None for i in range(len(date_list))}

    # Production (only at manufacturing)
    prod_index = [(p, t) for p in products for t in dates]
    model.production = Var(prod_index, within=NonNegativeReals, bounds=(0, 100000))

    # Inventory at each node
    inv_index = [(n, p, t) for n in loc_ids for p in products for t in dates]
    model.inventory = Var(inv_index, within=NonNegativeReals, bounds=(0, 100000))

    # in_transit variables (keyed by origin, dest, prod, departure_date, state)
    intransit_index = []
    for route in routes:
        for prod in products:
            for t in dates:
                intransit_index.append((route.origin_id, route.destination_id, prod, t, 'ambient'))

    model.in_transit = Var(intransit_index, within=NonNegativeReals, bounds=(0, 100000))

    # demand_consumed
    demand_index = list(demand.keys())
    model.demand_consumed = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))
    model.shortage = Var(demand_index, within=NonNegativeReals, bounds=(0, 100000))

    # Material balance at each node
    def balance_rule(model, node, prod, t):
        prev = date_to_prev[t]
        prev_inv = model.inventory[node, prod, prev] if prev else 0

        # Production (only at mfg)
        production_inflow = model.production[prod, t] if node == mfg_id else 0

        # Arrivals (goods that departed t - transit_days ago)
        arrivals = 0
        for route in routes:
            if route.destination_id == node:
                departure_date = t - timedelta(days=route.transit_time_days)
                if departure_date in dates:
                    key = (route.origin_id, node, prod, departure_date, 'ambient')
                    if key in intransit_index:
                        arrivals += model.in_transit[key]

        # Departures (leaving today)
        departures = 0
        for route in routes:
            if route.origin_id == node:
                key = (node, route.destination_id, prod, t, 'ambient')
                if key in intransit_index:
                    departures += model.in_transit[key]

        # Demand consumption (if demand node)
        demand_consumption = 0
        if (node, prod, t) in demand_index:
            demand_consumption = model.demand_consumed[node, prod, t]

        return model.inventory[node, prod, t] == prev_inv + production_inflow + arrivals - departures - demand_consumption

    model.balance_con = Constraint(inv_index, rule=balance_rule)

    # Demand satisfaction
    def demand_rule(model, node, prod, t):
        if (node, prod, t) not in demand:
            return Constraint.Skip
        return model.demand_consumed[node, prod, t] + model.shortage[node, prod, t] == demand[node, prod, t]

    model.demand_con = Constraint(demand_index, rule=demand_rule)

    # Objective
    model.obj = Objective(
        expr=1.30 * quicksum(model.production[p,t] for (p,t) in prod_index) +
             0.10 * quicksum(model.in_transit[k] for k in intransit_index) +
             10.00 * quicksum(model.shortage[k] for k in demand_index),
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


def main():
    """Test critical levels with real data."""
    print("="*80)
    print("PERFORMANCE TEST: Find which level is slow with real data")
    print("="*80)

    data = load_real_data()

    # Test each level
    results = {}

    results['Level 4'] = test_level4_real(data)
    results['Level 13'] = test_level13_real(data)

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    for level, t in results.items():
        if t:
            status = "⚠️ SLOW" if t > 10 else "✓ FAST"
            print(f"{level:20s} {t:8.2f}s  {status}")


if __name__ == "__main__":
    main()
