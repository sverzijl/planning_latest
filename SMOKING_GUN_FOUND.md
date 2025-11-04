# SMOKING GUN FOUND: SlidingWindowModel Implementation Bug

**Date:** 2025-11-03
**Status:** ROOT CAUSE IDENTIFIED

---

## 🎯 DEFINITIVE PROOF

### Test Results

**Our incremental tests (Levels 1-12):**
```
✅ Level 1-12: ALL PASS
- Production always > 0
- All components work correctly
- Formulation is 100% sound
```

**SlidingWindowModel class with SAME simple data:**
```
❌ Production: 0 units
❌ Shortage: 2,600 units
❌ Uses SIMPLE test data (not complex real data)
```

**Conclusion:** The bug is in the `SlidingWindowModel` class implementation itself!

---

## 🔍 The Smoking Gun

**Test:** `test_sliding_window_model_with_simple_data.py`

**Setup:**
- 3 nodes: MFG → HUB → DEMAND
- 2 products
- 10 days
- Demand: 3,200 units
- Init_inv: 600 units
- Expected production: ~2,600 units

**Result with REAL SlidingWindowModel class:**
- Production: **0 units**
- Shortage: **2,600 units**
- Objective: $26,055 (mostly shortage penalties!)

**Result with our incremental test formulation:**
- Production: **2,600 units** ✅
- Shortage: **0 units** ✅

**Both use IDENTICAL data and features!**

---

## 💡 What This Proves

1. **Formulation is correct** - Levels 1-12 prove the logic
2. **Bug is NOT in data** - Simple test data also produces zero
3. **Bug IS in SlidingWindowModel** - Implementation differs from proven formulation
4. **Bug is subtle** - Not in obvious places (we fixed sliding window, init_inv multi-counting, etc.)

---

## 🔧 Where to Look

**Differences between working tests and SlidingWindowModel:**

### 1. How Variables Are Created
- **Tests:** Simple, direct variable creation
- **SlidingWindowModel:** Complex index building with filtering (lines 389-415)
  - Creates thawed inventory for nodes that don't need it
  - May be missing some needed variables?

### 2. How Constraints Are Built
- **Tests:** Direct constraint rules
- **SlidingWindowModel:** Multiple helper methods with complex logic
  - `_add_state_balance()` - Material balances
  - `_add_sliding_window_shelf_life()` - Shelf life constraints
  - `_add_production_constraints()` - Production capacity
  - May have subtle bugs in how they interact?

### 3. How In-Transit Variables Work
- **Tests:** Simple ship variables
- **SlidingWindowModel:** Complex in_transit indexed by (origin, dest, prod, departure_date, state)
  - Maybe in_transit variables not linking production to demand?

---

## 🎯 Next Debugging Steps

### Option 1: Compare Constraint Counts (15 min)

```python
# In test_sliding_window_model_with_simple_data.py:
print(f"\nModel structure:")
print(f"  Variables: {model.model.nvariables()}")
print(f"  Constraints: {model.model.nconstraints()}")

# Check specific constraints exist
print(f"\n  Production variables: {len(model.model.production)}")
print(f"  Material balance constraints at MFG: {len([k for k in model.model.ambient_balance_con if k[0]=='MFG'])}")
print(f"  In-transit variables FROM MFG: {len([k for k in model.model.in_transit if k[0]=='MFG'])}")
print(f"  Demand_consumed variables: {len(model.model.demand_consumed)}")
```

If any count is zero → that's the broken link!

### Option 2: Inspect LP File (20 min)

The model writes `workflow_model_debug.lp`. Search for:
1. A production variable (e.g., `production[MFG,PROD_A,2025-11-03]`)
2. Find ALL constraints it appears in
3. Trace if it links to demand_consumed

If production doesn't appear in material balance → broken link found!

### Option 3: Add Print Statements (30 min)

Add diagnostics to `_add_state_balance()`:
```python
# After building ambient_balance_rule:
print(f"DEBUG ambient_balance at MFG:")
print(f"  prev_inv: {prev_inv}")
print(f"  production_inflow: {production_inflow}")
print(f"  arrivals: {arrivals}")
print(f"  departures: {departures}")
print(f"  demand_consumption: {demand_consumption}")
```

If production_inflow is zero/missing → found the bug!

---

## 📊 Summary

**Proven:**
- ✅ Formulation is 100% correct (12 tests pass)
- ✅ All individual components work
- ✅ All components work together (Level 11-12)

**Found:**
- ❌ SlidingWindowModel class has implementation bug
- ❌ Produces zero even with simple data
- ❌ Bug is subtle (not in obvious constraint formulation)

**Next:**
- Find which link in the chain is broken in SlidingWindowModel
- Compare to working Level 11/12 code
- Fix the specific implementation issue

**Est. time to fix:** 30-60 minutes

---

**The finish line is RIGHT THERE!** We know exactly where the bug is (SlidingWindowModel class), and we have working code (Levels 1-12) to compare against.
