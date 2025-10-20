# Warmstart Integration Design

**Status:** PENDING DESIGN COMPLETION
**Dependencies:** CBC mechanism + Campaign algorithm
**Priority:** MEDIUM
**Last Updated:** 2025-10-19

---

## Objective

Define complete integration architecture for warmstart functionality across the codebase.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedNodeModel                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ solve(use_warmstart=True)                            │   │
│  │   ↓                                                   │   │
│  │ 1. Generate warmstart (if use_warmstart=True)        │   │
│  │    WarmstartGenerator.generate()                     │   │
│  │   ↓                                                   │   │
│  │ 2. Pass to base class                                │   │
│  │    super().solve(..., warmstart_values=dict)         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    BaseOptimizationModel                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ solve(warmstart_values=None, ...)                    │   │
│  │   ↓                                                   │   │
│  │ 1. Build model (self.build_model())                  │   │
│  │   ↓                                                   │   │
│  │ 2. Apply warmstart (line 283)                        │   │
│  │    if warmstart_values:                              │   │
│  │        _apply_warmstart(self.model, warmstart_values)│   │
│  │   ↓                                                   │   │
│  │ 3. Create solver                                     │   │
│  │   ↓                                                   │   │
│  │ 4. Solve (solver.solve(self.model))                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    WarmstartGenerator                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ __init__(model: UnifiedNodeModel)                    │   │
│  │   ↓                                                   │   │
│  │ generate() -> Dict[Tuple, float]                     │   │
│  │   ↓                                                   │   │
│  │ 1. _aggregate_demand()                               │   │
│  │    → Weekly demand by product                        │   │
│  │   ↓                                                   │   │
│  │ 2. _generate_campaign_pattern()                      │   │
│  │    → Production plan: {(node, product, date): qty}   │   │
│  │   ↓                                                   │   │
│  │ 3. _production_to_warmstart()                        │   │
│  │    → Warmstart dict: {(var_name, index): value}      │   │
│  │   ↓                                                   │   │
│  │ 4. (Optional) _generate_inventory_cohorts()          │   │
│  │    → Add inventory/shipment initial values           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## File Modifications

### 1. base_model.py

**Location:** `/home/sverzijl/planning_latest/src/optimization/base_model.py`
**Lines to Modify:** 187-332 (solve method)

#### Changes Required:

**A. Add warmstart_values parameter (line 187-195)**
```python
def solve(
    self,
    solver_name: Optional[str] = None,
    solver_options: Optional[Dict[str, Any]] = None,
    tee: bool = False,
    time_limit_seconds: Optional[float] = None,
    mip_gap: Optional[float] = None,
    use_aggressive_heuristics: bool = False,
    warmstart_values: Optional[Dict[Tuple, float]] = None,  # <<< NEW
) -> OptimizationResult:
```

**B. Add warmstart application (after line 283)**
```python
# Build model
build_start = time.time()
self.model = self.build_model()
self._build_time = time.time() - build_start

# Apply warmstart if provided
if warmstart_values:
    self._apply_warmstart(self.model, warmstart_values)

# Prepare solver options
options = solver_options or {}
...
```

**C. Add _apply_warmstart helper method (after line 565)**
```python
def _apply_warmstart(
    self,
    model: ConcreteModel,
    warmstart_values: Dict[Tuple, float]
) -> None:
    """Apply warmstart values to model variables.

    Args:
        model: Pyomo model
        warmstart_values: Dict mapping (var_name, index_tuple) to value

    Example:
        warmstart_values = {
            ('production', ('6122', 'PROD_001', date(2025,10,20))): 5000.0,
            ('product_produced', ('6122', 'PROD_001', date(2025,10,20))): 1.0,
        }
    """
    applied_count = 0
    failed_count = 0

    for (var_name, index_tuple), value in warmstart_values.items():
        try:
            # Get variable component
            var_component = getattr(model, var_name, None)
            if var_component is None:
                # Variable doesn't exist (may be optional)
                failed_count += 1
                continue

            # Set value (handles indexed and scalar variables)
            if index_tuple:
                var = var_component[index_tuple]
            else:
                var = var_component

            var.value = value
            applied_count += 1

        except (KeyError, AttributeError, ValueError) as e:
            # Invalid index or type mismatch
            failed_count += 1
            # Log warning but continue (graceful degradation)
            warnings.warn(
                f"Warmstart failed for {var_name}{index_tuple}: {e}"
            )

    # Log summary
    total = applied_count + failed_count
    if total > 0:
        success_rate = (applied_count / total) * 100
        print(f"Warmstart applied: {applied_count}/{total} values ({success_rate:.1f}%)")
        if failed_count > 10:
            warnings.warn(
                f"Warmstart had {failed_count} failures. "
                f"Check variable names and indices."
            )
```

