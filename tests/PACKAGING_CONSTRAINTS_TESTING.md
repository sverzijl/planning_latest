# Packaging Constraints Testing Guide

## Overview

This document describes the comprehensive test suite for packaging constraints in the production planning optimization models. The tests ensure that production and distribution decisions respect real-world packaging requirements.

## Packaging Hierarchy

The gluten-free bread production system uses a hierarchical packaging structure:

```
Case = 10 units (minimum shipping quantity)
Pallet = 32 cases = 320 units
Truck = 44 pallets = 14,080 units maximum capacity
```

### Critical Constraint

**Partial pallets consume full pallet space** in trucks. This creates an integer optimization problem:

- 320 units = 1 pallet (100% efficient)
- 321 units = 2 pallets (50.2% efficient - one case on second pallet)
- 640 units = 2 pallets (100% efficient)
- 641 units = 3 pallets (66.8% efficient)

## Test Structure

### Test Files

1. **`test_packaging_constraints.py`** - Core packaging constraint tests
   - Unit tests for case constraints
   - Unit tests for pallet constraints
   - Integration tests with simple production model
   - Performance tests
   - Edge case tests

2. **`test_packaging_constraints_integrated.py`** - Distribution network tests
   - Truck capacity constraints with routing
   - Hub transshipment with packaging
   - Multi-product truck sharing
   - Frozen vs ambient routing
   - Real-world network scenarios

3. **`packaging_test_utils.py`** - Reusable test utilities
   - Validation functions
   - Test data generators
   - Assertion helpers
   - Scenario builders

## Running the Tests

### Run All Packaging Tests

```bash
# From project root
pytest tests/test_packaging_constraints.py -v
pytest tests/test_packaging_constraints_integrated.py -v
```

### Run Specific Test Classes

```bash
# Case constraint tests only
pytest tests/test_packaging_constraints.py::TestCaseConstraints -v

# Pallet constraint tests only
pytest tests/test_packaging_constraints.py::TestPalletConstraints -v

# Integration tests
pytest tests/test_packaging_constraints.py::TestSmallInstance -v

# Performance tests (marked as slow)
pytest tests/test_packaging_constraints.py::TestPerformance -v -m slow
```

### Run with Coverage

```bash
pytest tests/test_packaging_constraints.py --cov=src/optimization --cov-report=html
```

## Test Categories

### 1. Unit Tests - Case Constraints

**Purpose**: Verify that production quantities are in whole cases (10-unit multiples)

**Key Tests**:
- `test_exact_case_multiple` - Valid case multiples (10, 20, 100, 320, 14080)
- `test_non_case_multiple_detection` - Invalid quantities (1, 5, 15, 235)
- `test_zero_production_allowed` - Zero production is valid
- `test_edge_case_exactly_one_case` - Boundary at 10 units
- `test_validate_case_constraints_function` - Validator function

**Expected Behavior**:
- Production variables should be constrained to multiples of 10
- Demand not divisible by 10 should round up to next case
- Zero production is allowed (no constraint)

### 2. Unit Tests - Pallet Constraints

**Purpose**: Verify pallet calculations and truck capacity limits

**Key Tests**:
- `test_one_pallet_exactly` - 320 units = 1 pallet (100% efficient)
- `test_partial_pallet_one_case` - 10 units = 1 pallet (3.1% efficient)
- `test_partial_pallet_321_units` - 330 units = 2 pallets (51.6% efficient)
- `test_truck_max_44_pallets` - 14,080 units = 44 pallets max
- `test_truck_capacity_exceeded` - Detection of overload

**Expected Behavior**:
- Pallets calculated using ceiling division: `⌈units / 320⌉`
- Partial pallets waste space (inefficiency)
- Truck capacity enforced at 44 pallets

### 3. Integration Tests - Small Instance

**Purpose**: Test packaging constraints in realistic but small optimization problems

**Test Instance**:
- 3 days planning horizon
- 1-2 products
- Demand: 1,235 units (not case multiple), 320 units (exact pallet), 640 units (2 pallets)

**Tests**:
- `test_small_instance_production_feasibility` - Model solves
- `test_small_instance_case_multiples` - Production in case multiples

**Note**: These tests will **currently fail** until integer constraints are added to the optimization model. They serve as regression tests.

### 4. Integration Tests - Medium Instance

**Purpose**: Test with moderate complexity (7 days, 2 products, varying demand)

**Tests**:
- `test_medium_instance_feasibility` - Solution exists
- `test_medium_instance_demand_satisfaction` - Demand met within rounding

**Expected Challenges**:
- Non-case-multiple demands require rounding
- Weekend production at premium rates
- Multiple products competing for production time

### 5. Edge Case Tests

**Purpose**: Test boundary conditions and special scenarios

**Key Scenarios**:
- Exact truck capacity (14,080 units)
- Single case shipment (10 units, very inefficient)
- Partial pallets (33 cases = 1 full + 1 partial)
- Multiple products totaling 47 pallets (exceeds 44)

