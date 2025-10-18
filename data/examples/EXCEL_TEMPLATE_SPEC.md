# Excel Template Specification

## Overview

This document specifies the exact format expected by the `ExcelParser` for loading forecast and operational data. The Excel file must be in `.xlsm` or `.xlsx` format and contain up to 6 sheets.

## Required Sheets

### 1. Forecast Sheet

**Sheet Name:** `Forecast` (default)

**Purpose:** Daily demand forecast by location and product

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `location_id` | string | Breadroom destination ID | "6104" | Yes |
| `product_id` | string | Product identifier | "168846" | Yes |
| `date` | date | Forecast date | "2025-06-02" | Yes |
| `quantity` | float | Forecasted units | 125.5 | Yes |
| `confidence` | float | Confidence level (0-1) | 0.85 | No |

**Example Rows:**
```
location_id  product_id  date        quantity  confidence
6104         168846      2025-06-02  120       0.90
6105         168846      2025-06-02  85        0.88
6104         168847      2025-06-02  95        0.85
```

**Notes:**
- Dates can be in any format pandas recognizes (ISO 8601 recommended)
- Quantity must be non-negative
- Confidence is optional, defaults to None

---

### 2. Locations Sheet

**Sheet Name:** `Locations` (default)

**Purpose:** Network nodes (manufacturing, storage, breadrooms)

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `id` | string | Unique location ID | "6122" | Yes |
| `name` | string | Location name | "QBA-Moorebank" | Yes |
| `type` | string | Location type | "manufacturing", "storage", "breadroom" | Yes |
| `storage_mode` | string | Storage capability | "ambient", "frozen", "both" | Yes |
| `capacity` | float | Storage capacity (units) | 50000 | No |
| `latitude` | float | GPS latitude | -33.8688 | No |
| `longitude` | float | GPS longitude | 151.2093 | No |

**Valid Values:**
- `type`: "manufacturing", "storage", "breadroom"
- `storage_mode`: "ambient", "frozen", "both"

**Manufacturing-Specific Columns** (required when `type="manufacturing"`):
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `production_rate` | float | Units produced per hour | 1400.0 | Yes (for mfg) |
| `max_daily_capacity` | float | Max production per day (units) | 19600 | No |
| `daily_startup_hours` | float | Production line startup time (hours) | 0.5 | No (default: 0.5) |
| `daily_shutdown_hours` | float | Production line shutdown time (hours) | 0.5 | No (default: 0.5) |
| `default_changeover_hours` | float | Product changeover time (hours) | 1.0 | No (default: 1.0) |
| `morning_truck_cutoff_hour` | int | Morning truck production cutoff (0-24) | 24 | No (default: 24) |
| `afternoon_truck_cutoff_hour` | int | Afternoon truck production cutoff (0-24) | 12 | No (default: 12) |

**Notes:**
- Manufacturing-specific columns only apply to rows where `type="manufacturing"`
- For non-manufacturing locations, these columns can be omitted or left blank
- `production_rate` is REQUIRED for manufacturing locations
- Cutoff hours: 24 = end of previous day, 12 = noon same day

**Example Rows:**
```
id    name              type          storage_mode  capacity  production_rate  max_daily_capacity  daily_startup_hours  daily_shutdown_hours
6122  Manufacturing     manufacturing both          100000    1400.0           19600               0.5                  0.5
6104  QBA-Moorebank     breadroom     ambient       5000
LIN01 Lineage Frozen   storage       frozen        50000
```

---

### 3. Routes Sheet

**Sheet Name:** `Routes` (default)

**Purpose:** Transport connections between locations

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `id` | string | Unique route ID | "R1" | Yes |
| `origin_id` | string | Origin location ID | "6122" | Yes |
| `destination_id` | string | Destination location ID | "6104" | Yes |
| `transport_mode` | string | Transport mode | "ambient", "frozen" | Yes |
| `transit_time_days` | float | Transit time in days | 1.5 | Yes |
| `cost` | float | Transport cost per unit | 0.25 | No |
| `capacity` | float | Route capacity (units) | 14080 | No |

