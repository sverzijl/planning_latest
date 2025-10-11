# Packaging Constraints Implementation Checklist

## Quick Reference for Pyomo Expert

### Prerequisites
- [ ] Review `PACKAGING_CONSTRAINTS_IMPLEMENTATION.md` - Full implementation plan
- [ ] Review `PACKAGING_CONSTRAINTS_REVIEW.md` - Code review & edge cases
- [ ] Understand existing code in `src/production/feasibility.py` (lines 69-278)

---

## Implementation Checklist

### 1. Import Integer Variables ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~36-45

```python
from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    NonNegativeIntegers,  # ← ADD THIS
    Binary,
    minimize,
    value,
)
```

**Verification:**
- [ ] Import added successfully
- [ ] No import errors when running model

---

### 2. Add Packaging Constants ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~94-104 (after existing constants)

```python
class IntegratedProductionDistributionModel(BaseOptimizationModel):
    # Production rate: 1,400 units per hour
    PRODUCTION_RATE = 1400.0

    # Max hours per day (with overtime)
    MAX_HOURS_PER_DAY = 14.0

    # Packaging constants ← ADD THESE
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320  # 32 cases × 10 units
    PALLETS_PER_TRUCK = 44
    UNITS_PER_TRUCK = 14080  # 44 pallets × 320 units
```

**Verification:**
- [ ] Constants added to class
- [ ] Values match business requirements (see `data/examples/MANUFACTURING_SCHEDULE.md`)

---

### 3. Create Integer Variables ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~1278 (immediately after `model.production` variable)

```python
# Decision variables: production[date, product]
model.production = Var(
    model.dates,
    model.products,
    within=NonNegativeReals,
    doc="Production quantity by date and product"
)

# PACKAGING: Integer variable for production in cases ← ADD THIS
model.production_cases = Var(
    model.dates,
    model.products,
    within=NonNegativeIntegers,
    doc="Production quantity in cases (10-unit increments)"
)
```

**Line:** ~1356 (after `model.truck_load` variable, inside `if self.truck_schedules:` block)

```python
# PACKAGING: Integer variable for pallets loaded ← ADD THIS
if self.truck_schedules:
    # ... existing truck_load variable ...

    model.pallets_loaded = Var(
        model.trucks,
        model.truck_destinations,
        model.dates,
        within=NonNegativeIntegers,
        doc="Pallets loaded on truck to destination (partial pallets occupy full pallet space)"
    )
```

**Verification:**
- [ ] `production_cases` variable created
- [ ] `pallets_loaded` variable created (only if truck_schedules exists)
- [ ] Variables indexed correctly (dates × products, trucks × destinations × dates)

---

### 4. Add Production-Case Linking Constraint ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~1505 (after `model.max_capacity_con` constraint)

```python
# Constraint: Production capacity per day
def max_capacity_rule(model, d):
    return sum(model.production[d, p] for p in model.products) <= self.max_capacity_per_day

model.max_capacity_con = Constraint(
    model.dates,
    rule=max_capacity_rule,
    doc="Maximum production capacity per day"
)

# PACKAGING CONSTRAINT: Production must be in 10-unit case multiples ← ADD THIS
def production_case_link_rule(model, d, p):
    """Link production units to cases: production = cases × 10."""
    return model.production[d, p] == model.production_cases[d, p] * self.UNITS_PER_CASE

model.production_case_link_con = Constraint(
    model.dates,
    model.products,
    rule=production_case_link_rule,
    doc="Production must be in 10-unit case increments"
)
```

**Verification:**
- [ ] Constraint added successfully
- [ ] Equality constraint (`==`) enforces exact case multiples
- [ ] Indexed over all dates and products

---

### 5. Add Pallet Loading Constraints ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~1510 (after production_case_link_con, inside conditional block)

