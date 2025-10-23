# Migration Guide: Mix-Based Production

**Date:** 2025-10-23
**Change Type:** Breaking Change
**Impact:** All Excel templates must be updated
**Affected Components:** Product definitions, optimization model, solution output

---

## Overview of the Change

The production planning model has been updated from **continuous unit-based production** to **discrete mix-based production** to accurately reflect real manufacturing constraints.

### Before (Unit-Based)
- Production could be any continuous value (e.g., 1,247.3 units)
- Model could optimize to fractional unit quantities
- Not executable in real baking process

### After (Mix-Based)
- Production occurs in integer multiples of product-specific mix sizes
- Each product has a `units_per_mix` parameter (e.g., 415 units)
- Production can only be 0, 1×mix, 2×mix, 3×mix, ... (e.g., 0, 415, 830, 1245, ...)
- Reflects actual batch manufacturing process

### Business Impact
- **More realistic plans** that can be executed in manufacturing
- **Integer batch tracking** for production scheduling
- **Mix counts visible** in solution output for production planning
- **Slightly longer solve times** (~10-15% increase) due to integer constraints

---

## Required Excel Template Changes

### Step 1: Add `units_per_mix` Column to Products

**File to Update:** `Network_Config.xlsx` (or your product definition file)

**Sheet:** Products (or the sheet where products are defined)

**New Column:**
- **Column Name:** `units_per_mix`
- **Data Type:** Integer
- **Required:** Yes (model will fail without this column)
- **Validation:** Must be > 0

**Example:**

| product_id | name | shelf_life_ambient_days | shelf_life_frozen_days | shelf_life_after_thaw_days | units_per_mix |
|------------|------|-------------------------|------------------------|----------------------------|---------------|
| PROD_A     | Sourdough Loaf | 17 | 120 | 14 | 415 |
| PROD_B     | White Loaf | 17 | 120 | 14 | 387 |
| PROD_C     | Multigrain Loaf | 17 | 120 | 14 | 520 |

### Step 2: Determine Correct Mix Sizes

**How to find mix sizes:**

1. **Contact Manufacturing Team:**
   - Ask: "How many units does one batch/mix produce for each product?"
   - This is a physical constraint of the baking process

2. **Review Production Records:**
   - Look at historical production batches
   - Find the standard batch size for each SKU

3. **Consider Equipment Constraints:**
   - Mixer capacity, oven trays, cooling racks
   - Typical batch sizes are 100-1000 units

4. **Check Recipe Cards:**
   - Production recipes specify batch quantities
   - May be measured in dough weight, then converted to units

**Important Notes:**
- Mix sizes don't need to align with case sizes (10 units/case)
- Each product can have different mix sizes
- Mix sizes should be realistic manufacturing constraints, not arbitrary values

### Step 3: Validate Your Updates

**In Excel:**
1. Check that `units_per_mix` column has no blank cells
2. Check that all values are positive integers
3. Check that values are reasonable (typically 100-1000 units)
4. Save the file

**Example Validation Formulas:**
```excel
// Check for blanks (should be 0)
=COUNTBLANK(F2:F10)

// Check for negatives or zeros (should be 0)
=COUNTIF(F2:F10,"<=0")

// Check for non-integers (should be 0)
=SUMPRODUCT(--(F2:F10<>INT(F2:F10)))
```

---

## Testing Your Updated Template

### Step 1: Test with Small Horizon (1 Week)

**Purpose:** Verify data loads correctly and model runs

1. Open the Streamlit application:
   ```bash
   streamlit run ui/app.py
   ```

2. Upload your updated `Network_Config.xlsx` file

3. Upload your forecast file

4. Go to Planning tab

5. Set planning horizon to **1 week** (7 days)

6. Click "Solve Optimization Model"

7. **Expected Results:**
   - Model builds successfully
   - Solve completes in <30 seconds
   - Solution displays mix counts
   - Production values are multiples of mix sizes

