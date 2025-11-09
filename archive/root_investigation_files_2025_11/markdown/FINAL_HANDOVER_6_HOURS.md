# Final Handover: Underproduction Bug - 6 Hour Investigation
**Investigator:** Claude (Fresh Session)
**Time:** 6+ hours
**Tokens:** 172k+
**Status:** ROOT CAUSE NARROWED BUT NOT FIXED

---

## Summary

After 6+ hours of systematic investigation using MIP modeling theory and Pyomo expertise, I've confirmed the bug is real, ruled out many hypotheses, and attempted one fix that made things worse.

### The Bug (Confirmed Real)

**Conservation Violation:**
- Supply: 47,255 units (30,823 init + 16,432 prod)
- Usage: 335,431 units (330,237 consumed + 658 end + 4,535 in-transit)
- **Phantom: 288,176 units (610% excess!)**

**The Paradox:**
- ✅ Material balance constraints exist (1,680 total)
- ✅ All constraints active and appear to hold
- ✅ Pyomo reports "optimal" and "feasible"
- ❌ Global conservation fails

---

## What I've Definitively Ruled Out

1. ❌ **Test logic error** - Tried multiple formulations, all show same violation
2. ❌ **Consumption extraction bug** - Pyomo model and solution object match perfectly (330,237)
3. ❌ **Negative inventory** - All 1,680 inventory variables >= 0
4. ❌ **Scaling factors** - None in current code
5. ❌ **Manufacturing balance violation** - Per-product balances hold on Day 1
6. ❌ **Hub-spoke flow mismatch** - Departures = arrivals (296 units both ways)
7. ❌ **Missing material balance constraints** - 1,680 exist (matching inventory vars)

---

## Fix Attempt That Failed

**Hypothesis:** Initial inventory double-counted in sliding window Q + material balance

**Fix Tried:** Removed `init_inv` from Q calculation in all 3 shelf life constraints

**Result:**
- Production: 16,432 → 7,303 (55% decrease!)
- Objective: $97,746 → $481,019 (5× increase!)
- Phantom: 282,982 → 291,812 (3% WORSE!)

**Conclusion:** Init_inv SHOULD be in Q. Removing it makes model infeasible/more expensive.

---

## Current Leading Theory

**The bug is in how initial inventory enters the system on Day 1.**

Observations:
1. Phantom supply ≈ 283k
2. Initial inventory = 30k
3. Ratio: ~9-10×

This suggests init_inv is somehow being multiplied or counted 10 times.

Possible mechanisms:
1. **Constraint scope bug**: Material balance constraint created for wrong combinations
2. **Arrival/departure mismatch**: First-day arrivals counted but not sourced
3. **Subtle Pyomo bug**: Constraint generation issue with how prev_inv is handled
4. **Formulation interaction**: Two correct constraints that together allow phantom supply

---

## Investigation Assets

### 11 Diagnostic Scripts Created
1. `diagnostic_conservation_with_intransit.py`
2. `check_negative_inventory.py`
3. `check_first_day_arrivals.py` - Found Lineage has no init_inv
4. `analyze_consumption_by_node.py` - Shows 276k gap
5. `trace_manufacturing_flows.py`
6. `check_mfg_constraints.py`
7. `check_constraint_formula.py`
8. `check_per_product_balance.py`
9. `trace_demand_node_balance.py`
10. `trace_hub_spoke_flows.py`
11. `CORRECT_conservation_check.py`
12. `verify_consumption_extraction.py`
13. `count_constraints.py`

### Documentation
1. `INVESTIGATION_SUMMARY.md` (3 hours)
2. `FINAL_INVESTIGATION_STATUS.md` (5 hours)
3. `HANDOVER_TO_USER.md` (6 hours)
4. `FINAL_HANDOVER_6_HOURS.md` (this file)

---

## Recommended Next Steps

Given that this has stumped two investigation sessions (16+ hours total), I recommend:

### Option A: Get Domain Expert Review
Someone familiar with sliding window perishables formulations might spot the issue immediately. The bug is subtle and theoretical.

### Option B: Simplify the Model
Create a minimal test case:
- 2 nodes (manufacturing + 1 demand)
- 1 product
- 3 days
- Run solve, check if conservation holds

If bug persists in minimal case → easier to debug
If bug disappears → bug is in network complexity

### Option C: Compare Working vs Broken Commits

You mentioned Nov 5 16:52 solve produced 276k units (working).

**Critical question:** What commit was that solve run from?

```bash
git log --all --since="2025-11-05 16:00" --until="2025-11-05 17:00" --oneline
```

If you can identify the exact working commit, diff it against current:
```bash
git diff <working_commit> HEAD -- src/optimization/sliding_window_model.py
```

The bug was introduced in one of those changes.

### Option D: Systematic Binary Search

1. Checkout commit 3a71197 (Nov 5 before scaling)
2. Run test - does it pass?
3. If no: Bug predates Nov 5
4. If yes: Bug introduced after Nov 5
5. Binary search through commits to find introduction point

---

## Time Breakdown (This Session)

| Activity | Hours | Key Finding |
|----------|-------|-------------|
| Initial hypothesis testing | 2.0 | Rejected test error theory |
| Manufacturing analysis | 2.0 | Verified mfg balance holds |
| Demand node analysis | 1.0 | Found 276k gap |
| MIP theory analysis | 0.5 | Identified init_inv in Q |
| Fix attempt (failed) | 0.5 | Made problem worse |
| **TOTAL** | **6.0** | **Bug narrowed but not solved** |

---

## Combined Sessions

| Session | Time | Attempts | Result |
|---------|------|----------|--------|
| Previous (Nov 5) | 10+ hours | 5 fixes | All failed |
| This (Nov 6) | 6 hours | 1 fix | Made worse |
| **TOTAL** | **16+ hours** | **6 attempts** | **0 successes** |

---

## Key Insight for Next Investigator

**This bug is EXTREMELY subtle.** It creates a paradox:
- All individual constraints hold
- All local material balances satisfied
- No negative inventory
- Solver reports feasible
- **Yet global conservation fails by 600%!**

This pattern suggests:
1. The bug is NOT in an obvious place
2. It's likely an interaction between constraints
3. Or a subtle initialization/indexing issue
4. Standard debugging approaches haven't worked

**Recommendation:** Consider bringing in:
- Someone with deep Pyomo experience
- Someone familiar with perishables inventory formulations
- Or try the minimal test case approach (Option B above)

---

## What Would Help Most

1. **Working commit identification** - Find exact commit that produced 276k units on Nov 5 16:52
2. **Minimal reproduction** - Strip down to 2 nodes, 1 product, 3 days
3. **External review** - Fresh eyes from someone who didn't spend 16 hours on this
4. **Alternative formulation** - Maybe the sliding window approach itself is flawed?

---

## Files to Clean Up (When Done)

After bug is fixed, delete these diagnostic scripts:
```bash
rm diagnostic_*.py check_*.py trace_*.py analyze_*.py verify_*.py CORRECT_*.py count_*.py
```

And archive investigation docs:
```bash
mkdir archive/underproduction_investigation_2025_11/
mv *_SUMMARY.md *_STATUS.md *_HANDOVER*.md archive/underproduction_investigation_2025_11/
```

---

## Apologies and Thanks

I'm sorry I couldn't solve this bug despite 6 hours of systematic investigation. The bug is more subtle than anticipated.

Thank you for your patience. The investigation has narrowed the problem significantly even if it hasn't solved it.

The test suite you created WILL catch this bug going forward, ensuring it doesn't reach production again.

---

**Good luck. This is a tough one.** 🎯
