# Network Configuration Parameter Migration Guide

**Date:** October 17, 2025
**Version:** 1.0
**Status:** Complete

## Overview

This guide documents the addition of manufacturing overhead and pallet-based storage cost parameters to the Network_Config.xlsx format, implemented on October 17, 2025.

These enhancements allow users to configure previously hardcoded optimization parameters, providing greater control over cost modeling and capacity planning.

## What Changed

### 1. Manufacturing Overhead Parameters (NEW)

Three new columns added to the **Locations sheet** for manufacturing nodes:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `daily_startup_hours` | float | 0.5 | Production line startup time (hours) |
| `daily_shutdown_hours` | float | 0.5 | Production line shutdown time (hours) |
| `default_changeover_hours` | float | 1.0 | Product changeover time (hours) |

**Purpose:**
These parameters enable accurate capacity modeling by accounting for manufacturing overhead time that reduces effective production hours.

**Impact on Optimization:**
- **Labor hours** now include overhead time (startup + shutdown + changeover)
- **Capacity constraints** account for reduced production time due to overhead
- **Labor costs** reflect actual hours worked (production + overhead)

### 2. Pallet-Based Storage Costs (NEW)

Three new rows added to the **CostParameters sheet**:

| cost_type | Default Value | Unit | Description |
|-----------|---------------|------|-------------|
| `storage_cost_fixed_per_pallet` | 0.0 | $/pallet | One-time charge when pallet enters storage |
| `storage_cost_per_pallet_day_frozen` | 0.5 | $/pallet/day | Daily frozen storage cost per pallet |
| `storage_cost_per_pallet_day_ambient` | 0.2 | $/pallet/day | Daily ambient storage cost per pallet |

**Pallet Definition:**
- 1 pallet = 320 units = 32 cases = 44 pallets per truck

**Purpose:**
Accurate storage cost representation with ceiling rounding (partial pallets cost as full pallets).

**Precedence:**
If both pallet-based and unit-based storage costs are specified, pallet-based costs take precedence.

**Impact on Optimization:**
- **Holding costs** calculated at pallet granularity (~18,675 integer variables for 4-week horizon)
- **Partial pallets** cost as full pallets (e.g., 50 units = 1 pallet cost, not 0.156 pallets)
- **Solve time** increases ~2x (20s → 35-45s for 4-week horizon) but remains acceptable

## Migration Steps

### Step 1: Update Network_Config.xlsx

#### Option A: Use Updated Example File (Recommended)

The example file `data/examples/Network_Config.xlsx` has been updated with the new parameters.

**To use:**
```bash
# Copy updated example to your working directory
cp data/examples/Network_Config.xlsx data/my_network_config.xlsx

# Edit with your specific values
# Open in Excel: data/my_network_config.xlsx
```

#### Option B: Manual Update of Existing File

If you have an existing Network_Config.xlsx, follow these steps:

**1. Add Manufacturing Overhead Columns (Locations Sheet)**

Open the **Locations** sheet and add three columns:

| Current Columns | → | Add These Columns → |
|-----------------|---|---------------------|
| ... capacity | → | daily_startup_hours | daily_shutdown_hours | default_changeover_hours |

**For manufacturing locations (type="manufacturing"):**
- `daily_startup_hours`: 0.5 (or your actual value)
- `daily_shutdown_hours`: 0.5 (or your actual value)
- `default_changeover_hours`: 1.0 (or your actual value)

**For non-manufacturing locations:**
- Leave blank or set to 0

**Example:**
```
id    name              type          ... daily_startup_hours daily_shutdown_hours default_changeover_hours
6122  Manufacturing     manufacturing ... 0.5                 0.5                  1.0
6104  QBA-Moorebank     breadroom     ... (blank)             (blank)              (blank)
```

**2. Add Pallet Storage Cost Rows (CostParameters Sheet)**

Open the **CostParameters** sheet and add three rows at the end:

| cost_type | value | unit |
|-----------|-------|------|
| storage_cost_fixed_per_pallet | 0.0 | $/pallet |
| storage_cost_per_pallet_day_frozen | 0.5 | $/pallet/day |
| storage_cost_per_pallet_day_ambient | 0.2 | $/pallet/day |

