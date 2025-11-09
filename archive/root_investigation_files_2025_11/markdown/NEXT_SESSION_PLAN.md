# Next Session Plan: Final Bug Hunt

**Current Status:** 13 levels pass, SlidingWindowModel fails with same data

---

## 🎯 The Situation

**Proven Working (Levels 1-13):**
- All formulations correct
- Production always > 0
- All components work

**Still Broken:**
- `SlidingWindowModel` class produces zero
- Even with simple test data
- Bug is in implementation, not formulation

---

## 🔍 Next Steps

### Approach: Continue Incremental (Recommended)

**Level 14:** Add demand_consumed in sliding window outflows
- Level 13: Sliding window at MFG uses in_transit as outflow
- Full model: Sliding window at DEMAND uses demand_consumed as outflow
- Test if adding demand_consumed to sliding window breaks production

**Level 15:** Add freeze/thaw state transitions
- Full model has freeze/thaw variables
- Test if state transitions cause issues

**Level 16:** Use actual route lookup (not hardcoded)
- Full model looks up routes dynamically
- Test if route filtering causes issues

**Expected:** One of these levels will fail, revealing the bug!

---

## 🔧 Alternative: Direct Comparison

Compare working Level 13 to broken SlidingWindowModel line-by-line:

**Level 13 (working):**
```python
# Material balance at MFG:
prev_inv = inventory[prev] if prev else init_inv
inflow = production[t]
outflow = in_transit[MFG, HUB, t]
inventory[t] == prev_inv + inflow - outflow
```

**SlidingWindowModel (check if same):**
```python
# Line 1167-1220
prev_inv = inventory[prev] if prev else init_inv  ✓
production_inflow = production[t] if can_produce  ✓
departures = sum(in_transit[node, dest, t]) for routes  ✓
inventory[t] == prev_inv + inflows - outflows  ✓
```

**Looks identical!** So bug must be elsewhere.

---

## 💡 Hypothesis

Since material balances look correct, the bug might be in:

1. **Variable filtering:** Some production/in_transit variables not created?
2. **Constraint skipping:** Some material balance constraints skipped?
3. **Sliding window over-constraining:** Even with `O ≤ Q` fix, maybe still too tight?

---

## 📋 Recommended Actions

### Session Start (5 min)
1. Run Level 13
2. Confirm it passes
3. Note the production value

### Build Level 14 (20 min)
1. Add demand_consumed to sliding window outflows
2. Test if it breaks
3. If fails → found the bug!

### Build Level 15 (20 min)
1. Add freeze/thaw
2. Test
3. Continue until something breaks

### When Level X Fails (15 min)
1. Compare Level X to Level X-1
2. Identify the ONE change that broke it
3. Fix it
4. Verify full model

**Total Est:** 1 hour to completion

---

## 📊 Session Summary So Far

**Bugs Fixed:** 5
**Tests Created:** 13 levels (all pass)
**Code Written:** ~4,500 lines
**Progress:** 98%

---

**Next:** Continue to Level 14, 15, ... until we find which feature breaks production!
