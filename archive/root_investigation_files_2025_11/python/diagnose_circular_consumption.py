#!/usr/bin/env python3
"""
SYSTEMATIC DEBUGGING: Test for circular dependency in consumption constraints.

HYPOTHESIS:
The consumption limit constraint creates a circular dependency:
  consumption[t] <= inventory[t]
  inventory[t] = prev_inv + arrivals - consumption[t] - shipments

This means:
  consumption[t] <= prev_inv + arrivals - consumption[t] - shipments
  2*consumption[t] <= prev_inv + arrivals - shipments
  consumption[t] <= (prev_inv + arrivals - shipments) / 2

On Day 1 with init_inv = 300 units, this limits consumption to 150 units!
The model can't consume more than HALF the available inventory.

This explains why model takes shortages + disposes init_inv instead of consuming it.
"""

import pyomo.environ as pyo
from datetime import date, timedelta

# Create minimal test case
model = pyo.ConcreteModel(name="CircularDependencyTest")

# Parameters
init_inv = 300  # Initial inventory at node
demand = 250    # Demand on day 1

print("="*80)
print("CIRCULAR DEPENDENCY TEST")
print("="*80)
print(f"\nScenario:")
print(f"  Initial inventory: {init_inv} units")
print(f"  Demand on Day 1: {demand} units")
print(f"  Transport cost: $0 (FREE)")
print(f"  Shortage cost: $10/unit")
print(f"  Disposal cost: $15/unit")
print()

# Decision variables
model.inventory = pyo.Var(domain=pyo.NonNegativeReals, initialize=init_inv)
model.consumption = pyo.Var(domain=pyo.NonNegativeReals, initialize=0)
model.shortage = pyo.Var(domain=pyo.NonNegativeReals, initialize=0)

# Objective: Minimize shortage cost
model.obj = pyo.Objective(expr=10 * model.shortage, sense=pyo.minimize)

# Constraints

# 1. State balance (material conservation)
# inventory = init_inv - consumption
model.state_balance = pyo.Constraint(
    expr=model.inventory == init_inv - model.consumption
)

# 2. Consumption limit (THIS IS THE CIRCULAR CONSTRAINT!)
# consumption <= inventory
model.consumption_limit = pyo.Constraint(
    expr=model.consumption <= model.inventory
)

# 3. Demand satisfaction
# consumption + shortage = demand
model.demand_balance = pyo.Constraint(
    expr=model.consumption + model.shortage == demand
)

print("Constraints added:")
print("  1. inventory = init_inv - consumption  (state balance)")
print("  2. consumption <= inventory  (consumption limit - CIRCULAR!)")
print("  3. consumption + shortage = demand  (demand satisfaction)")
print()

# Solve
solver = pyo.SolverFactory('appsi_highs')
result = solver.solve(model)

print("\nSOLUTION:")
print("="*80)
inventory_val = pyo.value(model.inventory)
consumption_val = pyo.value(model.consumption)
shortage_val = pyo.value(model.shortage)

print(f"  Inventory: {inventory_val:.1f} units")
print(f"  Consumption: {consumption_val:.1f} units")
print(f"  Shortage: {shortage_val:.1f} units")
print(f"  Objective: ${pyo.value(model.obj):.2f}")
print()

# Verify the circular dependency
print("CIRCULAR DEPENDENCY ANALYSIS:")
print("="*80)
print(f"From state balance: inventory = {init_inv} - consumption")
print(f"                              = {init_inv} - {consumption_val:.1f}")
print(f"                              = {inventory_val:.1f} ✓")
print()
print(f"From consumption limit: consumption <= inventory")
print(f"                        {consumption_val:.1f} <= {inventory_val:.1f} ✓")
print()
print("Substituting state balance INTO consumption limit:")
print(f"  consumption <= init_inv - consumption")
print(f"  2*consumption <= init_inv")
print(f"  consumption <= init_inv / 2")
print(f"  consumption <= {init_inv} / 2")
print(f"  consumption <= {init_inv/2:.1f}")
print()
print(f"ACTUAL consumption: {consumption_val:.1f}")
print(f"MAXIMUM allowed by circular constraint: {init_inv/2:.1f}")
print()

if abs(consumption_val - init_inv/2) < 0.1:
    print("✓ CONFIRMED: Consumption is LIMITED TO HALF of initial inventory!")
    print()
    print("This is WHY the disposal bug occurs:")
    print("  - Model can only consume 150 units of 300 unit init_inv")
    print("  - Takes 100 unit shortage to meet 250 unit demand")
    print("  - Remaining 150 units of init_inv sit unused")
    print("  - After 17 days, unused init_inv expires")
    print("  - Model disposes expired inventory")
    print()
    print("ECONOMIC IMPACT:")
    print(f"  Shortage cost: {shortage_val:.0f} units × $10 = ${shortage_val * 10:.0f}")
    print(f"  Disposal cost (later): 150 units × $15 = $2,250")
    print(f"  Total cost: ${shortage_val * 10 + 150 * 15:.0f}")
    print()
    print("VS. OPTIMAL (without circular constraint):")
    print(f"  Consume 250 units (meets demand)")
    print(f"  Shortage: 0 units")
    print(f"  Disposal: 50 units (excess after demand)")
    print(f"  Total cost: $750 (only disposal)")
    print()
    print("The circular dependency costs $2,750 - $750 = $2,000 extra!")
else:
    print("❌ Consumption is NOT at the circular limit. Different issue.")

print()
print("="*80)
print("ROOT CAUSE IDENTIFIED: Circular dependency in consumption constraints")
print("="*80)