**Valid Values:**
- `transport_mode`: "ambient", "frozen"

**Example Rows:**
```
id  origin_id  destination_id  transport_mode  transit_time_days  cost  capacity
R1  6122       6104           ambient         1.0                0.30  14080
R2  6122       LIN01          frozen          0.5                0.50  14080
R3  LIN01      6130           frozen          3.0                1.20  14080
```

---

### 4. LaborCalendar Sheet

**Sheet Name:** `LaborCalendar` (default)

**Purpose:** Daily labor availability and cost rates

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `date` | date | Calendar date | "2025-06-02" | Yes |
| `fixed_hours` | float | Fixed labor hours allocated | 12.0 | No (default: 0) |
| `regular_rate` | float | Regular hourly rate ($/hr) | 25.00 | Yes |
| `overtime_rate` | float | Overtime hourly rate ($/hr) | 37.50 | Yes |
| `non_fixed_rate` | float | Non-fixed day rate ($/hr) | 40.00 | No |
| `minimum_hours` | float | Minimum hours on non-fixed days | 4.0 | No (default: 0) |
| `is_fixed_day` | boolean | True if fixed labor day | TRUE | No (default: TRUE) |

**Business Rules:**
- **Weekdays (Mon-Fri):** `fixed_hours=12`, `is_fixed_day=TRUE`
- **Weekends:** `fixed_hours=0`, `is_fixed_day=FALSE`, `non_fixed_rate=40`, `minimum_hours=4`
- **Public holidays:** Same as weekends

**Example Rows:**
```
date        fixed_hours  regular_rate  overtime_rate  non_fixed_rate  minimum_hours  is_fixed_day
2025-06-02  12           25.00         37.50          NULL            0              TRUE
2025-06-03  12           25.00         37.50          NULL            0              TRUE
2025-06-07  0            25.00         37.50          40.00           4              FALSE
2025-06-08  0            25.00         37.50          40.00           4              FALSE
2025-06-09  0            25.00         37.50          40.00           4              FALSE
```

**Note:** For public holidays in 2025 and 2026, use weekend labor rules.

#### Date Coverage Requirements

⚠️ **IMPORTANT:** The labor calendar must cover all production dates in your schedule.

**Coverage Guidelines:**
- **Minimum:** Cover all forecast dates
- **Recommended:** Extend 7 days before forecast start (for production lead time)
- **For Optimization:** Extend 7-10 days before forecast start and to forecast end

**What happens if dates are missing:**
- **Default mode:** System uses weekday/weekend defaults with warnings
  - Weekdays (Mon-Fri): 12h fixed hours at regular rates
  - Weekends (Sat-Sun): Non-fixed hours at premium rates with 4h minimum
- **Strict validation mode:** System fails with clear error message indicating missing dates

**Example:**
```
Forecast period: 2025-06-15 to 2025-07-15
Recommended labor calendar: 2025-06-08 to 2025-07-15 (7 days before forecast start)
```

**Common Scenarios Requiring Extended Coverage:**
- Heuristic planning: Production scheduled before delivery dates
- Optimization: Planning horizon extended backward for production lead time
- Multi-echelon network: Transit times require early production

---

### 5. TruckSchedules Sheet

**Sheet Name:** `TruckSchedules` (default)

**Purpose:** Daily truck departure schedules from manufacturing

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `id` | string | Unique truck schedule ID | "T1" | Yes |
| `truck_name` | string | Human-readable name | "Morning 6125" | Yes |
| `departure_type` | string | Morning or afternoon | "morning", "afternoon" | Yes |
| `departure_time` | time | Departure time | "08:00:00" | Yes |
| `destination_id` | string | Fixed destination (if any) | "6125" | No |
| `capacity` | float | Truck capacity (units) | 14080 | Yes |
| `cost_fixed` | float | Fixed cost per departure | 100.00 | No (default: 0) |
| `cost_per_unit` | float | Variable cost per unit | 0.50 | No (default: 0) |
| `day_of_week` | string | Specific day (if not daily) | "monday", "tuesday", etc. | No |
| `intermediate_stops` | string | Comma-separated stop IDs | "Lineage" | No |
| `pallet_capacity` | integer | Max pallets | 44 | No (default: 44) |
| `units_per_pallet` | integer | Units per pallet | 320 | No (default: 320) |
| `units_per_case` | integer | Units per case | 10 | No (default: 10) |

