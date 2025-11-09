# Model-UI Interface Refactoring Progress

**Started:** 2025-10-28
**Status:** Phase 1 Complete (Core Infrastructure) - 3/13 tasks done
**Next Steps:** Follow established patterns for remaining models and adapters

---

## Executive Summary

Refactoring the optimization model-UI interface from defensive duck-typing to strict Pydantic validation with fail-fast error handling. This eliminates the flakiness in Results page display by enforcing a formal contract at the model-UI boundary.

**Architecture Pattern:** Interface Specification with Pydantic Validation
- Schema defines the contract (single source of truth)
- Models produce validated data (fail-fast at extraction)
- UI trusts validated data (no defensive code needed)

---

## ✅ Completed Tasks (3/13)

### 1. Created Pydantic Result Schema ✅
**File:** `src/optimization/result_schema.py` (NEW - 400+ lines)

**What it defines:**
- `OptimizationSolution` - Top-level validated solution container
- `ProductionBatchResult` - Production batch data structure
- `LaborHoursBreakdown` - ALWAYS dict format (never simple float)
- `ShipmentResult` - Shipment with routing and state
- `TotalCostBreakdown` - Complete cost structure with 5 categories
- `InventoryStateKey` / `InventoryCohortKey` - Model-specific inventory formats

**Key Features:**
- `Extra.allow` - Models can add implementation-specific fields
- Cross-field validation - Ensures total_cost = sum(components)
- Fail-fast validation - Raises ValidationError on schema violations
- JSON serialization support - `to_dict_json_safe()` for serialization

**Configuration:**
- Validation: Fail-fast (raises exceptions)
- Extensibility: Open spec (extra fields permitted)
- Compatibility: Hard cutover (no backward compatibility layer)

### 2. Updated Base Model Interface ✅
**File:** `src/optimization/base_model.py` (MODIFIED)

**Changes:**
- `extract_solution()` return type: `Dict[str, Any]` → `OptimizationSolution`
- `get_solution()` return type: `Dict[str, Any]` → `OptimizationSolution`
- `self.solution` type: `Optional[Dict]` → `Optional[OptimizationSolution]`
- solve() method: Converts Pydantic to dict for metadata (`solution.model_dump()`)
- FEFO support: Updates Pydantic attributes instead of dict keys

**Impact:**
- ALL models inheriting from BaseOptimizationModel MUST return OptimizationSolution
- Validation happens automatically at extraction time
- Type hints enable IDE autocomplete and static analysis

### 3. Updated SlidingWindowModel ✅
**File:** `src/optimization/sliding_window_model.py` (MODIFIED)

**Implementation Pattern:**
1. extract_solution() builds dict (existing 237-line logic unchanged)
2. Calls `_dict_to_optimization_solution()` converter at end
3. Returns validated OptimizationSolution

**Converter Method:** `_dict_to_optimization_solution()` (NEW - 160 lines)
- Converts production_batches list → List[ProductionBatchResult]
- Converts labor_hours dict → Dict[Date, LaborHoursBreakdown]
- Converts shipments_by_route dict → List[ShipmentResult]
- Builds TotalCostBreakdown from individual cost components
- Preserves legacy fields as extra attributes (for FEFO allocator)

**Other Updates:**
- `apply_fefo_allocation()` - Accesses Pydantic attributes instead of dict
- `extract_shipments()` - Uses getattr() for optional fields
- Tuple keys converted to strings for JSON serialization

**Result:**
- Zero changes to core optimization logic (237-line extract_solution preserved)
- Validation happens transparently via converter
- Full backward compatibility with FEFO batch allocator

---

## 📋 Remaining Tasks (10/13)

### 4. Update UnifiedNodeModel ⏳
**File:** `src/optimization/unified_node_model.py`
**Pattern:** Follow SlidingWindowModel exactly