```python
# PALLET CONSTRAINTS: Truck loading with partial pallet space accounting ← ADD THIS
if self.truck_schedules:

    # Constraint 1: Total units ≤ pallets × 320
    def pallet_loading_rule(model, truck_idx, dest, date):
        """Total units loaded must fit in assigned pallets."""
        total_units = sum(
            model.truck_load[truck_idx, dest, p, date]
            for p in model.products
        )
        return total_units <= model.pallets_loaded[truck_idx, dest, date] * self.UNITS_PER_PALLET

    model.pallet_loading_con = Constraint(
        model.trucks,
        model.truck_destinations,
        model.dates,
        rule=pallet_loading_rule,
        doc="Truck loads must fit in assigned pallets"
    )

    # Constraint 2: Force minimum pallets (ceiling division)
    def pallet_minimum_rule(model, truck_idx, dest, date):
        """If units > 0, pallets ≥ ceil(units/320). Enforced as: pallets×320 - units ≤ 319."""
        total_units = sum(
            model.truck_load[truck_idx, dest, p, date]
            for p in model.products
        )
        return (model.pallets_loaded[truck_idx, dest, date] * self.UNITS_PER_PALLET -
                total_units <= self.UNITS_PER_PALLET - 1)

    model.pallet_minimum_con = Constraint(
        model.trucks,
        model.truck_destinations,
        model.dates,
        rule=pallet_minimum_rule,
        doc="Force minimum pallets for loaded units (ceiling division)"
    )

    # Constraint 3: Truck pallet capacity (max 44 pallets)
    def truck_pallet_capacity_rule(model, truck_idx, date):
        """Total pallets across all destinations ≤ truck pallet capacity (44)."""
        total_pallets = sum(
            model.pallets_loaded[truck_idx, dest, date]
            for dest in model.truck_destinations
        )
        truck = self.truck_by_index[truck_idx]
        return total_pallets <= truck.pallet_capacity

    model.truck_pallet_capacity_con = Constraint(
        model.trucks,
        model.dates,
        rule=truck_pallet_capacity_rule,
        doc="Total pallets per truck cannot exceed capacity (44)"
    )
```

**Verification:**
- [ ] All 3 constraints added inside `if self.truck_schedules:` block
- [ ] `pallet_loading_con`: Ensures units fit in pallets (≤ constraint)
- [ ] `pallet_minimum_con`: Forces ceiling division (prevents over-assignment)
- [ ] `truck_pallet_capacity_con`: Enforces 44-pallet limit per truck

---

### 6. Update Solution Extraction ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~2650 (in `extract_solution()` method)

**Replace:**
```python
# Extract production quantities
production_by_date_product: Dict[Tuple[Date, str], float] = {}
for d in model.dates:
    for p in model.products:
        qty = value(model.production[d, p])
        if qty > 1e-6:  # Only include non-zero production
            production_by_date_product[(d, p)] = qty
```

**With:**
```python
# Extract production quantities
production_by_date_product: Dict[Tuple[Date, str], float] = {}
production_cases_by_date_product: Dict[Tuple[Date, str], int] = {}  # NEW

for d in model.dates:
    for p in model.products:
        qty = value(model.production[d, p])
        if qty > 1e-6:  # Only include non-zero production
            production_by_date_product[(d, p)] = qty

            # Extract case quantity (should be integer)
            cases = value(model.production_cases[d, p])
            cases_int = int(round(cases))

            # Validate rounding error
            if abs(cases - cases_int) > 1e-3:
                warnings.warn(
                    f"Large rounding error in production_cases: {cases} → {cases_int} "
                    f"on {d} for {p}"
                )

            production_cases_by_date_product[(d, p)] = cases_int
```

**Line:** ~2775 (after truck extraction code)

**Add:**
```python
# Extract pallet loading data (if truck schedules exist)
pallet_loads_by_truck_dest_date: Dict[Tuple[int, str, Date], int] = {}
if self.truck_schedules:
    for truck_idx in model.trucks:
        for dest in model.truck_destinations:
            for d in model.dates:
                pallets = value(model.pallets_loaded[truck_idx, dest, d])
                if pallets > 0.5:  # Integer variable, use threshold
                    pallets_int = int(round(pallets))

                    # Validate rounding
                    if abs(pallets - pallets_int) > 1e-3:
                        warnings.warn(
                            f"Large rounding error in pallets_loaded: {pallets} → {pallets_int}"
                        )

                    pallet_loads_by_truck_dest_date[(truck_idx, dest, d)] = pallets_int
```

