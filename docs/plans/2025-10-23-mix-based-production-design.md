# Mix-Based Production Design

**Date:** 2025-10-23
**Status:** Approved
**Author:** Claude Code (with user validation)

## Executive Summary

Transform the production planning optimization model from continuous unit-based production to discrete mix-based production. In the real baking process, products are manufactured in batches (mixes) of fixed sizes - for example, one mix might produce 415 units. This design enforces that production quantities must be integer multiples of the mix size for each SKU.

## Business Context

**Current Model:** Production can be any continuous value (e.g., 1,247.3 units)

**Reality:** Production happens in discrete mixes where each mix produces a fixed number of units (e.g., 415 units per mix). We can only make 0, 1, 2, 3... mixes, resulting in 0, 415, 830, 1245... units.

**Impact:** Current model allows fractional production that's impossible to execute in the real manufacturing process.

## Requirements

### Functional Requirements
1. Production must be in integer multiples of product-specific mix sizes
2. Each product has its own `units_per_mix` parameter (e.g., Product A = 415, Product B = 387)
3. Mix sizes can be any positive integer (not necessarily multiples of 10-unit cases)
4. Labor time calculations remain unit-based (total_units / production_rate)
5. Changeover tracking stays at product level (one changeover per product per day, regardless of mix count)
6. UI must display mix counts by product by day

### Non-Functional Requirements
1. Solution time should remain < 400s for 4-week horizon (current baseline: 300s)
2. No backward compatibility required - existing templates must be updated
3. All existing tests must pass
4. Integration test must pass before commit

## Design Decisions

### Key Decisions Made

**1. Mix-Case Relationship**
- **Decision:** Mix sizes can be any value (not necessarily divisible by 10)
- **Rationale:** Reflects real manufacturing where mix sizes (e.g., 415 units) don't align with case sizes (10 units)
- **Impact:** Cases are relevant only for shipping/truck loading, not production planning

**2. Fractional Cases Handling**
- **Decision:** Cases are only for shipping, not production
- **Rationale:** Cleanest separation - production creates units in mix quantities, cases/pallets only matter for truck loading
- **Impact:** Production tracked in units, case/pallet constraints apply only to distribution

**3. Labor Time Calculation**
- **Decision:** Keep units-per-hour rate (production_rate from config)
- **Rationale:** Simpler, uses existing logic, assumes linear time scaling
- **Formula:** Labor hours = (mix_count × units_per_mix) / production_rate

**4. Changeover Costs**
- **Decision:** One changeover per product per day (current behavior)
- **Rationale:** Changeover = product startup, regardless of how many mixes made
- **Impact:** 3 mixes of Product A on Monday counts as 1 changeover

**5. Daily Capacity Constraints**
- **Decision:** Only labor hours constrain production (no mix count limits)
- **Rationale:** If labor hours allow it, unlimited mixes can be made
- **Impact:** No additional integer constraints on daily mix counts

**6. Compatibility Mode**
- **Decision:** Replace unit-based completely with mix-based
- **Rationale:** Clean design, no dual-mode complexity
- **Impact:** All Excel templates must add `units_per_mix` column

### Architectural Approach

**Chosen:** Reformulate production as derived expression from `mix_count` variable

**Alternatives Considered:**
1. Add `mix_count` variable with linking constraint: `production = mix_count × units_per_mix`
   - Rejected: Creates redundant variables
2. Make production variable with discrete stepped domain: `{0, mix_size, 2×mix_size, ...}`
   - Rejected: Complex domain definition, harder to report mix counts

**Selected Approach Benefits:**
- Fewer total variables (production is expression, not variable)
- Explicit mix tracking for UI reporting
- Tighter formulation (implicit constraint enforcement)
- Cleaner model structure

## Technical Design

### 1. Data Model Changes

**File:** `src/models/product.py`

```python
@dataclass
class Product:
    product_id: str
    name: str
    shelf_life_ambient_days: int
    shelf_life_frozen_days: int
    shelf_life_after_thaw_days: int
    units_per_mix: int  # NEW: Number of units produced per mix

    def __post_init__(self):
        if self.units_per_mix <= 0:
            raise ValueError(f"units_per_mix must be positive, got {self.units_per_mix}")
```

### 2. Excel Template Changes

**File:** `data/examples/Network_Config.xlsx`

**New Column:** Products sheet (or Forecast sheet if products defined there)
- Column name: `units_per_mix`
- Data type: Integer
- Validation: Must be > 0
- Example values: 415, 387, 520

### 3. Parser Changes

**File:** `src/parsers/excel_parser.py`

