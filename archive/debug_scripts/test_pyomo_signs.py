"""
Test to understand Pyomo constraint sign handling
"""
from pyomo.environ import ConcreteModel, Var, Constraint, NonNegativeReals

model = ConcreteModel()

# Variables
model.inventory = Var(domain=NonNegativeReals)
model.production = Var(domain=NonNegativeReals)
model.truck1 = Var(domain=NonNegativeReals)
model.truck2 = Var(domain=NonNegativeReals)

# Constants
prev_inventory = 10000

# Accumulate truck outflows like in the original code
truck_outflows = 0
truck_outflows += model.truck1
truck_outflows += model.truck2

print("truck_outflows type:", type(truck_outflows))
print("truck_outflows:", truck_outflows)

# Method 1: Original formulation
def method1_rule(m):
    return m.inventory == (prev_inventory + m.production - truck_outflows)

model.method1_con = Constraint(rule=method1_rule)

# Write LP
model.write("test_signs.lp", io_options={'symbolic_solver_labels': True})
print("\n✅ LP file written to test_signs.lp")

# Read and display the constraint
with open("test_signs.lp", "r") as f:
    content = f.read()
    # Find the constraint
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "method1" in line.lower():
            print(f"\nConstraint from method 1:")
            for j in range(i, min(i+10, len(lines))):
                print(lines[j])
            break