**Valid Values:**
- `departure_type`: "morning", "afternoon"
- `day_of_week`: "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", or NULL/empty for daily

**Example Rows:**
```
id   truck_name        departure_type  departure_time  destination_id  capacity  day_of_week  intermediate_stops
T1   Morning 6125 Mon  morning         08:00          6125            14080     NULL         NULL
T2   Morning 6125 Wed  morning         08:00          6125            14080     wednesday    Lineage
T3   Afternoon 6104    afternoon       14:00          6104            14080     monday       NULL
T4   Afternoon 6110    afternoon       14:00          6110            14080     tuesday      NULL
```

**Notes:**
- `day_of_week=NULL` means daily schedule (e.g., morning truck Mon-Fri)
- `intermediate_stops` is comma-separated list (e.g., "Lineage,TempStorage")
- Pallet fields default to standard values (44 pallets, 320 units/pallet, 10 units/case)

---

### 6. CostParameters Sheet

**Sheet Name:** `CostParameters` (default)

**Purpose:** Cost coefficients for optimization

**Required Columns:**
| Column | Type | Description | Example | Required |
|--------|------|-------------|---------|----------|
| `cost_type` | string | Parameter name | "production_cost_per_unit" | Yes |
| `value` | float | Cost value | 5.00 | Yes |
| `unit` | string | Unit description | "$/unit" | No |

**Standard Cost Types:**
| cost_type | Description | Typical Unit | Example Value |
|-----------|-------------|--------------|---------------|
| `production_cost_per_unit` | Base production cost | $/unit | 5.00 |
| `holding_cost_ambient_per_unit_day` | Ambient storage cost | $/(unit·day) | 0.05 |
| `holding_cost_frozen_per_unit_day` | Frozen storage cost | $/(unit·day) | 0.10 |
| `transport_cost_ambient_per_unit` | Ambient transport | $/unit | 0.30 |
| `transport_cost_frozen_per_unit` | Frozen transport | $/unit | 0.50 |
| `truck_fixed_cost` | Fixed truck cost | $/departure | 100.00 |
| `waste_cost_multiplier` | Waste cost multiplier | dimensionless | 1.5 |
| `shortage_penalty_per_unit` | Stockout penalty | $/unit | 10.00 |
| `default_regular_rate` | Default labor rate | $/hour | 25.00 |
| `default_overtime_rate` | Default OT rate | $/hour | 37.50 |
| `storage_cost_frozen_per_unit_day` | Frozen storage (unit-based, legacy) | $/(unit·day) | 0.10 |
| `storage_cost_ambient_per_unit_day` | Ambient storage (unit-based, legacy) | $/(unit·day) | 0.05 |
| `storage_cost_fixed_per_pallet` | Fixed pallet storage cost (DEPRECATED - use state-specific) | $/pallet | 0.0 |
| `storage_cost_per_pallet_day_frozen` | Frozen storage per pallet per day | $/pallet/day | 0.5 |
| `storage_cost_per_pallet_day_ambient` | Ambient storage per pallet per day | $/pallet/day | 0.2 |
| `storage_cost_fixed_per_pallet_frozen` | Fixed cost for frozen pallet storage (NEW 2025-10-18) | $/pallet | 0.0 |
| `storage_cost_fixed_per_pallet_ambient` | Fixed cost for ambient pallet storage (NEW 2025-10-18) | $/pallet | 0.0 |