```python
def _parse_products(self, df_products: pd.DataFrame) -> Dict[str, Product]:
    """Parse products with units_per_mix."""
    products = {}
    for _, row in df_products.iterrows():
        product = Product(
            product_id=row['product_id'],
            name=row['name'],
            shelf_life_ambient_days=int(row['shelf_life_ambient_days']),
            shelf_life_frozen_days=int(row['shelf_life_frozen_days']),
            shelf_life_after_thaw_days=int(row['shelf_life_after_thaw_days']),
            units_per_mix=int(row['units_per_mix'])  # NEW
        )
        products[product.product_id] = product
    return products
```

**Error Handling:** If `units_per_mix` column is missing, raise clear error directing user to update template.

### 4. Optimization Model Changes

**File:** `src/optimization/unified_node_model.py`

#### 4.1 Replace Production Variable

**OLD:**
```python
model.production = Var(
    model.manufacturing_nodes,
    model.products,
    model.dates,
    domain=NonNegativeReals
)
```

**NEW:**
```python
# Integer mix_count variable
model.mix_count = Var(
    model.manufacturing_nodes,
    model.products,
    model.dates,
    domain=NonNegativeIntegers,
    bounds=self._calculate_mix_bounds
)

# Production as derived expression
def production_rule(m, loc, p, d):
    units_per_mix = self.products[p].units_per_mix
    return m.mix_count[loc, p, d] * units_per_mix

model.production = Expression(
    model.manufacturing_nodes,
    model.products,
    model.dates,
    rule=production_rule
)
```

#### 4.2 Mix Bounds Calculation

```python
def _calculate_mix_bounds(self, model, loc, p, d):
    """Calculate upper bound on mix count for a product."""
    # Maximum production hours per day (including overtime)
    max_hours = 14  # From labor calendar
    production_rate = self.manufacturing_site.production_rate  # e.g., 1400 units/hour
    units_per_mix = self.products[p].units_per_mix

    # Maximum mixes = ceiling(max_hours × production_rate / units_per_mix)
    max_units = max_hours * production_rate
    max_mixes = math.ceil(max_units / units_per_mix)

    return (0, max_mixes)
```

**Example:** For 415-unit mix:
- max_units = 14h × 1400 units/h = 19,600 units
- max_mixes = ceil(19,600 / 415) = ceil(47.23) = 48 mixes

#### 4.3 Update Start Detection Constraint

**OLD:**
```python
def start_detection_rule(m, loc, p, d):
    max_production = ... # Big-M value
    return m.product_start[loc, p, d] >= m.production[loc, p, d] / max_production
```

**NEW:**
```python
def start_detection_rule(m, loc, p, d):
    max_mixes = self._calculate_max_mixes(p)
    return m.product_start[loc, p, d] >= m.mix_count[loc, p, d] / max_mixes
```

#### 4.4 Labor Capacity Constraint

**No changes needed** - constraint references `model.production`, which is now automatically computed as `mix_count × units_per_mix`.

**Critical:** Ensure production_rate comes from config (`self.manufacturing_site.production_rate`), not hardcoded 1400.

### 5. Solution Extraction Changes

**File:** `src/optimization/unified_node_model.py`

```python
def extract_solution(self) -> Dict:
    """Extract solution including mix counts."""
    solution = {
        'status': self.solver_status,
        'objective_value': self.objective_value,
        'mix_counts': {},  # NEW
        'production': {},
        'inventory': {},
        # ... other solution components
    }

    # Extract mix counts
    for loc in self.model.manufacturing_nodes:
        for p in self.model.products:
            for d in self.model.dates:
                mix_count = value(self.model.mix_count[loc, p, d])
                if mix_count > 0:
                    key = (loc, p, d)
                    solution['mix_counts'][key] = {
                        'mix_count': int(mix_count),
                        'units': int(mix_count * self.products[p].units_per_mix)
                    }

    return solution
```

### 6. UI Changes

**File:** `ui/pages/2_Planning.py`

#### 6.1 Add Mix Count Metric

```python
# Update summary metrics from 4 to 5 columns
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Production", f"{total_units:,} units")
col2.metric("Total Mixes", f"{total_mixes:,} mixes")  # NEW
col3.metric("Labor Hours", f"{total_hours:,.1f} hrs")
col4.metric("Changeovers", f"{total_changeovers}")
col5.metric("Fill Rate", f"{fill_rate:.1%}")
```

#### 6.2 Add Mix Production Schedule Table

```python
st.subheader("Mix Production Schedule")
if 'mix_counts' in solution:
    mix_df = pd.DataFrame([
        {
            'Date': d,
            'Product': p,
            'Mixes': solution['mix_counts'][(loc, p, d)]['mix_count'],
            'Units': solution['mix_counts'][(loc, p, d)]['units']
        }
        for (loc, p, d) in solution['mix_counts'].keys()
    ])
    st.dataframe(mix_df)
```

## Testing Strategy

### Unit Tests

