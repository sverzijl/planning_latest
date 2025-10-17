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
  - **Critical:** Partial pallets occupy full pallet space (e.g., 1 case = 1 pallet space, 50 units = 1 pallet space)
  - **Optimization Implementation:**
    - **Holding costs:** ✅ Integer `pallet_count` variables enforce ceiling rounding for storage
    - **Truck loading:** ⚠️ Uses continuous units (pallet-level deferred to Phase 4 due to performance)
    - **Ceiling constraint:** `pallet_count * 320 >= quantity` drives pallet count to minimum
    - **Business accuracy:** Ensures 50 units in storage costs as 1 pallet, not 0.156 pallets
    - **Truck approximation:** 50 units allowed in truck (costs as 0.156 pallets - acceptable for capacity)
  - **Target:** Multiples of 320 units maximize truck and storage utilization

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

**Phase 2: Core Logic** ✅ **DEPRECATED**
- **Status**: Replaced by Phase 3 mathematical optimization
- Heuristic rule-based planning approach (no longer used)
- Code removed in unified-model-only cleanup (2025-10-16)

**Phase 3: Optimization** ✅ **COMPLETE - PRIMARY APPROACH**

*Status: UnifiedNodeModel is the sole optimization approach*

**Completed Features:**
- ✅ **UnifiedNodeModel** (unified_node_model.py) - Clean node-based architecture
  - No virtual locations (eliminated 6122/6122_Storage bug)
  - Generalized truck constraints (works for any node, not just manufacturing)
  - Proper weekend enforcement (no weekend hub inventory bug)
  - Unified inventory balance equation (works for all node types)
- ✅ Decision variables: production[node, date, product], inventory_cohort[node, product, prod_date, curr_date, state], shipment_cohort[route, product, prod_date, delivery_date, state]
- ✅ Constraints: labor capacity, production capacity, unified inventory balance, demand satisfaction, truck scheduling (pallet-level), shelf life
- ✅ Objective: minimize total cost (labor + production + transport + **holding** + shortage penalty)
- ✅ **Pallet-based holding costs** (2025-10-17) - Integer pallet_count variables with ceiling constraints enforce storage pallet granularity
- ✅ Solver integration with CBC 2.10.12 compatibility (CBC, GLPK, Gurobi, CPLEX)
- ✅ Cross-platform support (Linux, macOS, Windows)
- ✅ Batch tracking with age-cohort inventory (use_batch_tracking parameter)
- ✅ Soft constraints for demand shortages (allow_shortages parameter)
- ✅ Shelf life enforcement (enforce_shelf_life parameter)
- ✅ Multi-echelon hub-and-spoke network with state transitions
- ✅ Planning horizon management with transit time extension
- ✅ Full-featured optimization UI (solver detection, configuration, results)
- ✅ Cost breakdown visualization and solution analysis
- ✅ Daily inventory snapshot feature - Interactive daily view of:
  - Inventory at each location with batch-level detail and age tracking
  - In-transit shipments with origin/destination/ETA
  - Manufacturing activity (production on selected date)
  - Inflows/outflows (production, arrivals, departures, demand)
  - Demand satisfaction tracking with fill rate calculation
- ✅ Complete documentation and solver installation guide
- ✅ 7 core tests validating UnifiedNodeModel + 42 supporting tests

**Phase 3 Deliverables:**
- Proven optimal solutions minimizing total cost to serve
- 100% demand satisfaction with proper planning horizons
- **Performance:** 4-week horizon in ~35-45s (with pallet-based holding costs enabled - default)
- **Performance:** 4-week horizon in ~20s (with holding costs disabled via zero storage rates)
- **Performance:** Truck pallet-level loading attempted but deferred (CBC could not solve in <300s)
- Shortage penalty option for infeasible demand scenarios
- Clean architecture eliminating legacy bugs
- Interactive UI for optimization configuration and results
- Pallet-based holding costs with ceiling rounding for accurate storage cost representation

