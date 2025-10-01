# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Gluten-Free Bread Production-Distribution Planning Application**

This application provides integrated production scheduling and distribution planning for gluten-free bread from manufacturing through a multi-echelon network to breadroom destinations. It optimizes production timing, labor allocation, truck loading, and distribution routing while managing perishable inventory with complex shelf life rules across frozen and ambient modes.

**Primary Objective:** Minimize total cost to serve

### Business Domain

**Network Structure:**
- **Topology:** 2-echelon hub-and-spoke + frozen buffer design
- **Source:** Manufacturing site (Location ID: 6122)
- **Regional Hubs:** 6104 (NSW/ACT), 6125 (VIC/TAS/SA)
- **Intermediate Storage:** Lineage (external frozen facility for WA route)
- **Destinations:** 9 breadrooms across Australia
- **Routes:** 10 route legs (4 primary from manufacturing + 5 secondary from hubs + 1 frozen buffer)
- **Special Operation:** 6130 (WA) receives frozen, thaws on-site (shelf life resets to 14 days)

**Shelf Life Rules:**
- **Ambient storage:** 17 days shelf life
- **Frozen storage:** 120 days shelf life
- **Thawing:** Resets shelf life to 14 days (critical constraint!)
- **Breadroom policy:** Discards stock with less than 7 days remaining

**Manufacturing Operations (Location 6122):**

- **Labor Schedule:**
  - **Monday-Friday:** 12 hours fixed labor, max 2 hours overtime (14h total)
  - **Saturday-Sunday:** Overtime only, 4-hour minimum payment
  - **Public holidays:** Same as weekend rules (4h minimum, premium rate) - 13 in 2025, 14 in 2026
  - **Production rate:** 1,400 units/hour
  - **Daily capacity:** 16,800 units (regular), 19,600 units (with OT)
  - **Weekly capacity:** 84,000 units (regular), 98,000 units (with daily OT)
  - **Note:** Weekday public holidays (~8-10/year) reduce standard production days

- **Packaging Constraints:**
  - **Case:** 10 units (minimum shipping quantity - no partial cases allowed)
  - **Pallet:** 32 cases = 320 units per pallet
  - **Truck:** 44 pallets = 14,080 units per truck capacity
  - **Critical:** Partial pallets occupy full pallet space (e.g., 1 case = 1 pallet space)
  - **Optimization:** Target multiples of 320 units to maximize truck utilization