**File:** `tests/test_models.py`
- Test Product model with `units_per_mix` attribute
- Test validation: units_per_mix > 0
- Test validation: units_per_mix = 0 raises ValueError
- Test validation: units_per_mix < 0 raises ValueError

**File:** `tests/test_parsers.py`
- Test parser reads `units_per_mix` from Excel
- Test parser raises error if column missing

**File:** `tests/test_unified_node_model.py`
- Test `mix_count` variable creation with correct bounds
- Test `production` expression computes correctly
- Test `_calculate_mix_bounds()` method
- Test start_detection constraint uses mix_count
- Test small example: 2 products, 2 days, verify integer multiples

### Integration Tests

**File:** `tests/test_integration_ui_workflow.py`

**CRITICAL REGRESSION GATE:**
- Update test data files to include `units_per_mix` column
- Verify 4-week solve completes successfully
- Verify solution contains `mix_counts` key
- Verify all production values are integer multiples of respective mix sizes
- Verify solve time < 400s (update threshold from 30s)

**New Regression Test:**
```python
def test_production_is_multiple_of_mix_size(solution, products):
    """Ensure production is always mix_count × units_per_mix."""
    for (loc, p, d), prod_data in solution['production'].items():
        units = prod_data['units']
        mix_size = products[p].units_per_mix
        assert units % mix_size == 0, \
            f"Production {units} not multiple of mix size {mix_size} for product {p}"

        # Verify mix_count entry exists and matches
        if (loc, p, d) in solution['mix_counts']:
            mix_count = solution['mix_counts'][(loc, p, d)]['mix_count']
            assert units == mix_count * mix_size, \
                f"Production {units} != mix_count {mix_count} × mix_size {mix_size}"
```

### Performance Benchmarks

**Test Scenarios:**
1. 2-week horizon with real data (GFree Forecast.xlsm)
2. 4-week horizon with real data
3. 6-week horizon with real data

**Metrics to Capture:**
- Solve time (seconds)
- Number of integer variables
- Number of constraints
- MIP gap at termination
- Objective value

**Baseline:**
- Current model: ~300s for 4-week horizon

**Targets:**
- 2-week: < 100s
- 4-week: < 400s (acceptable given 300s baseline)
- 6-week: TBD (establish baseline first)

**Expected Impact:**
- Integer variables harder to solve than continuous
- But fewer total variables (production is expression)
- Tighter formulation may improve solve
- Net effect: likely 280-350s for 4-week (±10-15%)

## Documentation Updates

### CLAUDE.md
**Section:** Key Design Decisions #13
- Update to reflect mix-based production
- Note: Production in discrete mixes, not continuous units

**Section:** Manufacturing Operations
- Mention mix sizes in production capacity discussion

**Section:** Technology Stack
- Update performance benchmarks with new timings

### EXCEL_TEMPLATE_SPEC.md
**New Section:** Products Sheet - units_per_mix
```markdown
#### units_per_mix
- **Type:** Integer
- **Required:** Yes
- **Description:** Number of units produced per mix/batch
- **Validation:** Must be positive integer
- **Example:** 415, 387, 520
- **Business Rule:** Each product has a fixed batch size. Production can only occur in integer multiples of this value.
```

**Add Migration Guide:**
```markdown
## Migration from Unit-Based to Mix-Based Production

Existing templates must be updated:

1. Add `units_per_mix` column to Products sheet
2. Populate with actual mix sizes for each product
3. Validate all values are positive integers
4. Test with small planning horizon first

**Example:**
| product_id | name | shelf_life_ambient_days | ... | units_per_mix |
|------------|------|-------------------------|-----|---------------|
| PROD_A     | ...  | 17                      | ... | 415           |
| PROD_B     | ...  | 17                      | ... | 387           |
```

### UNIFIED_NODE_MODEL_SPECIFICATION.md

**Section:** Decision Variables
```markdown
#### mix_count[loc, p, d]
- **Type:** Integer variable
- **Domain:** NonNegativeIntegers
- **Bounds:** (0, max_mixes) where max_mixes = ceil(max_hours × production_rate / units_per_mix)
- **Purpose:** Number of mixes of product p produced at location loc on date d
- **Indexed by:** Manufacturing nodes × Products × Dates

#### production[loc, p, d]
- **Type:** Expression (derived, not a variable)
- **Formula:** production[loc, p, d] = mix_count[loc, p, d] × units_per_mix[p]
- **Purpose:** Total units of product p produced at location loc on date d
- **Note:** Automatically enforces integer multiples of mix size
```

**Section:** Constraints - Update Start Detection
```markdown
#### Start Detection (start_detection_con)
**Formula:**
```
product_start[loc, p, d] >= mix_count[loc, p, d] / max_mixes[p]
```

**Purpose:** Binary product_start = 1 when mix_count > 0 (product is produced)

**Note:** Changed from production-based to mix_count-based detection
```

