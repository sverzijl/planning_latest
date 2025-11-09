#!/usr/bin/env python3
"""
MINIMAL PYOMO TEST: Prove the sliding window bug

This creates a 10-line Pyomo model that demonstrates the root cause:
Initial inventory counted as "inflow" in sliding window creates
overlapping constraints that prevent consumption.
"""

from pyomo.environ import *

model = ConcreteModel()

# Two days
model.days = Set(initialize=[1, 2])

# Decision variables
model.consumption = Var(model.days, within=NonNegativeReals)
model.shortage = Var(model.days, within=NonNegativeReals)

# Parameters
init_inv = 518  # Initial inventory from Oct 16
demand = {1: 300, 2: 300}  # Demand on each day

# Objective: Minimize shortage cost ($10/unit)
model.obj = Objective(
    expr=sum(10 * model.shortage[d] for d in model.days),
    sense=minimize
)

# Demand balance
def demand_balance_rule(model, d):
    return model.consumption[d] + model.shortage[d] == demand[d]
model.demand_balance = Constraint(model.days, rule=demand_balance_rule)

# Sliding window constraints (THIS IS THE BUG)
# Day 1: consumption[1] <= 518
model.window_day1 = Constraint(
    expr=model.consumption[1] <= init_inv
)

# Day 2: consumption[1] + consumption[2] <= 518
# This double-counts! The same 518 units are restricted twice.
model.window_day2 = Constraint(
    expr=model.consumption[1] + model.consumption[2] <= init_inv
)

# Solve
solver = SolverFactory('appsi_highs')
result = solver.solve(model)

print("="*80)
print("MINIMAL TEST: Sliding Window Bug with Initial Inventory")
print("="*80)
print(f"\nInitial inventory: {init_inv} units")
print(f"Demand: Day 1 = {demand[1]}, Day 2 = {demand[2]}")
print()

print("Constraints:")
print(f"  Day 1 window [1]:     consumption[1] <= {init_inv}")
print(f"  Day 2 window [1,2]:   consumption[1] + consumption[2] <= {init_inv}")
print()

consumption_day1 = value(model.consumption[1])
consumption_day2 = value(model.consumption[2])
shortage_day1 = value(model.shortage[1])
shortage_day2 = value(model.shortage[2])

print("Results:")
print(f"  Consumption Day 1: {consumption_day1:.0f}")
print(f"  Consumption Day 2: {consumption_day2:.0f}")
print(f"  Shortage Day 1: {shortage_day1:.0f}")
print(f"  Shortage Day 2: {shortage_day2:.0f}")
print()

total_shortage = shortage_day1 + shortage_day2
total_consumption = consumption_day1 + consumption_day2

if total_shortage > 0:
    print(f"❌ BUG CONFIRMED:")
    print(f"   Model takes {total_shortage:.0f} units shortages instead of consuming")
    print(f"   free inventory because Day 2 constraint limits total consumption")
    print(f"   to {init_inv} across BOTH days!")
    print()
    print("   The sliding window incorrectly treats init_inv as a 'flow'")
    print("   that can only be used once across the window, even though")
    print("   it's the SAME inventory available on both days.")
else:
    print("✓ No bug (consumption = demand)")

print()
print("="*80)
print("PROOF: Remove Day 2 constraint and re-solve...")
print("="*80)

# Remove the buggy constraint
model.del_component(model.window_day2)

# Re-solve
result2 = solver.solve(model)

consumption_day1_fixed = value(model.consumption[1])
consumption_day2_fixed = value(model.consumption[2])
shortage_day1_fixed = value(model.shortage[1])
shortage_day2_fixed = value(model.shortage[2])

print()
print("Results WITHOUT Day 2 constraint:")
print(f"  Consumption Day 1: {consumption_day1_fixed:.0f}")
print(f"  Consumption Day 2: {consumption_day2_fixed:.0f}")
print(f"  Shortage Day 1: {shortage_day1_fixed:.0f}")
print(f"  Shortage Day 2: {shortage_day2_fixed:.0f}")
print()

if shortage_day1_fixed + shortage_day2_fixed == 0:
    print("✅ PROOF COMPLETE: Without overlapping window constraint,")
    print("   model correctly consumes inventory instead of taking shortages!")
else:
    print("? Unexpected result")