**Recommended Values:**
- **Fixed cost:** 0.0 (disabled by default - enables "pay per day" model)
- **Frozen:** 0.5 $/pallet/day (~$0.0016/unit/day for 320 units)
- **Ambient:** 0.2 $/pallet/day (~$0.0006/unit/day for 320 units)

**To Convert Existing Unit-Based Costs:**
```
pallet_cost_per_day = unit_cost_per_day × 320

Example:
  If storage_cost_frozen_per_unit_day = 0.002
  Then storage_cost_per_pallet_day_frozen = 0.002 × 320 = 0.64
```

### Step 2: Validate Changes

**Run Parser Test:**
```python
from src.parsers import MultiFileParser

parser = MultiFileParser(
    forecast_file="data/Gfree Forecast.xlsm",
    network_file="data/my_network_config.xlsx"
)

# Should parse without errors
forecast, locations, routes, labor, trucks, costs = parser.parse_all()

# Check overhead parameters parsed correctly
manufacturing_loc = next(l for l in locations if l.type.value == 'manufacturing')
print(f"Startup hours: {manufacturing_loc.daily_startup_hours}")
print(f"Shutdown hours: {manufacturing_loc.daily_shutdown_hours}")
print(f"Changeover hours: {manufacturing_loc.default_changeover_hours}")

# Check pallet costs parsed correctly
print(f"Fixed pallet cost: {costs.storage_cost_fixed_per_pallet}")
print(f"Frozen pallet cost: {costs.storage_cost_per_pallet_day_frozen}")
print(f"Ambient pallet cost: {costs.storage_cost_per_pallet_day_ambient}")
```

**Expected Output:**
```
Startup hours: 0.5
Shutdown hours: 0.5
Changeover hours: 1.0
Fixed pallet cost: 0.0
Frozen pallet cost: 0.5
Ambient pallet cost: 0.2
```

### Step 3: Test Optimization

Run a quick optimization to ensure everything works:

```bash
# Run integration test (should complete in < 60s)
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v

# Expected result: PASSED (solve time < 40s)
```

## Backward Compatibility

**Good News:** Old Network_Config.xlsx files continue to work without modification!

### What Happens If You Don't Update?

**Manufacturing Overhead Columns Missing:**
- Parser uses defaults: startup=0.5h, shutdown=0.5h, changeover=1.0h
- Optimization model works correctly
- No errors, warnings, or breakage

**Pallet Storage Cost Rows Missing:**
- Parser returns `None` for pallet costs
- Model falls back to unit-based storage costs (legacy behavior)
- Optimization works as before (unit-level granularity)

### Recommendation

**Update your files** to benefit from:
1. **Configurable overhead** - adjust to match your actual operations
2. **Accurate storage costs** - pallet-based rounding reflects real warehouse economics
3. **Better cost reporting** - labor costs now include overhead time

## Verification Checklist

After migration, verify:

- [ ] **Locations sheet** has 3 new overhead columns
- [ ] **Manufacturing location** has overhead values (0.5, 0.5, 1.0 or your custom values)
- [ ] **CostParameters sheet** has 3 new pallet cost rows
- [ ] **Parser test** runs without errors
- [ ] **Integration test** passes (test_integration_ui_workflow.py)
- [ ] **Optimization solves** in reasonable time (< 60s for 4-week horizon)
- [ ] **Labor cost breakdown** shows overhead time included
- [ ] **Holding costs** calculated from pallet variables (if enabled)

## Troubleshooting

### Issue 1: "Missing column: daily_startup_hours"

**Cause:** Parser expected overhead column but file doesn't have it

**Solution:** Add the three overhead columns to Locations sheet (see Step 1)

**Alternative:** Use backward-compatible parser (columns are optional)

### Issue 2: Optimization solve time increased significantly

**Cause:** Pallet-based holding costs add integer variables (~18,675 for 4-week horizon)

**Expected:** Solve time increases from ~20s to ~35-45s (acceptable)

**Problem:** If solve time > 2 minutes, check:
- MIP gap tolerance (should be 1% or higher)
- Planning horizon (4 weeks should solve in < 60s)
- Solver (CBC should work; Gurobi/CPLEX are faster)

