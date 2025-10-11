# Packaging Constraints Implementation Guide

## Overview

This document provides technical guidance for implementing integer packaging constraints in the production planning optimization models. It covers the mathematical formulation, Pyomo implementation, and integration with existing models.

## Mathematical Formulation

### Decision Variables

#### Current (Continuous)
```
production[d, p] ∈ ℝ₊     (non-negative reals)
shipment[r, p, t] ∈ ℝ₊    (non-negative reals)
```

#### Proposed (Integer-Constrained)
```
production[d, p] ∈ 10ℤ₊   (non-negative multiples of 10)
shipment[r, p, t] ∈ 10ℤ₊  (non-negative multiples of 10)
pallets[r, p, t] ∈ ℤ₊      (non-negative integers)
```

### Constraints

#### Case Constraint (10-unit multiples)
```
∀d, p: production[d, p] = 10 × cases[d, p]
       cases[d, p] ∈ ℤ₊
```

Or equivalently in Pyomo:
```
∀d, p: production[d, p] mod 10 = 0
```

#### Pallet Constraint (ceiling division for partial pallets)
```
∀r, p, t: pallets[r, p, t] ≥ shipment[r, p, t] / 320
          pallets[r, p, t] ∈ ℤ₊
```

#### Truck Capacity Constraint (44 pallets max)
```
∀r, t: Σₚ pallets[r, p, t] ≤ 44
```

Where:
- `r` = route (truck departure)
- `p` = product
- `t` = time (date)
- `d` = production date

### Demand Satisfaction with Rounding

Original constraint:
```
∀loc, p, t: delivered[loc, p, t] ≥ demand[loc, p, t]
```

Modified to allow case rounding:
```
∀loc, p, t: delivered[loc, p, t] ≥ ⌈demand[loc, p, t] / 10⌉ × 10
```

This ensures demand is met but allows up to 9 units overage per product per day.

## Pyomo Implementation

### Option 1: Integer Variables (Recommended)

```python
from pyomo.environ import Integers, NonNegativeIntegers

# Decision variable: number of cases
model.production_cases = Var(
    model.dates,
    model.products,
    within=NonNegativeIntegers,
    doc="Number of cases to produce (1 case = 10 units)"
)

# Derived variable: production in units
def production_units_rule(model, d, p):
    return model.production[d, p] == 10 * model.production_cases[d, p]

model.production_units_def = Constraint(
    model.dates,
    model.products,
    rule=production_units_rule,
    doc="Production in units = 10 × cases"
)
```

### Option 2: Modulo Constraint

```python
from pyomo.environ import NonNegativeReals

# Keep continuous variables but add divisibility constraint
model.production = Var(
    model.dates,
    model.products,
    within=NonNegativeReals,
    doc="Production quantity (must be multiple of 10)"
)

# Note: Pyomo doesn't directly support modulo constraints
# This requires reformulation using integer variables
```

### Option 3: Binary Expansion (For Advanced Cases)

```python
# For very tight formulations, decompose into binary variables
# production = 10 × Σᵢ 2ⁱ × binary[i]
# This is typically overkill for this problem
```

### Recommended: Option 1 - Integer Cases Variable

This is the cleanest and most solver-friendly approach.

## Implementation in ProductionOptimizationModel

### Step 1: Add Case Variables

Modify `/home/sverzijl/planning_latest/src/optimization/production_model.py`:

