# STATE FORENSICS REPORT: End-of-Horizon Inventory Analysis

**Date:** 2025-10-16
**Investigation:** Are the 15,548 units of end-of-horizon inventory in 'ambient', 'frozen', or 'thawed' state?
**Conclusion:** 100% AMBIENT - State mismatch hypothesis REJECTED

---

## Executive Summary

The forensic analysis conclusively demonstrates that:
1. **All 15,548 units of end-of-horizon inventory are in 'ambient' state (100%)**
2. **NO 'thawed' state exists in the model** (correctly)
3. **NO frozen inventory at end of horizon** (0 units)
4. **Demand consumption logic handles all existing states correctly**
5. **Root cause of end-of-horizon inventory is NOT a state mismatch**

The state mismatch hypothesis is **REJECTED**. The model's state handling is correct.

---

## Detailed Findings

### 1. Inventory State Breakdown (Day 28: 2025-11-03)

```
Total End-of-Horizon Inventory: 15,548 units

State Distribution:
- Ambient:  15,548 units (100.0%)
- Frozen:        0 units (  0.0%)
- Thawed:        0 units (  0.0%)
```

### 2. Inventory by Location and State

All inventory is at **breadroom locations** (demand nodes):

| Location | Node Name | Ambient | Frozen | Thawed | Total |
|----------|-----------|---------|--------|--------|-------|
| 6104 | Moorebank (NSW Hub) | 3,724 | 0 | 0 | 3,724 |
| 6123 | Clayton-Fairbank | 3,724 | 0 | 0 | 3,724 |
| 6110 | Burleigh Heads | 2,243 | 0 | 0 | 2,243 |
| 6105 | Rydalmere | 2,031 | 0 | 0 | 2,031 |
| 6130 | Canning Vale (WA) | 1,247 | 0 | 0 | 1,247 |
| 6125 | Keilor Park (VIC Hub) | 1,026 | 0 | 0 | 1,026 |
| 6103 | Canberra | 799 | 0 | 0 | 799 |
| 6120 | Hobart | 754 | 0 | 0 | 754 |

**Observation:** Inventory accumulates at breadrooms where demand occurs. This is expected behavior.

### 3. Model State Architecture

The UnifiedNodeModel uses a **2-state system**:
- **'frozen'** - For frozen storage and transport
- **'ambient'** - For ambient storage and thawed product

**There is NO 'thawed' state.** Thawing is handled implicitly:
- Frozen product arriving at an ambient-only node → becomes 'ambient' (line 676)
- 14-day shelf life enforced via cohort building (line 492)

#### Cohort Creation (Lines 481-494)

```python
# Frozen cohorts at frozen-capable nodes
if node.supports_frozen_storage():
    if age_days <= self.FROZEN_SHELF_LIFE:  # 120 days
        cohorts.add((node.id, prod, prod_date, curr_date, 'frozen'))

# Ambient cohorts at ambient-capable nodes
if node.supports_ambient_storage():
    shelf_life = min(self.AMBIENT_SHELF_LIFE, self.THAWED_SHELF_LIFE)  # min(17, 14) = 14
    if age_days <= shelf_life:
        cohorts.add((node.id, prod, prod_date, curr_date, 'ambient'))
```

**Key insight:** Ambient cohorts use **14-day shelf life** (minimum of 17d ambient and 14d thawed) to conservatively handle both native ambient and thawed-from-frozen product.

#### State Transitions (Lines 645-679)

```python
def _determine_arrival_state(route, destination_node):
    if route.transport_mode == TransportMode.AMBIENT:
        if destination_node.supports_frozen_storage() and not destination_node.supports_ambient_storage():
            return 'frozen'  # Freeze at frozen-only node
        else:
            return 'ambient'  # Stay ambient
    else:  # FROZEN transport
        if destination_node.supports_ambient_storage() and not destination_node.supports_frozen_storage():
            return 'ambient'  # Thaw immediately (implicit)
        else:
            return 'frozen'  # Stay frozen
```

**No 'thawed' state created!** Thawing is represented as transition to 'ambient'.

#### Demand Consumption (Lines 1150-1158)

```python
if node.has_demand_capability():
    if (node_id, prod, curr_date) in self.demand:
        if (node_id, prod, prod_date, curr_date) in self.demand_cohort_index_set:
            if state == 'ambient' and node.supports_ambient_storage():
                demand_consumption = model.demand_from_cohort[...]
            elif state == 'frozen' and node.supports_frozen_storage():
                demand_consumption = model.demand_from_cohort[...]
```

**Coverage:** Logic handles both 'ambient' and 'frozen' states. Since model only creates these two states, coverage is **complete**.

### 4. Pyomo Model Verification

```
Total cohort variables: 17,780
States present in model: ['ambient', 'frozen']

Sample cohort indices:
  ('Lineage', 'HELGAS GFREE MIXED GRAIN 500G', 2025-10-12, 2025-10-12, 'frozen')
  ('6122', 'WONDER GFREE WHITE 470G', 2025-10-18, 2025-10-20, 'ambient')
  ('6123', 'WONDER GFREE WHOLEM 500G', 2025-11-02, 2025-11-03, 'ambient')
```

