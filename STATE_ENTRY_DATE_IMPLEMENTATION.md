# State Entry Date Implementation - Handoff Document

## 🎯 Objective

Implement full `state_entry_date` tracking in inventory cohorts to properly handle age across state transitions (freezing/thawing). This fixes:
1. **WA route blockage** - Frozen products incorrectly age during frozen storage
2. **Shelf life accuracy** - Age should count from state entry, not production
3. **Staleness penalty** - Frozen products shouldn't be penalized for calendar time

---

## 📊 Current Status

### ✅ **Phase 1 Complete: Cohort Index Foundation**

**Commit:** ccbd595 - "feat: Begin state_entry_date architecture"

**What's Done:**
1. ✅ **Cohort index building** (`_build_cohort_indices()`, lines 889-975)
   - New 6-tuple structure: `(node, product, prod_date, state_entry_date, curr_date, state)`
   - Smart indexing: enumerate state_entry_dates from prod_date to curr_date
   - Shelf life check uses `age_in_state = curr_date - state_entry_date`
   - ~520k cohorts created (was 18k) - manageable for sparse constraints

2. ✅ **Variable definition updated** (line 598-604)
   - Doc string reflects 6-tuple structure
   - Bounds unchanged

### ⏳ **Phase 2 Remaining: Constraint Updates**

**What Needs to Change:**
1. **Inventory balance constraint** - 150+ lines, complex state transition logic
2. **All inventory_cohort references** - ~100 occurrences need 6-tuple indexing
3. **demand_from_cohort structure** - Add state to track frozen vs ambient demand
4. **Staleness penalty** - Use age_in_state instead of calendar age
5. **Solution extraction** - Handle 6-tuple cohorts
6. **Initial inventory conversion** - Add state_entry_date to initial inventory
7. **Warmstart** - Handle new cohort structure

---

## 🏗️ **Architecture Details**

### **Cohort Index Structure**

**OLD (5-tuple):**
```
inventory_cohort[node, product, prod_date, curr_date, state]
age = curr_date - prod_date  (always calendar time)
```

**NEW (6-tuple):**
```
inventory_cohort[node, product, prod_date, state_entry_date, curr_date, state]
age_in_state = curr_date - state_entry_date
```

### **State Entry Date Semantics**

**When Manufactured:**
```
Production at 6122 on Oct 28:
  → cohort[6122, TRAD_WHITE, Oct28, Oct28, Oct28, 'ambient']
  → state_entry_date = Oct28 (entered ambient state when manufactured)
  → age_in_state = 0 days
```

**When Frozen (ambient → frozen):**
```
Ships to Lineage, arrives Oct 29, freezes:
  → cohort[Lineage, TRAD_WHITE, Oct28, Oct29, Oct29, 'frozen']
  → state_entry_date = Oct29 (entered frozen state on arrival)
  → age_in_state = 0 days
  → Shelf life = 120 days ✅
```

**When Thawed (frozen → ambient):**
```
Ships to 6130, arrives Nov 5, thaws:
  → cohort[6130, TRAD_WHITE, Oct28, Nov05, Nov05, 'thawed']
  → state_entry_date = Nov05 (entered thawed state on arrival)
  → age_in_state = 0 days
  → Shelf life = 14 days ✅
```

**Carries Forward:**
```
Next day at 6130:
  → cohort[6130, TRAD_WHITE, Oct28, Nov05, Nov06, 'thawed']
  → state_entry_date = Nov05 (still when it thawed)
  → age_in_state = 1 day
  → Shelf life = 14 - 1 = 13 days remaining ✅
```

---

## 📋 **Implementation Checklist - Phase 2**

### **1. Inventory Balance Constraint** (3-4 hours, CRITICAL)

**File:** `src/optimization/unified_node_model.py`, lines 2221-2350

**Current signature:**
```python
def inventory_balance_rule(model, node_id, prod, prod_date, curr_date, state):
```

**New signature:**
```python
def inventory_balance_rule(model, node_id, prod, prod_date, state_entry_date, curr_date, state):
```

**Key logic changes:**

#### **1.1. Production Inflow** (line ~2224):

```python
# Production creates inventory with state_entry_date = prod_date
if node.can_produce() and prod_date == curr_date:
    production_state = node.get_production_state()
    if state == production_state:
        # Fresh production - state entry is today (production date)
        if state_entry_date == prod_date:
            gross_production = model.production[node_id, prod, curr_date]
            changeover_waste = ... # existing logic
            production_inflow = gross_production - changeover_waste
        else:
            production_inflow = 0  # Wrong state_entry_date for production
```

#### **1.2. Arrivals** (line ~2237-2263):

