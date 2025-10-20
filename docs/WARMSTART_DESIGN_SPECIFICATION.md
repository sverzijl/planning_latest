# Warmstart Design Specification for UnifiedNodeModel

**Document Version:** 1.0
**Date:** 2025-10-19
**Author:** Pyomo Optimization Expert
**Status:** Design Proposal

---

## Executive Summary

This document specifies a warmstart mechanism for the UnifiedNodeModel to improve MIP solve performance by providing initial values for binary/integer variables, particularly the `product_produced` variables that control which products are manufactured on each day.

**Key Findings:**
- **Pyomo supports warmstart** via `variable.set_value()` + `solver.solve(model, warmstart=True)`
- **CBC has LIMITED warmstart support** - requires CBC 2.8.0+, cpxlp format, feasible complete solutions
- **Gurobi/CPLEX have ROBUST warmstart** - support both MIPStart (feasible solutions) and VarHint (partial hints)
- **Expected speedup:** 20-50% reduction in solve time when good initial solution provided

---

## 1. Problem Context

### 1.1 Performance Bottleneck

The UnifiedNodeModel has binary `product_produced` variables that cause slow MIP solves (>300s for some problem instances):

```python
# Binary: Which products are produced on each day?
model.product_produced[node_id, product, date] ∈ {0, 1}

# Integer: Count of products produced
model.num_products_produced[node_id, date] ∈ {0, 1, 2, ..., 5}

# Binary: Is production happening?
model.production_day[node_id, date] ∈ {0, 1}
```

**Root Cause:**
- Solver explores many infeasible/suboptimal combinations (e.g., producing all 5 SKUs daily)
- Optimal pattern typically produces 2-3 SKUs per day (campaign production)
- No guidance provided → solver wastes time exploring bad solutions

**Desired Behavior:**
- Start from a good initial solution (e.g., heuristic campaign schedule)
- Guide solver toward 2-3 SKU production patterns
- Reduce time exploring infeasible/expensive solution space

---

## 2. Pyomo Warmstart API Research

### 2.1 How Warmstart Works in Pyomo

**Two-Step Process:**

1. **Set initial variable values** (before calling solve):
   ```python
   # Approach 1: Direct assignment (recommended)
   model.x[i] = initial_value

   # Approach 2: Using set_value() method
   model.x[i].set_value(initial_value)
   ```

2. **Enable warmstart when solving:**
   ```python
   results = solver.solve(model, warmstart=True)
   ```

**Complete Example:**
```python
from pyomo.environ import *

# Build model
model = ConcreteModel()
model.I = Set(initialize=[1, 2, 3])
model.x = Var(model.I, domain=Binary)
model.obj = Objective(expr=sum(model.x[i] for i in model.I))
# ... constraints ...

# Set initial values for binary variables
model.x[1] = 1
model.x[2] = 0
model.x[3] = 1

# Solve with warmstart
solver = SolverFactory('gurobi')  # or 'cbc', 'cplex'
results = solver.solve(model, warmstart=True, tee=True)
```

### 2.2 Solver Interface Differences

**LP/MPS File Interface (CBC, GLPK):**
- Adding `warmstart=True` creates a separate warmstart solution file
- File contains initial values for integer/binary variables
- Solver reads file and uses as MIP start

**NL File Interface (AMPL solvers like "gurobi_ampl"):**
- Initial values ALWAYS passed to solver (if not None)
- `warmstart=True` keyword NOT accepted (raises error)
- Solver decides whether to use values

**Python/Direct API (Gurobi Persistent Solver):**
- Can use advanced features like VarHint (partial hints)
- More control over MIP start behavior

---

## 3. CBC Solver Warmstart Capability

### 3.1 CBC Warmstart Support

**Status:** LIMITED but functional

**Requirements:**
- CBC version 2.8.0 or later
- Problem format: CPXLP (`.lp` file format)
- Solution: MUST be feasible and complete (all variables)

**Known Issues:**
- **Pyomo path issue:** CBC expects relative path, Pyomo provides absolute path
  - **Workaround:** Use `warmstart_file='./temp_initial_sol.soln'` parameter
- **Silent failures:** CBC silently ignores warmstart if file not found or infeasible
- **Windows:** CBC may ignore warmstart if file on different drive

**CBC Warmstart Example:**
```python
solver = SolverFactory('cbc')
results = solver.solve(
    model,
    warmstart=True,
    warmstart_file='./warmstart.soln',  # Relative path workaround
    tee=True
)
```

**Verification:**
- Check CBC output for "Read MIP start from file" message
- If not present, warmstart was ignored

### 3.2 CBC Limitations

**Critical Constraints:**
1. **Complete feasible solution required** - partial solutions ignored
2. **Only integer/binary variables** - continuous variables not needed
3. **Relative path workaround** - absolute paths may fail silently
4. **No VarHint support** - cannot provide "hints" for partial solutions

**Performance Impact:**
- **Good warmstart:** 20-40% faster solve time
- **Poor/infeasible warmstart:** NO speedup (or slight slowdown from file I/O)
- **Partial warmstart:** Ignored by CBC (no effect)

---

## 4. Gurobi/CPLEX Warmstart Capability

### 4.1 MIPStart vs VarHint (Gurobi-specific)

**Two mechanisms available:**

| Feature | MIPStart | VarHint |
|---------|----------|---------|
| **Purpose** | Provide feasible starting solution | Guide search toward anticipated values |
| **Completeness** | Full feasible solution | Partial solution acceptable |
| **Validation** | Must satisfy all constraints | Not validated (just guidance) |
| **Heuristics** | Enables RINS, solution polishing | Triggers diving and fixing heuristics |
| **Multiple** | Can provide multiple MIPStarts | Single hint per variable |
| **Performance** | Best when near-optimal | Best when feasible solution hard to find |