**Steps:**
1. Find extract_solution() method (should return `Dict[str, Any]`)
2. Add `_dict_to_optimization_solution()` converter method after extract_solution()
   - Convert production_batches → List[ProductionBatchResult]
   - Convert labor_hours_by_date → Dict[Date, LaborHoursBreakdown]
   - Convert cohort_inventory (6-tuple keys) → Dict[str, float]
   - Build shipments from solution data
   - Build TotalCostBreakdown
3. Update extract_solution() to call converter and return OptimizationSolution
4. Update return type annotation: `Dict[str, Any]` → `'OptimizationSolution'`
5. Find all `self.solution.get()` calls and replace with attribute access
6. Update any methods that pass self.solution to other modules (convert to dict via `.model_dump()`)

**Key Differences from SlidingWindow:**
- `model_type` = "unified_node" (not "sliding_window")
- `use_batch_tracking` = True (not `has_aggregate_inventory`)
- `cohort_inventory` field (6-tuple keys) instead of `inventory_state` (4-tuple)

**Estimated Time:** 2-3 hours (following established pattern)

### 5. Simplify result_adapter.py ⏳
**File:** `ui/utils/result_adapter.py` (487 lines → ~250 lines)

**Removals:**
- Lines 162-172: Labor hours format checking (`isinstance()` checks)
- Lines 176-180: Production date fallback logic (Pydantic guarantees presence)
- Lines 238-247: Graceful handling of missing fields (fail-fast instead)
- All try/except blocks for missing keys (Pydantic validation ensures presence)

**Updates:**
- Function signature: `result: dict` → `result: OptimizationSolution`
- Access via attributes: `result.production_batches` (not `result.get('production_batches')`)
- Add single ValidationError check at entry
- Trust Pydantic-validated data throughout

**Expected Result:**
- ~50% code reduction (487 → 250 lines)
- Zero isinstance() checks
- Zero .get() fallbacks
- Single validation point at function entry

**Estimated Time:** 1-2 hours

### 6. Update DailySnapshotGenerator ⏳
**File:** `src/analysis/daily_snapshot.py`

**Changes:**
- Accept `OptimizationSolution` instead of `dict` in constructor
- Remove MODE detection logic (use `solution.get_inventory_format()`)
- Access inventory via: `solution.inventory_state` or `solution.cohort_inventory`
- Remove LEGACY MODE reconstruction (fail-fast instead)

**Estimated Time:** 1 hour

### 7. Create MODEL_RESULT_SPECIFICATION.md ⏳
**File:** `docs/MODEL_RESULT_SPECIFICATION.md` (NEW)

**Contents:**
1. Overview and purpose
2. Complete field reference table (all OptimizationSolution fields)
3. Required vs optional fields
4. Model-specific discriminated union (sliding_window vs unified_node)
5. Examples for both model types
6. Development workflow (schema first, then implementation)
7. Validation rules and error handling

**Estimated Time:** 1-2 hours

### 8. Update Existing Documentation ⏳
**Files:** `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`, `CLAUDE.md`

**Updates:**
- Add "Interface Contract" section referencing result_schema.py
- Update return type documentation
- Add link to MODEL_RESULT_SPECIFICATION.md
- Update development workflow section

**Estimated Time:** 30 minutes

### 9. Create Schema Validation Tests ⏳
**File:** `tests/test_result_schema.py` (NEW)

**Test Cases:**
1. Valid SlidingWindowModel solution validates successfully
2. Valid UnifiedNodeModel solution validates successfully
3. Missing required field raises ValidationError
4. Invalid cost sum raises ValidationError
5. Invalid labor hours (paid < used) raises ValidationError
6. Extra fields are permitted and preserved
7. JSON serialization works (`to_dict_json_safe()`)
8. model_dump() produces correct structure

**Estimated Time:** 1-2 hours

### 10. Create Model Compliance Tests ⏳
**File:** `tests/test_model_compliance.py` (NEW)

**Test Cases:**
1. SlidingWindowModel inherits from BaseOptimizationModel
2. SlidingWindowModel.extract_solution() returns OptimizationSolution
3. UnifiedNodeModel inherits from BaseOptimizationModel
4. UnifiedNodeModel.extract_solution() returns OptimizationSolution
5. Both models set correct model_type flag
6. Both models set correct inventory format flags