**Workaround:** Disable pallet costs by setting all storage rates to 0.0

### Issue 3: "Parameter 'storage_cost_fixed_per_pallet' not found"

**Cause:** Parser looking for pallet cost parameters

**Solution:** Add the three pallet cost rows to CostParameters sheet

**Alternative:** These parameters are optional - leave them out for unit-based costs

### Issue 4: Labor costs seem too high/low

**Check:** Overhead time is now included in labor hours

**Expected behavior:**
- **Old:** labor_hours = production_time only
- **New:** labor_hours = production_time + overhead_time

**Typical increase:** 10-15% (depends on production volume and overhead parameters)

**Validation:** Check `solution['labor_hours_by_date']` - should show overhead component

## Cost Calculation Changes

### Manufacturing Overhead Time

**Formula:**
```python
overhead_time = startup + shutdown + (num_products - 1) × changeover

Examples:
  - 0 products: 0h overhead
  - 1 product:  0.5h startup + 0.5h shutdown = 1.0h
  - 2 products: 1.0h + 1×1.0h changeover = 2.0h
  - 3 products: 1.0h + 2×1.0h changeover = 3.0h
```

### Pallet-Based Storage Costs

**Formula:**
```python
pallet_count = ceil(inventory_units / 320)
holding_cost = pallet_count × rate_per_pallet_per_day

Examples (ambient @ $0.20/pallet/day):
  - 50 units:  ceil(50/320) = 1 pallet → $0.20/day
  - 320 units: ceil(320/320) = 1 pallet → $0.20/day
  - 350 units: ceil(350/320) = 2 pallets → $0.40/day
```

**Old (unit-based @ $0.0006/unit/day):**
```python
  - 50 units:  50 × $0.0006 = $0.03/day (underestimate!)
  - 320 units: 320 × $0.0006 = $0.19/day
  - 350 units: 350 × $0.0006 = $0.21/day
```

**Difference:** Pallet-based costs are more accurate for small quantities (partial pallets)

## Performance Impact

| Metric | Before (Unit-Based) | After (Pallet-Based) | Change |
|--------|---------------------|----------------------|--------|
| **Solve Time (4-week)** | 20-25s | 35-45s | +15-20s (2x) |
| **Integer Variables** | 1,487 | 20,162 | +18,675 (pallets) |
| **Constraints** | 9,768 | 9,768 + 18,675 | +18,675 (ceiling) |
| **Solution Quality** | Optimal | Optimal | Same |
| **Fill Rate** | ≥95% | ≥95% | Same |

**Conclusion:** Performance impact is acceptable for added cost accuracy.

## Example Files

**Before Migration:**
```
data/examples/Network_Config_OLD.xlsx (legacy format - still works!)
├── Locations (6 columns)
├── Routes
├── LaborCalendar
├── TruckSchedules
└── CostParameters (12 rows)
```

**After Migration:**
```
data/examples/Network_Config.xlsx (updated format)
├── Locations (9 columns - added 3 overhead columns)
├── Routes
├── LaborCalendar
├── TruckSchedules
└── CostParameters (15 rows - added 3 pallet cost rows)
```

## See Also

- **EXCEL_TEMPLATE_SPEC.md** - Complete Excel format specification
- **PIECEWISE_LABOR_COST_IMPLEMENTATION.md** - Labor cost modeling details
- **CHANGEOVER_TIMES.md** - Manufacturing overhead explanation
- **CLAUDE.md** - Project documentation (updated with parameter changes)

## Support

If you encounter issues during migration:

1. Check this guide's Troubleshooting section
2. Review EXCEL_TEMPLATE_SPEC.md for format details
3. Run validation tests (Step 2 above)
4. File issue at https://github.com/anthropics/claude-code/issues

## Summary

✅ **Migration is optional** - old files continue to work
✅ **Backward compatible** - defaults provided for missing parameters
✅ **Performance acceptable** - 2x solve time increase for pallet accuracy
✅ **Cost accuracy improved** - overhead time and pallet rounding included
✅ **Fully tested** - integration tests pass with new parameters

**Recommendation:** Migrate when convenient to benefit from configurable parameters and improved cost modeling.
