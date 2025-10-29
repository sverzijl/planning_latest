# Model Result Interface Specification

**Version:** 1.0
**Last Updated:** 2025-10-28
**Status:** ACTIVE - All models MUST conform to this specification

---

## Overview

This document defines the **strict interface contract** between optimization models and the UI layer. All optimization models MUST return results conforming to the `OptimizationSolution` Pydantic schema defined in `src/optimization/result_schema.py`.

**Purpose:**
- Eliminate flaky UI behavior caused by inconsistent data formats
- Enable fail-fast validation at the model-UI boundary
- Provide type safety and IDE autocomplete support
- Serve as executable documentation (Pydantic validates automatically)

**Key Principles:**
1. **Fail Fast:** ValidationError raised immediately if data doesn't conform
2. **Single Source of Truth:** `result_schema.py` IS the specification
3. **Open Extension:** Models can add extra fields beyond the spec
4. **Type Safety:** Full type hints enable static analysis

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│          OptimizationSolution (Pydantic Schema)              │
│                  Single Source of Truth                      │
│          src/optimization/result_schema.py                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
       ┌─────────┴─────────┐
       │                   │
       ▼                   ▼
  PRODUCERS           CONSUMER
  (Models)              (UI)
       │                   │
       ├─ SlidingWindow   ├─ result_adapter.py
       ├─ UnifiedNode     ├─ 5_Results.py
       └─ Future models   └─ Components
```

---

## Development Workflow

### When UI Needs Change:

1. **Update Schema FIRST** (`src/optimization/result_schema.py`)
   - Add new fields to `OptimizationSolution`
   - Add validation rules if needed
   - Update this specification document

2. **Update Models** (conform to new schema)
   - Modify `extract_solution()` / `_dict_to_optimization_solution()`
   - Ensure new fields are populated
   - Run compliance tests

3. **Update UI** (use new fields)
   - Access via Pydantic attributes
   - No defensive code needed (validation guarantees presence)

4. **Update Tests**
   - Add schema validation tests
   - Update compliance tests
   - Run full test suite

### When Adding New Models:

1. **Inherit from** `BaseOptimizationModel`
2. **Implement** `extract_solution() -> OptimizationSolution`
3. **Use converter pattern** (preserve existing logic, convert at end)
4. **Set correct flags** (model_type, has_aggregate_inventory, etc.)
5. **Add compliance tests**

---

## Required Fields

All models MUST provide these fields:

| Field | Type | Description |
|-------|------|-------------|
| `model_type` | `Literal["sliding_window", "unified_node"]` | Model architecture identifier |
| `production_batches` | `List[ProductionBatchResult]` | All production runs |
| `labor_hours_by_date` | `Dict[Date, LaborHoursBreakdown]` | Daily labor hours (ALWAYS dict, never float) |
| `shipments` | `List[ShipmentResult]` | All shipments with routing and state |
| `costs` | `TotalCostBreakdown` | Complete cost breakdown (5 categories) |
| `total_cost` | `float` | Total objective value (must equal costs.total_cost) |
| `fill_rate` | `float` | Demand satisfaction (0.0 to 1.0) |
| `total_production` | `float` | Total units produced (must equal sum of batches) |
| `total_shortage_units` | `float` | Total unmet demand |

---

## Model-Specific Fields (Discriminated Union)

### SlidingWindowModel

**MUST set:**
- `model_type = "sliding_window"`
- `has_aggregate_inventory = True`
- `use_batch_tracking = False`

**MUST provide:**
- `inventory_state: Dict[(node, product, state, date), quantity]` - 4-tuple keys

**Inventory format:** `get_inventory_format()` returns `"state"`

### UnifiedNodeModel

**MUST set:**
- `model_type = "unified_node"`
- `use_batch_tracking = True`
- `has_aggregate_inventory = False`

**MUST provide:**
- `cohort_inventory: Dict[(node, prod, prod_date, state_entry, curr_date, state), quantity]` - 6-tuple keys

**Inventory format:** `get_inventory_format()` returns `"cohort"`

---

## Optional Fields

Models MAY provide these fields (all models):

| Field | Type | Description |
|-------|------|-------------|
| `production_by_date_product` | `Dict[(node,product,date), qty]` | Production lookup |
| `thaw_flows` | `Dict[(node,product,date), qty]` | Frozen→thawed transitions |
| `freeze_flows` | `Dict[(node,product,date), qty]` | Ambient→frozen transitions |
| `shortages` | `Dict[(node,product,date), qty]` | Unmet demand |
| `truck_assignments` | `Dict[(origin,dest,product,date), truck_id]` | Truck assignments |
| `labor_cost_by_date` | `Dict[Date, float]` | Daily labor costs |
| `fefo_batches` | `List[Dict]` | FEFO batch detail (JSON-serializable) |
| `fefo_batch_objects` | `List[Batch]` | FEFO batch objects (in-memory) |
| `fefo_batch_inventory` | `Dict` | Batches grouped by location |
| `fefo_shipment_allocations` | `List[Dict]` | Shipment-to-batch allocations |

---

## Extra Fields

Models can add implementation-specific fields beyond the specification:

```python
# Extra fields are allowed (Extra.allow in schema)
solution.custom_metric = 42.0
solution.debug_info = "test"
solution.model_specific_data = {...}
```

**Guidelines:**
- Use for model-specific extensions
- Don't override required fields
- Document in model's docstring
- Consider adding to spec if widely useful

---

## Nested Data Structures

### ProductionBatchResult

```python
@dataclass
class ProductionBatchResult:
    node: str          # Manufacturing node ID
    product: str       # Product ID
    date: Date         # Production date
    quantity: float    # Production quantity (units, >= 0)