**Estimated Time:** 1 hour

### 11. Update Integration Tests ⏳
**File:** `tests/test_integration_ui_workflow.py`

**Changes:**
- Add import: `from src.optimization.result_schema import OptimizationSolution`
- Add assertion: `isinstance(solution, OptimizationSolution)`
- Update dict access to attribute access: `solution.total_cost` (not `solution['total_cost']`)
- Add ValidationError test case (intentionally malformed data)

**Estimated Time:** 30 minutes

### 12. Update UI Results Page ⏳
**File:** `ui/pages/5_Results.py`

**Changes:**
- Add try/except around `adapt_optimization_results()`:
  ```python
  from pydantic import ValidationError
  try:
      adapted = adapt_optimization_results(model, result, date)
  except ValidationError as e:
      st.error(f"Model violated interface specification: {e}")
      st.stop()
  ```
- Add "Model Compliance" indicator in Overview tab
- Display schema version / model_type

**Estimated Time:** 30 minutes

### 13. Run Full Test Suite ⏳
**Command:** `pytest tests/ -v`

**Expected Issues:**
- result_adapter.py tests may fail (update to expect OptimizationSolution)
- Daily snapshot tests may fail (update to expect Pydantic attributes)
- Any code accessing solution as dict needs updating

**Resolution Strategy:**
- Fix one test file at a time
- Update assertions to use Pydantic attribute access
- Replace dict access with attribute access throughout

**Estimated Time:** 2-3 hours

---

## Key Implementation Patterns

### Pattern 1: Converting Model extract_solution()

```python
# OLD (returns dict)
def extract_solution(self, model: ConcreteModel) -> Dict[str, Any]:
    solution = {}
    # ... 200+ lines building dict ...
    return solution

# NEW (returns Pydantic)
def extract_solution(self, model: ConcreteModel) -> 'OptimizationSolution':
    solution = {}
    # ... 200+ lines building dict (UNCHANGED) ...
    return self._dict_to_optimization_solution(solution)  # Convert at end
```

### Pattern 2: Converter Method Structure

```python
def _dict_to_optimization_solution(self, solution_dict: Dict[str, Any]) -> 'OptimizationSolution':
    from .result_schema import OptimizationSolution, ProductionBatchResult, ...

    # 1. Convert batches
    production_batches = [ProductionBatchResult(**batch) for batch in solution_dict['production_batches']]

    # 2. Convert labor (ALWAYS dict format)
    labor_hours_by_date = {
        date: LaborHoursBreakdown(**hours) if isinstance(hours, dict) else
              LaborHoursBreakdown(used=hours, paid=hours, ...)
        for date, hours in solution_dict['labor_hours_by_date'].items()
    }

    # 3. Convert shipments
    shipments = [ShipmentResult(...) for ...]

    # 4. Build costs
    costs = TotalCostBreakdown(
        total_cost=solution_dict['total_cost'],
        labor=LaborCostBreakdown(total=solution_dict['total_labor_cost'], ...),
        ...
    )

    # 5. Build solution
    return OptimizationSolution(
        model_type="sliding_window",  # or "unified_node"
        production_batches=production_batches,
        labor_hours_by_date=labor_hours_by_date,
        shipments=shipments,
        costs=costs,
        ...
    )
```

### Pattern 3: Accessing Pydantic Solution

```python
# OLD (dict access)
production = self.solution.get('production_by_date_product', {})
total_cost = self.solution['total_cost']

# NEW (attribute access)
production = self.solution.production_by_date_product or {}
total_cost = self.solution.total_cost
```

### Pattern 4: Passing Solution to Legacy Code

```python
# If legacy code expects dict, convert:
solution_dict = self.solution.model_dump()
legacy_function(solution_dict)

# Or access preserved dict fields:
shipments_dict = getattr(self.solution, 'shipments_by_route_product_date', {})
```

