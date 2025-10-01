# Gluten-Free Bread Production-Distribution Planning

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

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src tests/

# Run specific test file
pytest tests/test_models.py
```

**Test Coverage:** 41 tests covering all core models and parsers

### Code Quality

```bash
# Format code
black src/ tests/ ui/

# Lint code
flake8 src/ tests/ ui/

# Type checking
mypy src/
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
   - Validation rules and common errors
   - Minimal working example structure

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
   - **Note:** This is in SAP IBP format and requires preprocessing before use with the application parser
   - See `SAP_IBP_FORMAT.md` and `EXCEL_TEMPLATE_SPEC.md` for conversion details

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

## License

TBD

## Contact

TBD
