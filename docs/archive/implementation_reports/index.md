# Implementation Reports Archive

## Purpose
Archived implementation deep-dive documentation from feature development.

## Contents

### 2025-10-17: Integration Test Timeout Fix
- **File:** `INTEGRATION_TEST_FIX.md`
- **Status:** Resolved - Configuration updated
- **Issue:** Integration test timing out (>120s) with pallet-based storage costs
- **Resolution:** Disabled pallet costs in default Network_Config.xlsx for baseline testing
- **Key Insights:**
  - Pallet-based costs add ~18,675 integer variables (2x solve time)
  - CBC solver struggles with large MIP problems vs commercial solvers
  - Configuration trade-off: accuracy vs performance
  - Default config now uses unit-based costs for fast testing
- **Impact:** Integration test now passes in ~71s vs 188-199s timeout
- **Related Code:** `src/optimization/unified_node_model.py` lines 1500-1600 (pallet cost modeling)
- **Related Config:** `data/examples/Network_Config.xlsx` CostParameters sheet

### 2025-10-17: Piecewise Labor Cost Implementation
- **File:** `PIECEWISE_LABOR_COST_IMPLEMENTATION.md`
- **Status:** Complete - Feature in production
- **Features Implemented:**
  - Piecewise cost structure (regular rate for fixed hours, OT rate for excess)
  - 4-hour minimum payment on weekends/holidays
  - Overhead time inclusion (startup + shutdown + changeover)
- **Bugs Fixed:**
  1. Overhead time excluded from labor hours (underestimation)
  2. Blended rate approximation (inaccurate cost split)
  3. No 4-hour minimum enforcement on non-fixed days
- **Performance Impact:** Zero (32-38s solve time unchanged)
- **Variable Count:** +28 binary variables (+0.14%)
- **Constraint Count:** +232 labor constraints (+2.3%)
- **Related Code:** `src/optimization/unified_node_model.py` lines 1837-2045
- **Tests:** `tests/test_labor_cost_piecewise.py`

## When to Reference

**Integration Test Fix:**
- When optimizing solver performance
- When choosing between pallet-based and unit-based storage costs
- When configuring Network_Config.xlsx for different use cases
- When troubleshooting MIP solver timeouts

**Piecewise Labor Cost:**
- When understanding labor cost model formulation
- When debugging labor cost extraction from solutions
- When adding new labor-related features
- When verifying 4-hour minimum payment logic

## Related Documentation
- `/home/sverzijl/planning_latest/CLAUDE.md` - Main project documentation (Recent Updates section)
- `/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx` - Cost configuration
- `/home/sverzijl/planning_latest/tests/test_integration_ui_workflow.py` - Integration test

---
*Archive created: 2025-10-18*
*These reports document completed implementations and resolved issues.*