---

## Testing Strategy

### Phase 1: Unit Tests (Schema)
1. Create `tests/test_result_schema.py`
2. Test all Pydantic models validate correctly
3. Test validation errors are raised properly
4. Test JSON serialization

### Phase 2: Integration Tests (Model Compliance)
1. Create `tests/test_model_compliance.py`
2. Test both models return OptimizationSolution
3. Test solution validates successfully
4. Run existing test_integration_ui_workflow.py

### Phase 3: Regression Tests (Full Suite)
1. Run full test suite: `pytest tests/ -v`
2. Fix any tests expecting dict format
3. Update result_adapter tests
4. Update daily_snapshot tests

### Phase 4: Manual UI Testing
1. Upload test data in Planning page
2. Run optimization with both models
3. View Results page tabs (all 7 tabs)
4. Verify no errors, all data displays correctly

---

## Risk Mitigation

### Risk: Breaking existing tests
**Mitigation:** Update tests incrementally, one file at a time. Each test file should be fixed before moving to the next.

### Risk: Pydantic validation too strict
**Mitigation:** Schema allows extra fields (`Extra.allow`). Models can add implementation-specific data without breaking validation.

### Risk: Performance overhead from validation
**Mitigation:** Validation only happens once at model-UI boundary. Negligible compared to solve time (seconds vs minutes).

### Risk: Incomplete schema coverage
**Mitigation:** Iterate on schema based on ValidationErrors during testing. Each error reveals a missing or incorrect field.

---

## Success Criteria

1. ✅ All 13 tasks completed
2. ✅ All tests passing (pytest tests/ -v)
3. ✅ No ValidationErrors in UI workflow
4. ✅ Results page displays all data correctly
5. ✅ No defensive isinstance() checks in UI code
6. ✅ result_adapter.py reduced to ~250 lines
7. ✅ Both SlidingWindowModel and UnifiedNodeModel return OptimizationSolution
8. ✅ Documentation complete (MODEL_RESULT_SPECIFICATION.md)

---

## Files Modified/Created

### Created (4 files):
1. `src/optimization/result_schema.py` - Pydantic schema (400+ lines) ✅
2. `docs/MODEL_RESULT_SPECIFICATION.md` - Specification doc ⏳
3. `tests/test_result_schema.py` - Schema validation tests ⏳
4. `tests/test_model_compliance.py` - Model compliance tests ⏳
5. `REFACTORING_PROGRESS.md` - This file ✅

### Modified (7+ files):
1. `src/optimization/base_model.py` - Abstract base class ✅
2. `src/optimization/sliding_window_model.py` - Converter added ✅
3. `src/optimization/unified_node_model.py` - Follow pattern ⏳
4. `ui/utils/result_adapter.py` - Simplify defensive code ⏳
5. `src/analysis/daily_snapshot.py` - Pydantic attributes ⏳
6. `ui/pages/5_Results.py` - ValidationError handling ⏳
7. `tests/test_integration_ui_workflow.py` - Update assertions ⏳
8. `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md` - Add interface section ⏳
9. `CLAUDE.md` - Add development workflow ⏳

---

## Estimated Remaining Time: 12-15 hours

**Breakdown:**
- UnifiedNodeModel: 2-3 hours
- result_adapter.py: 1-2 hours
- DailySnapshotGenerator: 1 hour
- Documentation: 2-3 hours
- Tests (creation + fixing): 4-5 hours
- UI updates: 1 hour
- Final integration testing: 1-2 hours

**Recommendation:** Tackle in order listed (UnifiedNodeModel → result_adapter → DailySnapshot → Tests → Documentation → UI).

---

## Next Steps

**Immediate:** Complete UnifiedNodeModel following SlidingWindowModel pattern
**Then:** Simplify result_adapter.py (biggest code reduction)
**Then:** Update DailySnapshotGenerator
**Then:** Write tests and documentation in parallel
**Finally:** Full integration testing

**Questions/Blockers:** None - pattern established, remaining work is mechanical replication.