**Line:** ~2937 (in return dictionary)

**Add to return dict:**
```python
return {
    'production_by_date_product': production_by_date_product,
    'production_cases_by_date_product': production_cases_by_date_product,  # NEW
    'production_batches': production_batches,
    # ... other existing keys ...
    'pallet_loads_by_truck_dest_date': pallet_loads_by_truck_dest_date if self.truck_schedules else {},  # NEW
    # ... rest of keys ...
}
```

**Verification:**
- [ ] Case quantities extracted and rounded
- [ ] Pallet quantities extracted and rounded
- [ ] Rounding warnings logged if error > 1e-3
- [ ] New keys added to solution dictionary

---

### 7. Add Validation Method ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~3085 (before `print_solution_summary()` method)

```python
def validate_packaging_constraints(self) -> Dict[str, Any]:
    """
    Validate that solution meets packaging constraints.

    Returns:
        Dictionary with validation results and metrics:
        - valid: bool (True if all constraints satisfied)
        - issues: List[str] (constraint violations)
        - warnings: List[str] (efficiency warnings)
        - metrics: Dict with packaging statistics
    """
    import math

    if not self.solution:
        return {'valid': False, 'reason': 'No solution available'}

    issues = []
    warnings_list = []
    metrics = {
        'total_cases': 0,
        'total_pallets': 0,
        'full_pallets': 0,
        'partial_pallets': 0,
        'pallet_efficiency': 0.0,
    }

    # Validate production is in case multiples
    production_by_date_product = self.solution.get('production_by_date_product', {})
    for (prod_date, product_id), qty in production_by_date_product.items():
        if qty % self.UNITS_PER_CASE != 0:
            issues.append(
                f"Production on {prod_date} for {product_id}: {qty} units "
                f"is not a multiple of {self.UNITS_PER_CASE} (case size)"
            )
        else:
            cases = int(qty / self.UNITS_PER_CASE)
            metrics['total_cases'] += cases

    # Validate pallet loading (if truck schedules exist)
    if self.truck_schedules and 'pallet_loads_by_truck_dest_date' in self.solution:
        pallet_loads = self.solution['pallet_loads_by_truck_dest_date']
        truck_loads = self.solution.get('truck_loads_by_truck_dest_product_date', {})

        for (truck_idx, dest, date), num_pallets in pallet_loads.items():
            metrics['total_pallets'] += num_pallets

            # Calculate actual units on this truck-destination
            total_units = sum(
                qty for (t, d, p, dt), qty in truck_loads.items()
                if t == truck_idx and d == dest and dt == date
            )

            if total_units > 0:
                # Calculate cases and required pallets
                cases = int(total_units / self.UNITS_PER_CASE)
                required_pallets = math.ceil(cases / self.CASES_PER_PALLET)

                # Check if correct number of pallets assigned
                if num_pallets != required_pallets:
                    issues.append(
                        f"Truck {truck_idx} to {dest} on {date}: "
                        f"Assigned {num_pallets} pallets but {required_pallets} required "
                        f"for {total_units} units ({cases} cases)"
                    )

                # Track full vs partial pallets
                if cases % self.CASES_PER_PALLET == 0:
                    metrics['full_pallets'] += num_pallets
                else:
                    metrics['full_pallets'] += (required_pallets - 1) if required_pallets > 1 else 0
                    metrics['partial_pallets'] += 1

                    # Warn about partial pallet inefficiency
                    cases_on_last = cases % self.CASES_PER_PALLET
                    efficiency = (cases_on_last / self.CASES_PER_PALLET) * 100
                    if efficiency < 50:
                        warnings_list.append(
                            f"Low pallet efficiency on truck {truck_idx} to {dest} on {date}: "
                            f"{cases_on_last}/{self.CASES_PER_PALLET} cases on last pallet ({efficiency:.1f}%)"
                        )

            # Check truck pallet capacity
            truck = self.truck_by_index[truck_idx]
            total_pallets_on_truck = sum(
                pallets for (t, d, dt), pallets in pallet_loads.items()
                if t == truck_idx and dt == date
            )
            if total_pallets_on_truck > truck.pallet_capacity:
                issues.append(
                    f"Truck {truck_idx} on {date}: "
                    f"{total_pallets_on_truck} pallets exceeds capacity of {truck.pallet_capacity}"
                )

    # Calculate overall pallet efficiency
    if metrics['total_pallets'] > 0:
        # Efficiency = (full pallets + 50% credit for partial) / total
        metrics['pallet_efficiency'] = (
            (metrics['full_pallets'] + metrics['partial_pallets'] * 0.5) /
            metrics['total_pallets'] * 100
        )

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings_list,
        'metrics': metrics,
    }
```

