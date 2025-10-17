# Inventory Parser Update - Unit Conversion Support

## Summary

Updated the inventory parser to correctly handle multiple unit types (EA and CAS) and exclude Storage Location 5000 entries.

## Changes Made

### 1. Unit Conversion Support

**Previous Behavior:**
- Assumed all quantities were in cases (CAS)
- Always multiplied by 10 to convert to units

**New Behavior:**
- Reads `Base Unit of Measure` column
- Applies correct conversion factor:
  - **EA (Each)**: 1:1 conversion (already in units)
  - **CAS (Cases)**: 10:1 conversion (10 units per case)
- Warns about unknown unit types (defaults to 1:1)

### 2. Storage Location 5000 Exclusion

- **Skips all entries** with `Storage Location = 5000`
- Provides warning message with count of excluded entries
- Commonly used for reserved or non-available inventory

### 3. Enhanced Error Handling

- Added `Base Unit of Measure` to required columns
- Warnings for:
  - Negative quantities (set to 0)
  - Storage Location 5000 entries (skipped)
  - Unknown unit types (defaults to 1:1)
  - Unmapped product codes

## File Updates

### Modified Files:
1. **src/parsers/inventory_parser.py**
   - Updated class docstring with new format expectations
   - Added `UNIT_CONVERSION` dictionary for unit factors
   - Updated parsing logic to check Base Unit and apply conversion
   - Added Storage Location 5000 filtering
   - Enhanced warning messages

### New Files:
2. **tests/test_inventory_unit_conversion.py**
   - Test EA vs CAS conversion
   - Test Storage Location 5000 exclusion
   - Test specific conversion examples

3. **data/examples/inventory_latest.XLSX** (from GitHub)
   - New test file with both EA and CAS units
   - Contains Storage Location 5000 entries
   - 153 total rows, 39 excluded, 49 final entries

## Test Results

### Unit Conversion Test
```
✓ Parsed 49 inventory entries (from 153 total, 39 excluded)
✓ Total quantity: 49,581 units
✓ EA Example: 6180 EA → 6180 units (1:1) ✓
✓ CAS Example: 128 CAS → 1,280 units (10:1) ✓
```

### Storage Location 5000 Exclusion
```
✓ Total rows in file: 153
✓ Storage Location 5000 entries: 39
✓ Parsed entries (after exclusions): 49
✓ No 5000 entries in final result ✓
```

### Baseline Test (Existing)
```
✓ test_baseline_with_initial_inventory PASSED
✓ Backward compatible with existing inventory.XLSX (all CAS)
```

## Expected File Format

```
Required Columns:
- Material: Product code (e.g., 168846, 176283)
- Plant: Location ID (e.g., 6122, 6130)
- Base Unit of Measure: Unit type (EA or CAS)
- Unrestricted: Quantity in specified unit

Optional Columns:
- Storage Location: 4000 (plant), 4070 (Lineage), 5000 (excluded)

Ignored Columns:
- All other columns (Batch, Transit, etc.)
```

## Example Data

### Input (Excel):
| Material | Plant | Storage Location | Base Unit | Unrestricted |
|----------|-------|------------------|-----------|--------------|
| 168846   | 6122  | 4000             | EA        | 6180         |
| 176283   | 6122  | 4070             | CAS       | 128          |
| 168846   | 6104  | 5000             | EA        | 376          |

### Output (Parsed):
```python
{
    ("6122", "168846"): 6180,   # 6180 EA × 1 = 6180 units
    ("6122", "176283"): 1280,   # 128 CAS × 10 = 1280 units
    # Storage Location 5000 excluded
}
```

## Warnings Generated

During parsing, the following warnings may appear:

1. **Negative quantities**: "Found 8 negative quantity values. These were set to 0."
2. **Storage Location 5000**: "Skipped 39 entries with Storage Location 5000 (excluded from inventory)."
3. **Unknown units**: "Found 2 unknown unit types (using 1:1 conversion): ['KG', 'LB']"
4. **Unmapped products**: "Found 3 unmapped product codes: [...]"

## Usage

```python
from src.parsers.inventory_parser import InventoryParser
from datetime import date

# Parse inventory with unit conversion
parser = InventoryParser(
    file_path="data/examples/inventory_latest.XLSX",
    snapshot_date=date(2025, 1, 15)
)

snapshot = parser.parse()

# Convert to optimization format
initial_inventory = snapshot.to_optimization_dict()
# Returns: {(location_id, product_id): quantity_in_units, ...}
```

## Backward Compatibility

✅ **Fully backward compatible** with existing files that:
- Have `Base Unit of Measure` column (required)
- Only contain CAS units (will use 10:1 conversion)
- Existing test files continue to work

## Related Files

- Parser: `src/parsers/inventory_parser.py`
- Model: `src/models/inventory.py`
- Tests: `tests/test_inventory_unit_conversion.py`
- Baseline: `tests/test_baseline_initial_inventory.py`
- Data: `data/examples/inventory_latest.XLSX`
