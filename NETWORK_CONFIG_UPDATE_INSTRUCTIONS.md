# Network_Config.xlsx Update Instructions

## Overview

The Network Configuration template now supports manufacturing-specific parameters. This document provides instructions for updating `data/examples/Network_Config.xlsx` to include these parameters.

## Changes Required

### Locations Sheet - Add Manufacturing Columns

The following columns need to be added to the **Locations** sheet:

| Column Name | Type | Required | Default | Description |
|------------|------|----------|---------|-------------|
| `production_rate` | Float | Yes (for mfg) | - | Units produced per hour |
| `max_daily_capacity` | Float | No | None | Maximum production capacity per day |
| `daily_startup_hours` | Float | No | 0.5 | Production line startup time in hours |
| `daily_shutdown_hours` | Float | No | 0.5 | Production line shutdown time in hours |
| `default_changeover_hours` | Float | No | 1.0 | Product changeover time in hours |
| `morning_truck_cutoff_hour` | Integer | No | 24 | Hour by which morning truck production must complete (0-24) |
| `afternoon_truck_cutoff_hour` | Integer | No | 12 | Hour by which afternoon truck production must complete (0-24) |

### Update Steps

1. **Open `data/examples/Network_Config.xlsx`** in Excel or another spreadsheet application

2. **Navigate to the Locations sheet**

3. **Add the new columns** after the existing columns (after `longitude`)

4. **For the manufacturing location (ID: 6122)**, populate the following values:
   - `production_rate`: **1400.0** (units/hour)
   - `max_daily_capacity`: **19600** (with maximum overtime: 14 hours × 1400)
   - `daily_startup_hours`: **0.5**
   - `daily_shutdown_hours`: **0.5**
   - `default_changeover_hours`: **1.0**
   - `morning_truck_cutoff_hour`: **24** (end of previous day)
   - `afternoon_truck_cutoff_hour`: **12** (noon)

5. **For non-manufacturing locations** (breadrooms, storage):
   - Leave these columns **blank/empty** or enter `NULL`
   - The parser will skip these for non-manufacturing rows

### Example Updated Locations Sheet

```
id    name              type          storage_mode  capacity  lat      long      production_rate  max_daily_capacity  daily_startup_hours  daily_shutdown_hours  default_changeover_hours  morning_truck_cutoff_hour  afternoon_truck_cutoff_hour
6122  Manufacturing     manufacturing both          100000    ...      ...       1400.0           19600               0.5                  0.5                   1.0                       24                         12
6104  QBA-Moorebank     breadroom     ambient       5000      ...      ...
6125  QBA-Truganina     breadroom     ambient       8000      ...      ...
LIN01 Lineage Frozen   storage       frozen        50000     ...      ...
...
```

## Validation

After updating the file, you can validate it works correctly by running:

```bash
python -c "
from src.parsers import ExcelParser
parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = parser.parse_locations()
mfg = [l for l in locations if l.location_type.value == 'manufacturing'][0]
print(f'Manufacturing site: {mfg.name}')
print(f'Production rate: {mfg.production_rate} units/hour')
print(f'Max daily capacity: {mfg.max_daily_capacity} units')
print(f'Type: {type(mfg).__name__}')
"
```

Expected output:
```
Manufacturing site: Manufacturing
Production rate: 1400.0 units/hour
Max daily capacity: 19600.0 units
Type: ManufacturingSite
```

## Backwards Compatibility

### Old Files Without Manufacturing Columns

If you have existing Network_Config.xlsx files without the new manufacturing columns:

- **Non-manufacturing locations** will work without any changes
- **Manufacturing locations** will raise a `ValueError` with message:
  ```
  Manufacturing location {id} missing required 'production_rate' parameter
  ```
- **Solution**: Add the `production_rate` column (minimum requirement) for manufacturing locations

### Migration Path

For existing files, you have two options:

1. **Add only `production_rate`** (minimum change):
   - Sufficient for basic functionality
   - Other parameters will use defaults

2. **Add all manufacturing columns** (recommended):
   - Full control over manufacturing parameters
   - Aligned with updated template specification

## Code Changes Summary

The following code changes have been implemented:

1. **EXCEL_TEMPLATE_SPEC.md** (data/examples/):
   - Added manufacturing-specific columns section
   - Updated example rows
   - Added usage notes

2. **excel_parser.py** (src/parsers/):
   - Modified `parse_locations()` to detect manufacturing type
   - Creates `ManufacturingSite` objects for manufacturing locations
   - Creates regular `Location` objects for other types
   - Validates required `production_rate` parameter
   - Applies defaults for optional parameters

3. **Tests**:
   - Existing parser tests pass with changes
   - Manufacturing locations will be automatically parsed correctly

## Questions or Issues

If you encounter any problems updating the file or have questions about the new parameters:

1. Refer to `data/examples/EXCEL_TEMPLATE_SPEC.md` for complete specification
2. Check the ManufacturingSite model definition in `src/models/manufacturing.py`
3. Review existing test implementations for examples

## Next Steps

After updating the Excel file:

1. Run existing integration tests to verify functionality
2. Update any test scripts that manually create ManufacturingSite objects
3. Update documentation referencing the old Locations sheet structure
