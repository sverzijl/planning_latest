# Packaging Constraints Implementation Plan

## Overview

Implement discrete packaging constraints in the integrated optimization model to ensure:
1. All production quantities are in 10-unit case multiples
2. Pallet space accounting for truck capacity (partial pallets consume full pallet space)
3. Validation and diagnostics for packaging efficiency

## Mathematical Formulation

### Decision Variables (New)

```python
# Integer variables for packaging
model.production_cases = Var(
    model.dates,
    model.products,
    within=NonNegativeIntegers,
    doc="Production in cases (10-unit increments)"
)

model.pallets_loaded = Var(
    model.trucks,
    model.truck_destinations,
    model.dates,
    within=NonNegativeIntegers,
    doc="Number of pallets loaded on truck (partial pallets count as full)"
)
```

### Linking Constraints

```python
# Link production units to cases
def production_case_link_rule(model, d, p):
    """Production must equal cases × 10 units per case."""
    return model.production[d, p] == model.production_cases[d, p] * UNITS_PER_CASE

model.production_case_link = Constraint(
    model.dates,
    model.products,
    rule=production_case_link_rule,
    doc="Link production units to cases"
)

# Link truck loads to pallets
def pallet_loading_rule(model, truck_idx, dest, date):
    """Total units on truck to destination ≤ pallets × 320 units per pallet."""
    total_units = sum(
        model.truck_load[truck_idx, dest, p, date]
        for p in model.products
    )
    return total_units <= model.pallets_loaded[truck_idx, dest, date] * UNITS_PER_PALLET

model.pallet_loading_con = Constraint(
    model.trucks,
    model.truck_destinations,
    model.dates,
    rule=pallet_loading_rule,
    doc="Truck loads must fit in assigned pallets"
)

# Truck pallet capacity constraint
def truck_pallet_capacity_rule(model, truck_idx, date):
    """Total pallets across all destinations ≤ 44 pallets per truck."""
    total_pallets = sum(
        model.pallets_loaded[truck_idx, dest, date]
        for dest in model.truck_destinations
    )
    truck = self.truck_by_index[truck_idx]
    return total_pallets <= truck.pallet_capacity  # 44 pallets

model.truck_pallet_capacity_con = Constraint(
    model.trucks,
    model.dates,
    rule=truck_pallet_capacity_rule,
    doc="Total pallets per truck cannot exceed capacity"
)

# Force pallet loading (reverse constraint)
def pallet_minimum_rule(model, truck_idx, dest, date):
    """If units loaded, must have at least 1 pallet (prevents fractional pallets)."""
    total_units = sum(
        model.truck_load[truck_idx, dest, p, date]
        for p in model.products
    )
    # If total_units > 0, then pallets_loaded >= ceil(total_units / 320)
    # We can enforce: total_units <= pallets_loaded * 320
    # AND: pallets_loaded * 320 - total_units <= 319 (prevents over-assignment)
    return model.pallets_loaded[truck_idx, dest, date] * UNITS_PER_PALLET - total_units <= (UNITS_PER_PALLET - 1)

model.pallet_minimum_con = Constraint(
    model.trucks,
    model.truck_destinations,
    model.dates,
    rule=pallet_minimum_rule,
    doc="Force minimum pallets for loaded units"
)
```

## Implementation Steps

### Step 1: Add Constants to Model Class

```python
class IntegratedProductionDistributionModel(BaseOptimizationModel):
    # Packaging constants
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320  # 32 cases × 10 units
    PALLETS_PER_TRUCK = 44
    UNITS_PER_TRUCK = 14080  # 44 pallets × 320 units
```

### Step 2: Import NonNegativeIntegers

```python
from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    NonNegativeIntegers,  # ADD THIS
    Binary,
    minimize,
    value,
)
```

### Step 3: Add Integer Variables in build_model()

Add after line ~1278 (after production variable definition):

```python
# INTEGER PACKAGING: Decision variables for discrete packaging
model.production_cases = Var(
    model.dates,
    model.products,
    within=NonNegativeIntegers,
    doc="Production quantity in cases (10-unit increments)"
)

# Only create pallet variables if truck schedules exist
if self.truck_schedules:
    model.pallets_loaded = Var(
        model.trucks,
        model.truck_destinations,
        model.dates,
        within=NonNegativeIntegers,
        doc="Pallets loaded on truck to destination (partial pallets occupy full pallet space)"
    )
```

