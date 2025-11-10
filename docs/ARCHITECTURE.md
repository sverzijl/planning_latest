# System Architecture - Production-Distribution Planning

**Last Updated:** November 9, 2025
**Model Version:** SlidingWindowModel (Primary - Only)
**Status:** Production Ready

---

## Overview

The gluten-free bread production-distribution planning system uses mathematical optimization to minimize total cost-to-serve while meeting demand through a multi-echelon distribution network.

**Core Technology:**
- **Optimization:** Pyomo + APPSI HiGHS solver
- **Model:** SlidingWindowModel (state-based aggregate flows)
- **UI:** Streamlit web application
- **Data:** Excel-based input format

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE (Streamlit)                  │
│  ui/app.py + ui/pages/ (Data, Planning, Results, Network)      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─── Upload Excel Files (Forecast, Network Config, Inventory)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER (Parsers + Models)                │
│                                                                   │
│  src/parsers/                                                    │
│  ├── MultiFileParser (forecast, network, labor, trucks, costs)  │
│  ├── SAPParser (SAP IBP format detection)                       │
│  └── InventoryParser (initial inventory snapshots)              │
│                                                                   │
│  src/models/                                                     │
│  ├── UnifiedNode, UnifiedRoute (network topology)               │
│  ├── Product, Forecast (demand data)                            │
│  ├── LaborCalendar, TruckSchedule (operations)                  │
│  └── CostStructure (cost parameters)                            │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─── Parse and validate data
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDATION LAYER (Data Quality)               │
│                                                                   │
│  src/validation/                                                 │
│  ├── PlanningDataSchema (Pydantic validation)                   │
│  ├── NetworkTopologyValidator (route validation)                │
│  ├── TruckScheduleValidator (truck feasibility)                 │
│  └── DataCoordinator (orchestration)                            │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─── Validated data structures
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              OPTIMIZATION LAYER (Decision Engine)                │
│                                                                   │
│  src/optimization/                                               │
│  ├── SlidingWindowModel (PRIMARY MODEL)                         │
│  │   ├── State-based aggregate flows                            │
│  │   ├── Sliding window shelf life constraints                  │
│  │   ├── Integer pallet tracking                                │
│  │   └── FEFO batch allocation (post-processing)                │
│  │                                                               │
│  ├── BaseOptimizationModel (abstract base class)                │
│  ├── ResultSchema (Pydantic interface contract)                 │
│  ├── SolverConfig (solver management)                           │
│  ├── Constants (centralized constants)                          │
│  └── WarmstartGenerator (MIP heuristics)                        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─── Optimize and extract solution
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SOLUTION EXTRACTION & ANALYSIS                  │
│                                                                   │
│  src/optimization/sliding_window_model.py::extract_solution()   │
│  Returns: OptimizationSolution (Pydantic validated)             │
│                                                                   │
│  src/analysis/                                                   │
│  ├── LPFEFOAllocator (batch allocation)                         │
│  ├── DailySnapshotGenerator (inventory tracking)                │
│  └── ProductionLabelingReport (D-1 vs D0 batches)              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─── Format for display
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UI PRESENTATION LAYER                         │
│                                                                   │
│  ui/utils/result_adapter.py (format OptimizationSolution)       │
│  ui/components/ (charts, tables, visualizations)                │
│                                                                   │
│  Display Tabs:                                                   │
│  ├── Production Summary (total quantities, labor hours)         │
│  ├── Production Labeling (D-1 vs D0 batches)                   │
│  ├── Distribution (shipments, routes, truck assignments)        │
│  ├── Daily Snapshot (inventory state by day)                    │
│  └── Cost Breakdown (labor, transport, holding, waste)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Model: SlidingWindowModel

### Design Philosophy

**State-based aggregate flows with sliding window shelf life constraints**

Instead of tracking individual product batches and their ages (cohort tracking), SlidingWindowModel tracks aggregate inventory by state (ambient, frozen, thawed) and uses sliding window constraints to ensure products don't exceed shelf life.

**Key Innovation:** Implicit age tracking via sliding windows
- Product that entered state >L days ago automatically excluded from feasible region
- No need to track production dates or age explicitly
- Dramatic problem size reduction: O(H) variables instead of O(H³)

### Variable Structure