**Recommendation:** Use **MIPStart** when you have a good feasible solution (e.g., from heuristic)

**MIPStart Example (Gurobi):**
```python
# Set initial values
for (node_id, product, date) in model.product_produced:
    model.product_produced[node_id, product, date] = heuristic_value

# Solve with warmstart
solver = SolverFactory('gurobi')
results = solver.solve(model, warmstart=True, tee=True)
```

**VarHint Example (Gurobi Persistent):**
```python
from pyomo.environ import SolverFactory

# Use persistent solver for VarHint
solver = SolverFactory('gurobi_persistent')
solver.set_instance(model)

# Set VarHint attribute (not MIPStart)
for (node_id, product, date) in model.product_produced:
    var = model.product_produced[node_id, product, date]
    var.VarHintVal = heuristic_value  # Hint value
    var.VarHintPri = 1  # Priority (higher = more important)

# Solve
results = solver.solve(tee=True)
```

### 4.2 CPLEX Warmstart

**Mechanism:** MIPStart only (no VarHint equivalent)

**Example:**
```python
# Set initial values
model.x[1] = 1
model.x[2] = 0

# Solve with warmstart
solver = SolverFactory('cplex')
results = solver.solve(model, warmstart=True, tee=True)
```

**Requirements:**
- Solution MUST be feasible
- CPLEX rejects infeasible warmstarts and starts from scratch

---

## 5. Recommended Warmstart Implementation

### 5.1 Design Goals

1. **Solver-agnostic:** Work with CBC, Gurobi, CPLEX, GLPK
2. **Graceful degradation:** If warmstart fails, solve proceeds normally
3. **Optional feature:** Warmstart is opt-in (default behavior unchanged)
4. **Easy to use:** Simple API for providing initial values
5. **Heuristic-friendly:** Accept values from heuristic algorithms

### 5.2 Proposed API

**Approach 1: Warmstart Dictionary (Simple)**

```python
# Define warmstart values
warmstart_values = {
    'product_produced': {
        ('6122', 'Product_A', date(2025, 10, 20)): 1,
        ('6122', 'Product_B', date(2025, 10, 20)): 1,
        ('6122', 'Product_C', date(2025, 10, 20)): 0,
        # ... more values
    },
    'production_day': {
        ('6122', date(2025, 10, 20)): 1,
        # ... more values
    }
}

# Solve with warmstart
result = model.solve(
    solver_name='cbc',
    warmstart=warmstart_values,  # NEW parameter
    tee=True
)
```

**Approach 2: Heuristic Object (Advanced)**

```python
# Define heuristic that generates warmstart
from src.optimization.heuristics import CampaignSchedulingHeuristic

heuristic = CampaignSchedulingHeuristic(
    max_products_per_day=2,  # Limit to 2 SKUs per day
    campaign_length=3,       # 3-day campaigns
)

# Solve with heuristic warmstart
result = model.solve(
    solver_name='cbc',
    heuristic=heuristic,     # NEW parameter
    tee=True
)
```

### 5.3 Implementation Architecture

**Three components:**

1. **Warmstart Validator** - Checks feasibility before applying
2. **Variable Setter** - Sets values on Pyomo model variables
3. **Solver Invoker** - Passes warmstart to solver with correct options

**Flowchart:**

```
User provides warmstart
        ↓
Validate feasibility (optional)
        ↓
Set variable values on model
        ↓
Build Pyomo model
        ↓
Detect solver type
        ↓
    ┌───┴─────┐
    ↓         ↓
  CBC      Gurobi/CPLEX
    ↓         ↓
warmstart   warmstart
 =True      =True
    ↓         ↓
Solve with initial values
```

---

## 6. Detailed Implementation Plan

### 6.1 Code Changes to UnifiedNodeModel

**File:** `src/optimization/unified_node_model.py`

**Step 1: Add warmstart parameter to solve() method**

```python
def solve(
    self,
    solver_name: Optional[str] = None,
    time_limit_seconds: Optional[float] = None,
    mip_gap: Optional[float] = None,
    tee: bool = False,
    use_aggressive_heuristics: bool = False,
    warmstart: Optional[Dict[str, Dict]] = None,  # NEW PARAMETER
) -> OptimizationResult:
    """Build and solve the unified node model.

    Args:
        solver_name: Solver to use (None = auto-detect)
        time_limit_seconds: Time limit in seconds
        mip_gap: MIP gap tolerance
        tee: Show solver output
        use_aggressive_heuristics: Enable aggressive CBC heuristics
        warmstart: Optional warmstart values dictionary
            Format: {
                'variable_name': {
                    (index_tuple): value,
                    ...
                }
            }
            Example: {
                'product_produced': {
                    ('6122', 'Product_A', date(2025,10,20)): 1,
                    ('6122', 'Product_B', date(2025,10,20)): 0,
                }
            }

    Returns:
        OptimizationResult with solve status and metrics
    """
    # Store warmstart for use in build_model
    self._warmstart = warmstart

    # Call base class solve (builds model + solves)
    return super().solve(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        mip_gap=mip_gap,
        tee=tee,
        use_aggressive_heuristics=use_aggressive_heuristics,
    )
```

**Step 2: Apply warmstart after building model (before solve)**

**Option A: Modify build_model() to apply warmstart at the end**

```python
def build_model(self) -> ConcreteModel:
    """Build the Pyomo optimization model."""
    # ... existing model building code ...

    # Apply warmstart if provided (AFTER all variables created)
    if hasattr(self, '_warmstart') and self._warmstart:
        self._apply_warmstart(model, self._warmstart)

    return model
```