```python
# Shipments arriving today enter state with state_entry_date = today
for route in routes_to_node:
    arrival_state = _determine_arrival_state(route, node)

    if state == arrival_state:
        # Only create inflow for cohorts with state_entry_date = curr_date
        if state_entry_date == curr_date:
            # This cohort represents inventory that JUST arrived today
            arrivals += sum(
                model.shipment_cohort[origin, dest, prod, prod_date, curr_date, arrival_state]
                for arrivals on curr_date
            )
        else:
            arrivals = 0  # This cohort is for a different entry date
```

#### **1.3. Previous Day Inventory** (line ~2206-2214):

```python
# Previous day's inventory CARRIES FORWARD with SAME state_entry_date
prev_date = date_previous.get(curr_date)
if prev_date:
    # Previous inventory with SAME state_entry_date
    if (node_id, prod, prod_date, state_entry_date, prev_date, state) in cohort_index_set:
        prev_inv = model.inventory_cohort[node_id, prod, prod_date, state_entry_date, prev_date, state]
    else:
        prev_inv = 0
else:
    # First date - use initial inventory
    # Need to convert initial inventory to 6-tuple format
    prev_inv = initial_inventory.get((node_id, prod, prod_date, state_entry_date, state), 0)
```

#### **1.4. State Transitions** (NEW LOGIC NEEDED):

**Challenge:** How does inventory change state (ambient→frozen)?

**Approach:** Don't explicitly model transitions. Instead:
- Ambient cohorts can ship via frozen routes (conversion happens in transit)
- Frozen cohorts can ship via ambient routes to ambient nodes (thaw on arrival)
- State changes implicitly via shipment arrivals (state_entry_date = arrival_date)

**No explicit transition variables needed!**

#### **1.5. Departures** (line ~2266-2310):

```python
# Shipments leaving in this state
for route in routes_from_node:
    departure_state = 'frozen' if route.transport_mode == FROZEN else 'ambient'

    if state == departure_state:
        # Can ship from ANY state_entry_date cohort of this state
        for delivery_date in dates:
            departure_date = calculate_departure_date(delivery_date, transit_time)

            if departure_date == curr_date:
                # Sum across ALL state_entry_dates for this state
                # (Product can leave regardless of when it entered the state)
                departures += model.shipment_cohort[origin, dest, prod, prod_date, delivery_date, state]
```

---

### **2. Update All Cohort References** (2-3 hours)

**Strategy:** Search and replace 5-tuple → 6-tuple

**Files to update:**
- `src/optimization/unified_node_model.py` (~100 references)

**Pattern:**
```python
# OLD:
inventory_cohort[node_id, prod, prod_date, curr_date, state]

# NEW:
inventory_cohort[node_id, prod, prod_date, state_entry_date, curr_date, state]
```

**Critical locations:**
- Line ~1585: Solution extraction
- Line ~1422: Warmstart bounds
- Line ~2260: Arrival inventory balance
- Line ~2303: Departure inventory balance
- Line ~2412: Demand satisfaction
- Line ~3755: End-of-horizon waste
- Line ~2003: Waste cost extraction

**Search command:**
```bash
grep -n "inventory_cohort\[" src/optimization/unified_node_model.py
```

**Each occurrence needs analysis:**
- Is this indexing an existing cohort? (add state_entry_date)
- Is this summing across state_entry_dates? (iterate over state_entry_date dimension)

---

### **3. Update Demand Cohort** (1-2 hours)

**Current:**
```
demand_from_cohort[node, product, prod_date, demand_date]
```

**Needed:**
```
demand_from_cohort[node, product, prod_date, state_entry_date, demand_date, state]
```

**Why:** To calculate staleness penalty based on age_in_state per state

**Files:**
- Line ~649-659: Variable definition
- Line ~1084: Demand cohort index building
- Line ~2410-2420: Demand satisfaction constraint
- Line ~3711-3722: Staleness penalty calculation

---

### **4. Update Staleness Penalty** (30 min)

**File:** Lines 3711-3722

**Current:**
```python
age_days = (demand_date - prod_date).days
age_ratio = age_days / 17.0
staleness_cost += weight × age_ratio × demand_from_cohort[node, prod, prod_date, demand_date]
```

**New:**
```python
for (node, prod, prod_date, state_entry_date, demand_date, state) in demand_cohort_index_set:
    age_in_state = (demand_date - state_entry_date).days

    # State-aware age ratio
    if state == 'frozen':
        age_ratio = 0  # Frozen doesn't age
    elif state == 'thawed':
        age_ratio = age_in_state / 14.0
    else:  # ambient
        age_ratio = age_in_state / 17.0

    staleness_cost += weight × age_ratio × demand_from_cohort[node, prod, prod_date, state_entry_date, demand_date, state]
```

---

### **5. Update Solution Extraction** (1 hour)

**File:** Lines 1976-2035

