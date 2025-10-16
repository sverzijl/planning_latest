# Inventory-Based Truck Loading Analysis

## Problem Statement

The inventory-based truck loading model was inf feasible at presolve. The goal was to identify and fix the root cause of infeasibility in the inventory balance constraints.

## Root Cause Analysis

### Bug #1: Duplicate Handling of First-Day Morning Trucks (FIXED)

**Location:** `src/optimization/integrated_model.py`, lines 1243-1259 (original)

**Issue:** The code had two separate `if/elif` blocks that both handled the case where first-day morning trucks access inventory outside the planning horizon:

```python
# Block 1 (lines 1243-1248)
if inventory_access_date not in model.dates:
    first_date = min(model.dates)
    if date == first_date:
        truck_outflows += model.truck_load[...]

# Block 2 (lines 1252-1259) - DUPLICATE!
elif (inventory_access_date not in model.dates and
      date == min(model.dates) and
      truck.departure_type == 'morning'):
    truck_outflows += model.truck_load[...]
```

**Problem:** The second block was unreachable dead code because its condition was already caught by the first `if` statement. However, both blocks were attempting to subtract the same truck loads, which would have resulted in double-counting if the second block were reachable.

**Fix:** Removed the duplicate block (lines 1252-1259) and reorganized the logic to check the normal case first, then the special case:

```python
# Normal case: truck accesses inventory on a date in planning horizon
if inventory_access_date == date:
    truck_outflows += model.truck_load[truck_idx, dest, prod, delivery_date]
# Special case: First-day morning trucks access initial inventory (Day0)
elif inventory_access_date not in model.dates:
    first_date = min(model.dates)
    if date == first_date:
        truck_outflows += model.truck_load[truck_idx, dest, prod, delivery_date]
```

**Commit:** e6fe9d3

## Constraint Structure Analysis

### Inventory Balance Equation (Manufacturing Site)

**Mathematical Formulation:**
```
inventory[t] = inventory[t-1] + production[t] - truck_loads[t]
```

**Pyomo Implementation:**
```python
return model.inventory_ambient[loc, prod, date] == (
    prev_ambient + production_qty - truck_outflows
)
```

**LP Standard Form:**
```
inventory[t] - production[t] - truck_load1 - truck_load2 - ... = inventory[t-1]
```

For the first day with `inventory[t-1] = 10,000`:
```
inventory[2025-10-09] - production[2025-10-09] - truck_loads = 10000
```

### Verification

Created test script `/home/sverzijl/planning_latest/debug_inventory_constraints.py` to write the LP file and examine constraints.

**Before Fix:**
- Some constraints showed incorrect RHS (though this was an artifact of looking at the wrong constraint initially)
- Duplicate handling code existed but was unreachable

**After Fix:**
- LP constraints show correct signs:
  ```
  +1 inventory_ambient(_6122___168847__2025_10_09)
  -1 production(2025_10_09__168847_)
  -1 truck_load(...)  # All truck loads have negative coefficients
  = 10000.0  # Correct positive RHS
  ```

## Remaining Infeasibility

**Status:** Model is still infeasible after fixing the duplicate code bug.

**Likely Causes:**
1. **Truck inventory constraints** may be inconsistent with balance equations
2. **Demand satisfaction** may be impossible within the planning horizon
3. **Transit time handling** for trucks departing before planning horizon may have edge cases
4. **Initial inventory** may be insufficient for first-day morning truck loads

**Recommended Next Steps:**

1. **Relax demand constraints** - Set `allow_shortages=True` and check if model becomes feasible
2. **Check truck constraint consistency** - Verify that `truck_inventory_constraint_rule` (lines 1524-1576) correctly aligns with balance equations
3. **Examine first-day morning trucks** - Verify that trucks with `departure_date = Day1` and `inventory_access_date = Day0` are correctly:
   - Constrained by `initial_inventory` in `truck_inventory_constraint_rule` (lines 1551-1556)
   - Subtracted from Day1 balance in `inventory_balance_rule` (lines 1247-1252)
4. **Write IIS (Irreducible Infeasible Subset)** - Use Gurobi or CPLEX to identify the minimal set of conflicting constraints

## Files Modified

- `/home/sverzijl/planning_latest/src/optimization/integrated_model.py` (lines 1241-1252)

## Test Files Created

- `/home/sverzijl/planning_latest/debug_inventory_constraints.py` - Writes LP file and analyzes constraints
- `/home/sverzijl/planning_latest/test_pyomo_signs.py` - Tests Pyomo sign handling with simple examples
- `/home/sverzijl/planning_latest/test_pyomo_signs2.py` - Tests different ways of building Pyomo expressions
- `/home/sverzijl/planning_latest/test_pyomo_signs3.py` - Tests RHS constant handling
- `/home/sverzijl/planning_latest/test_exact_pyomo_bug.py` - Reproduces exact model scenario (verifies Pyomo is working correctly)
- `/home/sverzijl/planning_latest/test_pyomo_constant_param.py` - Tests Pyomo Param vs Python constant

## Conclusion

**Fixed:** Duplicate handling of first-day morning truck loads (dead code removal)

**Remaining Issue:** Model is still infeasible, but now with correct constraint formulation. Further investigation needed to identify the source of infeasibility (likely truck constraints, demand, or initial inventory insufficient for first-day loads).

**Key Insight:** The inventory balance equations are correctly formulated. The infeasibility is not due to sign errors or equation structure, but rather to conflicting constraint values or insufficient resources.