**Decision Variables:**
```python
# Production
production[node, product, date]  # How much to produce

# Inventory by state
inventory[node, product, state, date]  # State ∈ {ambient, frozen, thawed}

# Shipments
shipment[origin, dest, product, date, state]  # Shipments by state
in_transit[origin, dest, product, departure_date, state]  # Pipeline inventory

# State transitions
thaw[node, product, date]     # Frozen → ambient (for 6130 WA thawing)
freeze[node, product, date]   # Ambient → frozen (for long-term storage)

# Pallet tracking (integer)
pallet_count[node, product, state, date]  # Integer pallets for storage costs

# Demand consumption
demand_consumed_from_ambient[node, product, date]
demand_consumed_from_thawed[node, product, date]

# Labor (at manufacturing nodes)
labor_regular[node, date]      # Regular hours (0-12h weekdays)
labor_overtime[node, date]     # Overtime hours (12-14h weekdays)
labor_non_fixed[node, date]    # Non-fixed day hours (weekends/holidays)
```

**Complexity:** ~11,000 variables for 4-week horizon

### Constraint Structure

**Material Balance Equations (Acyclic):**
```
inventory[t] = inventory[t-1] + inflows[t] - outflows[t]

Inflows: production + arrivals + thaw
Outflows: shipments + demand + freeze
```

**Sliding Window Shelf Life:**
```
Σ(outflows over window [t-L+1, t]) ≤ Σ(inflows over same window)

Where L = shelf life (17d ambient, 120d frozen, 14d thawed)
```

**Production Capacity:**
```
production ≤ production_rate × labor_hours
labor_hours = labor_regular + labor_overtime + labor_non_fixed
```

**Truck Scheduling:**
```
Σ(shipments on truck) ≤ truck_capacity (14,080 units)
shipments constrained by truck departure schedule
```

**Integer Pallet Tracking:**
```
pallet_count × 320 ≥ inventory_quantity
pallet_count ∈ Integers (enforces ceiling rounding)
```

### Performance Characteristics

| Horizon | Variables | Build Time | Solve Time (APPSI HiGHS) |
|---------|-----------|------------|--------------------------|
| 1 week  | ~2,800    | <1s        | <2s                      |
| 4 weeks | ~11,000   | 2-5s       | 5-7s                     |
| 12 weeks| ~33,000   | 10-20s     | 30-60s                   |

**Compared to Previous (UnifiedNodeModel):**
- **60-80× faster** solve times
- **46× fewer** variables
- **Same accuracy** (exact shelf life enforcement)

---

## Data Flow

### Input Processing

```
Excel Files
  ├── Forecast (Gluten Free Forecast - Latest.xlsm)
  ├── Network Config (11 locations, 10 routes, costs)
  ├── Inventory Snapshot (optional initial state)
  └── Labor Calendar (585 labor days with rates)
       │
       ▼
  MultiFileParser
  ├── Parse forecast → Forecast object
  ├── Parse locations → List[UnifiedNode]
  ├── Parse routes → List[UnifiedRoute]
  ├── Parse trucks → List[UnifiedTruckSchedule]
  ├── Parse labor → LaborCalendar
  └── Parse costs → CostStructure
       │
       ▼
  Data Validation (Pydantic schemas)
  ├── ValidatedPlanningData
  ├── Network topology validation
  ├── Product ID resolution (aliases)
  └── Consistency checks
       │
       ▼
  Ready for Optimization
```

### Optimization Flow

```
SlidingWindowModel Initialization
  ├── Create decision variables
  ├── Build constraints (material balance, shelf life, capacity)
  ├── Build objective function (minimize costs)
  └── Model built (2-5s for 4-week)
       │
       ▼
  Solve with APPSI HiGHS
  ├── Set solver options (MIP gap, time limit)
  ├── Solve MIP problem (5-7s for 4-week)
  └── Extract solution
       │
       ▼
  extract_solution() → OptimizationSolution
  ├── Production batches
  ├── Shipments
  ├── Inventory state (aggregate)
  ├── Labor hours breakdown
  ├── Cost breakdown
  ├── Demand satisfaction
  └── Pydantic validation
       │
       ▼
  Post-Processing
  ├── FEFO batch allocation (age assignment)
  ├── Daily snapshot generation
  ├── Production labeling (D-1 vs D0)
  └── Cost attribution
       │
       ▼
  UI Display (result_adapter.py formats for Streamlit)
```

