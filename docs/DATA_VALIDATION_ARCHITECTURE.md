# Data Validation Architecture

## Overview

This document describes the robust data validation architecture implemented to ensure data quality and fail-fast error detection throughout the planning application.

**Problem Solved:** Previously, data errors (mismatched product IDs, missing references, invalid dates) would silently propagate through the system and only surface during optimization solve time, making debugging difficult.

**Solution:** A Pydantic-based validation layer that validates all data at load time, providing clear error messages with context.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INPUT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  Forecast    │  │   Network    │  │  Inventory   │             │
│  │  Excel File  │  │ Config Excel │  │  Excel File  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          PARSER LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ExcelParser   │  │UnifiedModel  │  │Inventory     │             │
│  │              │  │Parser        │  │Parser        │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA COORDINATOR                                 │
│  • Loads data from multiple sources                                  │
│  • Resolves product ID mismatches                                    │
│  • Coordinates date ranges                                           │
│  └──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  VALIDATION LAYER (Pydantic)                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ValidatedPlanningData                                        │  │
│  │  ✓ Product ID consistency                                     │  │
│  │  ✓ Node ID consistency                                        │  │
│  │  ✓ Date range validation                                      │  │
│  │  ✓ Cross-reference validation                                 │  │
│  │  ✓ Data type validation                                       │  │
│  │  ✓ Quantity reasonableness checks                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    OPTIMIZATION MODEL                                │
│  SlidingWindowModel receives only validated data                     │
│  • All product IDs guaranteed to exist                               │
│  • All node IDs guaranteed to exist                                  │
│  • All dates within valid range                                      │
│  • No type confusion or missing references                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. `planning_data_schema.py`

**Purpose:** Defines Pydantic schemas for all planning data

**Key Classes:**
- `ProductID`: Product identifier with SKU resolution
- `NodeID`: Node identifier with validation
- `DemandEntry`: Single demand record with validation
- `InventoryEntry`: Single inventory record with validation
- `ValidatedPlanningData`: Complete validated dataset with cross-validation

**Validation Rules:**
- Product IDs must be consistent between demand and inventory
- Node IDs must exist in both routes and demand
- Dates must be within planning horizon
- Quantities must be non-negative and reasonable (< 1M units)
- Storage states must be valid (ambient/frozen/thawed)

### 2. `data_coordinator.py`

**Purpose:** Coordinates data loading from multiple files

**Key Class:**
- `DataCoordinator`: Orchestrates loading and validation

**Features:**
- File existence validation
- **Automatic alias resolution** (auto-loads from network/forecast Alias sheet)
- Product ID resolution (handles SKU vs name mismatches)
- Date range coordination
- Support for both legacy and unified formats
- Clear error messages with context

**Usage:**
```python
from src.validation.data_coordinator import load_validated_data

# Load and validate all data
data = load_validated_data(
    forecast_file="data/forecast.xlsm",
    network_file="data/network.xlsx",
    inventory_file="data/inventory.xlsx",
    planning_weeks=4
)

# Data is now guaranteed valid
print(data.summary())
```

---

## Validation Checks

### Level 1: Field-Level Validation

**Performed by:** Pydantic field validators

**Examples:**
- Product ID not empty
- Quantities ≥ 0
- Dates valid
- Storage state in {'ambient', 'frozen', 'thawed'}

**Error Example:**
```
ValidationError: 1 validation error for DemandEntry
quantity
  Demand quantity cannot be negative: -100.0
```

### Level 2: Entity-Level Validation

**Performed by:** Pydantic model validators

**Examples:**
- Quantity reasonableness (< 1M units)
- Date ranges (start < end)
- ID format validity

**Error Example:**
```
ValidationError: 1 validation error for DemandEntry
quantity
  Demand quantity seems unreasonably large: 10,000,000 units. Check data.
```

### Level 3: Cross-Reference Validation

**Performed by:** `ValidatedPlanningData.validate_cross_references()`

**Examples:**
- Product IDs in demand exist in products list
- Product IDs in inventory exist in products list
- Node IDs in demand exist in nodes list
- Dates within planning horizon

**Error Example:**
```
Data Validation Error: Found 34 product IDs in inventory that are not in products list.
Sample: ['168846', '168847', '168848', '168849', '168850']
Check if inventory uses SKU codes while forecast uses product names.

Context:
  forecast_file: Gluten Free Forecast - Latest.xlsm
  network_file: Network_Config.xlsx
  inventory_file: inventory_latest.XLSX
```

### Level 4: Consistency Validation

**Performed by:** `ValidatedPlanningData.validate_product_id_consistency()`

**Examples:**
- Product ID format consistency (all numeric or all text)
- Inventory snapshot date before planning start
- No duplicate entries

**Error Example:**
```
Data Validation Error: Inventory snapshot date 2025-11-05 is AFTER planning start 2025-11-03.
Initial inventory should be measured before or at planning start.
```

---

## Migration Guide

### Old Pattern (Fragile)