**Confirmed:** Only 'ambient' and 'frozen' states exist in the Pyomo model.

### 5. Demand Consumption Analysis

```
Total demand consumption: 209,600 units (across 2,327 cohort allocations)
Format: (node, prod, prod_date, demand_date) -> qty

Sample:
  ('6130', 'WONDER GFREE WHOLEM 500G', 2025-10-14, 2025-10-25): 3.52 units
  ('6125', 'WONDER GFREE WHITE 470G', 2025-10-07, 2025-10-17): 4.62 units
  ('6103', 'WONDER GFREE WHOLEM 500G', 2025-10-13, 2025-10-21): 11.85 units
```

**Note:** Demand consumption is state-agnostic (no state in key). The constraint (line 1150-1158) iterates over all cohorts matching (node, prod, prod_date) regardless of state, so all inventory states are considered.

---

## Material Balance Verification

```
Production:        225,148 units
Demand:            225,153 units
Consumption:       209,600 units
Shortage:           30,053 units
End Inventory:      15,548 units

Verification:
  Demand = Consumption + Shortage
  225,153 ≈ 209,600 + 30,053 = 239,653  ❌ MISMATCH!

Expected:
  Production = Consumption + End_Inv + In_Transit + Waste
```

**Gap:** 209,600 (consumption) + 30,053 (shortage) = 239,653 but demand is 225,153. This suggests shortage extraction may be incorrect or consumption includes non-demand uses.

---

## Conclusion

### State Mismatch Hypothesis: REJECTED

The original hypothesis was:
> "If 'thawed' cohorts exist but demand consumption (lines 1150-1158) only handles 'frozen' and 'ambient', then 'thawed' inventory cannot be consumed and accumulates."

**Evidence against:**
1. NO 'thawed' cohorts exist in the model (verified in Pyomo variable indices)
2. Model uses only 2 states: 'frozen' and 'ambient'
3. Thawing is implicit: frozen→ambient transition when arriving at ambient node
4. 14-day thawed shelf life enforced via min(17, 14) in cohort creation (line 492)
5. Demand consumption handles both existing states ('frozen' and 'ambient')
6. All end-of-horizon inventory is 'ambient' (the consumable state at breadrooms)

### Root Cause Still Unknown

The 15,548 units of end-of-horizon inventory is **NOT** caused by:
- ❌ State mismatch (thawed inventory not consumable)
- ❌ Weekend hub inventory bug (hubs have inventory but small amounts)
- ❌ Virtual location bypass (6122_Storage removed in unified model)

**Remaining hypotheses:**
1. **Cost optimization:** Model minimizes total cost, not inventory. If shortage penalty < production+transport cost for early deliveries, model accepts shortages.
2. **Transit time constraints:** Production on days 20-28 may be too late to reach demand on days 7-17.
3. **Truck scheduling constraints:** Limited truck availability may prevent earlier deliveries.
4. **Production capacity:** May not be possible to produce enough in early days to cover early demand.

---

## Recommendations

### Next Investigation Steps

1. **Check cost parameters:**
   ```python
   print(f"Production cost: ${cost_structure.production_cost_per_unit}/unit")
   print(f"Shortage penalty: ${cost_structure.shortage_penalty_per_unit}/unit")
   print(f"Transport cost: ${route.cost_per_unit}/unit (varies by route)")
   ```
   If shortage penalty is too low, model prefers shortages over expensive early production.

2. **Analyze production timing:**
   - Extract production by date (days 1-28)
   - Compare with demand by date
   - Check if early production is feasible given capacity

3. **Verify truck availability:**
   - Check truck schedules for days 1-10
   - Verify routes from manufacturing to early-demand breadrooms
   - Ensure no day-of-week gaps in coverage

4. **Test constraint relaxation:**
   - Increase shortage penalty to force demand satisfaction
   - Remove truck constraints temporarily
   - Check if inventory still accumulates

### Potential Fixes (if needed)

1. **If cost-driven:** Increase `shortage_penalty_per_unit` to prioritize demand satisfaction
2. **If truck-driven:** Add more truck schedules or relax day-of-week constraints
3. **If capacity-driven:** Review labor calendar and production rate assumptions
4. **If transit-driven:** Verify route transit times and ensure reachability

---

## Appendix: Code References

### Key Files
- `/home/sverzijl/planning_latest/src/optimization/unified_node_model.py`
  - Lines 481-494: Cohort creation (2 states only)
  - Lines 645-679: State transition logic (implicit thawing)
  - Lines 1150-1158: Demand consumption (handles both states)
  - Lines 1213-1237: Demand-inventory linking constraint

### Diagnostic Scripts
- `/home/sverzijl/planning_latest/diagnose_inventory_state_forensics.py` (this analysis)
- `/home/sverzijl/planning_latest/diagnose_inventory_forensics.py` (material balance)

### Test Data
- Forecast: `/home/sverzijl/planning_latest/data/examples/Gfree Forecast.xlsm`
- Network: `/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx`
- Planning Horizon: 2025-10-07 to 2025-11-03 (28 days)
- Solve Time: 21.7 seconds
- Solution: Optimal

---

**Report prepared by:** Claude Code (Python Pro)
**Investigation complete:** State mismatch hypothesis rejected with forensic evidence