### Step 4: Add Linking Constraints

Add after line ~1505 (after production capacity constraint):

```python
# PACKAGING CONSTRAINT: Production must be in 10-unit case multiples
def production_case_link_rule(model, d, p):
    """Link production units to cases: production = cases × 10."""
    return model.production[d, p] == model.production_cases[d, p] * self.UNITS_PER_CASE

model.production_case_link_con = Constraint(
    model.dates,
    model.products,
    rule=production_case_link_rule,
    doc="Production must be in 10-unit case increments"
)

# PALLET CONSTRAINTS: Truck loading with partial pallet space accounting
if self.truck_schedules:
    def pallet_loading_rule(model, truck_idx, dest, date):
        """Total units loaded ≤ pallets × 320 units per pallet."""
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

    def pallet_minimum_rule(model, truck_idx, dest, date):
        """Force minimum pallets: if units > 0, pallets ≥ ceil(units/320)."""
        total_units = sum(
            model.truck_load[truck_idx, dest, p, date]
            for p in model.products
        )
        # Enforce: pallets × 320 - units ≤ 319
        # This ensures pallets = ceil(units/320) when units > 0
        return (model.pallets_loaded[truck_idx, dest, date] * self.UNITS_PER_PALLET -
                total_units <= self.UNITS_PER_PALLET - 1)

    model.pallet_minimum_con = Constraint(
        model.trucks,
        model.truck_destinations,
        model.dates,
        rule=pallet_minimum_rule,
        doc="Force minimum pallets for loaded units (ceil division)"
    )

    def truck_pallet_capacity_rule(model, truck_idx, date):
        """Total pallets across all destinations ≤ truck pallet capacity."""
        total_pallets = sum(
            model.pallets_loaded[truck_idx, dest, date]
            for dest in model.truck_destinations
        )
        truck = self.truck_by_index[truck_idx]
        return total_pallets <= truck.pallet_capacity  # 44 pallets

    model.truck_pallet_capacity_con = Constraint(
        model.trucks,
        model.dates,
        rule=truck_pallet_capacity_rule,
        doc="Total pallets per truck cannot exceed capacity (44)"
    )
```

### Step 5: Update Solution Extraction

In `extract_solution()` method, add after line ~2656:

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
            production_cases_by_date_product[(d, p)] = int(round(cases))

# Extract pallet loading data (if truck schedules exist)
pallet_loads_by_truck_dest_date: Dict[Tuple[int, str, Date], int] = {}
if self.truck_schedules:
    for truck_idx in model.trucks:
        for dest in model.truck_destinations:
            for d in model.dates:
                pallets = value(model.pallets_loaded[truck_idx, dest, d])
                if pallets > 0.5:  # Integer variable, use threshold
                    pallet_loads_by_truck_dest_date[(truck_idx, dest, d)] = int(round(pallets))
```

Add to return dictionary at line ~2937:

```python
return {
    'production_by_date_product': production_by_date_product,
    'production_cases_by_date_product': production_cases_by_date_product,  # NEW
    'pallet_loads_by_truck_dest_date': pallet_loads_by_truck_dest_date,  # NEW
    # ... existing keys ...
}
```

### Step 6: Add Validation Method

Add new method to class:

```python
def validate_packaging_constraints(self) -> Dict[str, Any]:
    """
    Validate that solution meets packaging constraints.

    Returns:
        Dictionary with validation results and metrics
    """
    if not self.solution:
        return {'valid': False, 'reason': 'No solution available'}

    from src.production.feasibility import ProductionFeasibilityChecker

    issues = []
    warnings = []
    metrics = {
        'total_cases': 0,
        'total_pallets': 0,
        'full_pallets': 0,
        'partial_pallets': 0,
        'pallet_efficiency': 0.0,
    }

    # Validate production is in case multiples
    production_by_date_product = self.solution['production_by_date_product']
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
                # Calculate cases and pallets
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
                    metrics['full_pallets'] += (required_pallets - 1)
                    metrics['partial_pallets'] += 1

                    # Warn about partial pallet inefficiency
                    cases_on_last = cases % self.CASES_PER_PALLET
                    efficiency = (cases_on_last / self.CASES_PER_PALLET) * 100
                    if efficiency < 50:
                        warnings.append(
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
        metrics['pallet_efficiency'] = (
            (metrics['full_pallets'] + metrics['partial_pallets'] * 0.5) /
            metrics['total_pallets'] * 100
        )

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'metrics': metrics,
    }
