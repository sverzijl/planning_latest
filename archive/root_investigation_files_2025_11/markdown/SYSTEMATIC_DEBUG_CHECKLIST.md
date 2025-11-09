# Systematic Debugging Checklist: Disposal Bug

## Phase 1: Root Cause Investigation ✅ IN PROGRESS

### Evidence Gathered So Far

**✅ Read Error Messages:**
- No explicit error
- But economically irrational behavior: Disposal > Shortage cost

**✅ Reproduce Consistently:**
- Natural solution: 0 disposal
- With end_inv <= 2000: 7,434 units disposal
- Happens every time - reproducible ✓

**✅ Check Recent Changes:**
- Change: Added end_inv constraint
- Result: Disposal increased 0 → 7,434 units
- Direct correlation identified

**✅ Gather Evidence - Multi-Component:**

Components in system:
1. Material balance (Day 1-28)
2. Sliding window constraints
3. Consumption bounds
4. Demand equations
5. end_inv constraint (new)

Evidence being gathered:
- ✅ Cost breakdown (found $112k disposal)
- ✅ Disposal timing (Days 24-28, validly expired)
- ✅ Disposal locations (6110, 6123, 6120, 6130)
- 🔄 Daily inventory trace (running now)
- ⏳ Production timing comparison
- ⏳ Consumption pattern comparison

**✅ Trace Data Flow:**
- init_inv enters at specific nodes (Day 0)
- Should be consumed Days 1-17
- In constrained: 7,434 units NOT consumed
- Expire Days 24-28
- Disposed

**Question:** WHERE in the flow does consumption get blocked?

---

## Phase 2: Pattern Analysis ⏳ PENDING

**Working example:** Natural solution (0 disposal)
**Broken example:** Constrained solution (7,434 disposal)

**To compare:**
- [ ] Production timing (when does each produce?)
- [ ] Consumption patterns (how much consumed each day?)
- [ ] Inventory positioning (where is inventory each day?)
- [ ] Shipment routing (different routes used?)

---

## Phase 3: Hypothesis Testing ⏳ PENDING

**Hypotheses to test (will form AFTER Phase 1 evidence):**

Potential hypotheses:
1. end_inv constraint + sliding window = over-constraint on early days
2. Production timing shifts, leaves init_inv stranded at wrong nodes
3. Consumption bounds become too tight with end_inv constraint
4. Network routing changes prevent init_inv from reaching high-demand nodes

**Will select ONE hypothesis based on Phase 1 evidence.**

---

## Phase 4: Implementation ⏳ PENDING

**Fix attempts so far:** 0 (following systematic debugging - no fixes before root cause!)

**When root cause identified:**
1. Create failing test
2. Apply minimal fix
3. Verify fix works
4. Check no other tests broken

---

## Adherence to Systematic Debugging

**✅ Following process:**
- No fixes attempted before understanding root cause
- Gathering evidence first
- Will form hypothesis after evidence review
- One fix at a time when ready

**❌ NOT doing:**
- Guessing at fixes
- Multiple changes at once
- Skipping evidence gathering
- Proposing solutions before investigation

---

## Current Status

**Phase 1:** 80% complete (waiting for daily trace)
**Estimated time to root cause:** 30-60 minutes
**Estimated time to fix:** 15-30 minutes
**Total:** 1-1.5 hours to complete disposal bug fix

---

## Exit Criteria

**Phase 1 complete when:**
- [ ] Daily inventory trace analyzed
- [ ] Divergence point identified (which day they differ)
- [ ] Mechanism hypothesis formed

**Investigation complete when:**
- [ ] Root cause identified with evidence
- [ ] Fix applied and tested
- [ ] Disposal = 0 in constrained solution
- [ ] Objective ~$941k (not $1,052k)
- [ ] All tests still pass
