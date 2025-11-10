# CRITICAL ISSUE: Zero Production in 4-Week Scenario

**Discovered:** November 9, 2025 (during cleanup verification)
**Severity:** HIGH - Model produces 0 units when demand is 338,051 units
**Status:** Needs investigation

---

## Issue Description

The reasonableness test revealed that SlidingWindowModel produces **ZERO production** for 4-week horizon scenarios.

### Test: test_4week_production_meets_demand

**Expected:**
- Total demand: 338,051 units
- Initial inventory: 30,823 units
- Expected production: 307,228 units

**Actual:**
- Actual production: **0 units** ❌

**Impact:** Model is completely broken for 4-week scenarios

---

## Context

**Where discovered:** `tests/test_solution_reasonableness.py::test_4week_production_meets_demand`

**Test configuration:**
```python
horizon_days = 28  # 4 weeks
solver = 'appsi_highs'
time_limit = 180s
mip_gap = 0.01
allow_shortages = True
use_pallet_tracking = True
```

**Model setup:**
- Start date: validated.planning_start_date
- End date: start + 27 days (28-day horizon)
- Initial inventory: 30,823 units (from inventory_latest.XLSX)
- Forecast: Gluten Free Forecast - Latest.xlsm

---

## What Works

**1-week scenario WORKS:**
- Total demand: 82,850 units
- Initial inventory: 30,823 units
- Actual production: 38,898 units ✅
- Fill rate: Good
- **Status:** PASSING after tolerance adjustment

**This proves:**
- SlidingWindowModel CAN solve problems
- Data loading works
- 1-week horizon works correctly

---

## What Doesn't Work

**4-week scenario BROKEN:**
- Production: 0 units ❌
- Same data source
- Same initial inventory
- Only difference: 28-day horizon vs 7-day

**Hypothesis:**
1. **Data issue:** Maybe demand data doesn't extend 4 weeks?
2. **Constraint issue:** Some constraint blocks all production for longer horizons?
3. **Solver issue:** Solver finds zero-production as "optimal"?
4. **Cost issue:** Production costs too high relative to shortage penalty?

---

## Evidence from Test Output

**Uninitialized variable warnings:**
```
No value for uninitialized VarData object pallet_count[Lineage,WONDER GFREE WHOLEM 500G,frozen,2025-11-16]
No value for uninitialized VarData object product_start['6122',HELGAS GFREE MIXED GRAIN 500G,2025-11-09]
No value for uninitialized VarData object inventory['6122',HELGAS GFREE MIXED GRAIN 500G,ambient,2025-12-07]
```

**These warnings suggest:**
- Many variables have no solution value
- Product_start = 0 (no production started)
- Inventory = 0 at many points
- Pallet_count = 0 (no storage used)

**This pattern is consistent with ZERO PRODUCTION scenario**

---

## Comparison: 1-Week vs 4-Week

| Aspect | 1-Week (WORKS) | 4-Week (BROKEN) |
|--------|----------------|-----------------|
| Demand | 82,850 units | 338,051 units |
| Init Inv | 30,823 units | 30,823 units |
| Horizon | 7 days | 28 days |
| Production | 38,898 units ✅ | **0 units** ❌ |
| Fill Rate | Good | Unknown (0 prod) |
| Test Result | PASSED | FAILED |

---

## Potential Root Causes

### 1. Infeasibility (Most Likely)

**Theory:** 4-week model is infeasible, solver returns zero solution

**Check:**
```python
print(result.termination_condition)
# If "infeasible" or "maxTimeLimit", this explains zero production
```

**Why might it be infeasible:**
- Shelf life constraints too restrictive for 28 days
- Truck capacity insufficient
- Labor calendar issues for extended horizon
- Initial inventory expiration timing

### 2. Cost Calibration Issue

**Theory:** Shortage penalty too low compared to production costs

**Check:**
```python
shortage_penalty = 10,000  # From CostParameters
production_cost = ??       # Need to verify
```

**If production cost > shortage penalty**, model prefers shortages over production

### 3. Data Loading Issue

**Theory:** Forecast data doesn't extend 28 days

**Check:**
```python
# In test, print:
print(f"Forecast entries: {len(forecast.entries)}")
print(f"Date range: {min(e.forecast_date)} to {max(e.forecast_date)}")
print(f"Horizon: {start} to {end}")
```

### 4. Model Extraction Issue

**Theory:** Model solved correctly but extraction returns zero

**Check:**
```python
# In extract_solution, verify production variables have values:
for v in model.production:
    if value(model.production[v]) > 0:
        print(f"Production: {v} = {value(model.production[v])}")
```

---

## Recommended Investigation

### Step 1: Check Solve Status

```python
# In build_and_solve_model, add after solve:
print(f"Solve status: {result.termination_condition}")
print(f"Is optimal: {result.is_optimal()}")
print(f"Is feasible: {result.is_feasible()}")
print(f"Objective: {result.objective_value}")
```

### Step 2: Check If Variables Have Values

```python
# After solve, check production variables:
from pyomo.environ import value
total_prod = sum(value(model_builder.model.production[key])
                 for key in model_builder.model.production
                 if value(model_builder.model.production[key]) > 0)
print(f"Total production from model: {total_prod}")
```

### Step 3: Compare to Working Integration Test

**Integration test works with 4-week:**
- `test_integration_ui_workflow.py` solves 4-week successfully
- Same data files
- Same SlidingWindowModel
- **Why does this test fail but integration test works?**

**Key difference to investigate:**
- Test configuration differences
- Data loading differences
- Horizon calculation differences

---

## Immediate Actions Needed

**1. Don't merge this state** - There's a real bug

**2. Investigate the zero production issue:**
- Add debug prints to build_and_solve_model
- Compare with working integration test
- Check solve status and objective

**3. Options:**
- **A)** Revert the reasonableness test fix commit (keep cleanup, investigate later)
- **B)** Debug the issue now (could be test setup, not model bug)
- **C)** Disable the failing tests temporarily (mark as xfail)

---

## My Recommendation

**This is likely a TEST SETUP ISSUE**, not a model bug, because:

1. ✅ Integration test with 4-week horizon WORKS
2. ✅ Same SlidingWindowModel
3. ✅ Same data files
4. ❌ Different test setup in reasonableness test

**Most likely cause:** The test's horizon calculation or data loading is wrong for 4-week.

**Next step:** Compare the working integration test setup with this test setup to find the difference.

---

**Status:** CRITICAL BUG OR TEST ISSUE - Needs immediate investigation before declaring cleanup complete