**Phase 4: Advanced Features**
- **Pallet-level truck loading constraints** (OPEN INVESTIGATION) - Integer truck_pallet_load variables for pallet-granular capacity
  - Only 9% more integer variables (1,759) vs inventory pallets, but causes Gap=100% after 195s
  - Attempted fixes: removed per-variable bounds, validated constraint formulation
  - Root cause unknown: Not just variable count (9% shouldn't break solver)
  - Hypotheses: Constraint coupling with shipments, weak LP relaxation, feasibility bottleneck
  - Current: Truck capacity uses continuous units (acceptable approximation)
  - Future: Deeper investigation needed OR commercial solver (Gurobi/CPLEX)
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
│   │                    #              ProductionBatch, ProductionSchedule, TruckLoad,
│   │                    #              ManufacturingSite, TruckSchedule, LaborCalendar)
│   ├── parsers/         # Excel input parsing (forecast, locations, routes,
│   │                    #                      labor, trucks, costs, inventory)
│   ├── optimization/    # UnifiedNodeModel (primary optimization model)
│   ├── network/         # Network/graph operations (route visualization)
│   ├── analysis/        # Daily snapshots, flow analysis, labeling reports
│   ├── costs/           # Cost calculation utilities
│   ├── shelf_life/      # Shelf life calculation engine
│   ├── validation/      # Data validation utilities
│   ├── scenario/        # Scenario management
│   └── exporters/       # Result export utilities
├── ui/
│   ├── app.py           # Main Streamlit application
│   ├── pages/           # Page modules (Data, Planning, Results, Network, Settings)
│   ├── components/      # Reusable UI components
│   └── utils/           # UI utilities (result adapters, session state)
├── tests/
│   ├── test_integration_ui_workflow.py  # CRITICAL regression gate
│   ├── test_baseline_*.py               # Baseline validation tests
│   ├── test_unified_*.py                # UnifiedNodeModel tests
│   ├── test_models.py                   # Core data model tests
│   ├── test_parsers.py                  # Excel parsing tests
│   ├── test_daily_snapshot*.py          # Daily snapshot tests
│   └── ...
├── archive/
│   └── debug_scripts/   # 235 archived troubleshooting scripts
├── docs/
│   └── features/        # Feature-specific documentation
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

1. **UnifiedNodeModel architecture:** Clean node-based design with no virtual locations, generalized constraints, proper weekend enforcement
2. **Integrated production-distribution optimization:** Couple production scheduling with distribution to capture interdependencies and cost trade-offs
3. **Age-cohort batch tracking:** Track inventory by production date and state for accurate shelf life management
4. **State machine for shelf life:** Track product state (frozen/ambient/thawed) and automatic transitions
5. **Tiered labor cost model:** Explicit modeling of fixed hours, overtime, and non-fixed labor days with different cost rates
6. **Generalized truck constraints:** Work for any node (not just manufacturing), day-of-week enforcement, intermediate stops
7. **Mathematical optimization first:** Proven optimal solutions via Pyomo/CBC (heuristics deprecated)
8. **Separation of concerns:** Clear boundaries between data models (src/models/), optimization (src/optimization/), UI (ui/), and analysis (src/analysis/)
9. **Excel as input format:** Maintain compatibility with existing workflows; comprehensive input covering forecast, network, labor, trucks, costs, inventory
10. **Cost-centric objective:** Minimize total cost to serve (not just waste); enables business-driven trade-off decisions
11. **Pallet-level granularity:** (2025-10-17) Integer pallet variables for storage enforce "partial pallets occupy full pallet space" rule. Truck pallet-level enforcement deferred (causes unexpected solver difficulty despite small variable count increase).

**Recent Updates:**
- **2025-10-17:** Added pallet-based holding costs with ceiling constraint enforcement
  - Storage: Integer `pallet_count` variables (18,675 for 4-week horizon) - ✅ **IMPLEMENTED**
  - Enforces: 50 units in storage = 1 pallet cost (not 0.156 pallets)
  - Performance impact: ~2x solve time (20s → 35-45s for 4-week horizon)
  - Truck pallet-level loading: **DEFERRED to Phase 4** (makes MIP intractable - Gap=100% after 300s)
  - Current truck loading: Uses continuous units (acceptable approximation for capacity)
- **2025-10-16:** Removed legacy IntegratedProductionDistributionModel (replaced by UnifiedNodeModel)
- **2025-10-16:** Removed heuristic/Phase 2 code (replaced by mathematical optimization)
- **2025-10-16:** Archived 235 troubleshooting scripts to archive/debug_scripts/
- **2025-10-16:** Reduced codebase by ~28,000 lines while maintaining all functionality

## Development Workflow

1. Always write tests for new functionality
2. Use type hints throughout the codebase
3. Keep UI and business logic separate
4. Document complex algorithms and business rules
5. Version control Excel file format specifications
6. **Run integration tests before committing changes to model or optimization code**

### Testing Requirements

#### Integration Test Validation (REQUIRED)

**All changes to the optimization model or solver code MUST pass the UI workflow integration test before being committed.**

Run the integration test:
```bash
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
```

This test validates:
- **UI workflow compatibility**: Matches exact UI settings (4-week horizon, 1% MIP gap, batch tracking enabled)
- **Real data files**: Uses actual forecast (GFree Forecast.xlsm) and network configuration (Network_Config.xlsx)
- **Performance requirements**: Solve time < 30 seconds for 4-week horizon
- **Solution quality**: Fill rate ≥ 95%, optimal solution with < 1% gap
- **Feature correctness**: Batch tracking, shelf life enforcement, demand satisfaction

**When to run this test:**
- Before committing any changes to `src/optimization/`
- After modifying constraint formulations or objective functions
- When updating solver parameters or performance optimizations
- After adding new decision variables or constraints
- Before merging feature branches affecting the optimization model

**Test Configuration:**
The integration test mirrors the UI Planning Tab settings:
- Allow Demand Shortages: True
- Enforce Shelf Life Constraints: True
- Enable Batch Tracking: True (age-cohort tracking)
- MIP Gap Tolerance: 1%
- Planning Horizon: 4 weeks from start date
- Solver: CBC (or any available solver)
- Time Limit: 120 seconds (expected solve time: <30s)

**Expected Results:**
- Status: OPTIMAL or FEASIBLE
- Solve time: < 30 seconds
- Fill rate: ≥ 95%
- MIP Gap: < 1%
- No infeasibilities

**If the test fails:**
1. Check solve time - if >30s, investigate performance regression
2. Check fill rate - if <95%, investigate constraint conflicts or infeasibility
3. Check solution status - if infeasible, review constraint modifications
4. Review test output for specific error messages and assertions
5. Compare with previous successful runs to identify regression

This test serves as a **regression gate** to ensure optimization changes don't break existing functionality or degrade performance.

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
   - **Truck Capacity (Unit-Based for Tractability):**
     - Capacity enforced at unit level (14,080 units = 44 pallets per truck)
     - Uses continuous truck_load variables (not integer pallets)
     - Allows fractional pallet loading (e.g., 14,050 units = 43.9 pallets OK)
     - **Note:** Pallet-level truck loading deferred to Phase 4 (performance limitations)
     - **Alternative:** Commercial solvers (Gurobi/CPLEX) may handle pallet-level truck constraints

4. **Storage/Holding Costs (Pallet-Based):**
   - **Pallet definition:** 320 units = 32 cases = 1 pallet
   - **Partial pallet rounding:** Partial pallets cost as full pallets (50 units = 1 pallet cost, not 0.156 pallets)
   - **Fixed cost per pallet:** One-time charge when pallet enters storage (optional, set via `storage_cost_fixed_per_pallet`)
   - **Daily frozen holding cost:** Cost per pallet per day in frozen storage (`storage_cost_per_pallet_day_frozen`)
   - **Daily ambient holding cost:** Cost per pallet per day in ambient storage (`storage_cost_per_pallet_day_ambient`)
   - **Ceiling constraint:** Implemented using auxiliary integer variables: `pallet_count * 320 >= inventory_qty`
   - **Cost minimization:** Solver automatically drives pallet_count to minimum (ceiling rounding)
   - **Legacy unit-based costs:** Still supported via `storage_cost_frozen_per_unit_day` and `storage_cost_ambient_per_unit_day`
   - **Precedence:** If both pallet and unit costs set, pallet-based takes precedence
   - **Incentive:** Minimizes inventory holding and optimizes inventory positioning across network
   - **Performance impact:** Adds ~18,675 integer variables for 4-week horizon, increasing solve time from ~20s to ~35-45s (2x increase, acceptable trade-off for cost accuracy)
   - **Disable option:** Set all storage costs to 0.0 to skip pallet variable creation (reverts to ~20s solve time)

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