**Option B: Override base_model.py solve() to apply after build**

Modify `base_model.py` to call an optional hook:

```python
# In base_model.py solve() method, after building:
build_start = time.time()
self.model = self.build_model()
self._build_time = time.time() - build_start

# NEW: Apply warmstart if model has hook
if hasattr(self, '_apply_model_warmstart'):
    self._apply_model_warmstart(self.model)
```

Then in `unified_node_model.py`:

```python
def _apply_model_warmstart(self, model: ConcreteModel):
    """Hook called by base class after building model."""
    if hasattr(self, '_warmstart') and self._warmstart:
        self._apply_warmstart(model, self._warmstart)
```

**Recommendation:** Use **Option A** (modify build_model) - simpler and keeps logic localized

**Step 3: Implement _apply_warmstart() method**

```python
def _apply_warmstart(
    self,
    model: ConcreteModel,
    warmstart: Dict[str, Dict]
) -> None:
    """Apply warmstart values to model variables.

    Args:
        model: Pyomo ConcreteModel
        warmstart: Dictionary of variable values
            Format: {
                'variable_name': {index_tuple: value, ...}
            }
    """
    if not warmstart:
        return

    print("\n" + "="*60)
    print("Applying Warmstart Initial Solution")
    print("="*60)

    total_vars_set = 0

    for var_name, values_dict in warmstart.items():
        if not hasattr(model, var_name):
            warnings.warn(f"Warmstart variable '{var_name}' not found in model")
            continue

        var_component = getattr(model, var_name)
        vars_set = 0

        for index, value in values_dict.items():
            # Handle both indexed and non-indexed variables
            try:
                if isinstance(index, tuple):
                    # Indexed variable
                    if index in var_component:
                        var_component[index] = value
                        vars_set += 1
                else:
                    # Non-indexed variable
                    var_component.set_value(value)
                    vars_set += 1
            except (KeyError, ValueError) as e:
                # Index not in variable domain (may be out of planning horizon)
                continue

        total_vars_set += vars_set
        print(f"  {var_name}: {vars_set:,} values set")

    print(f"Total warmstart values applied: {total_vars_set:,}")
    print("="*60 + "\n")
```

**Step 4: Modify base_model.py to pass warmstart=True to solver**

Current code in `base_model.py` solve():

```python
results = solver.solve(
    self.model,
    tee=tee,
    symbolic_solver_labels=False,
    load_solutions=False,
)
```

**Proposed change:**

```python
# Check if warmstart was applied
use_warmstart = (
    hasattr(self, '_warmstart') and
    self._warmstart is not None and
    len(self._warmstart) > 0
)

# Solve with warmstart if applicable
solve_kwargs = {
    'tee': tee,
    'symbolic_solver_labels': False,
    'load_solutions': False,
}

# Enable warmstart for solvers that support it
if use_warmstart:
    # CBC and Gurobi/CPLEX support warmstart keyword
    # NL-file interface solvers (gurobi_ampl) don't accept warmstart keyword
    # but always pass initial values anyway
    if solver_name not in ['gurobi_ampl', 'cplexamp', 'bonmin', 'ipopt']:
        solve_kwargs['warmstart'] = True
        print("Warmstart enabled for solver")

results = solver.solve(self.model, **solve_kwargs)
```

### 6.2 Warmstart Validation (Optional Enhancement)

**Purpose:** Verify warmstart solution is feasible before solve

**Implementation:**

```python
def _validate_warmstart(
    self,
    model: ConcreteModel,
    warmstart: Dict[str, Dict],
    check_constraints: bool = False
) -> Tuple[bool, str]:
    """Validate warmstart solution.

    Args:
        model: Pyomo model
        warmstart: Warmstart values
        check_constraints: If True, check constraint satisfaction (slow)

    Returns:
        Tuple of (is_valid, message)
    """
    # Check 1: All variables exist in model
    for var_name in warmstart.keys():
        if not hasattr(model, var_name):
            return False, f"Variable '{var_name}' not found in model"

    # Check 2: All indices are valid
    for var_name, values_dict in warmstart.items():
        var_component = getattr(model, var_name)
        for index in values_dict.keys():
            if index not in var_component:
                return False, f"Index {index} not valid for variable '{var_name}'"

    # Check 3: All values are within bounds
    for var_name, values_dict in warmstart.items():
        var_component = getattr(model, var_name)
        for index, value in values_dict.items():
            var = var_component[index]

            # Check lower bound
            if var.lb is not None and value < var.lb - 1e-6:
                return False, f"Value {value} below lower bound {var.lb} for {var_name}[{index}]"

            # Check upper bound
            if var.ub is not None and value > var.ub + 1e-6:
                return False, f"Value {value} above upper bound {var.ub} for {var_name}[{index}]"

            # Check domain (binary/integer)
            if var.is_binary() and value not in [0, 1]:
                return False, f"Binary variable {var_name}[{index}] has non-binary value {value}"

            if var.is_integer() and not isinstance(value, int) and abs(value - round(value)) > 1e-6:
                return False, f"Integer variable {var_name}[{index}] has non-integer value {value}"

    # Check 4: Constraint satisfaction (EXPENSIVE - optional)
    if check_constraints:
        # Apply warmstart temporarily
        original_values = {}
        for var_name, values_dict in warmstart.items():
            var_component = getattr(model, var_name)
            for index, value in values_dict.items():
                original_values[(var_name, index)] = var_component[index].value
                var_component[index] = value

        # Check all constraints
        for constraint in model.component_data_objects(Constraint, active=True):
            if constraint.body is None:
                continue

            try:
                body_value = value(constraint.body)

                # Check lower bound
                if constraint.lower is not None:
                    lb_value = value(constraint.lower)
                    if body_value < lb_value - 1e-6:
                        # Restore original values
                        self._restore_values(model, original_values)
                        return False, f"Constraint {constraint.name} violated: {body_value} < {lb_value}"

                # Check upper bound
                if constraint.upper is not None:
                    ub_value = value(constraint.upper)
                    if body_value > ub_value + 1e-6:
                        # Restore original values
                        self._restore_values(model, original_values)
                        return False, f"Constraint {constraint.name} violated: {body_value} > {ub_value}"

            except (ValueError, ZeroDivisionError):
                # Can't evaluate constraint (division by zero, etc.)
                pass

        # Restore original values
        self._restore_values(model, original_values)

    return True, "Warmstart solution is valid"
```