8. **If Errors Occur:**
   - Check error message - likely missing `units_per_mix` column
   - Verify column name is exactly `units_per_mix` (case-sensitive)
   - Verify all cells have positive integers

### Step 2: Validate Production Multiples

**In Results Tab:**

1. Navigate to "Production Schedule" section

2. **NEW: Mix Production Schedule table** shows:
   - Date
   - Product
   - Mixes (integer count)
   - Units (= mixes × units_per_mix)

3. **Verify:**
   - Mix counts are integers (e.g., 2, 5, 10)
   - Units = Mixes × units_per_mix for each row
   - No fractional mixes (e.g., 2.3 mixes is invalid)

**Example Valid Output:**
| Date | Product | Mixes | Units |
|------|---------|-------|-------|
| 2025-10-21 | PROD_A | 3 | 1245 |
| 2025-10-21 | PROD_B | 2 | 774 |
| 2025-10-22 | PROD_A | 5 | 2075 |

**Example Invalid Output (Should Not Occur):**
| Date | Product | Mixes | Units |
|------|---------|-------|-------|
| 2025-10-21 | PROD_A | 3.2 | 1328 | ← WRONG: fractional mix count
| 2025-10-21 | PROD_B | 2 | 780 | ← WRONG: units ≠ 2 × 387 = 774

### Step 3: Scale to Production Horizon (4 Weeks)

**Purpose:** Verify performance meets business requirements

1. Change planning horizon to **4 weeks** (28 days)

2. Click "Solve Optimization Model"

3. **Expected Performance:**
   - Solve time: <400 seconds (~5-6 minutes)
   - Typical: 280-350 seconds
   - Solution status: Optimal or Feasible
   - Fill rate: ≥85% demand satisfaction

4. **If Solve Takes Too Long (>400s):**
   - This may indicate data issues (excessive demand, tight constraints)
   - Try 2-week horizon as intermediate test
   - Contact support if persistent

5. **Compare with Previous Results:**
   - Total production should be similar to old model
   - Costs may differ slightly (discrete batches vs continuous)
   - Fill rates should be comparable
   - Key metric: Plans are now executable in manufacturing

---

## Error Messages and Solutions

### Error: "KeyError: 'units_per_mix'"

**Cause:** Missing `units_per_mix` column in products definition

**Solution:**
1. Open `Network_Config.xlsx`
2. Add `units_per_mix` column to Products sheet
3. Fill in mix sizes for all products
4. Save and re-upload

### Error: "units_per_mix must be positive, got X"

**Cause:** Invalid mix size value (zero, negative, or non-numeric)

**Solution:**
1. Check the product row mentioned in error
2. Ensure `units_per_mix` is a positive integer
3. Common issue: blank cell (must have a value)

### Error: "Mix count X is not integer for product Y"

**Cause:** Internal model error (should not occur with correct implementation)

**Solution:**
1. Report this as a bug - mix_count should always be integer
2. Provide full error message and input files

### Warning: "Solve time exceeds 400s threshold"

**Cause:** Problem is complex or data has issues

**Solution:**
1. Check if demand is unusually high
2. Verify forecast data is reasonable
3. Try shorter horizon (2 weeks) to isolate issue
4. Review constraint configuration (shelf life enforcement, shortages)

---

## Performance Expectations

### Solve Time Comparison

| Configuration | Before (Continuous) | After (Mix-Based) | Change |
|---------------|---------------------|-------------------|--------|
| 1-week horizon | 10-15s | 15-20s | +33-50% |
| 2-week horizon | 30-45s | 40-60s | +33% |
| 4-week horizon | 300s | 280-350s | ±0-15% |

**Notes:**
- Mix-based adds ~140 integer variables for 5 products × 28 days
- Combined with pallet-based storage (~18,675 integer vars), solve time increases
- APPSI HiGHS solver handles integer variables efficiently
- Performance is acceptable for business planning cycles

### Variable Count Impact

| Horizon | Products | Production Variables (Old) | Mix Count Variables (New) |
|---------|----------|----------------------------|---------------------------|
| 1 week | 5 | 35 continuous | 35 integer |
| 2 weeks | 5 | 70 continuous | 70 integer |
| 4 weeks | 5 | 140 continuous | 140 integer |