```

### LaborHoursBreakdown

**CRITICAL:** This structure is ALWAYS used, never a simple float!

```python
@dataclass
class LaborHoursBreakdown:
    used: float = 0.0       # Hours actually used
    paid: float = 0.0       # Hours paid (>= used, due to minimums)
    fixed: float = 0.0      # Fixed hours (weekday regular)
    overtime: float = 0.0   # Overtime hours (>12h weekdays)
    non_fixed: float = 0.0  # Non-fixed hours (weekends/holidays)
```

**Validation:** `paid >= used` (enforced by Pydantic)

### ShipmentResult

```python
@dataclass
class ShipmentResult:
    origin: str                    # Origin node ID
    destination: str               # Destination node ID
    product: str                   # Product ID
    quantity: float                # Shipment quantity (> 0)
    delivery_date: Date            # Delivery date at destination
    departure_date: Date | None    # Optional: departure from origin
    production_date: Date | None   # Optional: production date (batch tracking)
    state: StorageState | None     # Optional: frozen/ambient/thawed
    assigned_truck_id: str | None  # Optional: assigned truck
    first_leg_destination: str | None  # Optional: first hop (multi-leg)
```

**Validation:** `quantity > 0` (enforced by Pydantic)

### TotalCostBreakdown

```python
@dataclass
class TotalCostBreakdown:
    total_cost: float                # Total cost to serve
    labor: LaborCostBreakdown        # Labor costs
    production: ProductionCostBreakdown  # Production costs
    transport: TransportCostBreakdown    # Transport costs
    holding: HoldingCostBreakdown        # Holding costs
    waste: WasteCostBreakdown            # Waste/shortage costs
    cost_per_unit_delivered: float | None  # Average cost