```

### Step 7: Update print_solution_summary()

Add packaging metrics to solution summary (after line ~3099):

```python
def print_solution_summary(self) -> None:
    """Print summary of optimization solution."""
    if not self.solution:
        print("No solution available. Model not solved or infeasible.")
        return

    print("=" * 70)
    print("OPTIMIZATION SOLUTION SUMMARY")
    print("=" * 70)

    # ... existing summary code ...

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
    print(f"Total pallets loaded: {metrics['total_pallets']:,}")
    print(f"  - Full pallets: {metrics['full_pallets']:,}")
    print(f"  - Partial pallets: {metrics['partial_pallets']:,}")
    print(f"Overall pallet efficiency: {metrics['pallet_efficiency']:.1f}%")

    if validation['warnings']:
        print(f"\nPackaging warnings ({len(validation['warnings'])}):")
        for warning in validation['warnings'][:3]:
            print(f"  ⚠ {warning}")
```

## Testing Strategy

### Test 1: Case Multiple Enforcement

```python
def test_production_case_multiples(self):
    """Test that all production is in 10-unit case multiples."""
    # Run optimization
    result = model.solve()

    # Validate solution
    validation = model.validate_packaging_constraints()
    assert validation['valid'], f"Case constraint violations: {validation['issues']}"

    # Check all production quantities
    for (date, product), qty in model.solution['production_by_date_product'].items():
        assert qty % 10 == 0, f"Production {qty} is not a multiple of 10"
```

### Test 2: Pallet Space Accounting

```python
def test_pallet_space_accounting(self):
    """Test that partial pallets consume full pallet space."""
    result = model.solve()

    # Check a truck with partial pallet
    pallet_loads = model.solution['pallet_loads_by_truck_dest_date']
    truck_loads = model.solution['truck_loads_by_truck_dest_product_date']

    for (truck_idx, dest, date), pallets in pallet_loads.items():
        total_units = sum(
            qty for (t, d, p, dt), qty in truck_loads.items()
            if t == truck_idx and d == dest and dt == date
        )
        cases = total_units // 10
        expected_pallets = math.ceil(cases / 32)

        assert pallets == expected_pallets, \
            f"Truck {truck_idx} has {pallets} pallets but should have {expected_pallets}"
```

### Test 3: Truck Capacity Enforcement

```python
def test_truck_pallet_capacity(self):
    """Test that trucks do not exceed 44 pallet capacity."""
    result = model.solve()

    pallet_loads = model.solution['pallet_loads_by_truck_dest_date']

    # Group by truck and date
    truck_totals = {}
    for (truck_idx, dest, date), pallets in pallet_loads.items():
        key = (truck_idx, date)
        truck_totals[key] = truck_totals.get(key, 0) + pallets

    for (truck_idx, date), total_pallets in truck_totals.items():
        truck = model.truck_by_index[truck_idx]
        assert total_pallets <= truck.pallet_capacity, \
            f"Truck {truck_idx} on {date} has {total_pallets} pallets (max: {truck.pallet_capacity})"
```

## Backwards Compatibility

### Flag-Based Enablement (Optional)

Add parameter to `__init__`:

```python
def __init__(
    self,
    # ... existing params ...
    enforce_packaging_constraints: bool = True,  # NEW
):
    self.enforce_packaging_constraints = enforce_packaging_constraints
```

Conditionally create integer variables:

```python
if self.enforce_packaging_constraints:
    model.production_cases = Var(...)
    # Add packaging constraints
else:
    # Keep existing continuous variables only
```

**Recommendation:** Always enable packaging constraints (no flag needed) since this is a core business requirement.

## UI Integration

### Update Planning Page

In `ui/pages/2_Planning.py`, add packaging metrics display:

```python
# After optimization completes
if result.is_optimal():
    # Validate packaging
    validation = model.validate_packaging_constraints()

    st.subheader("📦 Packaging Efficiency")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cases", f"{validation['metrics']['total_cases']:,}")
    with col2:
        st.metric("Total Pallets", f"{validation['metrics']['total_pallets']:,}")
    with col3:
        st.metric("Full Pallets", f"{validation['metrics']['full_pallets']:,}")
    with col4:
        efficiency = validation['metrics']['pallet_efficiency']
        st.metric("Pallet Efficiency", f"{efficiency:.1f}%",
                 delta="Optimal" if efficiency > 95 else None)

    if validation['warnings']:
        with st.expander("⚠️ Packaging Warnings", expanded=False):
            for warning in validation['warnings']:
                st.warning(warning)