```python
# Old: Data loaded as unvalidated dicts
from src.parsers.excel_parser import ExcelParser

parser = ExcelParser("forecast.xlsm")
products, demand = parser.parse_forecast("forecast.xlsm")

# Problem: demand is Dict[(str, str, date), float] with no validation
# Product ID mismatches silently create zero demand!
model = SlidingWindowModel(
    ...
    demand=demand,  # Unvalidated dict
    ...
)

# Error surfaces 300 seconds later during solve:
# "Zero production - but why??"
```

### New Pattern (Robust)

```python
# New: Data validated at load time
from src.validation.data_coordinator import load_validated_data

# Load and validate (fails fast if data invalid)
try:
    data = load_validated_data(
        forecast_file="data/forecast.xlsm",
        network_file="data/network.xlsx",
        inventory_file="data/inventory.xlsx",
        planning_weeks=4
    )
except ValidationError as e:
    print(f"Data validation failed: {e}")
    # Clear error message with context
    # Fix data and retry
    sys.exit(1)

# At this point, data is guaranteed valid
print(data.summary())

# Convert to model format (validated)
model = SlidingWindowModel(
    ...
    demand=data.get_demand_dict(),  # Validated
    initial_inventory=data.get_inventory_dict(),  # Validated
    ...
)

# No surprises during solve!
```

---

## Error Message Examples

### Example 1: Missing Product in Forecast

**Scenario:** Inventory contains product '168846' but forecast uses name 'HELGAS GFREE MIXED GRAIN 500G'

**Error:**
```
Data Validation Error: Found 49 product IDs in inventory that are not in products list.
Sample: ['168846', '168847', '168848', '168849', '168850']
Check if inventory uses SKU codes while forecast uses product names.

Context:
  forecast_file: Gluten Free Forecast - Latest.xlsm
  inventory_file: inventory_latest.XLSX
  error_type: ValidationError
```

**Fix:** Use ProductAliasResolver or update inventory to use product names

### Example 2: Invalid Node Reference

**Scenario:** Demand references node 'BR10' but only 'BR1'-'BR9' exist

**Error:**
```
Data Validation Error: Invalid demand entries found:
  Demand entry BR10/PROD_A/2025-11-03: unknown node 'BR10'

Context:
  demand_entries: 1305
  registered_nodes: 9
```

**Fix:** Correct node ID in forecast or add node to network config

### Example 3: Date Range Issue

**Scenario:** Inventory snapshot dated after planning start

**Error:**
```
Data Validation Error: Inventory snapshot date 2025-11-05 is AFTER planning start 2025-11-03.
Initial inventory should be measured before or at planning start.
```

**Fix:** Adjust planning start date or update inventory snapshot date

---

## Benefits

### 1. Fail Fast
- Errors detected at data load time (seconds)
- Not at solve time (minutes later)

### 2. Clear Error Messages
- Exact location of problem
- Suggested fixes
- Context about what went wrong

### 3. Type Safety
- Pydantic ensures correct types
- No "string vs int" confusion
- IDE autocomplete works

### 4. Maintainability
- Single source of truth for validation rules
- Easy to add new checks
- Tests validate the validators

### 5. Debugging
- Product ID mismatches caught immediately
- Node ID typos caught immediately
- Date range errors caught immediately

---

## Testing Strategy

### Unit Tests
```python
def test_demand_entry_validation():
    """Test demand entry field validation."""
    # Valid entry
    entry = DemandEntry(
        node_id="BR1",
        product_id="PROD_A",
        demand_date=date(2025, 11, 3),
        quantity=100.0
    )
    assert entry.quantity == 100.0

    # Invalid: negative quantity
    with pytest.raises(ValidationError):
        DemandEntry(
            node_id="BR1",
            product_id="PROD_A",
            demand_date=date(2025, 11, 3),
            quantity=-100.0  # Invalid!
        )
```

### Integration Tests
```python
def test_product_id_consistency():
    """Test cross-validation of product IDs."""
    # Scenario: Inventory has product not in forecast
    data = ValidatedPlanningData(
        products=[ProductID(id="PROD_A", name="Product A")],
        nodes=[NodeID(id="BR1", name="Breadroom 1")],
        demand_entries=[...],  # Uses PROD_A
        inventory_entries=[
            InventoryEntry(
                node_id="BR1",
                product_id="PROD_B",  # Not in products list!
                state="ambient",
                quantity=100.0
            )
        ],
        ...
    )
    # Should raise ValidationError about missing PROD_B
```

---

## Future Enhancements

### Phase 2: Route Validation
- Validate route origins/destinations reference valid nodes
- Validate transit times are reasonable
- Check for disconnected network components

### Phase 3: Capacity Validation
- Validate demand fits within network capacity
- Check production capacity vs demand
- Validate storage capacity constraints

### Phase 4: Real-Time Validation
- Validation hooks in UI for immediate feedback
- Incremental validation as data changes
- Validation caching for performance

---

## Summary

The new validation architecture provides:

✅ **Fail-fast error detection** at data load time
✅ **Clear, actionable error messages** with context
✅ **Type safety** via Pydantic schemas
✅ **Cross-validation** of all entity relationships
✅ **Product ID resolution** handling SKU mismatches
✅ **Maintainability** through centralized validation logic

**Result:** Bugs are caught immediately with clear fixes, not 5 minutes later with cryptic solver messages.
