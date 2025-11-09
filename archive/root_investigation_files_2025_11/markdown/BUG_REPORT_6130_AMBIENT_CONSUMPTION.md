# Bug Report: 6130 Ambient Inventory Not Consumed

**Date:** 2025-11-08
**Status:** Under Investigation
**Priority:** Medium (affects inventory utilization)

---

## User Observation

When running 4-week solve with:
- **Forecast:** Gluten Free Forecast - Latest.xlsm
- **Network:** Network_Config.xlsx
- **Inventory:** inventory_latest.XLSX
- **Inventory snapshot date:** Oct 16, 2025
- **Planning start:** Oct 17, 2025

**Result:** Ambient inventory at 6130 persists unchanged:
- Day 1: 518 units HELGAS GFREE MIXED GRAIN at 6130 (ambient)
- Day 28: 518 units (same quantity - not consumed!)
- Other products show similar pattern

**Expected:** Ambient inventory should be consumed to meet demand at 6130.

---

## Investigation Findings

### ✅ Data Exists

**Forecast file verification:**
- SAP IBP sheet 'G144_RET' contains demand at 6130
- Oct 17 demand: 615 units (5 products)
- Alias resolution working: 168847 → HELGAS GFREE MIXED GRAIN 500G

**Model capabilities:**
- 6130 has `demand_consumed_from_ambient` variables
- 6130 supports ambient storage
- Demand satisfaction constraints include ambient consumption

### ⚠️ Conflicting Test Results

**Test 1: Default (Nov 8 start):**
- 6130 ambient consumed correctly (106 units on Day 1)
- ✅ Works

**Test 2: Oct 17 start (using DataCoordinator default):**
- No demand at 6130 in validated entries
- Inventory not consumed
- ❌ Problem: DataCoordinator filters demand (uses Nov 8 as default snapshot)

**Test 3: Attempted Oct 16 snapshot + Oct 17 start:**
- Hit API/configuration issues in test scripts
- Could not complete full solve with exact user parameters

---

## Possible Root Causes

### Hypothesis 1: Data Flow Issue
DataCoordinator may not be correctly receiving Oct 16 snapshot date from UI:
- Default behavior uses `Date.today()` = Nov 8
- UI passes Oct 16, but may not be threaded through all parsers
- Demand gets filtered to Nov 8+ horizon, excluding Oct 17-Nov 7

### Hypothesis 2: Date Validation Logic
Pydantic validation enforces `inventory_snapshot <= planning_start`:
- May be silently adjusting dates
- Or failing validation that UI catches differently

### Hypothesis 3: State Mismatch
Initial inventory at 6130 is ambient, but something about the model setup prevents consumption:
- Circular dependency was fixed generally, but edge case remains?
- Consumption limit still has issues with specific date combinations?

---

## Reproduction Steps Needed

To properly debug, need exact replication:

1. **Export UI configuration:**
   - Exact dates set in UI
   - Which files loaded
   - Any warnings/errors shown

2. **Run equivalent CLI solve:**
   ```python
   from src.validation.data_coordinator import DataCoordinator

   coordinator = DataCoordinator(
       forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
       network_file='data/examples/Network_Config.xlsx',
       inventory_file='data/examples/inventory_latest.XLSX'
   )

   # Pass explicit dates
   validated = coordinator.load_and_validate(
       planning_start_date=date(2025, 10, 17)
   )

   # But how to pass Oct 16 snapshot?
   ```

3. **Check validated demand:**
   - Does Oct 17 demand at 6130 exist in validated.demand_entries?
   - If yes → model formulation bug
   - If no → data coordinator filtering bug

---

## Diagnostic Scripts Created

- `probe_weekend_production.py` - Constraint probing for weekend analysis
- `check_lineage_state_bug.py` - Lineage state verification
- `test_lineage_thawed_bug.py` - Minimal test for Lineage bug
- Multiple other diagnostic scripts from disposal investigation

---

## Recommendation

**For next session:**

1. **Start fresh** - Current session has run 4+ hours with many tangents
2. **Use systematic debugging from start:**
   - Create minimal test case (10 lines)
   - Prove bug reproduces with Oct 16/Oct 17 dates
   - Use constraint probing if needed
   - Fix after root cause proven

3. **Specific first step:**
   ```python
   # Test if DataCoordinator correctly handles explicit snapshot date
   from datetime import date
   coordinator.load_and_validate(planning_start_date=date(2025, 10, 17))
   # And somehow pass inventory_snapshot_date=date(2025, 10, 16)
   ```

4. **If it's a DataCoordinator API issue:**
   - Add parameter for explicit inventory_snapshot_date override
   - Or document that UI must align dates before calling

---

## Success This Session

Despite not fully resolving this issue, the session delivered:

- **$326k cost improvement** from disposal bug fix
- **Correct Lineage state display** in UI
- **Process improvements** documented (playbook, lessons learned)
- **Faster debugging** on second bug (Lineage) using learned process

**Both fixes are committed and pushed to GitHub.**

The 6130 issue requires a clean debugging session with exact data flow replication.