**Usage:**

```python
def _apply_warmstart(self, model, warmstart):
    # Validate before applying
    is_valid, message = self._validate_warmstart(model, warmstart, check_constraints=False)

    if not is_valid:
        warnings.warn(f"Warmstart validation failed: {message}. Proceeding without warmstart.")
        return

    # Apply warmstart
    # ... existing code ...
```

---

## 7. Warmstart Generation Strategies

### 7.1 Strategy 1: Greedy Campaign Heuristic

**Algorithm:**
1. Sort products by total demand (descending)
2. For each day in planning horizon:
   - Select top K products (K=2 or 3)
   - Produce to meet next N days of demand
   - Mark `product_produced[node, product, date] = 1`

**Pseudocode:**

```python
def generate_campaign_warmstart(
    forecast: Forecast,
    planning_horizon: int,
    max_products_per_day: int = 2,
    campaign_length_days: int = 3,
) -> Dict[str, Dict]:
    """Generate warmstart using greedy campaign scheduling."""

    # Calculate total demand per product
    product_demand = defaultdict(float)
    for (node, product, date), qty in forecast.items():
        product_demand[product] += qty

    # Sort products by demand (highest first)
    sorted_products = sorted(
        product_demand.keys(),
        key=lambda p: product_demand[p],
        reverse=True
    )

    # Initialize warmstart
    warmstart = {
        'product_produced': {},
        'production_day': {},
        'num_products_produced': {},
    }

    # Assign products to days (campaign pattern)
    current_day = 0
    product_idx = 0

    while current_day < planning_horizon:
        # Select top K products for this campaign
        campaign_products = sorted_products[
            product_idx : product_idx + max_products_per_day
        ]

        # Assign to consecutive days
        for day_offset in range(campaign_length_days):
            date = start_date + timedelta(days=current_day + day_offset)

            # Set product_produced
            for product in campaign_products:
                warmstart['product_produced'][
                    ('6122', product, date)
                ] = 1

            # Set production_day
            warmstart['production_day'][('6122', date)] = 1

            # Set num_products_produced
            warmstart['num_products_produced'][
                ('6122', date)
            ] = len(campaign_products)

        # Move to next campaign
        current_day += campaign_length_days
        product_idx = (product_idx + max_products_per_day) % len(sorted_products)

    return warmstart
```

### 7.2 Strategy 2: Previous Solve Solution

**Use case:** Rolling horizon planning

**Algorithm:**
1. Solve model for days 1-28
2. Extract solution for days 1-28
3. Solve model for days 2-29 (shift window by 1 day)
4. Use days 2-28 from previous solution as warmstart

**Implementation:**

```python
def extract_warmstart_from_solution(
    model: ConcreteModel,
    shift_days: int = 0
) -> Dict[str, Dict]:
    """Extract warmstart from solved model.

    Args:
        model: Solved Pyomo model
        shift_days: Number of days to shift dates (for rolling horizon)

    Returns:
        Warmstart dictionary
    """
    warmstart = {
        'product_produced': {},
        'production_day': {},
        'num_products_produced': {},
    }

    # Extract product_produced values
    for (node_id, product, date) in model.product_produced:
        val = value(model.product_produced[node_id, product, date])

        # Shift date if rolling horizon
        if shift_days != 0:
            date = date + timedelta(days=shift_days)

        # Only store if value is meaningful (0 or 1 for binary)
        if abs(val) < 0.01:
            warmstart['product_produced'][(node_id, product, date)] = 0
        elif abs(val - 1.0) < 0.01:
            warmstart['product_produced'][(node_id, product, date)] = 1

    # Similarly for other variables
    # ...

    return warmstart
```

### 7.3 Strategy 3: Fixed Pattern Warmstart

**Use case:** Known good production pattern

**Example:** Produce Products A+B on Mon/Wed/Fri, Products C+D on Tue/Thu

```python
def generate_fixed_pattern_warmstart(
    products: List[str],
    start_date: Date,
    end_date: Date,
    pattern: Dict[int, List[str]]  # weekday -> products
) -> Dict[str, Dict]:
    """Generate warmstart with fixed weekday pattern.

    Args:
        products: List of all products
        start_date: Planning start date
        end_date: Planning end date
        pattern: Weekday to products mapping
            Example: {
                0: ['Product_A', 'Product_B'],  # Monday
                1: ['Product_C', 'Product_D'],  # Tuesday
                # ...
            }

    Returns:
        Warmstart dictionary
    """
    warmstart = {
        'product_produced': {},
        'production_day': {},
        'num_products_produced': {},
    }

    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()  # 0=Monday, 6=Sunday

        if weekday in pattern:
            # Production day
            products_today = pattern[weekday]

            for product in products:
                warmstart['product_produced'][
                    ('6122', product, current_date)
                ] = 1 if product in products_today else 0

            warmstart['production_day'][('6122', current_date)] = 1
            warmstart['num_products_produced'][
                ('6122', current_date)
            ] = len(products_today)
        else:
            # Non-production day
            for product in products:
                warmstart['product_produced'][
                    ('6122', product, current_date)
                ] = 0

            warmstart['production_day'][('6122', current_date)] = 0
            warmstart['num_products_produced'][('6122', current_date)] = 0

        current_date += timedelta(days=1)

    return warmstart
```

