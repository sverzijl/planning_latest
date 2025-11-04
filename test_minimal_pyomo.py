#!/usr/bin/env python3
"""Ultra-minimal Pyomo test: verify production → inventory linkage works."""

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

print("="*80)
print("MINIMAL PYOMO TEST: Production → Inventory Linkage")
print("="*80)

# Create minimal model
m = pyo.ConcreteModel()

# Variables
m.production = pyo.Var(domain=pyo.NonNegativeReals)
m.inventory = pyo.Var(domain=pyo.NonNegativeReals)
m.shipment = pyo.Var(domain=pyo.NonNegativeReals)
m.shortage = pyo.Var(domain=pyo.NonNegativeReals)

# Material balance: inventory = production - shipment
m.balance = pyo.Constraint(expr=m.inventory == m.production - m.shipment)

# Demand satisfaction: shipment + shortage = 1000
demand = 1000
m.demand_con = pyo.Constraint(expr=m.shipment + m.shortage == demand)

# Objective: minimize production cost + shortage penalty
production_cost = 1.30
shortage_penalty = 10.0
m.obj = pyo.Objective(
    expr=production_cost * m.production + shortage_penalty * m.shortage,
    sense=pyo.minimize
)

print(f"\nModel structure:")
print(f"  Variables: production, inventory, shipment, shortage")
print(f"  Constraints:")
print(f"    balance: inventory = production - shipment")
print(f"    demand: shipment + shortage = {demand}")
print(f"  Objective: {production_cost} × production + {shortage_penalty} × shortage")

print(f"\nExpected optimal solution:")
print(f"  production = {demand} (produce to meet demand)")
print(f"  shipment = {demand}")
print(f"  shortage = 0")
print(f"  inventory = 0")
print(f"  Cost = ${demand * production_cost:.2f}")

# Solve
solver = Highs()
solver.config.load_solution = False
results = solver.solve(m)

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
if results.termination_condition == AppsiTC.optimal:
    solver.load_vars()

    print(f"\nActual solution:")
    print(f"  production = {pyo.value(m.production):.2f}")
    print(f"  shipment = {pyo.value(m.shipment):.2f}")
    print(f"  shortage = {pyo.value(m.shortage):.2f}")
    print(f"  inventory = {pyo.value(m.inventory):.2f}")
    print(f"  Objective = ${pyo.value(m.obj):.2f}")

    if pyo.value(m.production) > 900:
        print(f"\n  ✓ PASS: Basic Pyomo linkage works correctly")
        print(f"  → Problem is in SlidingWindowModel-specific logic")
    else:
        print(f"\n  ✗ FAIL: Even minimal Pyomo model doesn't produce!")
        print(f"  → Fundamental Pyomo/solver issue")
else:
    print(f"\n  ✗ FAIL: {results.termination_condition}")

print("="*80)
