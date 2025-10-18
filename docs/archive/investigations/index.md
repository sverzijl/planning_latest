# Investigations Archive

## Purpose
Archived forensic analysis and investigation reports from troubleshooting sessions.

## Contents

### 2025-10-16: State Forensics - End-of-Horizon Inventory Analysis
- **File:** `STATE_FORENSICS_REPORT.md`
- **Investigation Question:** Are 15,548 units of end-of-horizon inventory in 'ambient', 'frozen', or 'thawed' state?
- **Status:** Closed - Hypothesis rejected
- **Conclusion:** 100% AMBIENT - State mismatch hypothesis REJECTED
- **Key Findings:**
  1. All 15,548 units at end of horizon are in 'ambient' state
  2. NO 'thawed' state exists in model (correctly uses 2-state system)
  3. NO frozen inventory at end of horizon
  4. Demand consumption logic handles both states correctly
  5. Root cause of inventory is NOT state mismatch
- **Forensic Methodology:**
  - Material balance verification (production vs consumption vs inventory)
  - Cohort variable inspection (Pyomo model indices)
  - State-by-state inventory breakdown by location
  - Demand consumption pattern analysis
- **Model Architecture Verified:**
  - 2-state system: 'frozen' and 'ambient' only
  - Thawing is implicit: frozen → ambient transition when arriving at ambient-only node
  - 14-day thawed shelf life enforced via min(17, 14) in cohort creation
  - State transitions correctly implemented (lines 645-679)
- **Root Cause (actual):** Cost optimization, not state mismatch
  - Model minimizes total cost, not inventory
  - Shortage penalty may be lower than production+transport cost
  - Transit time constraints prevent early production from reaching demand
- **Diagnostic Script:** `diagnose_inventory_state_forensics.py` (archived)
- **Related Code:** `src/optimization/unified_node_model.py`
  - Lines 481-494: Cohort creation
  - Lines 645-679: State transitions
  - Lines 1150-1158: Demand consumption

## Reusability

**State Forensics Investigation:**
- **Methodology:** When to use state-by-state forensic analysis
  - Suspected state mismatch or transition bugs
  - Unexpected inventory accumulation at specific locations
  - Demand satisfaction issues that might be state-related
  - Cohort variable inspection for debugging

- **Diagnostic Techniques:**
  1. Extract cohort variables from Pyomo model (`model.inventory_cohort`)
  2. Group by state and location
  3. Compare with expected state distribution
  4. Verify demand consumption covers all states
  5. Check material balance: production = consumption + end_inv + in_transit

- **When this approach is useful:**
  - Multi-state inventory systems (frozen/ambient/thawed)
  - State transition models (thawing, freezing, temperature zones)
  - Shelf life with state-dependent durations
  - Perishable goods with mode changes

## Related Documentation
- `/home/sverzijl/planning_latest/CLAUDE.md` - UnifiedNodeModel architecture
- `/home/sverzijl/planning_latest/archive/debug_scripts/` - Diagnostic scripts

---
*Archive created: 2025-10-18*
*This investigation demonstrated forensic methodology but hypothesis was rejected.*