```

**Validation:** `total_cost = labor.total + production.total + transport.total + holding.total + waste.total` (enforced, 1% tolerance)

---

## Cross-Field Validations

Pydantic automatically validates these consistency rules:

1. **Cost sum:** `total_cost == costs.total_cost` (1% tolerance for rounding)
2. **Production sum:** `total_production == sum(batch.quantity for batch in production_batches)` (1% tolerance)
3. **Labor paid >= used:** `labor_breakdown.paid >= labor_breakdown.used`
4. **Fill rate range:** `0.0 <= fill_rate <= 1.0`
5. **Model-type flags:**
   - `sliding_window` → `has_aggregate_inventory = True`
   - `unified_node` → `use_batch_tracking = True`

**Tolerance:** 1% for floating-point rounding errors

---

## Examples

### Example 1: SlidingWindowModel Solution

```python
from src.optimization.result_schema import (
    OptimizationSolution,
    ProductionBatchResult,
    LaborHoursBreakdown,
    ShipmentResult,
    TotalCostBreakdown,
    # ... other imports
)

solution = OptimizationSolution(
    # Required
    model_type="sliding_window",
    production_batches=[
        ProductionBatchResult(
            node="6122",
            product="PROD1",
            date=date(2025, 10, 1),
            quantity=1000.0
        )
    ],
    labor_hours_by_date={
        date(2025, 10, 1): LaborHoursBreakdown(
            used=12.0,
            paid=12.0,
            fixed=12.0,
            overtime=0.0,
            non_fixed=0.0
        )
    },
    shipments=[
        ShipmentResult(
            origin="6122",
            destination="6104",
            product="PROD1",
            quantity=500.0,
            delivery_date=date(2025, 10, 3),
            state=StorageState.AMBIENT
        )
    ],
    costs=TotalCostBreakdown(
        total_cost=1000.0,
        labor=LaborCostBreakdown(total=200.0),
        production=ProductionCostBreakdown(total=300.0, unit_cost=1.0, total_units=1000.0),
        transport=TransportCostBreakdown(total=200.0),
        holding=HoldingCostBreakdown(total=200.0, frozen_storage=100.0, ambient_storage=100.0),
        waste=WasteCostBreakdown(total=100.0, shortage_penalty=100.0)
    ),
    total_cost=1000.0,
    fill_rate=0.95,
    total_production=1000.0,
    total_shortage_units=50.0,

    # Model-specific
    has_aggregate_inventory=True,
    inventory_state={
        ("6122", "PROD1", "ambient", date(2025, 10, 1)): 500.0  # 4-tuple keys
    },

    # Optional
    production_by_date_product={
        ("6122", "PROD1", date(2025, 10, 1)): 1000.0
    },
)
```

### Example 2: UnifiedNodeModel Solution

```python
solution = OptimizationSolution(
    # Required
    model_type="unified_node",
    production_batches=[...],  # Same as SlidingWindow
    labor_hours_by_date={...},  # Same as SlidingWindow
    shipments=[...],  # Same as SlidingWindow
    costs=TotalCostBreakdown(...),  # Same structure
    total_cost=1000.0,
    fill_rate=0.95,
    total_production=1000.0,
    total_shortage_units=50.0,

    # Model-specific
    use_batch_tracking=True,
    cohort_inventory={
        ("6122", "PROD1", date(2025, 10, 1), date(2025, 10, 1), date(2025, 10, 1), "ambient"): 500.0  # 6-tuple keys
    },
)

# Extra fields (model-specific)
solution.mix_counts = {("6122", "PROD1", date(2025, 10, 1)): {"mix_count": 5, "units": 1000}}
solution.total_changeovers = 3
```

---

## Validation Errors

### Common Validation Errors:

**1. Missing Required Field:**
```
ValidationError: 1 validation error for OptimizationSolution
production_batches
  Field required [type=missing, input_value={...}, input_type=dict]
```
**Fix:** Ensure all required fields are populated in extract_solution()

**2. Cost Sum Mismatch:**
```
ValidationError: 1 validation error for TotalCostBreakdown
  Value error, total_cost (2000.00) does not match sum of components (1000.00)
```
**Fix:** Ensure total_cost = sum(labor, production, transport, holding, waste)

**3. Production Sum Mismatch:**
```
ValidationError: 1 validation error for OptimizationSolution
  Value error, total_production (5000.00) != sum of batch quantities (1000.00)
