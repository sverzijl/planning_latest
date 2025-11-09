# Architecture Hardening Plan

**Purpose:** Make UI display bugs structurally impossible through stronger type safety and validation.

**Status:** In Progress
**Priority:** HIGH - Prevents entire classes of bugs

---

## 🔍 Root Cause Analysis

### What Went Wrong (4 Recent Bugs)

**Bug Pattern Analysis:**

| Bug | Root Cause | Should Have Been Caught By |
|-----|------------|---------------------------|
| Labeling destinations | Tuple key format assumption | Typed dict keys, schema validation |
| Truck assignments | Index→ID type mismatch | Type hints, foreign key validation |
| Demand consumption | Missing field extraction | Required fields, completeness validation |
| Daily costs | Missing nested field | Non-optional dependencies, contract validation |

**Common Failures:**
1. ✗ Over-permissive schemas (`Optional[Dict[Any, Any]]`)
2. ✗ Late validation (errors caught in UI, not at boundary)
3. ✗ Weak type hints (`Any` instead of specific types)
4. ✗ No foreign key validation (IDs don't check references)
5. ✗ Implementation details leak (indices instead of domain IDs)

---

## 🎯 Architecture Improvements

### Improvement 1: Stronger Type System

**BEFORE (weak):**
```python
production_by_date_product: Optional[Dict[Any, float]]
truck_assignments: Optional[Dict[Any, Any]]
```

**AFTER (strong):**
```python
from typing import NewType

ProductionKey = Tuple[str, str, date]  # (node_id, product_id, date) - documented
TruckID = NewType('TruckID', str)  # Semantic type

production_by_date_product: Dict[ProductionKey, float]  # NOT optional
truck_assignments: Dict[ShipmentKey, TruckID]  # Typed, NOT Any
```

**Benefits:**
- Type checker catches mismatches
- Self-documenting (no guessing tuple order)
- Can't accidentally use wrong type

### Improvement 2: Foreign Key Validation

**Add validators to OptimizationSolution:**
```python
@model_validator(mode='after')
def validate_foreign_keys(self):
    """Ensure all IDs reference valid entities."""
    errors = []

    # Validate truck_ids exist
    if self.truck_assignments:
        valid_truck_ids = {t.id for t in self.truck_schedules or []}
        for shipment_key, truck_id in self.truck_assignments.items():
            if truck_id not in valid_truck_ids:
                errors.append(f"Invalid truck_id '{truck_id}' in truck_assignments")

    # Validate product_ids exist
    if self.production_by_date_product:
        valid_products = {p.id for p in self.products or []}
        for key in self.production_by_date_product.keys():
            node, product_id, date = key  # Documented structure
            if product_id not in valid_products:
                errors.append(f"Invalid product_id '{product_id}' in production")

    if errors:
        raise ValueError(f"Foreign key validation failed:\n" + "\n".join(errors))

    return self
```

### Improvement 3: UI Requirements Contract

**Document what each UI tab needs:**
```python
class UITabRequirements:
    """Contract: What data each UI tab requires to function."""

    LABELING = {
        'production_by_date_product': True,
        'shipments': True,
        'route_arrival_state': True,
    }

    DISTRIBUTION = {
        'truck_assignments': True,
        'truck_schedules': True,
        'shipments': True,
    }

    DAILY_SNAPSHOT = {
        'demand_consumed': True,  # For aggregate models
        'shortages': True,
    }

    DAILY_COSTS_GRAPH = {
        'costs.labor.daily_breakdown': True,
    }

    @staticmethod
    def validate(solution: OptimizationSolution, tab: str) -> List[str]:
        """Check if solution has all required data for tab.

        Returns:
            List of missing requirements (empty if valid)
        """
        requirements = getattr(UITabRequirements, tab.upper(), {})
        missing = []

        for field_path, required in requirements.items():
            if not required:
                continue

            # Navigate nested paths (e.g., 'costs.labor.daily_breakdown')
            obj = solution
            for part in field_path.split('.'):
                obj = getattr(obj, part, None)
                if obj is None:
                    missing.append(field_path)
                    break

        return missing
```

### Improvement 4: Fail-Fast Validation

**Add validation at model-UI boundary:**
```python
def adapt_optimization_results(model, result, inventory_snapshot_date):
    """Convert optimization results to UI format.

    CRITICAL: Validates ALL requirements before proceeding.
    Fails fast if any UI tab can't render.
    """
    solution = model.get_solution()

    # VALIDATE IMMEDIATELY (fail-fast)
    validation_errors = []

    # 1. Check completeness
    if not solution:
        raise ValueError("Model returned None solution")

    # 2. Validate foreign keys
    try:
        solution.validate_foreign_keys()  # Custom validator
    except ValueError as e:
        validation_errors.append(f"Foreign key validation: {e}")

    # 3. Check UI requirements for each tab
    for tab in ['LABELING', 'DISTRIBUTION', 'DAILY_SNAPSHOT', 'DAILY_COSTS_GRAPH']:
        missing = UITabRequirements.validate(solution, tab)
        if missing:
            validation_errors.append(f"{tab} missing: {', '.join(missing)}")

    if validation_errors:
        error_msg = "Solution validation failed:\n" + "\n".join(validation_errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Only proceed if ALL validations pass
    return _adapt_validated_solution(solution)
```

### Improvement 5: Model-Specific Required Fields

**Split schemas by model type:**
```python
class SlidingWindowSolutionExtras(BaseModel):
    """Fields REQUIRED for SlidingWindowModel (aggregate)."""
    demand_consumed: Dict[Tuple[str, str, date], float]  # NOT optional
    daily_breakdown: Dict[date, Dict[str, float]]  # NOT optional

    @field_validator('demand_consumed')
    @classmethod
    def demand_consumed_not_empty(cls, v):
        if not v:
            raise ValueError("demand_consumed cannot be empty for aggregate model")
        return v

class CohortSolutionExtras(BaseModel):
    """Fields REQUIRED for cohort tracking models."""
    cohort_demand_consumption: Dict[Tuple[str, str, date, date], float]
    batch_shipments: List[BatchShipment]
```

### Improvement 6: Comprehensive Model Tests

**Test that model populates ALL required fields:**
```python
@pytest.fixture
def ui_validator():
    """Fixture providing UI validation."""
    return UITabRequirements

def test_sliding_window_populates_all_ui_requirements(ui_validator):
    """Test that SlidingWindowModel satisfies ALL UI requirements."""
    # Setup and solve
    model = SlidingWindowModel(...)
    model.solve(...)
    solution = model.get_solution()

    # Validate ALL tabs can render
    all_tabs = ['LABELING', 'DISTRIBUTION', 'DAILY_SNAPSHOT', 'DAILY_COSTS_GRAPH']

    for tab in all_tabs:
        missing = ui_validator.validate(solution, tab)
        assert not missing, f"{tab} tab missing requirements: {missing}"

    # Validate foreign keys
    # This would have caught the truck_id bug
    if solution.truck_assignments:
        valid_truck_ids = {t.id for t in solution.truck_schedules}
        for truck_id in solution.truck_assignments.values():
            assert truck_id in valid_truck_ids, \
                f"Invalid truck_id '{truck_id}' not in schedules"

    # Validate tuple key structure
    # This would have caught the labeling bug
    if solution.production_by_date_product:
        for key in solution.production_by_date_product.keys():
            assert len(key) == 3, f"production key must be (node, product, date), got {key}"
            node, product, date_val = key
            assert isinstance(node, str)
            assert isinstance(product, str)
            assert isinstance(date_val, date)
```

---

## 📋 Implementation Checklist

### Phase 1: Critical Validations (Immediate)

- [ ] Add `UITabRequirements` contract class
- [ ] Add `validate_foreign_keys()` to OptimizationSolution
- [ ] Add fail-fast validation in `adapt_optimization_results()`
- [ ] Add comprehensive model tests checking ALL UI requirements

### Phase 2: Type System Hardening (Short-term)

- [ ] Replace `Dict[Any, Any]` with typed dicts
- [ ] Document tuple key structures with type aliases
- [ ] Add `NewType` for semantic types (TruckID, ProductID, etc.)
- [ ] Use `Literal` types for enums

### Phase 3: Schema Refinement (Medium-term)

- [ ] Make model-specific fields required (not Optional)
- [ ] Split OptimizationSolution into model-specific schemas
- [ ] Add field-level validators for completeness
- [ ] Document field dependencies in docstrings

### Phase 4: Eliminate Tuples (Long-term)

- [ ] Replace tuple keys with frozen dataclasses
- [ ] Benefits: type safety, self-documenting, extensible
- [ ] Gradual migration (start with new code)

---

## 🎯 Expected Impact

**With these improvements:**

| Bug Type | Before | After |
|----------|--------|-------|
| Wrong tuple structure | Runtime error in UI | Type error at compile time |
| Missing field | "No data" in UI | ValidationError at model boundary |
| Wrong ID type | Matching fails silently | Type error + foreign key error |
| Empty required data | Chart shows empty | ValidationError before UI |

**Architectural Guarantees:**

1. ✅ **Type Safety:** Wrong types caught by type checker
2. ✅ **Completeness:** Missing fields caught at model boundary
3. ✅ **Referential Integrity:** Invalid IDs caught by foreign key validation
4. ✅ **UI Contract:** Every tab's requirements documented and validated
5. ✅ **Fail-Fast:** Errors surface immediately, not in UI

---

## 📚 References

- `src/optimization/result_schema.py` - Schema definitions
- `src/ui_interface/solution_validator.py` - Validation logic
- `tests/test_ui_integration_complete.py` - Integration tests
- `MANDATORY_VERIFICATION_CHECKLIST.md` - Testing requirements

---

**Next Steps:** Implement Phase 1 (Critical Validations) immediately to prevent recurrence.