**Verification:**
- [ ] Method added to class
- [ ] Returns correct dictionary structure
- [ ] Validates case multiples
- [ ] Validates pallet assignments
- [ ] Calculates efficiency metrics

---

### 8. Update Solution Summary ✅
**File:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
**Line:** ~3099 (in `print_solution_summary()` method, before final separator)

**Add before final `print("=" * 70)`:**

```python
# PACKAGING METRICS (NEW)
print("\nPACKAGING EFFICIENCY:")
print("-" * 70)

validation = self.validate_packaging_constraints()

if validation['valid']:
    print("✓ All packaging constraints satisfied")
else:
    print("✗ Packaging constraint violations detected:")
    for issue in validation['issues'][:5]:  # Show first 5
        print(f"  - {issue}")

metrics = validation['metrics']
print(f"\nTotal cases produced: {metrics['total_cases']:,}")

if self.truck_schedules:
    print(f"Total pallets loaded: {metrics['total_pallets']:,}")
    print(f"  - Full pallets: {metrics['full_pallets']:,}")
    print(f"  - Partial pallets: {metrics['partial_pallets']:,}")
    print(f"Overall pallet efficiency: {metrics['pallet_efficiency']:.1f}%")

    if validation['warnings']:
        print(f"\nPackaging warnings ({len(validation['warnings'])}):")
        for warning in validation['warnings'][:3]:
            print(f"  ⚠ {warning}")
```

**Verification:**
- [ ] Packaging section added to summary
- [ ] Displays validation status
- [ ] Shows key metrics (cases, pallets, efficiency)
- [ ] Shows warnings if present

---

## Testing Checklist

### Unit Tests
- [ ] Test case multiple enforcement (all production divisible by 10)
- [ ] Test pallet space accounting (partial pallets = 1 pallet space)
- [ ] Test truck capacity (never exceed 44 pallets)
- [ ] Test rounding tolerance (integer variables rounded correctly)

### Integration Tests
- [ ] Test with real forecast data (`Gfree Forecast.xlsm`)
- [ ] Test solve time (should be < 5 minutes for 200-day horizon)
- [ ] Test validation method catches violations
- [ ] Test backward compatibility (existing code still works)

### Edge Cases
- [ ] Zero production (production_cases = 0)
- [ ] Partial pallet (e.g., 1 case = 1 pallet)
- [ ] Multiple products on same truck
- [ ] Infeasible demand (with allow_shortages=True)

---

## Verification Commands

### 1. Check Import
```bash
python -c "from src.optimization.integrated_model import IntegratedProductionDistributionModel; print('✓ Import successful')"
```

### 2. Check Constants
```bash
python -c "from src.optimization.integrated_model import IntegratedProductionDistributionModel as M; print(f'UNITS_PER_CASE={M.UNITS_PER_CASE}, CASES_PER_PALLET={M.CASES_PER_PALLET}')"
```