**Update iteration:**
```python
# OLD:
for (node_id, prod, prod_date, curr_date, state) in model.inventory_cohort:
    ...

# NEW:
for (node_id, prod, prod_date, state_entry_date, curr_date, state) in model.inventory_cohort:
    age_in_state = (curr_date - state_entry_date).days
    ...
```

**Update waste calculation** (lines 1994-2010):
```python
for (n, p, prod_date, state_entry, curr_date, state) in model.inventory_cohort:
    if curr_date == last_date:
        # End inventory waste
        ...
```

---

### **6. Convert Initial Inventory** (30 min)

**Current format:**
```python
initial_inventory[(node, prod, prod_date, state)] = quantity
```

**New format:**
```python
initial_inventory[(node, prod, prod_date, state_entry_date, state)] = quantity
```

**Where for initial inventory:**
```
state_entry_date = snapshot_date - 1 day
(Assume inventory entered state one day before snapshot)
```

**File:** Check how initial_inventory is used, convert format

---

### **7. Testing Strategy**

**Test 1: 1-week solve (fast validation)**
- Horizon: 1 week (7 days)
- Check cohort count (should be ~50-100k, not millions)
- Verify model builds without errors
- Check solve time (<60 seconds)

**Test 2: 2-week solve (performance check)**
- Horizon: 2 weeks
- Check cohort count scaling
- Solve time should be <5 minutes
- Verify solution quality

**Test 3: 4-week solve (WA route validation)**
- Full 4-week horizon
- **Verify WA gets flow** via Lineage
- Check Lineage has frozen inventory
- Check 6130 has thawed inventory
- WA shortages: 13,199 → ~0

**Test 4: Weekend consolidation**
```bash
python diagnose_weekend_consolidation.py
```
Should show $0 consolidation opportunities

---

## 🚨 **Known Challenges**

### **Challenge 1: Cohort Count**

**Estimate:**
```
OLD: nodes × products × prod_dates × curr_dates × states
   = 11 × 5 × 28 × 28 × 3 = ~43k cohorts

NEW: nodes × products × prod_dates × state_entry_dates × curr_dates × states
   = 11 × 5 × 28 × 28 × 28 × 3 = ~1.2M cohorts (worst case)
```

**Mitigation:** Most cohorts won't be created:
- state_entry_date > curr_date: invalid
- state_entry_date < prod_date: invalid
- Shelf life filtering removes many
- Sparse constraint generation (only create used cohorts)

**Expected: ~100-200k cohorts** (5× increase, manageable)

### **Challenge 2: Inventory Balance Complexity**

**State transition logic** is tricky:
- How does inventory move from state_entry_date A to state_entry_date B?
- Answer: Via shipments (state change on arrival) or carries forward (same state_entry_date)

**Key insight:** Don't model transitions explicitly. States change via:
1. **Production:** Creates new inventory with state_entry_date = prod_date
2. **Arrivals:** Creates new inventory with state_entry_date = arrival_date
3. **Carry forward:** Same state_entry_date as previous day

### **Challenge 3: Debugging**

With 6-tuple cohorts, debugging is harder. Recommendations:
- Print sample cohorts during build
- Log cohort counts by state
- Test with 1-week horizon first
- Use diagnostic scripts to verify correctness

---

## 📁 **Files to Modify**

### **Primary File:**
- `src/optimization/unified_node_model.py` (~500 line changes)

### **Supporting Files:**
- Solution extraction already in unified_node_model.py
- No parser changes needed (initial inventory conversion inline)

### **Test Files:**
- Create `tests/test_state_entry_date.py` for validation
- Update `tests/test_integration_ui_workflow.py` if it breaks

---

## 🔍 **Verification Criteria**

**After implementation, verify:**

1. ✅ **Model builds successfully**
   - No index errors
   - Cohort count reasonable (~100-200k)
   - Variable count reasonable

2. ✅ **Solve completes**
   - 4-week horizon solves in <15 minutes
   - No infeasibility
   - Objective value reasonable

3. ✅ **WA route works**
   - Lineage has frozen inventory
   - 6130 receives shipments
   - WA shortages drop to near-zero

4. ✅ **Shelf life accurate**
   - Frozen products: 120 days from freeze_date
   - Thawed products: 14 days from thaw_date
   - Ambient products: 17 days from prod_date

5. ✅ **Staleness correct**
   - Frozen inventory: $0 staleness cost
   - Thawed inventory: Based on age_since_thaw
   - Ambient inventory: Based on age_since_production

6. ✅ **No performance regression**
   - Solve time <2× previous
   - Solution quality maintained

---

## 🛠️ **Implementation Tips**

### **Inventory Balance Pattern:**