```

## Performance Considerations

### Integer Programming Complexity

- **Impact:** Adding integer variables increases solve time (MIP vs LP)
- **Scale:** For 204 days × 5 products = 1,020 integer variables (production_cases)
- **Mitigation:**
  - Use efficient MIP solvers (CBC, Gurobi, CPLEX)
  - Set time limits and optimality gaps
  - Consider relaxing for large instances (validate post-solve)

### Solver Configuration

```python
solver_config = SolverConfig(
    solver_name='cbc',
    time_limit_seconds=300,  # 5 minutes
    mip_gap=0.01,  # 1% optimality gap acceptable
)
```

## Documentation Updates

### Update Model Docstring

```python
class IntegratedProductionDistributionModel(BaseOptimizationModel):
    """
    Integrated production-distribution optimization model.

    ...

    Packaging Constraints (NEW):
    - Production in 10-unit case multiples (integer programming)
    - Pallet space accounting (partial pallets occupy full pallet space)
    - Truck capacity: max 44 pallets per truck
    - Efficiency tracking and validation

    Decision Variables:
    - production[date, product]: Quantity to produce (continuous)
    - production_cases[date, product]: Production in cases (integer)
    - pallets_loaded[truck, dest, date]: Pallets on truck (integer)
    - shipment[route_index, product, delivery_date]: Quantity to ship
    ...
    """
```

### Update CLAUDE.md

Add to "Key Design Decisions" section:

```markdown
10. **Discrete packaging constraints:** Integer programming for case/pallet enforcement
    - Production: 10-unit case multiples (no partial cases)
    - Pallets: 32-case capacity, partial pallets occupy full pallet space
    - Trucks: 44-pallet capacity with space accounting
    - Validation: Post-solve efficiency metrics and constraint checking
```

## Summary

### Files to Modify

1. ✅ `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
   - Add `NonNegativeIntegers` import
   - Add packaging constants
   - Create integer variables
   - Add linking constraints
   - Update `extract_solution()`
   - Add `validate_packaging_constraints()`
   - Update `print_solution_summary()`

2. ✅ `/home/sverzijl/planning_latest/ui/pages/2_Planning.py`
   - Add packaging metrics display
   - Show validation warnings

3. ✅ `/home/sverzijl/planning_latest/tests/test_packaging_constraints.py` (NEW)
   - Create comprehensive test suite

4. ✅ `/home/sverzijl/planning_latest/CLAUDE.md`
   - Document new constraints

### Implementation Checklist

- [ ] Import `NonNegativeIntegers` from Pyomo
- [ ] Add packaging constants to model class
- [ ] Create `production_cases` integer variable
- [ ] Create `pallets_loaded` integer variable (if truck schedules)
- [ ] Add `production_case_link_con` constraint
- [ ] Add `pallet_loading_con` constraint
- [ ] Add `pallet_minimum_con` constraint
- [ ] Add `truck_pallet_capacity_con` constraint
- [ ] Extract case/pallet quantities in `extract_solution()`
- [ ] Implement `validate_packaging_constraints()` method
- [ ] Update `print_solution_summary()` with packaging metrics
- [ ] Add UI components for packaging display
- [ ] Write comprehensive tests
- [ ] Update documentation

### Expected Outcomes

1. **Constraint Enforcement:**
   - All production in 10-unit multiples
   - Partial pallets correctly consume full pallet space
   - Trucks never exceed 44-pallet capacity

2. **Solution Quality:**
   - Higher pallet efficiency (minimize partial pallets)
   - Better truck utilization
   - Realistic production quantities

3. **Diagnostics:**
   - Clear visibility into packaging efficiency
   - Warnings for inefficient pallet usage
   - Validation of all packaging constraints

4. **Performance:**
   - Solve time increase: 2-5x (LP → MIP)
   - Still tractable for 200-day horizons
   - Can use optimality gaps for speed
