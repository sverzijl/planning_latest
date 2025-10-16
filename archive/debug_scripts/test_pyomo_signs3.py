"""
Test if Pyomo handles RHS constants correctly
"""
from pyomo.environ import ConcreteModel, Var, Constraint, NonNegativeReals

model = ConcreteModel()

model.x = Var(domain=NonNegativeReals)
model.y = Var(domain=NonNegativeReals)
model.z = Var(domain=NonNegativeReals)

# Test: x = 100 + y - z
# Expected LP form: x - y + z = 100
# We want: x = 100 + y - z
# Rearranging: x - y + z = 100

def test1_rule(m):
    # Method 1: RHS with constant first
    return m.x == (100 + m.y - m.z)

model.test1 = Constraint(rule=test1_rule)

def test2_rule(m):
    # Method 2: RHS with variables first
    return m.x == (m.y - m.z + 100)

model.test2 = Constraint(rule=test2_rule)

def test3_rule(m):
    # Method 3: LHS = RHS - move terms manually
    return m.x - m.y + m.z == 100

model.test3 = Constraint(rule=test3_rule)

model.write("test_signs3.lp", io_options={'symbolic_solver_labels': True})
print("✅ LP written\n")

# Parse and display
with open("test_signs3.lp", "r") as f:
    content = f.read()

for constraint_name in ["test1", "test2", "test3"]:
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if f"c_e_{constraint_name}_:" in line:
            print(f"\n{constraint_name}:")
            print(f"  Python: x == (100 + y - z)" if constraint_name == "test1" else
                  f"  Python: x == (y - z + 100)" if constraint_name == "test2" else
                  f"  Python: x - y + z == 100")
            print(f"  LP form:")
            for j in range(i, min(i+5, len(lines))):
                print(f"    {lines[j]}")
            break