---

## 8. Performance Expectations

### 8.1 Expected Speedup by Solver

| Solver | Warmstart Quality | Expected Speedup | Notes |
|--------|------------------|------------------|-------|
| **CBC** | Good (near-optimal) | 20-40% | Requires feasible complete solution |
| **CBC** | Poor/infeasible | 0-5% | May be slower due to file I/O |
| **Gurobi** | Good (near-optimal) | 30-60% | Strong warmstart support |
| **Gurobi** | Partial (VarHint) | 10-30% | Guides search without full solution |
| **CPLEX** | Good (near-optimal) | 25-50% | Similar to Gurobi |
| **GLPK** | Any | 0% | No warmstart support |

### 8.2 Success Criteria

**Warmstart is EFFECTIVE if:**
- Solve time reduced by ≥20% vs. cold start
- First feasible solution found faster (≥30% reduction)
- MIP gap closes faster (steeper improvement curve)

**Warmstart is INEFFECTIVE if:**
- Solve time unchanged or slower
- Solver ignores warmstart (check logs)
- Warmstart solution is infeasible

**Diagnostic Checks:**
1. **CBC:** Look for "Read MIP start from file" in solver output
2. **Gurobi:** Look for "Read MIP start with objective X"
3. **CPLEX:** Look for "MIP start provided"
4. **Compare solve times:** Run with and without warmstart on same instance

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Test File:** `tests/test_unified_warmstart.py`

**Test Cases:**

1. **test_warmstart_parameter_acceptance**
   - Verify solve() accepts warmstart parameter
   - Verify warmstart stored in model

2. **test_warmstart_application_product_produced**
   - Set values for product_produced variables
   - Verify values applied to Pyomo model variables

3. **test_warmstart_invalid_variable_name**
   - Provide warmstart for non-existent variable
   - Verify warning issued, solve proceeds

4. **test_warmstart_invalid_index**
   - Provide warmstart for invalid index (out of date range)
   - Verify graceful handling

5. **test_warmstart_validation_feasible**
   - Provide feasible warmstart
   - Verify validation passes

6. **test_warmstart_validation_infeasible**
   - Provide infeasible warmstart (violates bounds)
   - Verify validation fails with message

7. **test_warmstart_with_cbc_solver**
   - Solve with CBC and warmstart
   - Verify warmstart=True passed to solver

8. **test_warmstart_with_gurobi_solver**
   - Solve with Gurobi and warmstart
   - Verify warmstart=True passed to solver

### 9.2 Integration Tests

**Test File:** `tests/test_integration_warmstart.py`

**Test Cases:**

1. **test_warmstart_improves_solve_time**
   - Solve same instance with and without warmstart
   - Verify warmstart version is ≥20% faster

2. **test_warmstart_campaign_heuristic**
   - Generate warmstart using campaign heuristic
   - Verify solution quality (objective within 10% of optimal)

3. **test_warmstart_rolling_horizon**
   - Solve day 1-28
   - Extract warmstart
   - Solve day 2-29 with warmstart
   - Verify faster solve time

4. **test_warmstart_does_not_change_optimal_solution**
   - Solve small instance to optimality without warmstart
   - Solve same instance with warmstart
   - Verify objective value identical (within tolerance)

### 9.3 Performance Benchmarks

**Benchmark Scenarios:**

| Scenario | Planning Horizon | Products | Expected Solve Time (No Warmstart) | Expected Solve Time (With Warmstart) |
|----------|-----------------|----------|-------------------------------------|--------------------------------------|
| Small | 7 days | 5 | 10s | 7s (-30%) |
| Medium | 14 days | 5 | 30s | 20s (-33%) |
| Large | 28 days | 5 | 120s | 80s (-33%) |
| Extra Large | 42 days | 5 | 300s+ | 200s (-33%) |

**Benchmark Script:**

```python
def benchmark_warmstart():
    """Benchmark warmstart performance."""
    scenarios = [
        ('Small', 7, 5),
        ('Medium', 14, 5),
        ('Large', 28, 5),
        ('Extra Large', 42, 5),
    ]

    results = []

    for name, days, num_products in scenarios:
        # Solve without warmstart
        start = time.time()
        result_cold = model.solve(solver_name='cbc')
        time_cold = time.time() - start

        # Generate warmstart
        warmstart = generate_campaign_warmstart(
            forecast, days, max_products_per_day=2
        )

        # Solve with warmstart
        start = time.time()
        result_warm = model.solve(
            solver_name='cbc',
            warmstart=warmstart
        )
        time_warm = time.time() - start

        speedup = (time_cold - time_warm) / time_cold * 100

        results.append({
            'scenario': name,
            'cold_start_time': time_cold,
            'warm_start_time': time_warm,
            'speedup_pct': speedup,
        })

    # Print results
    print("\nWarmstart Performance Benchmark")
    print("="*60)
    for r in results:
        print(f"{r['scenario']:15s} | Cold: {r['cold_start_time']:6.1f}s | "
              f"Warm: {r['warm_start_time']:6.1f}s | "
              f"Speedup: {r['speedup_pct']:5.1f}%")
```

---

## 10. Fallback Strategy

### 10.1 When Warmstart Fails

