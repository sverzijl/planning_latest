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

**Phase 3: Optimization** ✅ **COMPLETE - TWO APPROACHES AVAILABLE**

*Status: SlidingWindowModel (PRIMARY) and UnifiedNodeModel (reference)*

**SlidingWindowModel** ⭐ **RECOMMENDED - 60-220× FASTER**

*File: `src/optimization/sliding_window_model.py`*

- ✅ **Architecture**: State-based aggregate flows with sliding window shelf life constraints
- ✅ **Decision variables**: production, inventory by state (ambient/frozen/thawed), shipments, state transitions
- ✅ **Shelf life enforcement**: Implicit via sliding windows (17d ambient, 120d frozen, 14d thawed)
- ✅ **Performance**: 4-week solve in 5-7s (vs 400s cohort = **60-80× speedup**)
- ✅ **Model size**: ~11k variables (vs 500k cohort = **46× reduction**)
- ✅ **All constraints**: Integer pallets, production capacity, state transitions, truck scheduling
- ✅ **Solver**: APPSI HiGHS (high-performance modern interface)
- ✅ **Testing**: Integration test passes, 100% fill rate validated

**UnifiedNodeModel** (Reference/Legacy)

*File: `src/optimization/unified_node_model.py`*

- ✅ **Architecture**: Age-cohort tracking with 6-tuple (node, product, prod_date, state_entry_date, curr_date, state)
- ✅ **Decision variables**: inventory_cohort (explicit age tracking), production_batch
- ✅ **Shelf life enforcement**: Explicit age-in-state calculations with state_entry_date
- ✅ **Performance**: 4-week solve in 300-500s (cohort overhead)
- ⚠️ **Status**: Reference implementation (superseded by SlidingWindowModel for production use)

**Phase 3 Deliverables:**
- **SlidingWindowModel**: Production-ready, 60-220× speedup, 100% fill rate, complete feature parity
- **Performance**: 4-week horizon in 5-7s (SlidingWindowModel) vs 300-500s (UnifiedNodeModel)
- Interactive planning now feasible (near-realtime response)
- Integer pallet tracking for accurate costs (storage + trucks)
- Complete state transition support (freeze/thaw for WA route)

**Phase 4: Advanced Features (Planned)**
- Pallet-level truck loading constraints (currently unit-based for tractability)
- Flexible truck routing optimization
- Multi-period rolling horizon with production smoothing
- Stochastic demand and robust optimization
- Sensitivity analysis and what-if scenarios
- Advanced reporting and cost attribution

## Technology Stack

- **Python 3.11+** - Core programming language
- **Streamlit** - Web interface and dashboards
- **Pandas** - Data manipulation and Excel I/O
- **NetworkX** - Graph/network modeling and algorithms
- **Pyomo** - Mathematical optimization modeling (Phase 3+)
- **HiGHS** - High-performance MIP solver (recommended for binary variables)
- **CBC** - Fallback open-source solver
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
│   ├── debug_scripts/   # 268 archived troubleshooting scripts
│   └── examples/        # 2 archived example scripts (deprecated model references)
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

### Solver Installation

**HiGHS (Recommended for Binary Variables):**
```bash
pip install highspy
```

**CBC (Fallback Open-Source Solver):**
```bash
# Ubuntu/Debian
sudo apt-get install coinor-cbc

# macOS
brew install cbc

# Conda
conda install -c conda-forge coincbc
```

**Commercial Solvers (Optional):**
- **Gurobi**: Requires license (academic licenses available)
- **CPLEX**: Requires license (academic licenses available)

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