**Tests**:
- `test_exact_truck_capacity_demand`
- `test_partial_pallet_demand`

### 6. Validation Tests

**Purpose**: Test the validation functions themselves

**Tests**:
- `test_validate_case_constraints_empty` - Empty production
- `test_validate_case_constraints_valid` - All valid
- `test_validate_case_constraints_invalid` - Detect violations
- `test_validate_pallet_constraints_valid`
- `test_calculate_pallet_efficiency_perfect` - 100% efficiency
- `test_calculate_pallet_efficiency_wasteful` - Low efficiency

### 7. Performance Tests

**Purpose**: Verify that integer constraints don't make problems unsolvable

**Test Instance**:
- 28 days planning horizon
- 4 products
- Multiple destinations
- Varying demand patterns

**Tests**:
- `test_large_instance_solve_time` - Solve within 120 seconds

**Performance Expectations**:
- Small (7 days): < 10 seconds
- Medium (14 days): < 30 seconds
- Large (28 days): < 120 seconds

Note: Times depend on solver (GLPK vs Gurobi) and hardware.

## Validation Functions

The test suite provides comprehensive validation functions in `packaging_test_utils.py`:

### `validate_case_constraints(production_values)`

Checks that all production quantities are multiples of 10.

**Returns**:
```python
{
    'is_valid': bool,
    'violations': [{'date': ..., 'product': ..., 'quantity': ..., 'remainder': ...}],
    'total_violations': int,
    'summary': str
}
```

### `validate_pallet_constraints(shipment_values, truck_capacity=44)`

Checks that shipments don't exceed truck capacity.

**Returns**:
```python
{
    'is_valid': bool,
    'violations': [{'key': ..., 'pallets_needed': ..., 'excess_pallets': ...}],
    'pallet_details': [{efficiency metrics}],
    'total_violations': int,
    'summary': str
}
```

### `calculate_pallet_efficiency(quantity)`

Calculates packing efficiency for a shipment.

**Returns**:
```python
{
    'quantity': float,
    'cases': float,
    'full_pallets': int,
    'partial_pallet_cases': float,
    'total_pallets': int,
    'wasted_pallet_space': float,
    'efficiency_pct': float
}
```

### `validate_solution_packaging(solution, check_production=True, check_shipments=True)`

Comprehensive solution validation.

**Returns**:
```python
{
    'overall_valid': bool,
    'production_validation': {...},
    'shipment_validation': {...}
}
```

## Test Data Generators

Utilities to create test scenarios:

### `generate_forecast(...)`

Generate forecast with configurable parameters:
- Start date and duration
- Locations and products
- Base demand and variation
- Case-aligned option

### `generate_labor_calendar(...)`

Generate labor calendar:
- Weekday vs weekend differentiation
- Configurable rates and hours

### `generate_simple_network(...)`

Generate network topology:
- Manufacturing site
- Hubs
- Destinations
- Routes (with optional frozen alternatives)

### Scenario Builders

Pre-built scenarios for common test cases:
- `create_exact_truck_capacity_scenario()` - 14,080 units
- `create_partial_pallet_scenario()` - Inefficient packing
- `create_non_case_aligned_scenario()` - Demands requiring rounding
- `create_multi_product_competition_scenario()` - Truck sharing

## Using Validation in Your Tests

### Example: Validate Production Solution

```python
from packaging_test_utils import validate_case_constraints, print_validation_report

# After solving optimization model
result = model.solve()

if result.is_optimal():
    production = model.solution['production_by_date_product']

    # Validate case constraints
    validation = validate_case_constraints(production)

    # Assert validity
    assert validation['is_valid'], \
        f"Production violates case constraints: {validation['violations']}"

    # Or use helper assertion
    from packaging_test_utils import assert_all_case_multiples
    assert_all_case_multiples(production)
```

### Example: Check Pallet Efficiency

```python
from packaging_test_utils import calculate_pallet_efficiency

quantity = 330  # 33 cases
metrics = calculate_pallet_efficiency(quantity)

print(f"Quantity: {metrics['quantity']} units")
print(f"Pallets: {metrics['total_pallets']}")
print(f"Efficiency: {metrics['efficiency_pct']:.1f}%")
print(f"Wasted space: {metrics['wasted_pallet_space']} cases")

# Output:
# Quantity: 330 units
# Pallets: 2
# Efficiency: 51.6%
# Wasted space: 31 cases
```

## Expected Test Results

### Current Status (Before Integer Constraints)

Most integration tests will **REPORT violations** but not necessarily fail:

```
Case constraint violations detected: 15
  Date: 2025-01-15, Product: PROD_A, Quantity: 1237.5, Remainder: 7.5
  Date: 2025-01-16, Product: PROD_A, Quantity: 843.2, Remainder: 3.2
  ...
```

This is expected behavior. The tests document what needs to be fixed.

### After Integer Constraints Added