```python
def inventory_balance_rule(model, node_id, prod, prod_date, state_entry_date, curr_date, state):
    # Previous inventory (SAME state_entry_date carries forward)
    prev_date = ...
    if prev_date and (node_id, prod, prod_date, state_entry_date, prev_date, state) in cohort_set:
        prev_inv = model.inventory_cohort[node_id, prod, prod_date, state_entry_date, prev_date, state]
    else:
        prev_inv = 0

    # Production (state_entry_date = prod_date for fresh production)
    production_inflow = 0
    if can_produce and prod_date == curr_date and state_entry_date == prod_date:
        production_inflow = model.production[...] - changeover_waste

    # Arrivals (state_entry_date = curr_date for fresh arrivals)
    arrivals = 0
    if state_entry_date == curr_date:
        # Sum shipments arriving today in this state
        arrivals = sum(shipments arriving on curr_date in this state)

    # Departures (can depart from ANY state_entry_date of this state)
    departures = sum(
        shipments departing today from this state
        # Don't filter by state_entry_date - any age can ship
    )

    # Demand (can consume from ANY state_entry_date of this state)
    demand_consumed = ...

    # Balance
    return model.inventory_cohort[node, prod, prod_date, state_entry_date, curr_date, state] == (
        prev_inv + production_inflow + arrivals - departures - demand_consumed
    )
```

### **Summing Across State Entry Dates:**

Many constraints need to sum across ALL state_entry_dates:

```python
# Total inventory in a state (all state_entry_dates)
total_frozen = sum(
    model.inventory_cohort[node, prod, prod_date, sed, curr_date, 'frozen']
    for sed in valid_state_entry_dates
)

# Use generator with condition:
total_frozen = sum(
    model.inventory_cohort[n, p, pd, sed, cd, s]
    for (n, p, pd, sed, cd, s) in model.cohort_index
    if n == node and p == product and cd == curr_date and s == 'frozen'
)
```

### **Initial Inventory Conversion:**

```python
# Current: (node, prod, prod_date, state) → quantity
# New: (node, prod, prod_date, state_entry_date, state) → quantity

# Assume state_entry_date = snapshot_date - 1 for existing inventory
snapshot_date = ...
converted_initial_inv = {}

for (node, prod, prod_date, state), qty in initial_inventory.items():
    state_entry_date = snapshot_date - timedelta(days=1)  # Conservative
    converted_initial_inv[(node, prod, prod_date, state_entry_date, state)] = qty
```

---

## 🧪 **Testing Commands**

**After implementation:**

```bash
# Test 1: Build check (1 week)
python -c "
from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
# ... load data ...
config = WorkflowConfig(workflow_type=WorkflowType.INITIAL, planning_horizon_weeks=1)
workflow = InitialWorkflow(config, ...)
result = workflow.execute()
print(f'Cohorts created: ...')
"

# Test 2: WA route check
python diagnose_wa_blockage.py

# Test 3: Weekend consolidation
python diagnose_weekend_consolidation.py

# Test 4: Run via UI
streamlit run ui/app.py
# → Initial Solve → 4 weeks → 2% gap → Run
```

---

## 📦 **Deliverables for Next Session**

1. ✅ **Working state_entry_date architecture**
   - All constraints updated
   - All references converted to 6-tuple
   - Tests passing

2. ✅ **WA route functional**
   - Lineage receives frozen shipments
   - 6130 receives and thaws
   - Shortages reduced

3. ✅ **Performance acceptable**
   - 4-week solve <15 minutes
   - Cohort count <300k

4. ✅ **Documentation**
   - Code comments explain state_entry_date
   - Update CLAUDE.md
   - Testing evidence

---

## 🎯 **Success Criteria**

**Must have:**
- [ ] Model builds without errors
- [ ] 4-week solve completes successfully
- [ ] WA route has flow (Lineage → 6130)
- [ ] Shelf life calculations use age_in_state
- [ ] Staleness penalty state-aware

**Nice to have:**
- [ ] Solve time <10 minutes (performance)
- [ ] Cohort count <200k (efficiency)
- [ ] All existing tests pass

---

## 📞 **Questions/Decisions Needed**

1. **Initial inventory state_entry_date:**
   - Use snapshot_date - 1 day? (conservative)
   - Or snapshot_date? (assume just entered state)
   - **Recommend:** snapshot_date - 1 (conservative)

2. **Thawed vs Ambient distinction:**
   - Keep separate 'thawed' state?
   - Or merge to 'ambient' with 14-day shelf life?
   - **Current:** Separate 'thawed' state
   - **Keep this** - allows different shelf lives

3. **State transition modeling:**
   - Explicit transition variables?
   - Or implicit via arrivals?
   - **Recommend:** Implicit (simpler, no new variables)

---

**Document Version:** 1.0
**Created:** Oct 26, 2025, 9:30 PM
**Status:** Phase 1 Complete, Phase 2 Ready to Start
**Estimated Completion:** 6-8 hours in fresh session