1. **Sliding window shelf life constraints:** (2025-10-27) Replace explicit age-cohort tracking with implicit sliding window formulation; 60-220× speedup, 46× fewer variables while maintaining exact shelf life enforcement. See `src/optimization/sliding_window_model.py`
2. **State-based aggregate flows:** Optimize SKU-level flows (how much to produce/ship) rather than individual batches; enables dramatic problem size reduction
3. **Integrated production-distribution optimization:** Couple production scheduling with distribution to capture interdependencies and cost trade-offs
4. **State machine for shelf life:** Track product state (frozen/ambient/thawed) with automatic transitions via freeze/thaw flows
5. **Tiered labor cost model:** Explicit modeling of fixed hours, overtime, and non-fixed labor days with different cost rates
6. **Generalized truck constraints:** Work for any node (not just manufacturing), day-of-week enforcement, intermediate stops
7. **Mathematical optimization first:** Proven optimal solutions via Pyomo/HiGHS (heuristics deprecated)
8. **Separation of concerns:** Clear boundaries between data models (src/models/), optimization (src/optimization/), UI (ui/), and analysis (src/analysis/)
9. **Excel as input format:** Maintain compatibility with existing workflows; comprehensive input covering forecast, network, labor, trucks, costs, inventory
10. **Cost-centric objective:** Minimize total cost to serve (not just waste); enables business-driven trade-off decisions
11. **Pallet-level granularity:** Integer pallet variables for storage enforce "partial pallets occupy full pallet space" rule
12. **Binary variable enforcement:** True binary product_produced variables prevent fractional SKU production; HiGHS solver enables practical performance
13. **Start tracking changeover:** (2025-10-22) Sequence-independent formulation tracks product startups (0→1 transitions) using inequality constraints instead of counting constraint; 2% better cost, 19% faster, enables APPSI warmstart for long horizons. See `docs/optimization/changeover_formulations.md`
14. **Mix-based production enforcement:** (2025-10-23) Production occurs in integer multiples of product-specific batch sizes. Each product has a `units_per_mix` parameter (e.g., 415 units per mix), and the optimization model uses integer `mix_count` variables with production as a derived expression (`production = mix_count × units_per_mix`). This reflects real manufacturing constraints where products are made in discrete batches, not continuous quantities.

**Recent Key Updates:**
- **Sliding Window Model** (Oct 27, 2025): Complete rewrite using sliding window shelf life constraints; 60-220× speedup, 46× fewer variables, production-ready and validated
- **APPSI HiGHS Integration**: Modern persistent solver interface with proper termination condition mapping
- **Shipment Date Range Fix**: Extended shipment variables to handle deliveries beyond planning horizon (critical for material balance)
- **Start Tracking Changeover** (Oct 2025): Sequence-independent formulation for product changeovers
- **Mix-Based Production**: Integer multiples of product-specific batch sizes

**Detailed Documentation:**
- Warmstart investigation: `docs/lessons_learned/warmstart_investigation_2025_10.md`
- Changeover formulations: `docs/optimization/changeover_formulations.md`
- Model specification: `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`

## Development Workflow

1. Always write tests for new functionality
2. Use type hints throughout the codebase
3. Keep UI and business logic separate
4. Document complex algorithms and business rules
5. Version control Excel file format specifications
6. **Run integration tests before committing changes to model or optimization code**
7. **Update model documentation when modifying optimization code** (see Documentation Maintenance below)

### Testing Requirements

#### Integration Test Validation (REQUIRED)

**All changes to the optimization model or solver code MUST pass the UI workflow integration test before being committed.**

```bash
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v
```

**Test validates:**
- UI workflow compatibility (4-week horizon, 1% MIP gap, batch tracking)
- Real data files (GFree Forecast.xlsm, Network_Config.xlsx)
- Performance (solve time < 400s for 4-week; baseline ~300s with pallet+mix constraints)
- Solution quality (fill rate ≥ 85%, optimal/feasible status)

**Run before:**
- Committing changes to `src/optimization/`
- Modifying constraints, objectives, or solver parameters
- Merging feature branches affecting optimization

This test serves as a **regression gate** for optimization changes.

### Documentation Maintenance (REQUIRED)

**All changes to the optimization model MUST be synchronized with `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md`**

Update documentation when modifying:
- Decision variables, constraints, or objective function
- Solver parameters or performance optimizations
- Model behavior or feature implementations