### Output Structure

**OptimizationSolution (Pydantic):**
```python
{
  "status": "optimal",
  "objective_value": 123456.78,
  "solve_time_seconds": 6.23,

  "production_batches": [
    {"node_id": "6122", "product_id": "HELGAS...", "date": "2025-11-10",
     "quantity": 3200, "is_initial_inventory": false}
  ],

  "shipments": [
    {"origin": "6122", "destination": "6125", "product_id": "HELGAS...",
     "departure_date": "2025-11-10", "quantity": 2560, "state": "ambient"}
  ],

  "inventory_state": {
    "('6122', 'HELGAS...', 'ambient', '2025-11-11')": 640.0
  },

  "total_costs": {
    "labor_costs": {...},
    "transport_costs": 45000.0,
    "holding_costs": {...},
    "total_cost": 123456.78
  },

  "demand_consumed": {...},
  "shortages": {...}
}
```

---

## Module Organization

### `src/optimization/` - Optimization Engine

**Active Files:**
- `sliding_window_model.py` (4,111 lines) - **PRIMARY MODEL**
- `base_model.py` (900 lines) - Abstract base class
- `result_schema.py` (651 lines) - Pydantic interface contract
- `solver_config.py` (629 lines) - Solver detection and configuration
- `constants.py` (210 lines) - **NEW** Centralized constants
- `types.py` (392 lines) - Semantic type system
- `validation_utils.py` (225 lines) - Fail-fast validation
- `warmstart_generator.py` (511 lines) - Warmstart hint generation
- `warmstart_utils.py` (598 lines) - Warmstart support utilities
- `feature_registry.py` (255 lines) - Incremental development tracking
- `legacy_to_unified_converter.py` (246 lines) - Data format conversion (for tests)

**Archived (2025-11-09):**
- `archive/optimization_models_deprecated_2025_11/`
  - `unified_node_model.py` - Cohort-tracking approach (reference)
  - `verified_sliding_window_model.py` - Experimental incremental build
  - `rolling_horizon_solver.py` - Alternative decomposition
  - `daily_rolling_solver.py` - Daily replanning experiment
  - Plus supporting files

**Total:** 9,558 lines (was 17,558 - reduced 46%)

### `src/models/` - Data Models

**Core Models:**
- `Product` - SKU definitions with shelf life and mix sizes
- `UnifiedNode` - Location with capabilities (manufacturing, storage, demand)
- `UnifiedRoute` - Routes with transit time and transport mode
- `Forecast` - Demand by location/product/date
- `LaborCalendar` - Labor availability and cost rates
- `UnifiedTruckSchedule` - Truck departure times and destinations
- `CostStructure` - All cost parameters
- `ProductionBatch`, `Shipment`, `Inventory` - Result structures

**Design Pattern:** Rich domain models with business logic methods

### `src/validation/` - Data Validation

**Fail-Fast Philosophy:** Catch errors at data ingestion, not during optimization

**Components:**
- `PlanningDataSchema` - Pydantic schemas for all inputs
- `NetworkTopologyValidator` - Route connectivity and feasibility
- `TruckScheduleValidator` - Truck schedule consistency
- `DataCoordinator` - Orchestrate validation workflow

**Benefits:**
- Descriptive error messages at parse time
- Prevents garbage-in-garbage-out
- Product ID alias resolution (inventory SKUs → forecast names)

### `src/analysis/` - Solution Analysis

**Post-Optimization Processing:**
- `LPFEFOAllocator` - Allocate aggregate flows to specific batches (FEFO)
- `DailySnapshotGenerator` - Track inventory state evolution day-by-day
- `ProductionLabelingReport` - Label batches as D-1 or D0 for truck assignment

**Why Post-Processing:**
- Optimization solves aggregate flows (faster)
- Batch-level details assigned after solve (still optimal)
- Enables 60-80× speedup without losing traceability

### `ui/` - User Interface

**Framework:** Streamlit (Python web framework)

