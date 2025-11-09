#!/usr/bin/env python3
"""
Test the FIX for circular dependency.

FIX: Change consumption limit from:
  consumption[t] <= inventory[t]  (CIRCULAR!)

To:
  consumption[t] <= prev_inv + arrivals - shipments  (CORRECT!)

This breaks the circular dependency by bounding consumption against INFLOWS
rather than the inventory variable itself.
"""

import pyomo.environ as pyo

# Create minimal test case
model = pyo.ConcreteModel(name="FixedConsumptionTest")

# Parameters
init_inv = 300  # Initial inventory at node
demand = 250    # Demand on day 1

print("="*80)
print("FIXED CONSUMPTION CONSTRAINT TEST")
print("="*80)
print(f"\nScenario:")
print(f"  Initial inventory: {init_inv} units")
print(f"  Demand on Day 1: {demand} units")
print()

# Decision variables
model.inventory = pyo.Var(domain=pyo.NonNegativeReals, initialize=init_inv)
model.consumption = pyo.Var(domain=pyo.NonNegativeReals, initialize=0)
model.shortage = pyo.Var(domain=pyo.NonNegativeReals, initialize=0)

# Objective: Minimize shortage cost
model.obj = pyo.Objective(expr=10 * model.shortage, sense=pyo.minimize)

# Constraints

# 1. State balance (material conservation)
model.state_balance = pyo.Constraint(
    expr=model.inventory == init_inv - model.consumption
)

# 2. FIXED consumption limit - bound against INFLOWS, not inventory variable!
# consumption <= prev_inv + arrivals - shipments
# For day 1: consumption <= init_inv (no arrivals, no shipments)
model.consumption_limit = pyo.Constraint(
    expr=model.consumption <= init_inv  # Bound against INFLOW, not inventory[t]!
)

# 3. Demand satisfaction
model.demand_balance = pyo.Constraint(
    expr=model.consumption + model.shortage == demand
)

print("Fixed constraints:")
print("  1. inventory = init_inv - consumption  (state balance)")
print("  2. consumption <= init_inv  (FIXED - no circular dependency!)")
print("  3. consumption + shortage = demand  (demand satisfaction)")
print()

# Solve
solver = pyo.SolverFactory('appsi_highs')
result = solver.solve(model)

print("\nSOLUTION WITH FIX:")
print("="*80)
inventory_val = pyo.value(model.inventory)
consumption_val = pyo.value(model.consumption)
shortage_val = pyo.value(model.shortage)

print(f"  Inventory: {inventory_val:.1f} units")
print(f"  Consumption: {consumption_val:.1f} units")
print(f"  Shortage: {shortage_val:.1f} units")
print(f"  Objective: ${pyo.value(model.obj):.2f}")
print()

if abs(consumption_val - demand) < 0.1 and abs(shortage_val) < 0.1:
    print("✅ SUCCESS! Model can now consume ALL available inventory!")
    print()
    print("  - Consumption: 250 units (meets full demand)")
    print("  - Shortage: 0 units")
    print("  - Remaining inventory: 50 units")
    print("  - Cost: $0 (no shortages!)")
    print()
    print("VS. BROKEN VERSION (circular dependency):")
    print("  - Consumption: 150 units (limited to 50%)")
    print("  - Shortage: 100 units")
    print("  - Cost: $1,000")
    print()
    print("✅ FIX ELIMINATES THE DISPOSAL BUG!")
else:
    print(f"❌ Fix didn't work as expected")
    print(f"   Expected: consumption=250, shortage=0")
    print(f"   Got: consumption={consumption_val:.1f}, shortage={shortage_val:.1f}")
