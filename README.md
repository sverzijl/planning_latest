# Gluten-Free Bread Production-Distribution Planning

![Tests](https://github.com/USER/REPO/workflows/Tests/badge.svg)
![Coverage](https://github.com/USER/REPO/workflows/Coverage/badge.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

An integrated production scheduling and distribution optimization application for gluten-free bread, from manufacturing through multi-echelon frozen and ambient transport networks to breadrooms.

## Overview

This application optimizes end-to-end operations for perishable gluten-free bread by:
- **Production scheduling:** Determining optimal daily production quantities and timing
- **Labor optimization:** Managing fixed hours, overtime, and non-fixed labor days to minimize costs
- **Truck loading:** Assigning production batches to morning and afternoon trucks
- **Route planning:** Modeling multi-step distribution routes (frozen/ambient)
- **Shelf life management:** Tracking state transitions (thawing resets from 120 days to 14 days)
- **Cost minimization:** Minimizing total cost to serve (labor + transport + storage + waste)

## Key Features

### Current (Phase 1 - MVP)
- 📊 Excel data upload (.xlsm format: forecast, locations, routes, labor, trucks, costs)
- 🏗️ Network modeling with graph structures
- 🏭 Production and manufacturing site modeling
- 📦 Location and route management
- 🚚 Truck schedule management (morning/afternoon departures)
- 💼 Labor calendar with cost structure
- 🌡️ Shelf life tracking (ambient: 17 days, frozen: 120 days, thawed: 14 days)

### Planned
- **Phase 2:** Production feasibility, labor cost calculation, truck loading logic, shelf life engine, route visualization
- **Phase 3:** Integrated production-distribution optimization with cost minimization and solver integration
- **Phase 4:** Flexible truck routing, multi-period planning, stochastic scenarios, production smoothing

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd planning_latest
```

2. Create and activate a virtual environment:
```bash
python -m venv venv

# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application

Start the Streamlit web interface:
```bash
streamlit run ui/app.py
```

The application will open in your browser at `http://localhost:8501`

### Quick Start: Two-File Workflow

The recommended workflow uses separate files for forecast and network configuration:

```python
from src.parsers import MultiFileParser

# Load forecast and network configuration
parser = MultiFileParser(
    forecast_file="data/examples/your_forecast.xlsx",  # Your forecast file
    network_file="data/examples/Network_Config.xlsx"   # Provided template
)

# Parse all data
forecast, locations, routes, labor, trucks, costs = parser.parse_all()

# Validate consistency
validation = parser.validate_consistency(forecast, locations, routes)
print(f"Loaded {len(forecast.entries)} forecast entries for {len(locations)} locations")
```

Alternatively, upload both files through the Streamlit UI (Upload Data page).

### SAP IBP Forecast Conversion

If your forecast data is in **SAP Integrated Business Planning (IBP)** export format (wide format with dates as columns), you can convert it to the required long format:

**Option 1: Streamlit UI (Automatic Detection)**
1. Upload your SAP IBP file to the Upload Data page
2. The application automatically detects SAP IBP format
3. Click "🔄 Convert SAP IBP to Long Format" button
4. Preview converted data and download the result

**Option 2: Command-Line Tool**
```bash
# Convert with default output name (input_file_Converted.xlsx)
python scripts/convert_sap_ibp.py "data/Gfree Forecast.xlsm"

# Convert with custom output name
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" "Forecast_Long.xlsx"

# Verbose mode with detailed output
python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" -v
```

**Option 3: Python API**
```python
from src.parsers import SapIbpConverter

# Convert SAP IBP file
converter = SapIbpConverter("data/Gfree Forecast.xlsm")
df_forecast = converter.convert()

# Save to Excel
converter.convert_and_save("Forecast_Converted.xlsx")

# Result: 9,180 entries (9 locations × 5 products × 204 days)
```

See `data/examples/SAP_IBP_FORMAT.md` for details on SAP IBP format structure.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src tests/

# Run specific test file
pytest tests/test_models.py

# Run labor validation integration tests
pytest tests/test_labor_validation_integration.py -v

# Run labor calendar validation tests
pytest tests/test_integrated_model.py::TestLaborCalendarValidation -v

# Run with verbose output and stop on first 5 failures
pytest tests/ -v --tb=short --maxfail=5

# Run tests with detailed coverage report
pytest --cov=src --cov-report=html --cov-report=term
# Then open htmlcov/index.html in browser
```

**Test Coverage:** 661 tests covering all core models, parsers, multi-file workflow, SAP IBP conversion, labor validation, and integrated optimization

#### ⚠️ CRITICAL: Integration Test (Required for Model Changes)

**Before committing ANY changes to optimization model or solver code, you MUST run the integration test:**

```bash
# Required validation gate for optimization changes
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
```

This test validates the complete UI workflow with real production data and ensures:
- ✓ Solve time < 30 seconds (4-week horizon with 17,760 forecast entries)
- ✓ Solution quality: 95%+ demand satisfaction, optimal status
- ✓ UI compatibility: Matches Planning Tab settings exactly
- ✓ No performance regressions or infeasibilities

**The test MUST pass before committing changes to:**
- `src/optimization/` (model formulation, constraints, objective)
- Solver parameters or performance optimizations
- Constraint logic or decision variables
- Route enumeration or batch tracking code

See `tests/test_integration_ui_workflow.py` for detailed documentation and `CLAUDE.md` for complete testing requirements.

### Continuous Integration

This project uses GitHub Actions for continuous integration:

- **Tests Workflow:** Runs all tests on Python 3.11 and 3.12
- **Coverage Workflow:** Generates coverage reports and uploads to Codecov
- **Pre-commit Hooks:** Optional local testing before commits

To enable pre-commit hooks:
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Manually run hooks on all files
pre-commit run --all-files
```

### Code Quality

```bash
# Format code
black src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/

# Type checking
mypy src/
```

## Troubleshooting

### ModuleNotFoundError: No module named 'ui'

**Problem:** When running the Streamlit app, you get:
```
ModuleNotFoundError: No module named 'ui'
Traceback:
File ".../ui/app.py", line X, in <module>
    from ui import session_state
```

**Root Cause:** The application uses absolute imports (`from ui import ...`) which require the project root directory to be in Python's path. This error occurs when:
1. Running from the wrong directory
2. Python path doesn't include the project root
3. Working directory is not set correctly

**Solution 1: Run from Correct Directory (Recommended)**

Always run Streamlit from the **project root directory** (`planning_latest/`):

```bash
# Navigate to project root
cd planning_latest

# Run Streamlit (NOT from ui/ directory!)
streamlit run ui/app.py
```

**Solution 2: Check Working Directory**

Verify you're in the correct directory:
```bash
# On Linux/Mac
pwd
# Should show: .../planning_latest

# On Windows
cd
# Should show: ...\planning_latest
```

If you're in the wrong directory (e.g., `planning_latest/ui/`), navigate up one level:
```bash
cd ..
streamlit run ui/app.py
```

**Solution 3: Windows WinPython Users**

If using WinPython portable distribution:
1. Open WinPython Command Prompt (not regular Command Prompt)
2. Navigate to project root: `cd C:\path\to\planning_latest`
3. Activate virtual environment: `venv\Scripts\activate`
4. Run: `streamlit run ui/app.py`

**Solution 4: Verify Python Path Setup**

The application automatically adds the project root to `sys.path`. If you still see errors:
1. Check the path in error message - look for duplicate directories (e.g., `planning_latest\planning_latest`)
2. Ensure project isn't nested incorrectly
3. Try: `python -c "import sys; print(sys.path)"` to debug

**Note:** The application includes automatic path setup in all UI files (added in v2.1), so this error should be resolved. If it persists, please report the issue with your environment details.

### Other Common Issues

**Streamlit Not Found:**
```bash
# Install/reinstall requirements
pip install -r requirements.txt
```

**Excel File Read Errors:**
```bash
# Install openpyxl for .xlsx/.xlsm files
pip install openpyxl
```

**Graph Visualization Issues:**
```bash
# Ensure NetworkX and Plotly are installed
pip install networkx plotly
```

## Project Structure

```
planning_latest/
├── src/                    # Core application logic
│   ├── models/            # Data models (Location, Route, Product)
│   ├── parsers/           # Excel input parsing
│   ├── network/           # Network/graph operations
│   ├── optimization/      # Optimization models (Phase 3+)
│   ├── shelf_life/        # Shelf life calculation engine
│   └── utils/             # Helper functions
├── ui/                     # Streamlit web interface
│   ├── app.py             # Main application
│   └── components/        # UI components
├── tests/                  # Unit and integration tests
├── data/
│   └── examples/          # Sample forecast files
├── .github/
│   └── workflows/         # CI/CD workflows
│       ├── tests.yml      # Test automation
│       └── coverage.yml   # Coverage reporting
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── CLAUDE.md              # Development guidelines
```

## Business Rules

### Manufacturing Operations

**Labor Schedule (Location 6122):**
- **Monday-Friday:** 12 hours fixed labor + max 2 hours overtime (14h total)
- **Saturday-Sunday:** Overtime available with 4-hour minimum payment
- **Public holidays:** Same as weekend rules (4h minimum, premium rate) - 13 days in 2025, 14 in 2026
- **Production rate:** 1,400 units/hour
- **Daily capacity:** 16,800 units (regular), 19,600 units (with OT)

**Packaging Structure:**
- **Case:** 10 units (minimum shipping quantity - no partial cases)
- **Pallet:** 32 cases = 320 units per pallet
- **Truck:** 44 pallets = 14,080 units per truck
- **Critical:** Partial pallets occupy full pallet space

**Truck Departure Schedule:**

*Morning Truck (Daily M-F):*
- **Mon, Tue, Thu, Fri:** 6122 → 6125 (VIC/TAS/SA hub)
- **Wednesday:** 6122 → Lineage (frozen drop) → 6125
- Loads D-1 production (previous day)

*Afternoon Truck (Day-specific):*
- **Monday:** 6122 → 6104 (NSW/ACT hub)
- **Tuesday:** 6122 → 6110 (QLD direct)
- **Wednesday:** 6122 → 6104 (NSW/ACT hub)
- **Thursday:** 6122 → 6110 (QLD direct)
- **Friday:** TWO trucks → 6110 AND 6104
- Loads D-1 production (D0 possible if ready)

*Weekly Capacity:* 11 trucks/week × 14,080 units = 154,880 units

**Hub Outbound:** Trucks from hubs (6104, 6125) to spoke locations depart in the morning

**Labor Cost Structure:**
- **Weekday fixed hours (0-12h):** Regular rate
- **Weekday overtime (12-14h):** Premium rate
- **Weekend overtime:** Premium rate with 4-hour minimum payment

See `data/examples/MANUFACTURING_SCHEDULE.md` for complete operational details

### Shelf Life
- **Ambient storage:** 17 days
- **Frozen storage:** 120 days
- **Thawed product:** 14 days (reset after thawing)
- **Breadroom policy:** Discards stock with <7 days remaining

### Distribution Network

**Topology:** 2-Echelon Hub-and-Spoke + Frozen Buffer

**Manufacturing Site:** Location ID 6122

**Regional Hubs (with dual role as local breadrooms):**
- **6104 (Moorebank, NSW):** Hub + local breadroom serving NSW & ACT region
  - Forwards to: 6105 (Rydalmere), 6103 (Canberra)
  - Hub region demand: 849,841 units (6104: 432,595 + spoke locations: 417,246)
- **6125 (Keilor Park, VIC):** Hub + local breadroom serving VIC/TAS/SA region
  - Forwards to: 6123 (Clayton), 6134 (Adelaide), 6120 (Hobart)
  - Hub region demand: 903,996 units (6125: 258,739 + spoke locations: 645,257)

**Critical:** Each location has an independent demand forecast. Hub forecasts represent ONLY local market demand, NOT spoke location demand. Product at hubs must be allocated between local fulfillment and forwarding to spoke locations.

**Direct Routes:**
- **6110 (Burleigh Heads, QLD):** Direct from manufacturing

**Special Frozen Route:**
- **6122 → Lineage (frozen storage) → 6130 (Canning Vale, WA)**
- Product thawed at 6130 destination (shelf life resets to 14 days)
- 6130 acts as thawing facility + storage + market release for WA

**Network Statistics:**
- 10 route legs total (4 primary + 5 secondary + 1 frozen buffer)
- 11 total nodes (1 manufacturing + 2 hubs + 1 frozen storage + 9 breadrooms)
- Hub consolidation serves 5 of 9 breadrooms (56%)

See `data/examples/NETWORK_ROUTES.md` for complete route details

### Cost Objective
**Minimize total cost to serve:**
- Labor costs (fixed hours + overtime + non-fixed days)
- Production costs
- Transport costs
- Storage/holding costs
- Waste costs (expired or insufficient shelf life)

## Input Data Format

The application expects an Excel file (.xlsm) containing the following sheets:

### Required Sheets

1. **Forecast** - Sales demand by location and date
   - Columns: `location_id`, `product_id`, `date`, `quantity`, `confidence` (optional)

2. **Locations** - Network nodes (manufacturing, storage, breadrooms)
   - Columns: `id`, `name`, `type`, `storage_mode`, `capacity` (optional), `latitude` (optional), `longitude` (optional)

3. **Routes** - Transport connections between locations
   - Columns: `id`, `origin_id`, `destination_id`, `transport_mode`, `transit_time_days`, `cost` (optional), `capacity` (optional)

4. **LaborCalendar** - Daily labor availability and costs
   - Columns: `date`, `fixed_hours`, `regular_rate`, `overtime_rate`, `non_fixed_rate`, `minimum_hours` (for non-fixed days)

5. **TruckSchedules** - Morning and afternoon truck departure times
   - Columns: `truck_id`, `departure_type` (morning/afternoon), `departure_time`, `destination_id` (for fixed routing), `capacity`

6. **CostParameters** - Cost coefficients
   - Columns: `cost_type`, `value`, `unit` (e.g., production_cost_per_unit, holding_cost_per_unit_per_day, waste_cost_multiplier)

### Example Data Files

The `data/examples/` directory contains:

1. **EXCEL_TEMPLATE_SPEC.md** - Excel file format specification ⭐ **START HERE**
   - Complete column-by-column specification for all 6 sheets
   - Required vs. optional fields with examples
   - **Multi-file workflow** (recommended): separate forecast and network config files
   - Validation rules and common errors
   - Minimal working example structure

1.5. **Network_Config.xlsx** - Network configuration template file ⭐ **NEW**
   - 11 locations, 10 routes, 204-day labor calendar, 11 truck schedules, 12 cost parameters
   - Ready to use with MultiFileParser
   - Use with forecast files for two-file workflow
   - Update for your specific network structure

2. **MANUFACTURING_SCHEDULE.md** - Manufacturing operations reference
   - Complete labor schedule (12h M-F + OT, weekends, 2025/2026 public holidays)
   - Production capacity (1,400 units/hour)
   - Weekly truck schedule (11 trucks/week, day-specific routing)
   - Packaging constraints (10 units/case, 320 units/pallet, 44 pallets/truck)
   - Capacity analysis and optimization strategies

3. **NETWORK_ROUTES.md** - Complete route topology
   - 2-echelon hub-and-spoke network structure
   - All 10 route legs documented
   - Hub assignments (6104 NSW/ACT, 6125 VIC/TAS/SA)
   - Special frozen route: 6122 → Lineage → 6130 with thawing
   - Truck departure schedules and capacity analysis

4. **BREADROOM_LOCATIONS.md** - Breadroom reference & network topology
   - Complete list of 9 breadroom destinations
   - Hub assignments and dual-role explanation
   - Geographic distribution across Australian states
   - Independent demand forecasts (critical: hub forecasts ≠ spoke forecasts)
   - Demand breakdown table with totals

5. **SAP_IBP_FORMAT.md** - SAP IBP export format analysis
   - Detailed analysis of SAP IBP export structure
   - Product and location mappings with demand totals
   - Conversion requirements for application use
   - Differences from application template format

6. **Gfree Forecast.xlsm** - Real-world SAP IBP forecast export
   - Format: SAP Integrated Business Planning (IBP) wide format
   - Contains: 9 breadroom locations, 5 products, 204 days of forecast (Jun 2 - Dec 22, 2025)
   - **Conversion:** Automatically converted by UI or use `python scripts/convert_sap_ibp.py`
   - See `SAP_IBP_FORMAT.md` for format details and conversion process

7. **Gfree Forecast_Converted.xlsx** - Converted forecast in application format
   - Pre-converted version of `Gfree Forecast.xlsm` in long format
   - Ready to use directly with `MultiFileParser` or Streamlit UI
   - 9,180 forecast entries (9 locations × 5 products × 204 days)

**Breadroom Destinations (from Gfree Forecast.xlsm):**
- 6103 - QBA-Canberra (ACT)
- 6104 - QBA-Moorebank (NSW)
- 6105 - QBA-Rydalmere (NSW)
- 6110 - QBA-Burleigh Heads (QLD)
- 6120 - QBA-Hobart (TAS)
- 6123 - QBA-Clayton - Fairbank (VIC)
- 6125 - QBA-Keilor Park (VIC)
- 6130 - QBA-Canning Vale (WA)
- 6134 - QBA-West Richmond SA (SA)

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines, architecture decisions, and phased implementation plan.

### Development Phases

1. **Phase 1 (Current):** Foundation - data models, parsers, basic UI
2. **Phase 2:** Core logic - shelf life engine, route analysis
3. **Phase 3:** Optimization - mathematical models, solvers
4. **Phase 4:** Advanced - multi-period planning, scenarios

## Contributing

1. Write tests for new functionality
2. Use type hints throughout
3. Follow PEP 8 style guidelines (enforced by black/flake8)
4. Keep UI and business logic separate
5. Document complex algorithms
6. **Run integration test for optimization changes** (see below)
7. Ensure all tests pass before submitting PR

### Pull Request Process

1. Fork the repository and create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. **REQUIRED: If changing optimization code, run integration test:**
   ```bash
   venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
   ```
   This test MUST pass for any changes to `src/optimization/` before PR submission.
5. Run code quality checks: `black src/ tests/ ui/` and `flake8 src/ tests/ ui/`
6. Update documentation as needed
7. Submit pull request with clear description

**Note:** PRs that modify optimization code without passing the integration test will not be merged.

## License

TBD

## Contact

TBD
