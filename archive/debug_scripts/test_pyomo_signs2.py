"""
Test Pyomo handling of subtraction of LinearExpression
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

# Test 1: Accumulate with += (like current code)
truck_outflows_v1 = 0
truck_outflows_v1 += model.truck1
truck_outflows_v1 += model.truck2

def method1_rule(m):
    return m.inventory == (prev_inventory + m.production - truck_outflows_v1)

model.method1_con = Constraint(rule=method1_rule)

# Test 2: Build as list and sum
truck_list = [model.truck1, model.truck2]
truck_outflows_v2 = sum(truck_list)

def method2_rule(m):
    return m.inventory == (prev_inventory + m.production - truck_outflows_v2)

model.method2_con = Constraint(rule=method2_rule)

# Test 3: Inline subtraction
def method3_rule(m):
    return m.inventory == (prev_inventory + m.production - model.truck1 - model.truck2)

model.method3_con = Constraint(rule=method3_rule)

# Write LP
model.write("test_signs2.lp", io_options={'symbolic_solver_labels': True})
print("✅ LP file written to test_signs2.lp\n")

# Read and display the constraints
with open("test_signs2.lp", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "method" in line.lower():
        print(f"Line {i}: {line.strip()}")
        for j in range(i+1, min(i+6, len(lines))):
            if lines[j].strip().startswith("c_"):
                break
            print(f"Line {j}: {lines[j].strip()}")
        print()
