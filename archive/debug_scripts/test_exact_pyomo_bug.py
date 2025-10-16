"""
Reproduce the exact Pyomo bug from the model
"""
from pyomo.environ import ConcreteModel, Var, Constraint, NonNegativeReals
from datetime import date

model = ConcreteModel()

# Simulate dates and products
dates = [date(2025, 10, 9), date(2025, 10, 10)]
products = ['168846', '168847']

model.dates = dates
model.products = products

# Variables
model.inventory = Var([(loc, prod, d) for loc in ['6122'] for prod in products for d in dates],
                     domain=NonNegativeReals)
model.production = Var([(d, prod) for d in dates for prod in products],
                       domain=NonNegativeReals)
model.truck_load = Var([('truck1', prod, d) for prod in products for d in dates],
                        domain=NonNegativeReals)

# Initial inventory
initial_inventory = {}
for prod in products:
    initial_inventory[('6122', prod, 'ambient')] = 10000.0

# Build constraint like in real model
def inventory_balance_rule(model, loc, prod, current_date):
    if loc != '6122':
        return Constraint.Skip

    production_qty = model.production[current_date, prod]

    # Accumulate truck outflows
    truck_outflows = 0
    for d in dates:
        if d == current_date:  # Simplified: truck accesses same day inventory
            truck_outflows += model.truck_load['truck1', prod, d]

    # Previous inventory
    if current_date == min(dates):
        prev_ambient = initial_inventory.get((loc, prod, 'ambient'), 0)
        print(f"Building constraint for first date {current_date}, prod={prod}")
        print(f"  prev_ambient = {prev_ambient}")
        print(f"  RHS will be: {prev_ambient} + production - truck_outflows")
    else:
        prev_date = dates[dates.index(current_date) - 1]
        prev_ambient = model.inventory[loc, prod, prev_date]

    return model.inventory[loc, prod, current_date] == (
        prev_ambient + production_qty - truck_outflows
    )

model.inventory_balance = Constraint(
    [('6122', prod, d) for prod in products for d in dates],
    rule=inventory_balance_rule
)

# Write LP
model.write("test_exact_bug.lp", io_options={'symbolic_solver_labels': True})
print("\n✅ LP written to test_exact_bug.lp\n")

# Check first constraint
with open("test_exact_bug.lp", "r") as f:
    content = f.read()

lines = content.split("\n")
for i, line in enumerate(lines):
    if "inventory_balance" in line and "6122" in line and products[0] in line and "2025_10_09" in line:
        print(f"Constraint for 6122, {products[0]}, 2025-10-09:")
        for j in range(i, min(i+10, len(lines))):
            print(f"  {lines[j]}")
            if lines[j].startswith("="):
                break
        break