```python
from pyomo.environ import (
    ConcreteModel,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    NonNegativeIntegers,  # Add this import
    minimize,
    value,
)

class ProductionOptimizationModel(BaseOptimizationModel):
    # ... existing code ...

    # Constants for packaging
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320
    PALLETS_PER_TRUCK = 44
    UNITS_PER_TRUCK = 14080

    def build_model(self) -> ConcreteModel:
        model = ConcreteModel()

        # Sets
        model.dates = list(self.production_dates)
        model.products = list(self.products)

        # NEW: Decision variables in cases (integers)
        model.production_cases = Var(
            model.dates,
            model.products,
            within=NonNegativeIntegers,
            doc="Production quantity in cases (1 case = 10 units)"
        )

        # Production in units (derived from cases)
        model.production = Var(
            model.dates,
            model.products,
            within=NonNegativeReals,
            doc="Production quantity in units (= 10 × cases)"
        )

        # NEW: Constraint linking units to cases
        def production_units_rule(model, d, p):
            return model.production[d, p] == self.UNITS_PER_CASE * model.production_cases[d, p]

        model.production_units_con = Constraint(
            model.dates,
            model.products,
            rule=production_units_rule,
            doc="Production units = 10 × cases"
        )

        # ... rest of existing constraints ...
```

### Step 2: Update Demand Satisfaction Constraint

```python
def demand_satisfaction_rule(model, p):
    total_production = sum(model.production[d, p] for d in model.dates)

    # Round demand up to next case
    demand = self.total_demand_by_product[p]
    demand_cases = -(-demand // self.UNITS_PER_CASE)  # Ceiling division
    demand_rounded = demand_cases * self.UNITS_PER_CASE

    return total_production >= demand_rounded

model.demand_satisfaction_con = Constraint(
    model.products,
    rule=demand_satisfaction_rule,
    doc="Total production meets demand (rounded to cases)"
)
```

### Step 3: Update Solution Extraction

```python
def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
    # Extract production quantities
    production_by_date_product: Dict[Tuple[Date, str], float] = {}
    production_cases_by_date_product: Dict[Tuple[Date, str], int] = {}

    for d in model.dates:
        for p in model.products:
            qty = value(model.production[d, p])
            cases = value(model.production_cases[d, p])

            if qty > 1e-6:
                production_by_date_product[(d, p)] = qty
                production_cases_by_date_product[(d, p)] = int(cases)

    # Add validation
    for (d, p), qty in production_by_date_product.items():
        remainder = qty % self.UNITS_PER_CASE
        if remainder > 1e-6:
            warnings.warn(
                f"Production at {d} for {p} is {qty}, "
                f"not a multiple of {self.UNITS_PER_CASE}"
            )

    return {
        'production_by_date_product': production_by_date_product,
        'production_cases_by_date_product': production_cases_by_date_product,
        # ... rest of solution ...
    }
```

## Implementation in IntegratedProductionDistributionModel

### Step 1: Add Pallet Variables

Modify `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`:

```python
class IntegratedProductionDistributionModel(BaseOptimizationModel):
    # ... existing code ...

    # Packaging constants
    UNITS_PER_CASE = 10
    CASES_PER_PALLET = 32
    UNITS_PER_PALLET = 320
    PALLETS_PER_TRUCK = 44

    def build_model(self) -> ConcreteModel:
        model = ConcreteModel()

        # ... existing sets ...

        # NEW: Integer decision variables
        model.production_cases = Var(
            model.production_dates,
            model.products,
            within=NonNegativeIntegers,
            doc="Production in cases"
        )

        model.shipment_cases = Var(
            model.route_indices,
            model.products,
            model.delivery_dates,
            within=NonNegativeIntegers,
            doc="Shipment in cases"
        )

        model.pallets_shipped = Var(
            model.route_indices,
            model.products,
            model.delivery_dates,
            within=NonNegativeIntegers,
            doc="Number of pallets shipped (1 pallet = 32 cases)"
        )

        # Continuous variables (derived from cases)
        model.production = Var(...)  # As before
        model.shipment = Var(...)    # As before

        # NEW: Link units to cases
        def production_units_rule(model, d, p):
            return model.production[d, p] == self.UNITS_PER_CASE * model.production_cases[d, p]

        model.production_units_con = Constraint(...)

        def shipment_units_rule(model, r, p, t):
            return model.shipment[r, p, t] == self.UNITS_PER_CASE * model.shipment_cases[r, p, t]

        model.shipment_units_con = Constraint(...)

        # ... existing constraints ...
```