**Failure Modes:**
1. Warmstart solution is infeasible
2. Solver doesn't support warmstart (GLPK)
3. Warmstart file not found/not readable
4. Warmstart makes solve time WORSE

**Fallback Actions:**

```python
def solve_with_fallback(
    model,
    solver_name='cbc',
    warmstart=None,
    tee=True
):
    """Solve with warmstart, fall back to cold start if fails."""

    if warmstart is None:
        # No warmstart provided - cold start
        return model.solve(solver_name=solver_name, tee=tee)

    # Try warmstart first
    print("Attempting solve with warmstart...")
    result_warm = model.solve(
        solver_name=solver_name,
        warmstart=warmstart,
        time_limit_seconds=300,
        tee=tee
    )

    # Check if warmstart was successful
    if result_warm.is_optimal() or result_warm.is_feasible():
        print(f"Warmstart successful: {result_warm}")
        return result_warm

    # Warmstart failed - try cold start
    print("Warmstart failed, retrying without warmstart...")
    result_cold = model.solve(
        solver_name=solver_name,
        time_limit_seconds=300,
        tee=tee
    )

    return result_cold
```

### 10.2 Solver Compatibility Matrix

| Solver | Warmstart Support | Recommended Approach |
|--------|------------------|---------------------|
| **CBC** | Limited (v2.8.0+) | Use warmstart=True with relative path |
| **Gurobi** | Full (MIPStart) | Use warmstart=True |
| **Gurobi Persistent** | Full (MIPStart + VarHint) | Use VarHintVal for partial hints |
| **CPLEX** | Full (MIPStart) | Use warmstart=True |
| **GLPK** | None | Skip warmstart (no effect) |
| **gurobi_ampl** | Automatic | Don't pass warmstart=True (raises error) |

---

## 11. Implementation Checklist

### Phase 1: Core Warmstart Functionality
- [ ] Add `warmstart` parameter to `UnifiedNodeModel.solve()`
- [ ] Implement `_apply_warmstart()` method
- [ ] Modify `build_model()` to apply warmstart after variable creation
- [ ] Update `base_model.py` to pass `warmstart=True` to solver
- [ ] Add warmstart logging/diagnostics
- [ ] Write unit tests for warmstart application

### Phase 2: Heuristic Warmstart Generation
- [ ] Implement `generate_campaign_warmstart()` heuristic
- [ ] Implement `extract_warmstart_from_solution()` utility
- [ ] Implement `generate_fixed_pattern_warmstart()` utility
- [ ] Add warmstart generation module (`src/optimization/warmstart_generators.py`)
- [ ] Write unit tests for heuristic generators

### Phase 3: Validation and Error Handling
- [ ] Implement `_validate_warmstart()` method
- [ ] Add bound checking for warmstart values
- [ ] Add constraint checking (optional, expensive)
- [ ] Implement fallback to cold start on validation failure
- [ ] Add warnings for invalid warmstart data

### Phase 4: Integration and Testing
- [ ] Integration test: warmstart improves solve time
- [ ] Integration test: campaign heuristic produces good warmstart
- [ ] Integration test: rolling horizon with warmstart
- [ ] Performance benchmark suite
- [ ] Documentation: user guide for warmstart usage

### Phase 5: Advanced Features (Optional)
- [ ] Gurobi VarHint support (for partial hints)
- [ ] Multiple MIPStart support (Gurobi)
- [ ] Adaptive warmstart quality checking
- [ ] Warmstart caching for repeated solves
- [ ] UI integration: "Use Warmstart" checkbox

---

## 12. Documentation Requirements

### 12.1 User-Facing Documentation

**File:** `docs/features/WARMSTART_GUIDE.md`

**Contents:**
- What is warmstart and why use it?
- When to use warmstart (problem size, solver, solution quality goals)
- How to provide warmstart values (API examples)
- How to use built-in heuristics
- Troubleshooting warmstart failures
- Performance tuning tips

### 12.2 Developer Documentation

**Update:** `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`

**Add section:**
- Warmstart API specification
- Warmstart variable list (which variables accept warmstart)
- Warmstart validation rules
- Solver-specific warmstart behavior
- Testing guidelines for warmstart features

### 12.3 Code Comments

**Update:** `src/optimization/unified_node_model.py`

**Add docstrings:**
- `solve()` method: document warmstart parameter
- `_apply_warmstart()`: explain algorithm and error handling
- `_validate_warmstart()`: explain validation checks
- Warmstart generator functions: explain heuristic logic

---

## 13. Risks and Mitigation

### 13.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| CBC warmstart path bug | High | Medium | Use relative path workaround |
| Infeasible warmstart breaks solve | Medium | Low | Implement validation before apply |
| Warmstart makes solve SLOWER | Medium | Low | Always compare with/without, use fallback |
| Gurobi NL interface rejects warmstart keyword | Low | High | Detect solver interface, skip keyword if NL |
| Partial warmstart ignored by CBC | Medium | High | Document CBC limitation, recommend Gurobi for partial |

### 13.2 User Experience Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| User provides infeasible warmstart | Users confused by failure | Clear validation error messages |
| Warmstart doesn't improve time | User disappointed | Document when warmstart helps vs. doesn't |
| Complex API too hard to use | Low adoption | Provide simple heuristic generators |
| Warmstart behavior varies by solver | Inconsistent UX | Document solver differences clearly |

---

## 14. Alternatives Considered

### 14.1 Alternative 1: Constraint-Based Warmstart

**Approach:** Add optional constraints to guide solver instead of warmstart

```python
# Add hint constraints (soft constraints with penalties)
for (node_id, product, date), hint_value in production_hints.items():
    if hint_value == 1:
        # Encourage producing this product
        model.production_hint_penalty += (
            hint_penalty * (1 - model.product_produced[node_id, product, date])
        )
```