**Backward Compatibility:** ✅ ZERO BREAKING CHANGES
- New parameter is optional (`warmstart_values=None`)
- Existing calls work without modification
- Warmstart is opt-in, not mandatory

---

### 2. unified_node_model.py

**Location:** `/home/sverzijl/planning_latest/src/optimization/unified_node_model.py`
**Lines to Modify:** 922-949 (solve method)

#### Changes Required:

**A. Add use_warmstart parameter (line 922-929)**
```python
def solve(
    self,
    solver_name: Optional[str] = None,
    time_limit_seconds: Optional[float] = None,
    mip_gap: Optional[float] = None,
    tee: bool = False,
    use_aggressive_heuristics: bool = False,
    use_warmstart: bool = True,  # <<< NEW (default True for auto-enable)
) -> OptimizationResult:
```

**B. Generate warmstart before calling super (line 930-949)**
```python
"""Build and solve the unified node model.

Args:
    solver_name: Solver to use (None = auto-detect)
    time_limit_seconds: Time limit in seconds
    mip_gap: MIP gap tolerance
    tee: Show solver output
    use_aggressive_heuristics: Enable aggressive CBC heuristics
    use_warmstart: Generate and apply warmstart solution (default: True)

Returns:
    OptimizationResult with solve status and metrics
"""
# Generate warmstart if requested
warmstart_values = None
if use_warmstart:
    try:
        from .warmstart_generator import WarmstartGenerator
        generator = WarmstartGenerator(self)
        warmstart_values = generator.generate()
        print(f"Generated warmstart with {len(warmstart_values)} values")
    except Exception as e:
        # Graceful degradation: log warning and continue without warmstart
        warnings.warn(f"Warmstart generation failed: {e}")
        warmstart_values = None

# Call base class solve (which applies warmstart at line 283)
return super().solve(
    solver_name=solver_name,
    time_limit_seconds=time_limit_seconds,
    mip_gap=mip_gap,
    tee=tee,
    use_aggressive_heuristics=use_aggressive_heuristics,
    warmstart_values=warmstart_values,  # <<< PASS TO BASE CLASS
)
```

**Backward Compatibility:** ✅ ZERO BREAKING CHANGES
- New parameter has default value (`use_warmstart=True`)
- Existing calls get warmstart automatically (opt-out, not opt-in)
- Can disable with `model.solve(use_warmstart=False)`

---

### 3. warmstart_generator.py (NEW FILE)

**Location:** `/home/sverzijl/planning_latest/src/optimization/warmstart_generator.py`
**Status:** NEW FILE CREATION

#### Module Structure:

```python
"""Warmstart solution generator for UnifiedNodeModel.

This module generates initial feasible solutions (warmstart values) to
accelerate CBC solver performance by 20-40%.

Strategy: Campaign-based production pattern with demand-weighted allocation.
"""

from __future__ import annotations

import warnings
from datetime import date as Date, timedelta
from typing import Dict, Tuple, List, Optional, Any
from collections import defaultdict

from src.models.unified_node import UnifiedNode
from src.models.forecast import Forecast


class WarmstartGenerator:
    """Generate warmstart solutions for production-distribution optimization.

    Campaign Pattern Strategy:
    - Group 2-3 SKUs per production day
    - Rotate all products weekly
    - Allocate demand proportionally
    - Prefer weekday production
    """

    def __init__(self, model):
        """Initialize generator.

        Args:
            model: UnifiedNodeModel instance
        """
        self.model = model
        self.nodes = model.nodes
        self.forecast = model.forecast
        self.start_date = model.start_date
        self.end_date = model.end_date

        # Extract manufacturing nodes
        self.manufacturing_nodes = [
            n for n in self.nodes if n.capabilities.can_manufacture
        ]

        # Extract products
        self.products = list(
            set(f.product_id for f in self.forecast.forecasts)
        )

    def generate(self) -> Dict[Tuple, float]:
        """Generate warmstart values.

        Returns:
            Dictionary mapping (variable_name, index_tuple) to value

        Example:
            {
                ('production', ('6122', 'PROD_001', date(2025,10,20))): 5000.0,
                ('product_produced', ('6122', 'PROD_001', date(2025,10,20))): 1.0,
                ('num_products_produced', ('6122', date(2025,10,20))): 2,
            }
        """
        warmstart = {}

        # 1. Aggregate demand
        demand_by_product = self._aggregate_demand()

        # 2. Generate campaign pattern
        production_plan = self._generate_campaign_pattern(demand_by_product)

        # 3. Convert to warmstart format
        warmstart.update(self._production_to_warmstart(production_plan))

        return warmstart

    def _aggregate_demand(self) -> Dict[str, float]:
        """Aggregate total demand by product.

        Returns:
            Dict mapping product_id to total demand
        """
        # >>> IMPLEMENT <<<
        pass

    def _generate_campaign_pattern(
        self, demand_by_product: Dict[str, float]
    ) -> Dict[Tuple[str, str, Date], float]:
        """Generate production campaign pattern.

        Args:
            demand_by_product: Total demand by product

        Returns:
            Production plan: {(node_id, product_id, date): quantity}
        """
        # >>> IMPLEMENT BASED ON ALGORITHM SPEC <<<
        pass

    def _production_to_warmstart(
        self, production_plan: Dict[Tuple, float]
    ) -> Dict[Tuple, float]:
        """Convert production plan to warmstart format.

        Args:
            production_plan: {(node_id, product_id, date): quantity}

        Returns:
            Warmstart values: {(var_name, index_tuple): value}
        """
        warmstart = {}

        # Production quantities (continuous variables)
        for (node_id, product_id, prod_date), quantity in production_plan.items():
            warmstart[('production', (node_id, prod_date, product_id))] = quantity

        # Product produced indicators (binary variables)
        for (node_id, product_id, prod_date), quantity in production_plan.items():
            if quantity > 0.01:  # Numerical threshold
                warmstart[('product_produced', (node_id, product_id, prod_date))] = 1.0

        # Count products per day (integer variables)
        products_per_day = defaultdict(set)
        for (node_id, product_id, prod_date), quantity in production_plan.items():
            if quantity > 0.01:
                products_per_day[(node_id, prod_date)].add(product_id)

        for (node_id, prod_date), products in products_per_day.items():
            warmstart[('num_products_produced', (node_id, prod_date))] = len(products)

        return warmstart
```

**Backward Compatibility:** ✅ NEW FILE (no breaking changes)

---

## Data Flow

### 1. Warmstart Generation Flow
```
UnifiedNodeModel.solve(use_warmstart=True)
    ↓
WarmstartGenerator.__init__(model)
    ↓
WarmstartGenerator.generate()
    ↓
_aggregate_demand()
    → Returns: {'PROD_001': 50000, 'PROD_002': 40000, ...}
    ↓
_generate_campaign_pattern(demand_by_product)
    → Returns: {('6122', 'PROD_001', date(2025,10,20)): 5000, ...}
    ↓
_production_to_warmstart(production_plan)
    → Returns: {('production', ('6122', date(2025,10,20), 'PROD_001')): 5000, ...}
    ↓
Return warmstart_values to UnifiedNodeModel.solve()
    ↓
Pass to super().solve(warmstart_values=...)
    ↓
BaseOptimizationModel._apply_warmstart(model, warmstart_values)
    ↓
Set model.production[index].value = 5000
    ↓
solver.solve(model) uses initial values
```

### 2. Error Handling Flow
```
Any step fails
    ↓
catch Exception
    ↓
warnings.warn("Warmstart generation failed: ...")
    ↓
Set warmstart_values = None
    ↓
Continue solve without warmstart
    ↓
Log: "Solving without warmstart (generation failed)"
```