**Pallet-Based Storage Costs (Added 2025-10-17, Enhanced 2025-10-18):**
- **Pallet definition:** 320 units = 32 cases = 1 pallet
- **Rounding behavior:** Partial pallets cost as full pallets (50 units = 1 pallet cost)
- **State-specific fixed costs (NEW 2025-10-18):**
  - `storage_cost_fixed_per_pallet_frozen`: Fixed cost when pallet enters frozen storage
  - `storage_cost_fixed_per_pallet_ambient`: Fixed cost when pallet enters ambient storage
  - These override the legacy `storage_cost_fixed_per_pallet` parameter
- **Conditional pallet tracking:** If a state's pallet costs are zero, that state uses unit-based tracking (continuous variables) instead of pallet tracking (integer variables)
  - **Performance benefit:** Fewer integer variables → faster solve times
  - **Example:** Set frozen pallet costs to 0 → frozen inventory uses unit tracking, ambient uses pallet tracking
- **Precedence:** If both pallet-based and unit-based costs are specified, pallet-based takes precedence
- **Conversion:** To convert unit-based to pallet-based: `pallet_cost = unit_cost × 320`
- **Recommended:** Use pallet-based costs for accurate storage cost representation
- **Legacy support:** Unit-based costs still supported for backward compatibility

**Example Rows:**
```
cost_type                          value   unit
production_cost_per_unit           5.00    $/unit
transport_cost_ambient_per_unit    0.30    $/unit
truck_fixed_cost                   100.00  $/departure
waste_cost_multiplier              1.5     -
```

**Notes:**
- Parser looks for specific cost_type names
- Missing cost types use defaults from CostStructure model
- `unit` column is optional (documentation only)

---

## Complete Example Structure

### Minimal Working Example

**File:** `data/examples/template_minimal.xlsx`

**Forecast Sheet (3 rows):**
```
location_id  product_id  date        quantity
6104         P1          2025-06-02  100
6104         P1          2025-06-03  120
6105         P1          2025-06-02  80
```

**Locations Sheet (3 rows):**
```
id    name            type          storage_mode
6122  Manufacturing   manufacturing both
6104  Moorebank       breadroom     ambient
6105  Rydalmere       breadroom     ambient
```

**Routes Sheet (2 rows):**
```
id  origin_id  destination_id  transport_mode  transit_time_days
R1  6122       6104           ambient         1.0
R2  6122       6105           ambient         1.0
```

**LaborCalendar Sheet (7 rows):**
```
date        fixed_hours  regular_rate  overtime_rate
2025-06-02  12           25.00         37.50
2025-06-03  12           25.00         37.50
2025-06-04  12           25.00         37.50
2025-06-05  12           25.00         37.50
2025-06-06  12           25.00         37.50
2025-06-07  0            25.00         37.50
2025-06-08  0            25.00         37.50
```

**TruckSchedules Sheet (2 rows):**
```
id  truck_name     departure_type  departure_time  capacity  destination_id
T1  Morning 6104   morning         08:00          14080     6104
T2  Morning 6105   morning         10:00          14080     6105
```

**CostParameters Sheet (2 rows):**
```
cost_type                        value
production_cost_per_unit         5.00
transport_cost_ambient_per_unit  0.30
```

---

## Usage in Python

```python
from pathlib import Path
from src.parsers import ExcelParser

# Parse all sheets
parser = ExcelParser("data/examples/template_minimal.xlsx")
forecast, locations, routes, labor, trucks, costs = parser.parse_all()

# Or parse individually
parser = ExcelParser("data/examples/my_forecast.xlsm")
forecast = parser.parse_forecast()  # Just forecast
locations = parser.parse_locations()  # Just locations
# etc.
```

---

## Validation Rules

### Common Validation Errors

**Missing Required Columns:**
```
ValueError: Missing required columns: {'date', 'quantity'}
```
→ Ensure all required columns exist with exact names