**Structure:**
```
ui/
├── app.py (Main entry point)
├── pages/
│   ├── 1_Data.py (Upload and visualize inputs)
│   ├── 2_Planning.py (Configure and run optimization)
│   ├── 3_Results.py (View solution and costs)
│   └── 4_Network.py (Network visualization)
├── components/
│   ├── cost_charts.py (Cost breakdown visualizations)
│   ├── data_tables.py (Production, shipment tables)
│   └── daily_snapshot.py (Inventory evolution view)
└── utils/
    ├── result_adapter.py (Format OptimizationSolution for display)
    └── session_state.py (Manage Streamlit state)
```

**Key Feature:** Real-time optimization with interactive UI (5-7s solve time enables try-different-scenarios workflow)

---

## Key Architectural Decisions

### 1. Sliding Window Shelf Life Constraints

**Previous Approach (Archived):**
- Explicit age tracking: 6-tuple inventory keys `(node, product, prod_date, state_entry_date, curr_date, state)`
- O(H³) variables where H = horizon in days
- 500,000 variables for 4-week horizon
- 300-500s solve time

**Current Approach (SlidingWindowModel):**
- Implicit age via sliding windows: O ≤ Q over L-day window
- O(H) variables where H = horizon
- 11,000 variables for 4-week horizon
- 5-7s solve time

**Why:** 60-80× speedup, 46× fewer variables, same accuracy

### 2. State-Based Aggregate Flows

**Decision:** Optimize at SKU level (how much), not batch level (which batch)

**Variables:**
- `production[product, date]` - Total production quantity
- `inventory[product, state, date]` - Total inventory by state

**Not:**
- ~~`inventory[product, prod_date, age, state, date]`~~ - Batch-specific tracking

**Benefits:**
- Dramatic problem size reduction
- Faster solve times
- Batch details assigned via post-processing (FEFO allocation)

### 3. Integer Pallet Tracking

**Decision:** Model pallets as integer variables for holding costs

**Constraint:**
```
pallet_count × 320 ≥ inventory_quantity
pallet_count ∈ Integers
```

**Why:**
- 50 units of inventory costs 1 full pallet (not 0.156 pallets)
- Enforces "partial pallets occupy full pallet space" business rule
- More accurate cost representation

**Tradeoff:** Adds ~6,000 integer variables but worth it for cost accuracy

### 4. Pydantic Schema Interface Contract

**Decision:** All models must return `OptimizationSolution` (Pydantic validated)

**Benefits:**
- Type safety at model-UI boundary
- Automatic validation (fails fast if data malformed)
- Self-documenting interface
- Enables model swapping (future proof)

**Contract:** `src/optimization/result_schema.py`

### 5. APPSI HiGHS Solver

**Decision:** Use APPSI interface with HiGHS solver (not legacy interface)

**Why:**
- Modern Pyomo interface (Pyomo 6.9.1+)
- Persistent solver (faster for repeated solves)
- Warmstart support (30-50% speedup on rolling horizon)
- Proper termination condition mapping

**Fallback:** CBC if HiGHS unavailable

### 6. Centralized Constants

**Decision:** All hardcoded values in `src/optimization/constants.py`

**Why:**
- Single source of truth
- No magic numbers scattered across files
- Easy to update
- Type-safe with docstrings

**Example:**
```python
from src.optimization.constants import AMBIENT_SHELF_LIFE_DAYS  # 17
```

---

## Network Topology

### 2-Echelon Hub-and-Spoke with Frozen Buffer

```
Manufacturing (6122)
  ├─→ Hub NSW/ACT (6104) ─→ Breadrooms (6102, 6103, 6113)
  ├─→ Hub VIC/TAS/SA (6125) ─→ Breadrooms (6106, 6107, 6108, 6118, 6129)
  ├─→ Direct QLD (6110)
  └─→ Lineage (frozen buffer) ─→ Hub VIC (6125) ─→ WA (6130) **THAWS HERE**
```

**Special Route:** WA (6130)
- Receives frozen product via Lineage buffer
- Thaws on-site (shelf life resets to 14 days)
- Critical constraint modeled via thaw variables

**Truck Schedule:**
- 11 trucks/week from manufacturing
- Morning/afternoon departures with day-specific routing
- Wednesday special: Lineage frozen drop-off
- Friday double capacity (2 afternoon trucks)

---

## Shelf Life State Machine