**Pros:**
- Works with all solvers (no warmstart support needed)
- Soft constraints allow solver to deviate if better solution exists

**Cons:**
- Changes optimization problem (not just initial solution)
- May worsen solve time if hints are poor
- More complex to tune (what penalty value to use?)

**Decision:** Rejected - Warmstart is cleaner and doesn't change problem

### 14.2 Alternative 2: Fix-and-Optimize Heuristic

**Approach:** Fix some variables, solve subproblem, unfix and resolve

```python
# Fix product selection for first 7 days
for date in first_week:
    for product in products:
        model.product_produced['6122', product, date].fix(heuristic_value)

# Solve with fixed variables
result = model.solve()

# Unfix and resolve
for date in first_week:
    for product in products:
        model.product_produced['6122', product, date].unfix()

result = model.solve()  # Use previous solution as warmstart
```

**Pros:**
- Can find good feasible solution quickly
- Useful for very large problems

**Cons:**
- More complex implementation
- Requires multiple solves
- May miss optimal solution if initial fix is poor

**Decision:** Consider for future (Phase 4+) - warmstart is prerequisite

### 14.3 Alternative 3: Decomposition Methods

**Approach:** Solve production scheduling separately, then distribution

**Pros:**
- Smaller subproblems solve faster
- Can use specialized algorithms for each subproblem

**Cons:**
- Misses interactions between production and distribution
- Much more complex to implement
- May produce suboptimal integrated solutions

**Decision:** Rejected - violates integrated optimization principle

---

## 15. Success Metrics

### 15.1 Performance Metrics

**Target:** Achieve ≥20% solve time reduction for medium/large instances

| Metric | Target | Measurement |
|--------|--------|-------------|
| Solve time reduction | ≥20% | Compare with/without warmstart on benchmark suite |
| Time to first feasible | ≥30% faster | Record time to first MIP solution |
| MIP gap at 60s | ≥2x better | Compare gap(warmstart) vs. gap(cold) at 60s mark |
| Warmstart application success rate | ≥95% | Track validation failures across test cases |

### 15.2 Code Quality Metrics

| Metric | Target |
|--------|--------|
| Test coverage (warmstart code) | ≥90% |
| Unit tests passing | 100% |
| Integration tests passing | 100% |
| Documentation completeness | 100% (all public APIs documented) |
| Code review approval | 2+ reviewers |

### 15.3 User Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Feature usage | ≥30% of solves use warmstart | Log warmstart parameter usage |
| User-reported bugs | <5 in first month | GitHub issue tracker |
| User satisfaction | ≥8/10 rating | Survey warmstart users |

---

## 16. Future Enhancements

### 16.1 Phase 5+ Features

1. **Adaptive Warmstart Quality Assessment**
   - Automatically detect if warmstart is helping or hurting
   - Disable warmstart if solve time worse than baseline

2. **Warmstart Library/Cache**
   - Store good solutions for similar problem instances
   - Reuse warmstart across runs (rolling horizon)

3. **Machine Learning Warmstart Prediction**
   - Train ML model to predict good production patterns
   - Use ML predictions as warmstart

4. **Multi-Start Strategies**
   - Provide multiple warmstart solutions to Gurobi (NumStart)
   - Solver chooses best initial solution automatically

5. **Interactive Warmstart Editing**
   - UI for manually editing warmstart values
   - Visualize warmstart production schedule
   - Click to toggle product_produced on/off

---

## 17. References