**Invalid Enum Values:**
```
ValueError: 'Manufacturing' is not a valid LocationType
```
→ Use lowercase: "manufacturing" not "Manufacturing"

**Date Parse Errors:**
```
ValueError: Could not parse date from '06/02/25'
```
→ Use ISO format: "2025-06-02" or Excel date cells

**Type Errors:**
```
ValueError: Quantity must be numeric
```
→ Ensure numeric columns contain numbers, not text

---

## Tips for Creating Templates

1. **Use Excel date cells** for date columns (not text)
2. **Use lowercase** for enum fields (type, storage_mode, departure_type)
3. **Leave optional columns blank** (or omit entirely)
4. **Use NULL or empty** for missing data in optional columns
5. **Validate enums** before loading:
   - LocationType: "manufacturing", "storage", "breadroom"
   - StorageMode: "ambient", "frozen", "both"
   - DepartureType: "morning", "afternoon"
   - DayOfWeek: "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"

6. **Test with minimal data first** before loading full dataset

---

## Multi-File Workflow (Recommended)

### Two-File Approach

For production use, we recommend **separating forecast data from network configuration** using two files:

**File 1: Forecast File** (`Gfree Forecast.xlsm` or similar)
- Contains: `Forecast` sheet only
- Updates: Frequently (weekly/monthly from demand planning system)
- Source: SAP IBP or other forecasting tools
- Format: Requires conversion to long format if from SAP IBP

**File 2: Network Configuration File** (`Network_Config.xlsx`)
- Contains: `Locations`, `Routes`, `LaborCalendar`, `TruckSchedules`, `CostParameters` sheets
- Updates: Infrequently (when network structure or operations change)
- Source: Operations team, manually maintained
- Format: Direct use with parser

### Benefits of Two-File Approach

1. **Separation of Concerns**: Demand planning team updates forecasts, operations team maintains network config
2. **Reduced File Size**: Forecast files can be large; separating keeps network config manageable
3. **Version Control**: Network config can be version-controlled separately
4. **Easier Updates**: Update forecast without touching network configuration
5. **Flexibility**: Use different forecast files with same network config for scenarios

### Usage with MultiFileParser

```python
from src.parsers import MultiFileParser

# Load both files
parser = MultiFileParser(
    forecast_file="data/Gfree Forecast.xlsm",  # After SAP IBP conversion
    network_file="data/Network_Config.xlsx"
)

# Parse all data
forecast, locations, routes, labor, trucks, costs = parser.parse_all()

# Validate consistency
validation = parser.validate_consistency(forecast, locations, routes)
if validation["warnings"]:
    for warning in validation["warnings"]:
        print(f"⚠️ {warning}")
```

### Example Files

**Forecast File**: Use `Gfree Forecast.xlsm` (requires SAP IBP conversion) or create your own with `Forecast` sheet

**Network Config File**: Use `Network_Config.xlsx` (provided in `data/examples/`)
- 11 locations (6122 manufacturing + 2 hubs + 1 frozen storage + 7 breadrooms)
- 10 routes (4 primary + 5 secondary + 1 frozen buffer)
- 204-day labor calendar (Jun 2 - Dec 22, 2025)
- 11 weekly truck departures
- 12 cost parameters

### Single-File Approach (Alternative)

You can still use a single file with all 6 sheets if preferred:

```python
from src.parsers import ExcelParser

parser = ExcelParser("data/complete_data.xlsx")
forecast, locations, routes, labor, trucks, costs = parser.parse_all()
```

---

## Differences from SAP IBP Format

The provided `Gfree Forecast.xlsm` is in SAP IBP export format, which differs from this template:

| Aspect | SAP IBP Format | Template Format |
|--------|----------------|-----------------|
| Forecast layout | Wide (dates as columns) | Long (date as field) |
| Multiple sheets | Single sheet | 6 separate sheets |
| Metadata | Embedded headers | Clean tabular |
| Ready to use | No (needs conversion) | Yes (direct load) |

