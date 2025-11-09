# Zero Production Bug - Complete Diagnosis & Fix Plan

**Date:** 2025-11-03
**Status:** 4 bugs fixed, incremental tests 1-5 pass, full model still has issue

---

## ✅ What We Fixed

### Bug 1: Disposal Pathway ✅
- Only allows disposal when inventory expires
- Prevents disposing fresh inventory

### Bug 2: Initial Inventory Multi-Counting ✅
- Init_inv only added when window includes Day 1
- Was being counted 16× times!

### Bug 3: Sliding Window Formulation ✅ **CRITICAL!**
- **OLD (WRONG):** `inventory[t] <= Q - O` → INFEASIBLE
- **NEW (CORRECT):** `O <= Q` → Works perfectly
- This was the ROOT CAUSE of infeasibility!

### Bug 4: Product ID Mismatch ✅
- Automatic alias resolution
- All 49,581 units of inventory now mapped

---

## 📊 Incremental Test Results - The Smoking Gun

| Level | Components | Status | Production | Shortage |
|-------|-----------|--------|------------|----------|
| 1 | Basic production-demand | ✅ PASS | 450 | 0 |
| 2 | + Material balance | ✅ PASS | 450 | 0 |
| 3 | + Initial inventory | ✅ PASS | 350 | 0 |
| 4 | + Sliding window | ✅ PASS | 300 | 0 |
| 5 | + Multi-node + Transport | ✅ PASS | 350 | 0 |
| **Full** | + Mix + Trucks + Pallets + Labor | ❌ FAIL | **0** | **346,687** |

**Conclusion:** Levels 1-5 all work perfectly. Bug is in features added in full model.

---

## 🔍 Differences: Level 5 vs Full Model

**Level 5 has:**
- ✅ Multi-node network (3 nodes)
- ✅ Transport with transit time
- ✅ Material balance at each node
- ✅ Sliding window constraints
- ✅ Initial inventory
- ✅ Demand satisfaction

**Full model ADDS:**
1. **Mix-based production:** `production = mix_count × units_per_mix`
2. **Truck schedules:** Specific departure times/days
3. **Pallet tracking:** Integer pallet variables
4. **Multiple products:** 5 products instead of 1
5. **Labor calendar:** Fixed hours, overtime, weekends
6. **Changeover tracking:** Product start variables

**One of these 6 features is blocking production!**

---

## 🎯 Most Likely Culprits

### #1: Mix-Based Production (PRIME SUSPECT)

**How it works:**
```python
production[node, prod, t] = mix_count[node, prod, t] × units_per_mix
```

**Potential bug:**
- If `mix_count` is somehow forced to zero
- Or if the constraint is written backwards
- Or if `units_per_mix` is zero/missing

**Test:** Check if mix_count variables have non-zero values in solution

### #2: Labor Calendar Constraints

**Potential bug:**
- If labor hours available = 0 (all days marked as holidays?)
- If production time calculation is wrong
- If labor constraints too tight

**Test:** Check if any labor hours are available

### #3: Truck Capacity Constraints

**Potential bug:**
- If no truck capacity available on any day
- If truck schedules prevent any shipments
- If pallet constraints too restrictive

---

## 🔧 Diagnostic Plan

### Step 1: Check Mix-Based Production

```python
# Add to extract_solution():
if hasattr(model, 'mix_count'):
    print(f"DEBUG: mix_count variables: {len(model.mix_count)}")
    non_zero_mixes = sum(1 for key in model.mix_count if value(model.mix_count[key]) > 0.01)
    print(f"DEBUG: Non-zero mix_count: {non_zero_mixes}")

    if non_zero_mixes == 0:
        print(f"ERROR: All mix_count variables are ZERO!")
        print(f"  This explains zero production if production = mix_count × units_per_mix")
```

### Step 2: Build Level 6 - Add Mix-Based Production Only

Test just adding mix-based production to Level 5:
- Keep multi-node working model
- Add: `production = mix_count × units_per_mix`
- See if production becomes zero

### Step 3: Check Mix Constraint Formulation

Look at how mix_production_con is formulated:
```python
# Expected:
production[node, prod, t] == mix_count[node, prod, t] * units_per_mix

# Potential bug if backwards:
mix_count[node, prod, t] == production[node, prod, t] / units_per_mix  # Division!
```

---

## 📋 Next Actions (Priority Order)

### Immediate (15 min)

1. **Add diagnostic to full model solve:**
   ```python
   # After solve, check mix_count values
   if hasattr(model.model, 'mix_count'):
       for key in list(model.model.mix_count.keys())[:10]:
           val = value(model.model.mix_count[key])
           print(f"mix_count{key} = {val}")
   ```

2. **Check mix_production_con formulation**
   - File: `src/optimization/sliding_window_model.py`
   - Search for: `mix_production_con` or `mix_count.*production`
   - Verify: `production == mix_count × units_per_mix` (not reversed!)

### Short Term (1 hour)

3. **Build Level 6:** Add mix-based production to working Level 5
4. **If Level 6 fails:** Bug is in mix formulation
5. **If Level 6 passes:** Bug is in trucks/pallets/labor

---

## 💡 Hypothesis

**Most Likely:** The mix-based production constraint is formulated incorrectly.

**Why:**
- All simpler levels work (production flows correctly)
- Full model has production variables but they're all zero
- Mix-based production is the main difference

**Expected bug pattern:**
```python
# WRONG (if found):
mix_count[n, p, t] * units_per_mix == production[n, p, t]
# Looks correct but...

# Or maybe:
production[n, p, t] = 0  # Somehow forced to zero
```

**Or:**
```python
# The constraint might not exist at all!
# Production variables created but never linked to mix_count
```

---

## 🏆 What We've Proven

**Incremental testing works:**
- Isolated 3 bugs (disposal, multi-counting, sliding window)
- Fixed them surgically
- Verified fixes work (Levels 1-5 all pass)

**Core model is sound:**
- Material balance: ✅ Correct
- Sliding window: ✅ Fixed and working
- Multi-node transport: ✅ Works perfectly
- Initial inventory: ✅ Handled correctly

**One feature breaks it:**
- Something in {mix, trucks, pallets, labor, multiple products, changeover}
- Most likely: Mix-based production

---

## 🚀 Estimated Time to Complete

- **Check mix_count diagnostics:** 5 min
- **Build Level 6 (add mix):** 20 min
- **Identify bug:** 10 min
- **Fix bug:** 15 min
- **Verify full model:** 10 min

**Total:** ~1 hour to complete fix

---

##  Files to Check Next

1. `src/optimization/sliding_window_model.py` - Search for `mix_production_con`
2. Look for how `production` and `mix_count` are linked
3. Check if constraint exists and is correct direction

---

**Summary:** We're 90% there! Levels 1-5 prove the core is sound. One more level will nail the final bug.