```
**Fix:** Ensure total_production = sum(batch.quantity for batch in production_batches)

**4. Invalid Model Type:**
```
ValidationError: 1 validation error for OptimizationSolution
  Input should be 'sliding_window' or 'unified_node'
```
**Fix:** Set model_type to one of the allowed literals

**5. Wrong Inventory Format:**
```
ValidationError: 1 validation error for OptimizationSolution
  Value error, SlidingWindowModel must set has_aggregate_inventory=True
```
**Fix:** Set model-type specific flags correctly

---

## Implementation Pattern: Converter Method

**Recommended pattern** to preserve existing optimization logic:

```python
class MyOptimizationModel(BaseOptimizationModel):

    def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
        """Extract solution from solved model.

        Returns:
            OptimizationSolution: Pydantic-validated solution
        """
        # Build solution dict using EXISTING logic (no changes needed)
        solution = {}
        # ... 200+ lines building dict (UNCHANGED) ...

        # Convert dict to Pydantic at the end (validation happens here)
        return self._dict_to_optimization_solution(solution)

    def _dict_to_optimization_solution(self, solution_dict: Dict[str, Any]) -> 'OptimizationSolution':
        """Convert dict to validated OptimizationSolution."""
        from .result_schema import OptimizationSolution, ProductionBatchResult, ...

        # 1. Convert production_batches
        production_batches = [
            ProductionBatchResult(**batch)
            for batch in solution_dict['production_batches']
        ]

        # 2. Convert labor_hours (ALWAYS LaborHoursBreakdown)
        labor_hours_by_date = {
            date: LaborHoursBreakdown(**hours) if isinstance(hours, dict)
                  else LaborHoursBreakdown(used=hours, paid=hours, ...)
            for date, hours in solution_dict['labor_hours_by_date'].items()
        }

        # 3. Convert shipments
        shipments = [ShipmentResult(...) for ...]

        # 4. Build cost breakdown
        costs = TotalCostBreakdown(
            total_cost=solution_dict['total_cost'],
            labor=LaborCostBreakdown(total=solution_dict['total_labor_cost'], ...),
            production=ProductionCostBreakdown(total=solution_dict['total_production_cost'], ...),
            transport=TransportCostBreakdown(total=solution_dict['total_transport_cost'], ...),
            holding=HoldingCostBreakdown(total=solution_dict['total_holding_cost'], ...),
            waste=WasteCostBreakdown(total=solution_dict['total_shortage_cost'], ...)
        )

        # 5. Build OptimizationSolution
        opt_solution = OptimizationSolution(
            model_type="my_model",
            production_batches=production_batches,
            labor_hours_by_date=labor_hours_by_date,
            shipments=shipments,
            costs=costs,
            total_cost=solution_dict['total_cost'],
            fill_rate=solution_dict['fill_rate'],
            total_production=solution_dict['total_production'],
            total_shortage_units=solution_dict.get('total_shortage_units', 0.0),
            ...
        )

        # 6. Preserve legacy dict fields as extra attributes
        opt_solution.my_model_specific_field = solution_dict.get('special_data')

        return opt_solution
```

---

## Tuple Keys vs String Keys

**Tuple keys are preserved** (not converted to strings):

```python
# Dict fields with tuple keys work (arbitrary_types_allowed=True)
inventory_state = {
    ("6122", "PROD1", "ambient", date(2025, 10, 1)): 500.0  # Tuple key preserved
}

production_by_date_product = {
    ("6122", "PROD1", date(2025, 10, 1)): 1000.0  # Tuple key preserved
}
```

**Why tuple keys?**
- Efficient lookup: `O(1)` vs `O(n)` for lists
- Natural key structure for optimization variables
- No performance overhead from string conversion

**JSON serialization:**
Use `solution.to_dict_json_safe()` to get JSON-compatible dict (converts tuples to strings)

---

## Error Handling in UI

**UI must catch ValidationError at boundary:**

```python
from pydantic import ValidationError

try:
    adapted_results = adapt_optimization_results(model, result, date)