**To convert SAP IBP:** See below for automatic conversion options.

---

## SAP IBP Conversion

The application includes automatic conversion from SAP Integrated Business Planning (IBP) export format to the required long format.

### What is SAP IBP Format?

SAP IBP exports use a **wide format** where:
- Dates are column headers (e.g., "02.06.2025", "03.06.2025", ...)
- Each row represents one location-product combination
- Forecast quantities are cell values at date intersections
- File contains 5 metadata/header rows before data

**Example SAP IBP Structure:**
```
Sheet: "G610 RET"
Row 5 (headers): [metadata...] | Product | Location | ... | 02.06.2025 | 03.06.2025 | ...
Row 6 (data):    [metadata...] | 168846  | 6104     | ... | 120        | 125        | ...
Row 7 (data):    [metadata...] | 168846  | 6105     | ... | 85         | 90         | ...
```

**Target Long Format:**
```
location_id  product_id  date        quantity
6104         168846      2025-06-02  120
6104         168846      2025-06-03  125
6105         168846      2025-06-02  85
6105         168846      2025-06-03  90
```

### Conversion Methods

#### Method 1: Streamlit UI (Recommended for Interactive Use)

1. **Upload SAP IBP file** to the Upload Data page
2. **Automatic detection**: App detects SAP IBP format by sheet names
3. **One-click conversion**: Click "🔄 Convert SAP IBP to Long Format" button
4. **Preview results**: View converted data with summary metrics
5. **Download**: Optionally download converted Excel file

**Features:**
- Automatic format detection
- Real-time preview of converted data
- Summary statistics (locations, products, date range)
- Excel download option
- Error handling with detailed messages

#### Method 2: Command-Line Tool (Recommended for Batch Processing)

Use the `convert_sap_ibp.py` script for batch conversion or automation:

```bash
# Basic usage - converts to [input_file]_Converted.xlsx
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm"

# Custom output filename
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" "Forecast_Long.xlsx"

# Verbose mode for detailed output
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" -v

# Specify sheet name (if multiple data sheets)
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" --sheet "G610 RET"

# Custom output sheet name
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" --output-sheet "Forecast"
```

**Command-Line Options:**
- `input_file` (required): Path to SAP IBP Excel file
- `output_file` (optional): Output path (default: input_file_Converted.xlsx)
- `--sheet SHEET`: Sheet name to read (auto-detects if not specified)
- `--output-sheet SHEET`: Output sheet name (default: "Forecast")
- `-v, --verbose`: Detailed output with statistics

**Example Output:**
```
🔄 Converting SAP IBP file...
   Input:  data/Gfree Forecast.xlsm
   Output: data/Gfree Forecast_Converted.xlsx

✅ Conversion successful!
   Output file: data/Gfree Forecast_Converted.xlsx
   Entries: 9180
```

#### Method 3: Python API (Recommended for Programmatic Use)

Use the `SapIbpConverter` class directly in your Python code:

```python
from pathlib import Path
from src.parsers import SapIbpConverter

# Initialize converter
converter = SapIbpConverter("data/Gfree Forecast.xlsm")

# Option A: Convert and get DataFrame
df_forecast = converter.convert()
print(f"Converted {len(df_forecast)} forecast entries")
print(df_forecast.head())

# Option B: Convert and save directly to Excel
converter.convert_and_save(
    output_path="Forecast_Converted.xlsx",
    sheet_name=None,  # Auto-detect
    output_sheet_name="Forecast"
)

# Option C: Step-by-step conversion
df_raw = converter.read_sap_ibp_data()  # Read raw data
df_long = converter.convert_to_long_format(df_raw)  # Transform

# Detect SAP IBP format
is_sap_ibp = SapIbpConverter.detect_sap_ibp_format("file.xlsx")
```

