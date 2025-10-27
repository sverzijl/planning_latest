# Prompt for Next Session

Copy and paste this to start your next session:

---

I'm continuing work on the gluten-free bread production planning application. In the previous session, we started implementing a `state_entry_date` architecture to properly track inventory age across state transitions (freezing/thawing).

**Read these files first:**
1. `STATE_ENTRY_DATE_IMPLEMENTATION.md` - Complete implementation plan and handoff
2. `TODAYS_ACCOMPLISHMENTS.md` - What was accomplished in previous session

**Current Status:**
- ✅ **Phase 1 Complete:** Cohort index building with 6-tuple structure `(node, product, prod_date, state_entry_date, curr_date, state)`
- ⏳ **Phase 2 Needed:** Update inventory balance constraint and all cohort references

**The Problem We're Solving:**
The WA location (6130) gets no shipments because the shelf life filter incorrectly ages frozen products. Products stored frozen at Lineage should have full 120-day shelf life, not diminished by calendar time. The state_entry_date architecture tracks when inventory entered its current state, enabling accurate age calculation:
- `age_in_state = curr_date - state_entry_date` (not curr_date - prod_date)

**Your Task:**
Complete the state_entry_date implementation following the plan in `STATE_ENTRY_DATE_IMPLEMENTATION.md`.

**Key Implementation Steps:**

1. **Update inventory balance constraint** (lines 2221-2350 in `src/optimization/unified_node_model.py`)
   - Change signature from 5-tuple to 6-tuple
   - Production: `if state_entry_date == prod_date` (fresh production)
   - Arrivals: `if state_entry_date == curr_date` (fresh arrivals)
   - Carry forward: same state_entry_date as previous day
   - See handoff document section 1.1-1.5 for detailed logic

2. **Update all inventory_cohort references** (~100 occurrences)
   - Search: `grep -n "inventory_cohort\[" src/optimization/unified_node_model.py`
   - Change each from 5-tuple to 6-tuple
   - Some need to iterate/sum across state_entry_date dimension

3. **Update demand_from_cohort to include state**
   - Add state to index for staleness penalty
   - See handoff section 3

4. **Fix staleness penalty** (lines 3711-3722)
   - Use `age_in_state` instead of calendar age
   - Frozen: age_ratio = 0
   - Thawed: age_in_state / 14
   - Ambient: age_in_state / 17

5. **Update solution extraction** (lines 1976-2035)
   - Handle 6-tuple cohort iteration
   - Update waste calculation

6. **Test incrementally:**
   - 1-week solve first (fast validation)
   - Check cohort count reasonable
   - Then 4-week solve
   - Verify WA gets flow via Lineage

**Success Criteria:**
- ✅ Model builds without errors
- ✅ 4-week solve completes
- ✅ WA location receives shipments
- ✅ Lineage has frozen inventory
- ✅ Solve time <15 minutes

**Useful commands:**
```bash
# Check cohort references
grep -n "inventory_cohort\[" src/optimization/unified_node_model.py | wc -l

# Test build
venv/bin/python3 -c "from src.workflows import InitialWorkflow; ..."

# Run diagnostic
python diagnose_wa_blockage.py
```

Please proceed with the implementation following the systematic approach in the handoff document. Use the pyomo skill and mip-modeling-expert skill as needed for constraint formulation.

---

**Additional Context:**
- This is a production planning system for a major Australian food manufacturer
- UnifiedNodeModel is the optimization core (Pyomo-based)
- 4-week horizon typical, 12-week for weekly planning
- Critical that WA location gets served (currently 13k units short)
- State transitions: ambient→frozen (at Lineage), frozen→thawed (at 6130)