except ValidationError as e:
    st.error("❌ Model Interface Violation")
    st.error("The model returned data that doesn't conform to OptimizationSolution specification.")
    with st.expander("🔍 Error Details"):
        st.code(str(e))
    st.stop()  # Prevent bad data propagation
```

**Benefits:**
- Clear error messages for users
- Exact field and violation shown
- Prevents mysterious UI crashes
- Actionable fix instructions

---

## Testing Requirements

### 1. Schema Validation Tests

**File:** `tests/test_result_schema.py`

**Must test:**
- Valid data structures pass validation
- Invalid data raises ValidationError
- Cross-field validations work
- Extra fields are preserved
- JSON serialization works

**Run:** `pytest tests/test_result_schema.py -v`

### 2. Model Compliance Tests

**File:** `tests/test_model_compliance.py`

**Must test:**
- Model inherits from BaseOptimizationModel
- extract_solution() returns OptimizationSolution
- Correct model_type flag set
- Correct inventory format flags set
- Solution validates successfully

**Run:** `pytest tests/test_model_compliance.py -v`

### 3. Integration Tests

**File:** `tests/test_integration_ui_workflow.py`

**Must include:**
```python
solution = model.get_solution()
assert isinstance(solution, OptimizationSolution), \
    f"Must return OptimizationSolution, got {type(solution)}"
```

---

## Performance

**Validation overhead:** <1ms per solve (negligible vs solve time)

**Benchmarks:**
- Schema validation: ~0.5ms
- Dict to Pydantic conversion: ~0.3ms
- Total overhead: ~0.8ms
- Typical solve time: 5s to 5 minutes
- **Overhead percentage:** <0.01%

---

## Migration Guide (For Existing Models)

### Step 1: Update return type
```python
# Before
def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:

# After
def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
```

### Step 2: Add converter call at end
```python
def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
    solution = {}
    # ... EXISTING logic (UNCHANGED) ...
    return self._dict_to_optimization_solution(solution)  # Add this line
```

### Step 3: Implement converter method
See "Implementation Pattern: Converter Method" section above

### Step 4: Update self.solution accesses
```python
# Before
production = self.solution.get('production_by_date_product', {})

# After
production = self.solution.production_by_date_product or {}
```

### Step 5: Add compliance tests
See `tests/test_model_compliance.py` for examples

---

## FAQs

### Q: Can I add custom fields to OptimizationSolution?
**A:** Yes! Schema allows extra fields (`Extra.allow`). Add as attributes after creation.

### Q: Do I need to convert tuple keys to strings?
**A:** No! Tuple keys are preserved (`arbitrary_types_allowed=True`). Use `to_dict_json_safe()` for JSON.

### Q: What if my model has different cost components?
**A:** Map your costs to the 5 standard categories (labor, production, transport, holding, waste). Document mapping in your model.

### Q: Can I skip fields that don't apply to my model?
**A:** Required fields MUST be provided (use empty lists/dicts/0.0). Optional fields can be None.

### Q: What happens if validation fails?
**A:** ValidationError raised immediately at extraction. Test will fail, UI will show error. This is by design (fail-fast).

---

## References

**Code:**
- Schema definition: `src/optimization/result_schema.py`
- Base model: `src/optimization/base_model.py`
- SlidingWindow example: `src/optimization/sliding_window_model.py`
- UnifiedNode example: `src/optimization/unified_node_model.py`

**Tests:**
- Schema tests: `tests/test_result_schema.py`
- Compliance tests: `tests/test_model_compliance.py`
- Integration tests: `tests/test_integration_ui_workflow.py`

**Documentation:**
- Model specification: `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`
- Project instructions: `CLAUDE.md`

---

## Changelog

### Version 1.0 (2025-10-28)
- Initial specification
- Pydantic-based validation
- Discriminated union for model types
- Tuple keys support
- Fail-fast validation
- Converter pattern established

---

**Status:** ✅ ACTIVE - All models must conform to this specification