All tests should **PASS**:
- All production in exact case multiples
- All shipments respect truck capacity
- Demand satisfied (possibly with overage due to case rounding)
- Efficient pallet packing where possible

## Adding New Tests

### Template for New Packaging Test

```python
def test_your_new_scenario(
    self,
    manufacturing_site,
    cost_structure,
    basic_labor_calendar,
    solver_config
):
    """Test description."""
    # 1. Create forecast
    forecast = Forecast(name="Test", entries=[
        ForecastEntry(
            location_id="DEST1",
            product_id="PROD_A",
            forecast_date=date(2025, 1, 15),
            quantity=1235  # Your test quantity
        )
    ])

    # 2. Create model
    model = ProductionOptimizationModel(
        forecast=forecast,
        labor_calendar=basic_labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        solver_config=solver_config,
    )

    # 3. Solve
    result = model.solve()
    assert result.is_optimal()

    # 4. Validate packaging
    production = model.solution['production_by_date_product']
    validation = validate_case_constraints(production)

    # 5. Assert expected behavior
    assert validation['is_valid'], \
        f"Expected case multiples: {validation['violations']}"
```

## Test Markers

Tests use pytest markers for organization:

```python
@pytest.mark.slow  # Performance tests (skip in quick test runs)
```

Run without slow tests:
```bash
pytest tests/test_packaging_constraints.py -m "not slow"
```

## Integration with CI/CD

Recommended test execution in CI pipeline:

```yaml
# .github/workflows/test.yml or similar

- name: Run Unit Tests
  run: pytest tests/test_packaging_constraints.py::TestCaseConstraints -v

- name: Run Validation Tests
  run: pytest tests/test_packaging_constraints.py::TestValidationFunctions -v

- name: Run Integration Tests (Quick)
  run: pytest tests/test_packaging_constraints.py::TestSmallInstance -v

- name: Run Integration Tests (Full)
  run: pytest tests/test_packaging_constraints_integrated.py -v -m "not slow"

- name: Run Performance Tests (Nightly)
  run: pytest tests/test_packaging_constraints.py -v -m slow
  # Only on nightly builds or before releases
```

## Debugging Failed Tests

### Common Failure Reasons

1. **Case constraint violations**
   - Cause: Production variables not constrained to integers
   - Fix: Add integer variable constraints in optimization model

2. **Pallet capacity violations**
   - Cause: Shipment variables not respecting truck limits
   - Fix: Add truck capacity constraints per shipment

3. **Demand not satisfied**
   - Cause: Case rounding creates shortage
   - Fix: Allow production to exceed demand by up to 9 units per product

4. **Performance timeout**
   - Cause: Integer constraints make problem harder
   - Fix: Tune solver parameters, reduce problem size, or use commercial solver

### Debugging Commands

```bash
# Run single test with detailed output
pytest tests/test_packaging_constraints.py::TestCaseConstraints::test_exact_case_multiple -vv

# Run with print statements visible
pytest tests/test_packaging_constraints.py::TestSmallInstance -s

# Run with debugger on failure
pytest tests/test_packaging_constraints.py::TestMediumInstance --pdb

# Generate coverage report
pytest tests/test_packaging_constraints.py --cov=src/optimization --cov-report=term-missing
```

## Future Enhancements

### Additional Test Scenarios

1. **Truck Schedule Integration**
   - Test Monday afternoon to 6104
   - Test Wednesday morning via Lineage
   - Test Friday double trucks
   - Day-specific packaging constraints

2. **Hub Inventory**
   - Multi-day hub consolidation
   - Pallet accumulation and release
   - Hub capacity constraints

3. **Real-World Data**
   - Test with actual SAP IBP forecasts
   - Compare optimized vs manual plans
   - Validate against historical shipments

4. **Cost Optimization**
   - Verify model minimizes partial pallets
   - Test full-truck preference
   - Validate transport cost accuracy

5. **Solver Comparison**
   - Test with CBC, GLPK, Gurobi, CPLEX
   - Compare solution quality
   - Benchmark solve times

### Test Metrics to Track

- Test coverage percentage
- Average solve time by instance size
- Number of case constraint violations (should be 0)
- Average pallet packing efficiency
- Solver success rate

## Contact and Support

For questions about the packaging constraint tests:

1. Review this documentation
2. Check test comments in source files
3. Review related documentation:
   - `/docs/EXCEL_TEMPLATE_SPEC.md` - Input data formats
   - `/data/examples/MANUFACTURING_SCHEDULE.md` - Operational details
   - `/data/examples/NETWORK_ROUTES.md` - Route topology

## Summary

The packaging constraint test suite provides:

✓ **Comprehensive validation** of case and pallet constraints
✓ **Reusable utilities** for test data generation and validation
✓ **Progressive complexity** from unit to integration to performance tests
✓ **Clear documentation** of expected behavior
✓ **Regression protection** for future code changes
✓ **Performance benchmarks** to prevent slowdowns

These tests ensure that the optimization model produces realistic, executable production and distribution plans that respect real-world packaging constraints.