### Step 2: Add Pallet Calculation Constraint

```python
def pallet_calculation_rule(model, r, p, t):
    """
    Calculate pallets needed for shipment (ceiling division).

    pallets ≥ shipment_cases / 32
    pallets ∈ ℤ₊

    This ensures partial pallets consume full pallet space.
    """
    shipment_cases = model.shipment_cases[r, p, t]
    pallets = model.pallets_shipped[r, p, t]

    # Integer division ceiling: pallets ≥ ⌈cases / 32⌉
    # Implemented as: pallets × 32 ≥ cases
    return pallets * self.CASES_PER_PALLET >= shipment_cases

model.pallet_calculation_con = Constraint(
    model.route_indices,
    model.products,
    model.delivery_dates,
    rule=pallet_calculation_rule,
    doc="Pallets needed for shipment (rounds up for partial pallets)"
)
```

### Step 3: Add Truck Capacity Constraint

This requires grouping shipments by truck departure:

```python
def truck_capacity_rule(model, truck_id, departure_date):
    """
    Limit total pallets on each truck to 44 pallets max.

    This constraint requires identifying which routes/shipments
    correspond to the same physical truck.
    """
    # Get all routes that use this truck on this date
    relevant_routes = self._get_routes_for_truck(truck_id, departure_date)

    total_pallets = sum(
        model.pallets_shipped[r, p, delivery_date]
        for r in relevant_routes
        for p in model.products
        for delivery_date in model.delivery_dates
        if self._shipment_uses_truck(r, delivery_date, truck_id, departure_date)
    )

    return total_pallets <= self.PALLETS_PER_TRUCK

# Note: This requires truck schedule integration
# See below for details
```

### Step 4: Truck Schedule Integration

To properly enforce truck capacity, we need to map shipments to specific truck departures:

```python
def _extract_truck_assignments(self) -> Dict:
    """
    Map routes and delivery dates to truck departures.

    Returns mapping:
    {
        (route_idx, delivery_date): {
            'truck_id': str,
            'departure_date': date,
            'origin': str,
            'destination': str,
        }
    }
    """
    truck_assignments = {}

    if not self.truck_schedules:
        return truck_assignments

    for route_idx, route_info in self.enumerated_routes.items():
        # Get first leg (direct from manufacturing)
        first_leg = route_info['legs'][0]
        origin = first_leg['origin_id']

        # Find matching truck schedule
        for delivery_date in self.delivery_dates:
            # Work backwards from delivery to find departure
            transit_days = route_info['total_transit_time']
            departure_date = delivery_date - timedelta(days=int(transit_days))

            # Find truck schedule for this route and date
            truck = self._find_truck_schedule(origin, first_leg['destination_id'], departure_date)

            if truck:
                truck_assignments[(route_idx, delivery_date)] = {
                    'truck_id': truck.id,
                    'departure_date': departure_date,
                    'origin': origin,
                    'destination': first_leg['destination_id'],
                }

    return truck_assignments

def build_model(self) -> ConcreteModel:
    # ... earlier code ...

    # Extract truck assignments
    self.truck_assignments = self._extract_truck_assignments()

    # Build truck departure set
    truck_departures = set()
    for assignment in self.truck_assignments.values():
        truck_departures.add((assignment['truck_id'], assignment['departure_date']))

    model.truck_departures = list(truck_departures)

    # Truck capacity constraint
    def truck_capacity_rule(model, truck_id, departure_date):
        # Sum pallets for all shipments on this truck
        total_pallets = sum(
            model.pallets_shipped[route_idx, p, delivery_date]
            for (route_idx, delivery_date), assignment in self.truck_assignments.items()
            if assignment['truck_id'] == truck_id
            and assignment['departure_date'] == departure_date
            for p in model.products
        )

        return total_pallets <= self.PALLETS_PER_TRUCK

    model.truck_capacity_con = Constraint(
        model.truck_departures,
        rule=truck_capacity_rule,
        doc="Truck capacity: max 44 pallets per truck departure"
    )
```