**Class Methods:**
- `detect_sap_ibp_format(file_path)`: Static method to detect SAP IBP format
- `find_data_sheet()`: Find data sheet in SAP IBP file
- `read_sap_ibp_data(sheet_name)`: Read raw SAP IBP data
- `parse_date_column(date_str)`: Parse SAP IBP date format (DD.MM.YYYY)
- `convert_to_long_format(df_raw)`: Transform wide to long format
- `convert(sheet_name)`: Full conversion pipeline
- `convert_and_save(output_path, sheet_name, output_sheet_name)`: Convert and save

### Conversion Details

**Date Format Handling:**
- SAP IBP uses `DD.MM.YYYY` format (e.g., "02.06.2025")
- Also supports ISO format `YYYY-MM-DD` and common date formats
- Invalid dates are automatically filtered out

**Column Mapping:**
- Product ID: Column 7 (Excel index, 0-indexed column 6)
- Location ID: Column 8 (Excel index, 0-indexed column 7)
- Date columns: Start at column 11 (0-indexed column 10)

**Data Cleaning:**
- Removes rows with missing location_id or product_id
- Filters out non-numeric quantities
- Removes invalid or unparseable dates
- Sorts by location_id, product_id, date for consistency

**Output Format:**
- Columns: `location_id`, `product_id`, `date`, `quantity`
- Types: string, string, date, float
- Long format: One row per location-product-date combination

### Example Conversion Results

**Input: Gfree Forecast.xlsm (SAP IBP format)**
- Sheet: "G610 RET"
- Raw size: 50 rows × 214 columns
- File size: 441 KB

**Output: Gfree Forecast_Converted.xlsx (Long format)**
- Sheet: "Forecast"
- Converted size: 9,180 rows × 4 columns
- File size: 224 KB
- Coverage: 9 locations × 5 products × 204 days

**Summary Statistics:**
- Locations: 6103, 6104, 6105, 6110, 6120, 6123, 6125, 6130, 6134
- Products: 168846, 168847, 168848, 179649, 179650
- Date range: June 2, 2025 to December 22, 2025 (204 days)

### Integration with MultiFileParser

After conversion, use the converted file with `MultiFileParser`:

```python
from src.parsers import SapIbpConverter, MultiFileParser

# Step 1: Convert SAP IBP file
converter = SapIbpConverter("Gfree Forecast.xlsm")
converter.convert_and_save("Forecast_Converted.xlsx")

# Step 2: Load with MultiFileParser
parser = MultiFileParser(
    forecast_file="Forecast_Converted.xlsx",  # Converted forecast
    network_file="Network_Config.xlsx"         # Network configuration
)

# Step 3: Parse and validate
forecast, locations, routes, labor, trucks, costs = parser.parse_all()
validation = parser.validate_consistency(forecast, locations, routes)

print(f"✅ Loaded {len(forecast.entries)} forecast entries")
```

### Troubleshooting

**Error: "Worksheet named 'Forecast' not found"**
- Cause: File is in SAP IBP format (wide layout)
- Solution: Use automatic conversion via UI or CLI tool

**Error: "No SAP IBP data sheet found"**
- Cause: File doesn't contain recognized SAP IBP sheets
- Solution: Specify sheet name manually with `--sheet` option

**Error: "No valid date columns found"**
- Cause: Date columns not in expected format
- Solution: Verify column headers use DD.MM.YYYY or YYYY-MM-DD format

**Warning: "File may not be in SAP IBP format"**
- Cause: Detection heuristic failed but file might be valid
- Action: Review file structure; continue conversion if confident

### See Also

- `SAP_IBP_FORMAT.md`: Detailed SAP IBP structure analysis
- `scripts/convert_sap_ibp.py`: Command-line conversion tool source code
- `src/parsers/sap_ibp_converter.py`: Converter class implementation
- `tests/test_sap_ibp_converter.py`: Conversion tests (16 tests)

---

## Next Steps

1. Use this specification to create example Excel files
2. Test with `ExcelParser` to ensure compatibility
3. Build UI upload feature using these formats
4. Create validation layer for data quality checks
5. For SAP IBP files: Use automatic conversion before loading