```
           Production
                │
                ▼
          ┌──────────┐
          │ AMBIENT  │ (17 days shelf life)
          │ (fresh)  │
          └────┬─────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌──────────┐      ┌──────────┐
│ FROZEN   │      │ DEMAND   │
│(120 days)│      │SATISFIED │
└────┬─────┘      └──────────┘
     │
     │ thaw
     ▼
┌──────────┐
│ THAWED   │ (14 days - RESET!)
│(post-thaw)│
└────┬─────┘
     │
     ▼
  DEMAND
 SATISFIED
```

**Key States:**
- **AMBIENT:** Default production state (17 days)
- **FROZEN:** Long-term storage (120 days)
- **THAWED:** After thawing frozen product (14 days - shelf life RESETS)

**Critical:** Thawing resets shelf life to 14 days (modeled for 6130 WA route)

---

## Cost Structure

**Objective:** Minimize total cost-to-serve

```
Total Cost = Labor + Transport + Holding + Shortage + Changeover + Waste
```

**Components:**

1. **Labor Costs:**
   - Regular hours (0-12h weekdays): `regular_rate × hours`
   - Overtime hours (12-14h weekdays): `overtime_rate × hours`
   - Non-fixed days (weekends/holidays): `non_fixed_rate × max(hours, 4h)`
   - Overhead: Startup (0.5h) + shutdown (0.5h) per production day

2. **Transport Costs:**
   - Per route: `cost_per_unit × quantity_shipped`
   - Varies by route (frozen more expensive than ambient)

3. **Holding Costs:**
   - **Pallet-based** (if enabled): `pallet_count × daily_rate`
   - **Unit-based** (fallback): `quantity × daily_rate`
   - Different rates for frozen vs ambient storage

4. **Shortage Penalty:**
   - `shortage_penalty_per_unit × shortfall` (only if allow_shortages=True)
   - High penalty ($10,000/unit default) incentivizes meeting demand

5. **Changeover Costs:**
   - Tracked via product_start variables (0→1 transitions)
   - `changeover_cost_per_start × num_changeovers`

6. **Waste Costs:**
   - Currently minimal (disposal allowed only for expired products)
   - Future enhancement: Explicit waste cost modeling

---

## Testing Architecture

### Test Organization

**Test Count:** ~85 test files (down from 102 after consolidation)

**Categories:**

1. **Integration Tests** (~15 files)
   - `test_integration_ui_workflow.py` - **CRITICAL REGRESSION GATE**
   - `test_ui_integration_complete.py` - Full UI workflow
   - Real data files, end-to-end validation

2. **Model Tests** (~20 files)
   - Solver tests (APPSI HiGHS, CBC, performance)
   - Labor cost tests (regular, overtime, holidays)
   - Inventory tests (holding costs, state tracking)
   - Warmstart tests (performance, validation)

3. **Unit Tests** (~50 files)
   - Data models, parsers, validators
   - Cost calculators, snapshot generators
   - Schema validation, type guards

**Archived Tests:**
- `archive/tests_unified_node_model_2025_11/` - 12 UnifiedNodeModel-specific tests
- Baseline tests (test_baseline_*.py) - Deleted (redundant with integration tests)

### Test Standards

**All optimization changes must pass:**
```bash
pytest tests/test_integration_ui_workflow.py -v
```
- **Performance:** < 10s (baseline 5-7s)
- **Quality:** ≥85% fill rate
- **Status:** OPTIMAL or FEASIBLE

**Before committing:**
```bash
pytest tests/ -v  # Full suite
```
- **Target:** ≥90% pass rate

---

## Development Workflow

### Making Changes

**1. Update Code**
```bash
# Example: Add new constraint to SlidingWindowModel
vim src/optimization/sliding_window_model.py
```

**2. Update Documentation**
```bash
# Update model specification (REQUIRED)
vim docs/SLIDING_WINDOW_MODEL_SPECIFICATION.md
```

**3. Run Tests**
```bash
# Critical regression gate
pytest tests/test_integration_ui_workflow.py -v

# Full suite
pytest tests/ -v
```

**4. Commit**
```bash
git add .
git commit -m "feat: Add <description>"
# Pre-commit hooks run automatically
```

### Adding New Features

**Standard Flow:**
1. Update data models if needed (`src/models/`)
2. Add to SlidingWindowModel (`src/optimization/sliding_window_model.py`)
3. Update result schema if needed (`src/optimization/result_schema.py`)
4. Update UI to display feature (`ui/`)
5. Write tests
6. Update SLIDING_WINDOW_MODEL_SPECIFICATION.md
7. Run regression tests

