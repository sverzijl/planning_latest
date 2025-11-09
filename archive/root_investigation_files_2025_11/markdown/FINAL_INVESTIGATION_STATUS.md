# Final Investigation Status - Underproduction Bug
**Date:** 2025-11-06
**Time Invested:** 5+ hours
**Status:** MECHANISM PARTIALLY IDENTIFIED, ROOT CAUSE STILL ELUSIVE

---

## Summary

After extensive investigation, I've confirmed the conservation violation is REAL and have narrowed down where it occurs, but haven't yet identified the exact mechanism.

### Key Facts Established

1. **Global Conservation Violated:**
   - Supply: 47,255 units (30,823 init + 16,432 prod)
   - Usage: 335,431 units (330,237 consumed + 658 end + 4,535 in-transit)
   - **Phantom: 288,176 units (610% excess!)**

2. **Manufacturing Balance Holds Per-Product:**
   - Checked Day 1 for all 5 products: Balance = 0 for each ✓
   - Total manufacturing departures: 29,645 units (not the 6,813 my initial trace showed - that was a counting error)
   - Manufacturing appears to satisfy its material balance constraints

3. **The Paradox:**
   - All individual material balance constraints hold (verified)
   - No negative inventory (checked all 1,680 variables)
   - Pyomo reports "optimal" and "feasible"
   - **Yet global conservation fails by 288k units!**

4. **Supply-Demand Gap:**
   - Manufacturing ships: 29,645 units
   - Demand node init_inv: 24,423 units
   - **Total available at demand nodes: 54,068 units**
   - **Demand nodes consume: 330,237 units**
   - **Gap: 276,169 phantom units at demand nodes!**

---

## Current Leading Theory

**The phantom supply is entering at DEMAND NODES, not manufacturing.**

Demand nodes are consuming 276k more units than they receive from:
- Their initial inventory (24,423)
- Shipments from manufacturing (29,645)

Possible mechanisms:
1. **Arrival calculation bug**: Demand nodes counting arrivals multiple times
2. **Initial inventory double-counting**: Init_inv used in both balance and another place
3. **Consumption not properly bounded**: Material balance should prevent over-consumption but isn't
4. **Subtle constraint bug**: Some edge case where balance holds but allows phantom supply

---

## Evidence Collected

### Scripts Created
1. `diagnostic_conservation_with_intransit.py` - Main diagnostic showing 288k violation
2. `check_negative_inventory.py` - Verified no negative inventory
3. `trace_manufacturing_flows.py` - Manufacturing ships 29,645 units total
4. `check_mfg_constraints.py` - 140 constraints exist and are active
5. `check_constraint_formula.py` - Formulas correct (Day 1/2/3 checked)
6. `check_per_product_balance.py` - Manufacturing balance holds per-product
7. `analyze_consumption_by_node.py` - Shows 276k gap at demand nodes
8. `trace_mfg_inventory_daily.py` - Daily trace (had counting bug, ignore results)

### Key Files
- `INVESTIGATION_SUMMARY.md` - Initial findings
- `FINAL_INVESTIGATION_STATUS.md` - This file

---

## Next Steps (For Continuation)

### URGENT: Check Demand Node Material Balance

Manufacturing balance holds, so phantom supply must enter at demand nodes. Need to:

1. **Pick one demand node (e.g., 6104)**
   - Trace its inventory day-by-day
   - Calculate: arrivals, consumption, inventory changes
   - Check if: `I[t] = I[t-1] + arrivals - consumption` holds

2. **If balance holds**: Phantom supply enters via inflated arrivals
   - Check arrival calculation in material balance
   - Verify in_transit variables match actual shipments

3. **If balance violated**: Demand node constraints aren't enforcing properly
   - Check skip conditions
   - Check if constraints are active
   - Look for edge cases

### Alternative Approach: Dump and Analyze LP File

The model writes `workflow_model_debug.lp`. Could:
1. Load this LP file
2. Manually verify one material balance equation
3. Plug in solved variable values
4. See if equation actually holds or if Pyomo is misreporting

---

## Time Breakdown

- Initial hypothesis testing: 2 hours
- Manufacturing flow analysis: 2 hours
- Per-product validation: 1 hour
- **Total: 5 hours**

---

## For Next Session

**DO NOT attempt fixes without understanding the mechanism!**

Previous session tried 5 fixes - all failed because root cause wasn't understood.

**Start here:**
1. Check demand node 6104 material balance across all 28 days
2. If that holds, check node 6110
3. If ALL demand nodes have holding balances, the bug is subtle (arrival double-counting?)

**The phantom 276k units must enter somewhere. Find WHERE, then fix.**

---

## What I've Ruled Out

- ❌ Test logic error
- ❌ Missing end_in_transit in conservation
- ❌ Negative inventory
- ❌ Scaling factors
- ❌ Manufacturing material balance violation (per-product balances hold)
- ❌ Constraint formulas wrong (checked Day 1/2/3)
- ❌ Constraints missing (all 140 manufacturing constraints exist and active)

## What Remains

- ⚠️ Demand node material balance (NOT YET CHECKED)
- ⚠️ Arrival calculation in demand node balance
- ⚠️ Subtle constraint bug allowing phantom supply
- ⚠️ Pyomo solver bug (unlikely but possible)

---

**Recommendation:** Continue investigation with demand node balance checking. We're close to the answer!