## Solver Considerations

### Solver Selection

Integer programming requires MIP-capable solvers:

| Solver | Type | Speed | Cost | Recommendation |
|--------|------|-------|------|----------------|
| GLPK | Open-source | Slow | Free | Testing only |
| CBC | Open-source | Medium | Free | **Recommended for production** |
| Gurobi | Commercial | Fast | $$$$ | Large instances |
| CPLEX | Commercial | Fast | $$$$ | Enterprise |

### Solver Configuration

```python
from src.optimization.solver_config import SolverConfig

# For testing (GLPK)
config_test = SolverConfig(
    solver_name='glpk',
    time_limit_seconds=60,
    mip_gap=0.01,  # 1% optimality gap acceptable
)

# For production (CBC)
config_prod = SolverConfig(
    solver_name='cbc',
    time_limit_seconds=300,
    mip_gap=0.001,  # 0.1% gap
    threads=4,
)

# For large instances (Gurobi)
config_large = SolverConfig(
    solver_name='gurobi',
    time_limit_seconds=600,
    mip_gap=0.0001,
    threads=8,
    solver_options={
        'MIPFocus': 1,  # Focus on feasibility
        'Heuristics': 0.2,
        'Cuts': 2,  # Aggressive cutting planes
    }
)
```

### Performance Tuning

For integer programming problems, performance is critical:

1. **Warm Start**: Provide initial feasible solution
   ```python
   # Solve continuous relaxation first
   model_relaxed = build_model_without_integer_constraints()
   result_relaxed = solve(model_relaxed)

   # Round to feasible integer solution
   initial_solution = round_to_feasible(result_relaxed)

   # Use as warm start for MIP
   model_mip = build_model_with_integer_constraints()
   result_mip = solve(model_mip, initial_solution=initial_solution)
   ```

2. **Problem Reduction**: Fix variables when possible
   ```python
   # Fix zero production on weekends if always suboptimal
   for d in model.dates:
       if is_weekend(d):
           for p in model.products:
               model.production_cases[d, p].fix(0)
   ```

3. **Strengthened Constraints**: Add valid inequalities
   ```python
   # Example: Total production must be at least total demand
   def total_production_lower_bound_rule(model):
       total_demand_cases = sum(
           -(-self.total_demand_by_product[p] // self.UNITS_PER_CASE)
           for p in model.products
       )
       total_production_cases = sum(
           model.production_cases[d, p]
           for d in model.dates
           for p in model.products
       )
       return total_production_cases >= total_demand_cases

   model.total_production_lb = Constraint(
       rule=total_production_lower_bound_rule
   )
   ```

## Testing Strategy

### Phase 1: Unit Tests
- Verify integer variables are created
- Check constraint formulation
- Validate solution extraction

### Phase 2: Small Integration Tests
- 3-day horizon, 1 product
- Verify case multiples in solution
- Check pallet calculations

### Phase 3: Medium Integration Tests
- 7-day horizon, 2 products
- Verify demand satisfaction with rounding
- Check truck capacity constraints

### Phase 4: Performance Tests
- 28-day horizon, 4 products
- Measure solve time
- Compare solution quality vs continuous relaxation

### Phase 5: Regression Tests
- Ensure existing tests still pass
- Verify backward compatibility
- Check solution feasibility

## Migration Plan

### Step 1: Add Integer Constraints (Non-Breaking)

Add integer variables **alongside** existing continuous variables:

```python
# Keep existing continuous variables
model.production = Var(..., within=NonNegativeReals)

# Add new integer variables
model.production_cases = Var(..., within=NonNegativeIntegers)

# Link them with constraint
model.production[d, p] == 10 * model.production_cases[d, p]
```

This allows gradual testing without breaking existing functionality.

### Step 2: Add Feature Flag