### 3. Run Simple Test
```bash
pytest tests/test_packaging_constraints.py::test_production_case_multiples -v
```

### 4. Run Full Test Suite
```bash
pytest tests/test_packaging_constraints.py -v
```

### 5. Test with Real Data
```bash
python -c "
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.parsers.excel_parser import ExcelParser

parser = ExcelParser('data/examples/Gfree Forecast.xlsm')
# ... load data ...
model = IntegratedProductionDistributionModel(...)
result = model.solve(time_limit_seconds=300)

if result.is_optimal():
    validation = model.validate_packaging_constraints()
    print(f\"Valid: {validation['valid']}\")
    print(f\"Metrics: {validation['metrics']}\")
"
```

---

## Common Issues & Solutions

### Issue 1: Import Error - NonNegativeIntegers not found
**Solution:** Check Pyomo version. Need Pyomo >= 5.7
```bash
pip install --upgrade pyomo
```

### Issue 2: Constraint indexing error
**Solution:** Verify index sets match variable domains
```python
# Variable indexed by (dates, products)
model.production_cases = Var(model.dates, model.products, ...)

# Constraint must use same indices
model.production_case_link_con = Constraint(
    model.dates,  # ✓ matches
    model.products,  # ✓ matches
    rule=...
)
```

### Issue 3: Integer values have decimals (e.g., 149.9999)
**Solution:** Round with tolerance in extraction
```python
cases = value(model.production_cases[d, p])
cases_int = int(round(cases))
if abs(cases - cases_int) > 1e-3:
    warnings.warn(f"Rounding error: {cases} → {cases_int}")
```

### Issue 4: Solver very slow or times out
**Solution:** Set MIP gap tolerance
```python
from src.optimization.solver_config import SolverConfig

solver_config = SolverConfig(
    solver_name='cbc',
    time_limit_seconds=300,
    mip_gap=0.01  # Accept 1% gap (99% optimal)
)
```

### Issue 5: Infeasible due to integer constraints
**Solution:** Enable shortages
```python
model = IntegratedProductionDistributionModel(
    ...,
    allow_shortages=True  # Prevents hard infeasibility
)
```

---

## Success Criteria

### Must Have ✅
- [ ] All production quantities are multiples of 10 units
- [ ] Partial pallets correctly consume full pallet space on trucks
- [ ] No truck exceeds 44-pallet capacity
- [ ] Solution validates successfully (no constraint violations)
- [ ] Code passes all tests

### Should Have ✅
- [ ] Pallet efficiency > 80% (few partial pallets)
- [ ] Solve time < 5 minutes for typical instances
- [ ] Clear error messages if constraints violated
- [ ] Packaging metrics displayed in solution summary

### Nice to Have
- [ ] Pallet efficiency > 95% (minimal waste)
- [ ] Solve time < 2 minutes
- [ ] UI visualization of packaging efficiency
- [ ] Automatic suggestions for improving efficiency

---

## Reference Documents

1. **`PACKAGING_CONSTRAINTS_IMPLEMENTATION.md`** - Complete implementation guide with code
2. **`PACKAGING_CONSTRAINTS_REVIEW.md`** - Code review, edge cases, testing strategy
3. **`data/examples/MANUFACTURING_SCHEDULE.md`** - Business requirements and packaging rules
4. **`src/production/feasibility.py`** - Existing packaging domain logic (reference implementation)

---

## Contact Points

### Questions about:
- **Mathematical formulation:** Review section 1 in IMPLEMENTATION.md
- **Edge cases:** Review section in REVIEW.md
- **Business rules:** See MANUFACTURING_SCHEDULE.md lines 110-148
- **Existing code patterns:** See feasibility.py lines 209-278

### Code Locations:
- **Model class:** `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
- **Constants:** Lines 81-86 in feasibility.py (reference)
- **Validation logic:** Lines 209-236 in feasibility.py (reference)
- **Test examples:** `/home/sverzijl/planning_latest/tests/test_truck_loading.py`