**Do NOT:**
- Create new optimization models (SlidingWindowModel is sufficient)
- Modify UnifiedNodeModel (archived)
- Skip documentation updates

---

## Performance Optimization

### Current Baseline

**4-Week Horizon:**
- Build time: 2-5s
- Solve time: 5-7s (APPSI HiGHS)
- Total time: 7-12s

**Bottlenecks:**
- Integer pallet variables: ~6,000 (necessary for cost accuracy)
- Network complexity: 11 nodes × 10 routes × 5 products
- Horizon length: Linear growth (4wk → 12wk = 3× time)

### Optimization Strategies

**If solve times degrade:**

1. **Check solver:** Use APPSI HiGHS (not CBC)
2. **Disable pallet tracking:** `use_pallet_tracking=False` (50% faster)
3. **Reduce horizon:** 4 weeks → 2 weeks
4. **Increase MIP gap:** 1% → 2% (trade optimality for speed)
5. **Use warmstart:** For rolling horizon scenarios

**If model size explodes:**
- Verify using SlidingWindowModel (not UnifiedNodeModel)
- Check for accidentally creating cohort variables
- Validate dates range (shouldn't extend beyond horizon)

---

## Deployment Considerations

### Requirements

**Python:** 3.11+
**Key Dependencies:**
- `pyomo` ≥ 6.9.1 (APPSI interface)
- `highspy` (HiGHS solver Python bindings)
- `streamlit` (UI framework)
- `pandas`, `openpyxl` (Excel I/O)

**Installation:**
```bash
pip install -r requirements.txt
pip install highspy  # HiGHS solver
```

### Running the Application

```bash
streamlit run ui/app.py
```

**Access:** http://localhost:8501

**Workflow:**
1. Upload forecast Excel file
2. Upload network config Excel file
3. (Optional) Upload inventory snapshot
4. Click "Optimize" on Planning page
5. View results in tabs (Production, Distribution, Costs)

---

## Archive Organization

**Current Archives:**
- `archive/debug_scripts/` (292 files) - Phase 1-3 debug scripts
- `archive/warmstart_investigation_2025_10/` (38 files) - Warmstart research
- `archive/sliding_window_debug_2025_10_27/` (50 files) - Sliding window development
- `archive/initial_inventory_debug_2025_11/` (104 files) - Inventory debugging
- `archive/optimization_models_deprecated_2025_11/` (7 files) - **NEW** Archived models
- `archive/root_investigation_files_2025_11/` (186 files) - **NEW** Investigation reports

**Total:** ~51MB (preserves all development history)

---

## Future Enhancements (Phase 4+)

1. **Pallet-level truck loading:** Integer pallets per truck (currently unit-based)
2. **Flexible routing:** Optimize truck routes dynamically
3. **Production smoothing:** Minimize changeovers and setup costs
4. **Stochastic optimization:** Handle demand uncertainty
5. **Multi-period rolling horizon:** 52-week planning with warmstart
6. **Sensitivity analysis:** What-if scenarios and parameter exploration

---

## Getting Help

**Documentation:**
- `CLAUDE.md` - Project overview (this file)
- `docs/ARCHITECTURE.md` - System architecture (this document)
- `docs/TESTING_GUIDE.md` - Testing standards
- `CLEANUP_SUMMARY_2025_11.md` - Recent cleanup work
- `REVIEW_GUIDE.md` - Cleanup review instructions

**Archived Documentation:**
- `archive/optimization_models_deprecated_2025_11/README.md` - Archived models
- `archive/optimization_models_deprecated_2025_11/UNIFIED_NODE_MODEL_SPECIFICATION.md` - Historical reference

**Support:**
- Check test failures: `pytest tests/ -v`
- Import validation: `venv/bin/python tests/test_import_validation.py`
- Model specification: `docs/SLIDING_WINDOW_MODEL_SPECIFICATION.md` (if exists)

---

**Last Updated:** November 9, 2025
**Model Version:** SlidingWindowModel (Primary - Only)
**Archive Date:** November 9, 2025 (UnifiedNodeModel archived)
**Status:** Production Ready ✅