- **Truck Departure Schedule:**

  *Morning Truck (Daily Monday-Friday):*
  - **Standard route (Mon, Tue, Thu, Fri):** 6122 → 6125
  - **Wednesday special:** 6122 → Lineage → 6125 (drops frozen stock at Lineage)
  - Loads D-1 production (previous day's production)
  - Capacity: 14,080 units per truck

  *Afternoon Truck (Day-Specific Destinations):*
  - **Monday:** 6122 → 6104 (NSW/ACT hub)
  - **Tuesday:** 6122 → 6110 (QLD direct)
  - **Wednesday:** 6122 → 6104 (NSW/ACT hub)
  - **Thursday:** 6122 → 6110 (QLD direct)
  - **Friday:** TWO trucks: 6122 → 6110 AND 6122 → 6104 (double capacity)
  - Loads D-1 production; D0 (same-day) possible if ready before departure
  - Capacity: 14,080 units per truck (28,160 on Friday with two trucks)

  *Weekly Shipping Capacity:*
  - 11 truck departures per week
  - Maximum: 154,880 units/week
  - Destinations: 6125 (5x/week), 6104 (3x/week), 6110 (3x/week)

- **Hub Outbound Schedule:**
  - Trucks from hubs (6104, 6125) to spoke locations depart in the morning
  - Enables 2-day minimum transit: manufacturing → hub (day 1) → spoke (day 2)

- **Labor cost structure:**
  - **Weekday fixed hours (0-12h):** Regular rate
  - **Weekday overtime (12-14h):** Premium rate
  - **Weekend overtime:** Premium rate with 4-hour minimum payment
  - **Optimization goal:** Minimize overtime and weekend usage

See `data/examples/MANUFACTURING_SCHEDULE.md` for complete operational details including transit chains, capacity analysis, and optimization strategies

**Input Data:**
- Sales forecast by breadroom and date (Excel .xlsm format)
- Location definitions (manufacturing site, storage, breadrooms)
- Route definitions with transit times and transport modes
- Labor calendar with daily fixed hours and cost rates
- Truck schedules (morning/afternoon departure times and destinations)
- Cost parameters (labor rates, transport costs, holding costs, waste costs)

**Real-World Example:**
- **Gfree Forecast.xlsm** - SAP IBP export with 9 breadroom locations, 5 products, 204-day forecast
- Contains actual demand data for QBA (Quality Bakers Australia) breadrooms
- Manufacturing source: Location 6122
- Destinations: 9 breadrooms across Australia (NSW, VIC, QLD, ACT, TAS, WA, SA)
- Distribution network: Hub-and-spoke with 2 regional hubs (6104, 6125) plus special frozen route to WA via Lineage
- See `data/examples/SAP_IBP_FORMAT.md`, `data/examples/BREADROOM_LOCATIONS.md`, and `data/examples/NETWORK_ROUTES.md` for complete details

### Problem Complexity

This is an **integrated production-distribution planning problem for perishable goods** with multiple interacting decision layers:

**Production Layer:**
1. **Production scheduling:** Determine daily production quantities and timing
2. **Labor allocation:** Optimize use of fixed hours, overtime, and non-fixed labor days
3. **Batch timing:** Decide D-1 vs D0 production for afternoon truck loads
4. **Capacity management:** Balance production smoothing vs. cost minimization

**Distribution Layer:**
5. **Route selection:** Choose optimal paths through 2-echelon hub-and-spoke network
6. **Hub vs. direct shipping:** Utilize regional hubs (6104, 6125) or ship direct
7. **Mode selection:** Decide frozen vs ambient transport at each stage
8. **Truck loading:** Assign production batches to morning/afternoon trucks with hub destinations
9. **Timing optimization:** Determine when to thaw frozen inventory (critical for WA route at 6130)
10. **Inventory positioning:** Balance stock at hubs and Lineage frozen buffer

**Constraints:**
11. **Shelf life tracking:** Account for expiration and thawing state transitions (especially 6130: frozen→thawed 14 days)
12. **Demand satisfaction:** Meet breadroom forecasts with acceptable shelf life (≥7 days)
13. **Capacity constraints:** Production hours, truck capacity (44 pallets = 14,080 units), hub capacity, Lineage frozen storage capacity
14. **Temporal constraints:** Truck departure times, production lead times, hub transit times, day-specific truck routing
15. **Network structure:** Hub-and-spoke routing, frozen buffer for WA, Wednesday Lineage routing
16. **Discrete packaging:** All quantities in 10-unit increments (cases), partial pallets waste truck space (integer pallet optimization)

**Objective:**
Minimize total cost to serve = labor costs + transport costs + storage costs + waste costs

## Development Approach

### Design Philosophy
Start with a basic model and gradually increase complexity. Begin with a simple Streamlit interface that evolves with the application.

### Development Phases

**Phase 1: Foundation (MVP) ✅ COMPLETE**

*Status: All core functionality implemented and tested (41 tests passing)*

**Completed Features:**
- ✅ Data models: Location, Route, Product, Forecast, ManufacturingSite, TruckSchedule, LaborCalendar, LaborDay, ProductionBatch, CostStructure
- ✅ Excel parser with full support for all 6 sheet types (Forecast, Locations, Routes, LaborCalendar, TruckSchedules, CostParameters)
- ✅ Day-specific truck scheduling support (Monday-Friday afternoon routing)
- ✅ Intermediate stop handling (Wednesday Lineage route)
- ✅ Packaging constraint models (10 units/case, 320 units/pallet, 44 pallets/truck)
- ✅ Labor cost calculation methods (fixed hours, overtime, non-fixed days with 4h minimum)
- ✅ Production capacity and labor hours calculation methods
- ✅ Basic Streamlit UI for data upload and visualization
- ✅ Comprehensive documentation:
  - `EXCEL_TEMPLATE_SPEC.md` - Complete input format specification
  - `MANUFACTURING_SCHEDULE.md` - Operational details with public holidays
  - `NETWORK_ROUTES.md` - Complete route topology
  - `BREADROOM_LOCATIONS.md` - Location reference with demand breakdown
  - `SAP_IBP_FORMAT.md` - Real-world data format analysis
- ✅ Test coverage: 41 tests covering all core models and parsers

**Phase 1 Deliverables:**
- Fully functional data ingestion pipeline from Excel
- Complete manufacturing operations modeling (labor, production, trucks, packaging)
- Validated data models with business rule enforcement
- Comprehensive documentation for users and developers

**Phase 2: Core Logic**
- Production feasibility checking (labor hours, capacity constraints)
- Shelf life calculation engine with state transitions
- Truck loading logic with D-1/D0 production assignment
- Labor cost calculations (fixed hours, overtime, non-fixed days)
- Route enumeration and feasibility analysis
- Rule-based production and routing recommendations
- Interactive route and production schedule visualization

**Phase 3: Optimization**
- Integrated production-distribution mathematical model (Pyomo)
- Decision variables: production quantities/timing, truck assignments, inventory flows
- Constraints: labor capacity, truck capacity, shelf life, demand satisfaction
- Objective: minimize total cost to serve (labor + transport + storage + waste)
- Solver integration (CBC for prototyping, Gurobi for production)
- Two-stage optimization: production scheduling → distribution routing (fixed trucks)
- Enhanced UI with cost breakdowns and comparison scenarios

**Phase 4: Advanced Features**
- Flexible truck routing (destinations optimized, not fixed)
- Multi-period rolling horizon planning with production smoothing
- Stochastic demand scenarios with robust optimization
- Labor scheduling optimization across planning horizon
- Sensitivity analysis and what-if scenarios
- Production campaign optimization (batch sizing)
- Advanced reporting and cost attribution dashboards

## Technology Stack

- **Python 3.11+** - Core programming language
- **Streamlit** - Web interface and dashboards
- **Pandas** - Data manipulation and Excel I/O
- **NetworkX** - Graph/network modeling and algorithms
- **Pyomo** - Mathematical optimization modeling (Phase 3+)
- **Plotly** - Interactive visualizations
- **Openpyxl** - Excel file handling (.xlsm support)
- **Pytest** - Testing framework

## Project Structure

```
planning_latest/
├── src/
│   ├── models/          # Data models (Location, Route, Product, Forecast,
│   │                    #              ManufacturingSite, TruckSchedule, LaborCalendar,
│   │                    #              ProductionBatch, CostStructure)
│   ├── parsers/         # Excel input parsing (forecast, locations, routes,
│   │                    #                      labor, trucks, costs)
│   ├── production/      # Production scheduling and labor cost logic
│   ├── network/         # Network/graph operations and algorithms
│   ├── optimization/    # Optimization models (Phase 3+)
│   ├── shelf_life/      # Shelf life calculation engine
│   └── utils/           # Helper functions and utilities
├── ui/
│   ├── app.py           # Main Streamlit application
│   └── components/      # Reusable UI components
├── tests/
│   ├── test_models.py
│   ├── test_parsers.py
│   ├── test_production.py
│   ├── test_network.py
│   └── ...
├── data/
│   └── examples/        # Sample forecast files and test data
├── requirements.txt     # Python dependencies
├── README.md           # Getting started guide
└── CLAUDE.md           # This file
```

## Getting Started

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Start Streamlit UI
streamlit run ui/app.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/
```

## Key Design Decisions

1. **Integrated production-distribution model:** Couple production scheduling with distribution to capture interdependencies and cost trade-offs
2. **Graph-based network representation:** Use NetworkX for flexible route modeling and shortest path algorithms
3. **State machine for shelf life:** Track product state (frozen/ambient/thawed) and transitions
4. **Tiered labor cost model:** Explicit modeling of fixed hours, overtime, and non-fixed labor days with different cost rates
5. **Truck scheduling as constraint:** Morning/afternoon trucks with fixed departure times; destinations initially fixed (Phase 1-2), later flexible (Phase 3-4)
6. **Incremental complexity:** Start with feasibility checking and cost calculation before full optimization
7. **Separation of concerns:** Clear boundaries between data models (src/models/), production logic (src/production/), network operations (src/network/), and optimization (src/optimization/)
8. **Excel as input format:** Maintain compatibility with existing workflows; comprehensive input covering forecast, network, labor, trucks, and costs
9. **Cost-centric objective:** Minimize total cost to serve (not just waste); enables business-driven trade-off decisions

## Development Workflow

1. Always write tests for new functionality
2. Use type hints throughout the codebase
3. Keep UI and business logic separate
4. Document complex algorithms and business rules
5. Version control Excel file format specifications

## Cost Components

The objective function minimizes **total cost to serve**, comprising:

1. **Labor Costs:**
   - Fixed labor hours: Regular rate × fixed hours allocated
   - Overtime hours: Premium rate × (actual hours - fixed hours) when actual > fixed
   - Non-fixed labor days: Increased rate × max(actual hours, minimum hours commitment)
   - Cost varies by day based on labor calendar

2. **Production Costs:**
   - Direct production costs per unit
   - Setup costs if batch production is implemented (Phase 4)
   - Possible economies of scale

3. **Transport Costs:**
   - Cost per unit per route leg
   - May vary by transport mode (frozen typically more expensive than ambient)
   - Truck fixed costs vs. variable costs

4. **Storage/Holding Costs:**
   - Cost per unit per day at intermediate storage locations
   - May differ between frozen and ambient storage
   - Incentive to minimize inventory holding

5. **Waste Costs:**
   - Cost of discarded product (expired or insufficient shelf life)
   - Includes production cost + transport cost incurred to that point
   - High penalty to incentivize meeting demand with acceptable shelf life

## Data Format Considerations

### Input Format Flexibility

The application parser expects a **simplified multi-sheet format** for ease of use and testing. However, real-world data often comes in different formats:

**Application Expected Format:**
- 6 sheets: Forecast, Locations, Routes, LaborCalendar, TruckSchedules, CostParameters
- Long format for forecasts (one row per location-product-date combination)
- Simple column structure with clear headers

**Real-World Format (SAP IBP):**
- Export format from SAP Integrated Business Planning system
- Wide format with dates as columns
- Embedded metadata and filters
- Requires preprocessing/transformation

**Future Enhancement (Phase 2-3):**
- Build format converter for SAP IBP exports
- Add `parse_sap_ibp()` method to ExcelParser
- Support multiple input formats with auto-detection
- Provide data validation and transformation utilities

## Future Considerations

- Database backend for historical data and results
- API layer for integration with other systems
- Real-time data feeds from manufacturing and logistics
- Machine learning for demand forecasting improvements
- Mobile-friendly interface for warehouse operations
- SAP IBP integration and automated data sync
- Format converters for other planning systems (Oracle, Kinaxis, etc.)