### 17.1 Pyomo Documentation
- [Working with Pyomo Models](https://pyomo.readthedocs.io/en/6.8.0/working_models.html)
- [Pyomo Solver Plugins](https://pyomo.readthedocs.io/en/6.8.1/howto/solver_recipes.html)

### 17.2 Solver Documentation
- [CBC Command Line Options](https://www.coin-or.org/Cbc/cbcuserguide.html)
- [Gurobi MIPStart](https://www.gurobi.com/documentation/9.5/refman/start.html)
- [Gurobi VarHint](https://www.gurobi.com/documentation/9.5/refman/varhintval.html)
- [CPLEX MIP Start](https://www.ibm.com/docs/en/icos/22.1.0?topic=mip-starting-from-solution)

### 17.3 Research Papers
- Fischetti, M., & Monaci, M. (2014). "Proximity search for 0-1 mixed-integer convex programming"
- Berthold, T. (2014). "Heuristic algorithms in global MINLP solvers"

### 17.4 Stack Overflow / Forums
- [Pyomo Warm Start - Stack Overflow](https://stackoverflow.com/questions/55250019/pyomo-warm-start)
- [CBC Warmstart Discussion](https://github.com/coin-or/Cbc/discussions/369)
- [Pyomo Forum: Warmstart with CBC](https://groups.google.com/g/pyomo-forum/c/bL7jhdP1NQ8)

---

## 18. Appendix: Complete Code Example

### 18.1 End-to-End Warmstart Example

```python
"""
Complete example: Solve UnifiedNodeModel with campaign heuristic warmstart
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.warmstart_generators import generate_campaign_warmstart

# Assume model is already initialized with data
model = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=date(2025, 10, 20),
    end_date=date(2025, 11, 16),  # 28-day horizon
    truck_schedules=truck_schedules,
)

# Generate warmstart using campaign heuristic
warmstart = generate_campaign_warmstart(
    forecast=forecast,
    start_date=date(2025, 10, 20),
    end_date=date(2025, 11, 16),
    max_products_per_day=2,      # Produce 2 SKUs per day
    campaign_length_days=3,      # 3-day campaigns
    production_node='6122',
)

print(f"Generated warmstart with {len(warmstart['product_produced'])} variable values")

# Solve WITHOUT warmstart (baseline)
print("\n" + "="*60)
print("Solving WITHOUT warmstart (baseline)")
print("="*60)
result_cold = model.solve(
    solver_name='cbc',
    time_limit_seconds=300,
    mip_gap=0.01,
    tee=True
)
print(f"Cold start: {result_cold}")
print(f"  Objective: ${result_cold.objective_value:,.2f}")
print(f"  Solve time: {result_cold.solve_time_seconds:.1f}s")

# Solve WITH warmstart
print("\n" + "="*60)
print("Solving WITH warmstart")
print("="*60)
result_warm = model.solve(
    solver_name='cbc',
    time_limit_seconds=300,
    mip_gap=0.01,
    warmstart=warmstart,  # PROVIDE WARMSTART
    tee=True
)
print(f"Warm start: {result_warm}")
print(f"  Objective: ${result_warm.objective_value:,.2f}")
print(f"  Solve time: {result_warm.solve_time_seconds:.1f}s")

# Compare performance
if result_cold.solve_time_seconds and result_warm.solve_time_seconds:
    speedup_pct = (
        (result_cold.solve_time_seconds - result_warm.solve_time_seconds) /
        result_cold.solve_time_seconds * 100
    )
    print("\n" + "="*60)
    print(f"Warmstart Performance:")
    print(f"  Speedup: {speedup_pct:.1f}%")
    print(f"  Time saved: {result_cold.solve_time_seconds - result_warm.solve_time_seconds:.1f}s")

    if speedup_pct >= 20:
        print("  ✓ Warmstart EFFECTIVE (≥20% speedup)")
    elif speedup_pct > 0:
        print("  ~ Warmstart MARGINAL (0-20% speedup)")
    else:
        print("  ✗ Warmstart INEFFECTIVE (slower than cold start)")
```

**Expected Output:**

```
Generated warmstart with 140 variable values

============================================================
Solving WITHOUT warmstart (baseline)
============================================================
Welcome to the CBC MILP Solver
...
Result - Optimal solution found
Objective value: $125,432.15
Cold start: OPTIMAL, objective = 125,432.15, time = 87.3s
  Objective: $125,432.15
  Solve time: 87.3s

============================================================
Solving WITH warmstart
============================================================

============================================================
Applying Warmstart Initial Solution
============================================================
  product_produced: 140 values set
  production_day: 28 values set
  num_products_produced: 28 values set
Total warmstart values applied: 196
============================================================

Warmstart enabled for solver
Welcome to the CBC MILP Solver
Read MIP start from file /tmp/pyomo_warmstart_xxxx.soln
...
Result - Optimal solution found
Objective value: $125,432.15
Warm start: OPTIMAL, objective = 125,432.15, time = 58.2s
  Objective: $125,432.15
  Solve time: 58.2s

============================================================
Warmstart Performance:
  Speedup: 33.3%
  Time saved: 29.1s
  ✓ Warmstart EFFECTIVE (≥20% speedup)
```

---

## 19. Summary and Recommendation

### 19.1 Summary

**Warmstart Capability:**
- ✅ Pyomo supports warmstart via `variable.set_value()` + `solver.solve(warmstart=True)`
- ⚠️ CBC has LIMITED support (v2.8.0+, requires feasible complete solution)
- ✅ Gurobi/CPLEX have ROBUST support (MIPStart + VarHint for partial hints)
- ❌ GLPK has NO warmstart support

**Implementation Approach:**
- Add `warmstart` parameter to `UnifiedNodeModel.solve()`
- Implement `_apply_warmstart()` to set variable values before solve
- Pass `warmstart=True` to solver.solve() for CBC/Gurobi/CPLEX
- Provide heuristic generators for easy warmstart creation

**Expected Performance:**
- 20-40% solve time reduction for good warmstart (CBC)
- 30-60% solve time reduction for good warmstart (Gurobi/CPLEX)
- 0% improvement for GLPK (no warmstart support)

### 19.2 Recommended Next Steps

1. **Implement Phase 1 (Core Warmstart)** - 2-3 days
   - Add warmstart parameter and application logic
   - Test with simple warmstart values
   - Verify CBC/Gurobi compatibility

2. **Implement Phase 2 (Heuristic Generators)** - 2-3 days
   - Campaign heuristic warmstart generator
   - Extract warmstart from previous solve
   - Test on benchmark instances

3. **Implement Phase 3 (Validation)** - 1-2 days
   - Warmstart validation (bounds, feasibility)
   - Fallback to cold start on failure
   - Error handling and user warnings

4. **Testing and Documentation** - 2 days
   - Unit tests, integration tests, benchmarks
   - User guide and developer documentation
   - Performance comparison report

**Total Estimated Effort:** 7-10 days

### 19.3 Go/No-Go Decision

**Recommend: GO** with warmstart implementation

**Justification:**
- ✅ Proven technology (Pyomo + CBC/Gurobi support)
- ✅ Expected 20-40% speedup for target problem sizes
- ✅ Low implementation risk (straightforward API)
- ✅ Enables future enhancements (rolling horizon, fix-and-optimize)
- ✅ No changes to optimization problem (just initial solution)

**Caveats:**
- CBC warmstart is less robust than Gurobi (may need workarounds)
- Performance improvement depends on warmstart quality
- Requires heuristic development to generate good warmstarts

**Alternative if NO-GO:**
- Use aggressive CBC heuristics (already implemented in base_model.py)
- Upgrade to commercial solver (Gurobi/CPLEX) for better MIP performance
- Accept slower solve times and rely on time limits

---

**END OF SPECIFICATION**
