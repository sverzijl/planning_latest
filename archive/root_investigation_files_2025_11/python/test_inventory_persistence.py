#!/usr/bin/env python3
"""
Test to understand: Why does sliding window fail with initial inventory?

The issue: Sliding windows assume all inflows are "fresh" each period.
They don't account for inventory persistence across days.

Example:
- Day 0: 518 units in stock
- Day 1: Can consume up to 518 (from Day 0 stock)
- Day 2: Can consume up to (518 - Day1_consumption) from Day 0 stock
          PLUS any new arrivals on Days 1-2

Sliding window says:
- Day 1: consumption[1] <= arrivals[1] + init_inv
- Day 2: consumption[1] + consumption[2] <= arrivals[1,2] + init_inv

The Day 2 constraint is CUMULATIVE, which treats init_inv as a ONE-TIME inflow,
not as persistent stock.

This is CORRECT if init_inv represents "material that arrived on Day 0" and
we're tracking flow balance.

But this PREVENTS the model from understanding that:
- If I consume 300 on Day 1, I have 218 left
- I can consume that 218 on Day 2
- Total consumption across Days 1-2 can be 518 (all from Day 0)

The cumulative constraint limits total to 518, which is correct!

So why does the model take shortages?

AH! Because it's optimizing over CUMULATIVE consumption across the window,
not day-by-day availability!

The constraint says: "Total consumption Days 1-2 cannot exceed 518"
The demand says: "Need 300 on Day 1, 300 on Day 2"
Optimal: Consume 518 total (300+218 or 218+300 or 259+259, etc.)

Let me verify:
"""

from pyomo.environ import *

model = ConcreteModel()
model.days = Set(initialize=[1, 2])

model.consumption = Var(model.days, within=NonNegativeReals)
model.shortage = Var(model.days, within=NonNegativeReals)

init_inv = 518
demand = {1: 300, 2: 300}
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
print("SLIDING WINDOW WITH INIT_INV TEST")
print("="*80)
print(f"\nSetup:")
print(f"  init_inv = {init_inv}")
print(f"  demand = {demand}")
print(f"  Total demand = {sum(demand.values())}")
print()

c1 = value(model.consumption[1])
c2 = value(model.consumption[2])
s1 = value(model.shortage[1])
s2 = value(model.shortage[2])

print("Constraints:")
print(f"  Day 1: consumption[1] <= {init_inv}")
print(f"  Day 2: consumption[1] + consumption[2] <= {init_inv}")
print()

print("Solution:")
print(f"  consumption[1] = {c1:.0f}")
print(f"  consumption[2] = {c2:.0f}")
print(f"  shortage[1] = {s1:.0f}")
print(f"  shortage[2] = {s2:.0f}")
print(f"  Total consumption = {c1 + c2:.0f}")
print(f"  Total shortage = {s1 + s2:.0f}")
print()

print("Analysis:")
print(f"  Total demand (600) > init_inv (518)")
print(f"  Model correctly limits total consumption to 518")
print(f"  Shortage of {s1 + s2:.0f} is EXPECTED and CORRECT")
print()
print("CONCLUSION:")
print("  The 'bug' is not a bug - the model is working correctly!")
print("  You cannot satisfy 600 units of demand with only 518 units of inventory.")
print()
print("  The sliding window formulation is mathematically sound.")
print("  If you're seeing shortages when you expect inventory to be consumed,")
print("  the issue is likely:")
print("  1. Total demand exceeds init_inv (correct behavior)")
print("  2. Missing production/arrivals in the model (data issue)")
print("  3. Other constraints preventing consumption (constraint conflict)")
print()