**Section:** Model Statistics
Update variable counts:
- Before: production variables = |manufacturing_nodes| × |products| × |dates|
- After: mix_count variables (integer) = |manufacturing_nodes| × |products| × |dates|
- Note: production is now an expression (0 additional variables)
- Net change: Same variable count, but integers instead of continuous

**Example for 4-week horizon (28 days, 1 manufacturing node, 5 products):**
- mix_count variables: 1 × 5 × 28 = 140 integer variables
- production expressions: 140 (no additional variables)

## Migration Guide for Users

### Step-by-Step Migration

1. **Update Excel Template**
   - Open your Network_Config.xlsx file
   - Locate the Products sheet (or Forecast sheet if products defined there)
   - Add new column: `units_per_mix`
   - Fill in mix sizes for each product (get from manufacturing team)
   - Validate all values are positive integers
   - Save the file

2. **Verify Data**
   - Open file in Excel
   - Check that `units_per_mix` column has no blanks or zeros
   - Check that values make sense (typically 100-1000 units)

3. **Test with Small Horizon**
   - Start with 1-week planning horizon
   - Run optimization
   - Verify results:
     - Check production values are multiples of mix sizes
     - Check mix counts display in UI
     - Check solve completes successfully

4. **Scale to Production Horizon**
   - Gradually increase horizon: 2 weeks → 4 weeks
   - Monitor solve times
   - Compare results with previous unit-based runs

5. **Validate Business Logic**
   - Verify production quantities align with manufacturing reality
   - Check that mix counts make operational sense
   - Confirm labor hours calculations are correct

## Implementation Plan

### Git Workflow

1. Create feature branch: `feature/mix-based-production`
2. Implement changes in order:
   - Data model (Product.units_per_mix)
   - Excel template update
   - Parser changes
   - Optimization model refactor
   - Solution extraction
   - UI updates
   - Unit tests
   - Integration test updates
   - Documentation
3. Run full test suite before each commit
4. Run integration test as final gate
5. Create PR with:
   - Summary of changes
   - Performance benchmark results
   - Migration guide for users
   - Breaking changes notice

### Success Criteria

✅ All unit tests pass (existing + new)
✅ Integration test passes with 4-week horizon
✅ Production values are integer multiples of mix sizes
✅ UI displays mix counts correctly
✅ Solve time ≤ 400s for 4-week horizon
✅ Documentation updated and clear
✅ Migration guide provided

## Risks and Mitigations

### Risk 1: Slower Solve Times
**Impact:** High
**Probability:** Medium
**Mitigation:**
- Tighten bounds on mix_count using demand-based upper limits
- Add valid inequalities to strengthen integer formulation
- Consider commercial solvers (Gurobi/CPLEX) if open-source too slow
- Implement time limits and MIP gap tolerances

### Risk 2: Existing Templates Break
**Impact:** High
**Probability:** High (by design - no backward compatibility)
**Mitigation:**
- Clear error messages when `units_per_mix` missing
- Provide migration guide with examples
- Update all example templates in repository
- Communicate breaking change clearly in release notes

### Risk 3: Integer Infeasibility
**Impact:** Medium
**Probability:** Low
**Mitigation:**
- Allow shortages (if configured) to prevent infeasibility
- Verify mix size upper bounds are reasonable
- Test with various mix size combinations
- Add diagnostic output if solve fails

## Future Enhancements

1. **Mix-Level Changeover Costs** (if needed)
   - Track changeover between consecutive mixes
   - Cost per mix startup, not just per product per day

2. **Mix Time Variability**
   - Each mix has fixed production time (not linear with units)
   - More realistic for batch processes

3. **Mix Inventory Tracking**
   - Track completed mixes separately from units
   - Support partial mix consumption scenarios

4. **Campaign Planning**
   - Minimum run lengths (e.g., must make at least 3 mixes if product is started)
   - Sequence-dependent changeovers between products

## Appendix: Mathematical Formulation

### Current Model (Unit-Based)

**Variables:**
```
production[loc, p, d] ∈ ℝ₊
```

**Constraints:**
```
production[loc, p, d] ≤ max_daily_production
```

### New Model (Mix-Based)

**Variables:**
```
mix_count[loc, p, d] ∈ ℤ₊
production[loc, p, d] = mix_count[loc, p, d] × units_per_mix[p]  (expression)
```

**Constraints:**
```
mix_count[loc, p, d] ≤ max_mixes[p]
where max_mixes[p] = ⌈max_hours × production_rate / units_per_mix[p]⌉
```

**Implication:**
- Production automatically in discrete steps: {0, units_per_mix, 2×units_per_mix, ...}
- No additional constraints needed to enforce discrete production
- Tighter formulation: integer variable with expression vs. continuous variable with modulo constraint