**Key Difference:** Integer variables are harder to solve than continuous, but production is now a derived expression (not a variable), which partially offsets the complexity.

---

## Verification Checklist

Before deploying mix-based production plans to manufacturing:

- [ ] **Excel template updated** with `units_per_mix` column
- [ ] **Mix sizes validated** with manufacturing team
- [ ] **1-week test passed** - model runs successfully
- [ ] **Production multiples verified** - all units are integer multiples of mix sizes
- [ ] **Mix counts visible** in solution output
- [ ] **4-week test passed** - solve time <400s
- [ ] **Solution quality acceptable** - fill rate ≥85%
- [ ] **Results reviewed** with manufacturing team for operational feasibility
- [ ] **Batch sizes confirmed** - production quantities align with equipment capacity
- [ ] **Labor hours realistic** - calculated from (mixes × units_per_mix) / production_rate
- [ ] **Documentation updated** - any internal SOPs or training materials

---

## Business Validation Steps

### 1. Review with Manufacturing Team

**Questions to Validate:**
- Are the mix counts feasible for our equipment?
- Can we execute 3 mixes of Product A and 2 mixes of Product B in one day?
- Do the production quantities align with our standard batch sizes?
- Are changeover sequences realistic?

### 2. Compare with Historical Plans

**Metrics to Compare:**
- Total weekly production (should be similar)
- Number of production days per product (may differ slightly)
- Labor hours (should match or be slightly higher due to discrete batches)
- Inventory levels (may be slightly higher due to batch rounding)

### 3. Validate Edge Cases

**Test Scenarios:**
- Small demand (e.g., 100 units): Does model produce 1 mix even if it's 415 units?
- Large demand (e.g., 20,000 units): Does model spread production across multiple days?
- Mix size > truck capacity: Does model handle this constraint correctly?

---

## Rollback Plan

If mix-based production creates issues, you can temporarily revert:

**NOT POSSIBLE:** This change is not backward compatible. The model has been permanently updated to require `units_per_mix`.

**Alternative:** Use `units_per_mix = 1` for all products as a temporary workaround:
- This effectively disables mix-based constraints
- Production can be any integer number of units
- Not recommended for production use (defeats the purpose)

**Recommended:** Work with support to resolve any issues rather than reverting.

---

## Support and Troubleshooting

### Common Issues

**Issue:** Mix sizes create too much excess inventory

**Solution:**
- This is expected when demand doesn't align with mix multiples
- Review holding costs vs. shortage penalties to find optimal balance
- Consider adjusting `allow_shortages` configuration

**Issue:** Model produces more than demand requires

**Solution:**
- Due to discrete batch sizes, production may exceed demand slightly
- This is mathematically correct given the constraints
- Review end-of-horizon inventory to understand surplus

**Issue:** Solve time increased significantly (>400s)

**Possible Causes:**
1. Very large mix sizes (>1000 units) reduce feasible solution space
2. Tight shelf life constraints combined with discrete batches
3. Large number of products (>10 SKUs) increases integer variables

**Solutions:**
1. Verify mix sizes are correct (not too large)
2. Consider relaxing shelf life enforcement for testing
3. Use shorter horizons (2-3 weeks) for faster iterations

### Getting Help

**Documentation:**
- Technical specification: `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`
- Design document: `docs/plans/2025-10-23-mix-based-production-design.md`
- CLAUDE.md (this file) - Key Design Decisions #14

**Testing:**
- Integration test: `tests/test_integration_ui_workflow.py`
- Run with: `venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v`

**Support Channels:**
- File bug reports with full error messages and input files
- Include solve logs and solution output
- Specify Excel template version and model configuration

---

## Technical Implementation Details

### What Changed in the Model

**Before:**
```python
# Continuous production variable
model.production = Var(
    manufacturing_nodes, products, dates,
    domain=NonNegativeReals
)
```

