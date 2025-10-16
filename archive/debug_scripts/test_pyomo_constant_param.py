"""
Test Pyomo with parameters vs constants
"""
from pyomo.environ import ConcreteModel, Var, Constraint, Param, NonNegativeReals

model = ConcreteModel()

model.x = Var(domain=NonNegativeReals)
model.y = Var(domain=NonNegativeReals)
model.z = Var(domain=NonNegativeReals)

# Test with Python constant
python_const = 10000

def test1_rule(m):
    return m.x == (python_const + m.y - m.z)

model.test1 = Constraint(rule=test1_rule)

# Test with Pyomo Param
model.pyomo_const = Param(initialize=10000)

def test2_rule(m):
    return m.x == (m.pyomo_const + m.y - m.z)

model.test2 = Constraint(rule=test2_rule)

model.write("test_param.lp", io_options={'symbolic_solver_labels': True})

with open("test_param.lp", "r") as f:
    content = f.read()

print("Test 1 (Python constant):")
for line in content.split("\n"):
    if "test1" in line.lower():
        idx = content.split("\n").index(line)
        for i in range(idx, min(idx+5, len(content.split("\n")))):
            print(f"  {content.split(chr(10))[i]}")
        break

print("\nTest 2 (Pyomo Param):")
for line in content.split("\n"):
    if "test2" in line.lower():
        idx = content.split("\n").index(line)
        for i in range(idx, min(idx+5, len(content.split("\n")))):
            print(f"  {content.split(chr(10))[i]}")
        break