Control integer constraints with parameter:

```python
class ProductionOptimizationModel:
    def __init__(
        self,
        ...,
        enforce_packaging_constraints: bool = False,  # Feature flag
    ):
        self.enforce_packaging_constraints = enforce_packaging_constraints

    def build_model(self):
        if self.enforce_packaging_constraints:
            # Use integer variables
            model.production_cases = Var(..., within=NonNegativeIntegers)
            # ... packaging constraints ...
        else:
            # Use continuous variables (legacy)
            model.production = Var(..., within=NonNegativeReals)
            # ... existing constraints ...
```

### Step 3: Gradual Rollout

1. Test with small instances
2. Compare solutions with/without constraints
3. Verify performance is acceptable
4. Enable by default once stable
5. Remove feature flag in future version

### Step 4: Update Documentation

- Update model documentation
- Add packaging constraints section
- Update examples and tutorials
- Document performance expectations

## Common Pitfalls and Solutions

### Pitfall 1: Infeasibility Due to Rounding

**Problem**: Demand of 1,235 units rounds to 1,240, but exact capacity is 1,235.

**Solution**: Always round demand up when checking feasibility:
```python
demand_rounded = -(-demand // UNITS_PER_CASE) * UNITS_PER_CASE
production >= demand_rounded
```

### Pitfall 2: Solver Can't Find Solution

**Problem**: Integer programming is harder; solver times out.

**Solution**:
- Increase time limit
- Use better solver (CBC or Gurobi)
- Reduce problem size
- Add warm start from relaxation

### Pitfall 3: Partial Pallet Constraint Not Tight Enough

**Problem**: Model doesn't properly account for wasted pallet space.

**Solution**: Use tight pallet formulation:
```python
# Weak (may allow pallets < cases/32):
pallets >= shipment / 320

# Strong (ceiling division):
pallets * 32 >= shipment_cases
pallets ∈ ℤ₊
```

### Pitfall 4: Truck Capacity Ignored

**Problem**: Shipments exceed 44 pallets per truck.

**Solution**: Properly map shipments to truck departures and aggregate:
```python
# Group by physical truck
for truck_id, departure_date in truck_departures:
    sum(pallets for all shipments on this truck) <= 44
```

### Pitfall 5: Performance Degradation

**Problem**: Solve time increases from 5s to 300s.

**Solution**:
- Profile bottleneck constraints
- Strengthen formulation with valid inequalities
- Use commercial solver for large instances
- Consider rolling horizon approach

## Example: Complete Implementation

See `/home/sverzijl/planning_latest/tests/test_packaging_constraints.py` for complete test examples.

Key files to modify:
1. `/home/sverzijl/planning_latest/src/optimization/production_model.py`
2. `/home/sverzijl/planning_latest/src/optimization/integrated_model.py`
3. `/home/sverzijl/planning_latest/src/optimization/solver_config.py`

## Performance Benchmarks

Expected solve times with CBC solver on modern hardware:

| Instance Size | Products | Days | Variables | Constraints | Solve Time |
|--------------|----------|------|-----------|-------------|------------|
| Small | 1 | 7 | ~100 | ~150 | < 5s |
| Medium | 2 | 14 | ~500 | ~800 | < 30s |
| Large | 4 | 28 | ~2,000 | ~3,500 | < 300s |
| Very Large | 5 | 60 | ~10,000 | ~18,000 | < 1800s |

With Gurobi, expect 5-10x speedup.

## Summary

Implementing packaging constraints requires:

1. **Integer variables** for cases and pallets
2. **Linking constraints** between units and cases
3. **Ceiling division** for partial pallet calculation
4. **Truck capacity** constraints aggregated by departure
5. **Solver configuration** appropriate for MIP
6. **Performance tuning** for larger instances
7. **Comprehensive testing** at all levels

The test suite in `test_packaging_constraints.py` provides regression protection and performance benchmarks to ensure the implementation is correct and performant.