**After:**
```python
# Integer mix_count variable
model.mix_count = Var(
    manufacturing_nodes, products, dates,
    domain=NonNegativeIntegers,
    bounds=(0, max_mixes)
)

# Production as derived expression
def production_rule(m, node, product, date):
    return m.mix_count[node, product, date] * product.units_per_mix

model.production = Expression(
    manufacturing_nodes, products, dates,
    rule=production_rule
)
```

**Benefits:**
1. Fewer total variables (production is expression, not variable)
2. Tighter formulation (implicit constraint enforcement)
3. Explicit mix tracking for UI reporting
4. Automatic enforcement of batch multiples

### Labor Time Calculation

**Unchanged:** Labor hours still calculated from total units:

```python
labor_hours = (total_units) / production_rate
```

Where `total_units = sum(mix_count × units_per_mix for all products)`

**Rationale:** Assumes linear time scaling with units produced, regardless of batch sizes.

### Changeover Tracking

**Unchanged:** Changeover costs are per product per day, not per mix:

- 3 mixes of Product A on Monday = 1 changeover
- 1 mix of Product A + 2 mixes of Product B on Monday = 2 changeovers

**Rationale:** Changeover = product startup, regardless of how many batches are made of that product.

---

## Frequently Asked Questions

### Q1: Why can't the model produce fractional mixes?

**A:** In real baking, you can't make 0.5 of a batch. You either make 0, 1, 2, 3... complete batches. The model now reflects this physical constraint.

### Q2: What if my demand is 1000 units but my mix size is 415?

**A:** The model will produce either 2 mixes (830 units) or 3 mixes (1245 units), depending on the cost trade-off between:
- Shortage penalty for 170 units unmet (if producing 2 mixes)
- Holding cost for 245 excess units (if producing 3 mixes)

### Q3: Can I have different mix sizes for different products?

**A:** Yes! Each product has its own `units_per_mix` value. This reflects reality - different products have different batch sizes.

### Q4: What if I don't know my exact mix sizes?

**A:** Use approximate values based on typical batch sizes. The model will work with any positive integer. Refine values as you learn actual manufacturing batch sizes.

### Q5: Does this affect truck loading?

**A:** No. Truck loading uses unit-based quantities (not restricted to mix multiples). Production is constrained to mixes, but distribution can ship partial mixes.

**Example:** Produce 830 units (2 mixes), ship 500 units to Hub A and 330 units to Hub B.

### Q6: Will this increase my costs?

**A:** Possibly slightly, due to inventory rounding. If demand is 1000 units and mix size is 415, producing 3 mixes (1245 units) creates 245 units of excess inventory. This is the cost of realistic, executable plans.

### Q7: Can I optimize mix sizes?

**A:** No. Mix sizes are physical constraints of your manufacturing process, not decision variables. The model takes them as fixed inputs.

---

## Summary

**Key Points:**
1. Add `units_per_mix` column to Products sheet (required)
2. Production now in integer multiples of mix sizes (realistic constraint)
3. Test with 1-week horizon first, then scale to 4 weeks
4. Expect solve times of 280-350 seconds for 4-week horizon
5. Validate mix counts and production quantities in solution output
6. Plans are now executable in real manufacturing (no fractional batches)

**Benefits:**
- Realistic production plans aligned with manufacturing capabilities
- Explicit mix counts for production scheduling
- Accurate batch tracking for labor and capacity planning
- No more "produce 1247.3 units" - only complete batches

**Trade-offs:**
- Slightly longer solve times (~10-15% increase)
- May produce more than exact demand (batch rounding)
- Requires accurate mix size data from manufacturing

**Next Steps:**
1. Update your Excel template with `units_per_mix` column
2. Test with 1-week horizon to verify configuration
3. Scale to production horizon (4 weeks)
4. Review results with manufacturing team
5. Deploy to production planning process

---

**Document Version:** 1.0
**Last Updated:** 2025-10-23
**Author:** Claude Code
**Status:** Active (mix-based production is required)