---

## Testing Strategy

### Unit Tests
1. **test_warmstart_generator.py**
   - Test demand aggregation
   - Test campaign pattern generation
   - Test warmstart format conversion
   - Test with 1 product, 1 week
   - Test with 5 products, 4 weeks
   - Test with high demand (>capacity)

2. **test_base_model_warmstart.py**
   - Test _apply_warmstart with valid values
   - Test _apply_warmstart with invalid variable names
   - Test _apply_warmstart with invalid indices
   - Test graceful degradation

### Integration Tests
3. **test_warmstart_integration.py**
   - Test UnifiedNodeModel.solve(use_warmstart=True)
   - Test UnifiedNodeModel.solve(use_warmstart=False)
   - Test performance improvement (before/after)
   - Test with real dataset (GFree Forecast.xlsm)

### Performance Tests
4. **test_warmstart_performance.py**
   - Baseline: 4-week solve without warmstart (>300s)
   - Target: 4-week solve with warmstart (<120s)
   - Measure: solve time reduction %
   - Validate: objective value same or better

---

## Configuration

### UI Integration (Optional Phase 5)

**Planning Tab: Advanced Settings**
```python
# Add checkbox in Streamlit UI
use_warmstart = st.checkbox(
    "Enable Warmstart (Faster Solve)",
    value=True,
    help="Generate initial solution to accelerate solver (20-40% faster)"
)

# Pass to solve call
result = model.solve(
    solver_name=solver,
    time_limit_seconds=time_limit,
    mip_gap=mip_gap,
    tee=show_solver_output,
    use_aggressive_heuristics=use_aggressive,
    use_warmstart=use_warmstart,  # <<< NEW
)
```

---

## Rollback Plan

If warmstart causes issues:

1. **Disable by default:**
   ```python
   # unified_node_model.py line 929
   use_warmstart: bool = False,  # Changed from True
   ```

2. **Remove integration (revert commits):**
   - Revert base_model.py changes
   - Revert unified_node_model.py changes
   - Delete warmstart_generator.py

3. **Keep as experimental feature:**
   - Document as "experimental"
   - Require explicit opt-in
   - Add warning message

---

## Success Criteria

### Functional Success
- ✅ Warmstart generates valid initial solution
- ✅ All variables have correct types (continuous/integer/binary)
- ✅ Graceful degradation if generation fails
- ✅ Zero breaking changes to existing code

### Performance Success
- ✅ Solve time reduced by 20-40% for 4-week horizon
- ✅ Baseline: >300s → Target: <120s
- ✅ Warmstart generation overhead: <5s
- ✅ No degradation in objective value

### Quality Success
- ✅ Passes all existing tests
- ✅ New tests achieve >80% coverage
- ✅ No solver errors or warnings
- ✅ Documentation complete and accurate

---

## Timeline

**Phase 1: Design** (current)
- CBC mechanism design (pyomo-modeling-expert)
- Campaign algorithm design (production-planner)
- Integration design (context-manager)

**Phase 2: Implementation** (next)
- base_model.py modifications (python-pro)
- unified_node_model.py modifications (python-pro)
- warmstart_generator.py implementation (python-pro)

**Phase 3: Testing** (validation)
- Unit tests (test-automator)
- Integration tests (test-automator)
- Performance tests (test-automator)

**Phase 4: Review** (quality)
- Code review (code-reviewer)
- Performance validation (code-reviewer)
- Documentation review (code-reviewer)

**Phase 5: Deployment** (optional)
- UI integration
- User documentation
- Release notes

---

## Dependencies

**Upstream:**
- `cbc_warmstart_mechanism.md` (API specification)
- `campaign_pattern_algorithm.md` (algorithm logic)

**Downstream:**
- Implementation agents (python-pro)
- Testing agents (test-automator)
- Review agents (code-reviewer)

---

## Status Tracking

- [ ] CBC mechanism design complete
- [ ] Campaign algorithm design complete
- [ ] Integration design reviewed
- [ ] Dependencies mapped
- [ ] Approved for implementation
