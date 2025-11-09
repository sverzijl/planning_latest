#!/usr/bin/env python3
"""
Critical test: What if demand EQUALS init_inv?

This should show zero shortages if the formulation is correct.
"""

from pyomo.environ import *

model = ConcreteModel()
model.days = Set(initialize=[1, 2])

model.consumption = Var(model.days, within=NonNegativeReals)
model.shortage = Var(model.days, within=NonNegativeReals)

init_inv = 518
demand = {1: 300, 2: 218}  # Total = 518 (exactly init_inv)
shortage_cost = 10

model.obj = Objective(
    expr=sum(shortage_cost * model.shortage[d] for d in model.days),
    sense=minimize
)

def demand_balance_rule(model, d):
    return model.consumption[d] + model.shortage[d] == demand[d]
model.demand_balance = Constraint(model.days, rule=demand_balance_rule)

# Sliding window constraints
model.window_day1 = Constraint(expr=model.consumption[1] <= init_inv)
model.window_day2 = Constraint(expr=model.consumption[1] + model.consumption[2] <= init_inv)

solver = SolverFactory('appsi_highs')
result = solver.solve(model)

print("="*80)
print("TEST: Demand EQUALS init_inv")
print("="*80)
print(f"\nSetup:")
print(f"  init_inv = {init_inv}")
print(f"  demand[1] = {demand[1]}")
print(f"  demand[2] = {demand[2]}")
print(f"  Total demand = {sum(demand.values())}")
print()

c1 = value(model.consumption[1])
c2 = value(model.consumption[2])
s1 = value(model.shortage[1])
s2 = value(model.shortage[2])

print("Solution:")
print(f"  consumption[1] = {c1:.0f}")
print(f"  consumption[2] = {c2:.0f}")
print(f"  shortage[1] = {s1:.0f}")
print(f"  shortage[2] = {s2:.0f}")
print(f"  Total consumption = {c1 + c2:.0f}")
print(f"  Total shortage = {s1 + s2:.0f}")
print()

if s1 + s2 == 0:
    print("✅ CORRECT: Zero shortages when total demand = init_inv")
    print("   The sliding window formulation works as expected!")
else:
    print(f"❌ BUG: Model has {s1+s2:.0f} shortage even though demand = init_inv")
    print("   This would indicate a formulation error.")

print()