**Update process:**
1. Edit relevant sections in UNIFIED_NODE_MODEL_SPECIFICATION.md
2. Update "Last Updated" timestamp and changelog
3. Verify mathematical formulations and code references

This ensures the technical specification remains the single source of truth for model behavior.

## Cost Components

The objective function minimizes **total cost to serve**, comprising:

1. **Labor Costs:**
   - **Fixed days (Mon-Fri):** Regular rate (0-12h) + overtime rate (12-14h)
   - **Non-fixed days (weekends/holidays):** Premium rate with 4-hour minimum payment
   - **Overhead:** Includes startup (0.5h) + shutdown (0.5h) + changeover time
   - **Implementation:** Piecewise cost model with 5 decision variables per manufacturing node-date

2. **Production Costs:**
   - **Source:** CostParameters sheet → `production_cost_per_unit`
   - Direct production costs per unit
   - Setup costs tracked but not currently costed (Phase 4 feature)

3. **Transport Costs:**
   - **Source:** Routes sheet → `cost` column (per-route cost per unit)
   - Cost varies by route (frozen routes typically more expensive than ambient)
   - No fixed truck costs in current implementation
   - **Truck Capacity (Unit-Based for Tractability):**
     - Capacity enforced at unit level (14,080 units = 44 pallets per truck)
     - Uses continuous truck_load variables (not integer pallets)
     - Allows fractional pallet loading (e.g., 14,050 units = 43.9 pallets OK)
     - **Note:** Pallet-level truck loading deferred to Phase 4 (performance limitations)
     - **Alternative:** Commercial solvers (Gurobi/CPLEX) may handle pallet-level truck constraints

4. **Storage/Holding Costs:**
   - **Pallet definition:** 320 units = 32 cases = 1 pallet
   - **Pallet-based costs** (optional): Integer variables enforce ceiling rounding (50 units = 1 pallet cost)
     - Fixed costs: `storage_cost_fixed_per_pallet_{frozen|ambient}`
     - Daily costs: `storage_cost_per_pallet_day_{frozen|ambient}`
     - Performance: ~18,675 integer vars (both states), ~6,225 (one state) for 4-week horizon
   - **Unit-based costs** (default): Continuous variables for faster solve times
     - Daily costs: `storage_cost_{frozen|ambient}_per_unit_day`
   - **Configuration:** Pallet-based takes precedence if both are set; set to 0.0 to disable

   See `EXCEL_TEMPLATE_SPEC.md` for detailed parameter definitions.

5. **Shortage Penalty Costs:**
   - **Source:** CostParameters sheet → `shortage_penalty_per_unit`
   - High penalty for unmet demand (default: $10,000/unit)
   - Incentivizes meeting all demand when feasible
   - Only applied when `allow_shortages=True`

## Cost Parameter Configuration Summary

**CostParameters Sheet (Production & Storage Only):**
- `production_cost_per_unit` - Base production cost
- `storage_cost_frozen_per_unit_day` - Unit-based frozen holding cost
- `storage_cost_ambient_per_unit_day` - Unit-based ambient holding cost
- `storage_cost_per_pallet_day_frozen` - Pallet-based frozen holding cost
- `storage_cost_per_pallet_day_ambient` - Pallet-based ambient holding cost
- `storage_cost_fixed_per_pallet_frozen` - Fixed frozen pallet entry cost
- `storage_cost_fixed_per_pallet_ambient` - Fixed ambient pallet entry cost
- `waste_cost_multiplier` - Multiplier for waste cost (currently unused in objective)
- `shortage_penalty_per_unit` - Penalty for demand shortfalls

**LaborCalendar Sheet (Labor Rates):**
- `regular_rate` (per date) - Regular labor rate ($/hour)
- `overtime_rate` (per date) - Overtime labor rate ($/hour)
- `non_fixed_rate` (per date) - Non-fixed day labor rate ($/hour)

**Routes Sheet (Transport Costs):**
- `cost` (per route) - Transport cost per unit for each route
- Different routes can have different costs (frozen vs ambient, long vs short distance)

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
