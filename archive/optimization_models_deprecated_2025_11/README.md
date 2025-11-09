# Deprecated Optimization Models Archive

**Archive Date:** November 9, 2025
**Reason:** Codebase cleanup - migration to SlidingWindowModel as sole optimization engine
**Branch:** comprehensive-cleanup-2025-11

---

## Overview

This directory contains 7 optimization model files that have been deprecated and archived as part of a comprehensive codebase cleanup. These files represent the evolution of the production-distribution planning optimization from the original cohort-tracking approach to the modern sliding window formulation.

**Current Production Model:** `SlidingWindowModel` (src/optimization/sliding_window_model.py)

---

## Archived Files

### 1. `unified_node_model.py` (290K, 6,307 lines)

**Status:** REFERENCE IMPLEMENTATION (Superseded)

**Purpose:** Original unified node architecture using age-cohort tracking for shelf life constraints

**Key Features:**
- Node-based architecture with capability flags (manufacturing, storage, demand)
- Age-cohort inventory tracking with 6-tuple keys: (node, product, prod_date, state_entry_date, curr_date, state)
- Explicit shelf life enforcement via age-in-state calculations
- No virtual locations - direct node representation
- Complete feature parity with SlidingWindowModel

**Performance:**
- 4-week horizon: 300-500s solve time
- Model size: ~500,000 variables
- Variable complexity: O(H³) where H = horizon in days

**Why Archived:**
- 60-80× slower than SlidingWindowModel
- Massive variable count makes long horizons impractical
- Cohort tracking overhead unnecessary for aggregate planning
- All 40+ tests migrated to SlidingWindowModel

**Historical Context:**
- Original implementation (2025 early)
- Validated production-grade model
- Used in critical regression tests until Nov 2025
- Extensive debugging and validation (see archive/initial_inventory_debug_2025_11/)

**When to Use:**
- Research: Understanding cohort-based formulation
- Comparison: Validating SlidingWindowModel behavior
- Batch tracking: If explicit batch-level decisions needed (future feature)
- Reference: Learning MIP modeling techniques

---

### 2. `verified_sliding_window_model.py` (32K, 851 lines)

**Status:** EXPERIMENTAL/DEVELOPMENT

**Purpose:** Incrementally-built simplified sliding window model from test levels 1-16

**Key Features:**
- Level 16 equivalent (base ambient state + frozen state)
- Incremental feature addition validated at each step
- Simplified objective (no labor/cost modeling)
- Proof-of-concept for sliding window approach

**Limitations:**
- Missing labor cost modeling
- Minimal shipment handling
- No truck constraints
- Incomplete objective function

**Why Archived:**
- Development artifact, not production-ready
- SlidingWindowModel is complete and validated
- Served purpose as incremental validation tool

**Historical Context:**
- Built Oct-Nov 2025 during sliding window development
- Used to validate core formulations step-by-step
- See src/optimization/feature_registry.py for level definitions

**When to Use:**
- Education: Learning sliding window formulation incrementally
- Debugging: Simplified model for isolating issues
- Research: Understanding constraint evolution

---

### 3. `rolling_horizon_solver.py` (27K, 660 lines)

**Status:** INACTIVE (Alternative Approach)

**Purpose:** Break 20+ week problems into smaller overlapping windows

**Approach:**
- Solves multiple independent windows
- Combines solutions via overlap stitching
- Supports temporal aggregation/bucketing

**Why Archived:**
- Uses deprecated IntegratedProductionDistributionModel
- SlidingWindowModel handles 12-week horizons efficiently (30-60s)
- Rolling horizon adds complexity without clear benefit at current scale
- Not actively maintained or tested

**Historical Context:**
- Early solution for long-horizon problems
- Pre-dates SlidingWindowModel performance improvements
- Overlap stitching proved complex and error-prone

**When to Use:**
- Multi-year planning (if ever needed)
- Research into decomposition methods
- Comparing window vs. monolithic approaches

---

### 4. `daily_rolling_solver.py` (21K, 570 lines)

**Status:** INACTIVE (Performance Investigation)

**Purpose:** Daily rolling horizon with warmstart for replanning

**Workflow:**
- Day 1: Full solve (cold start)
- Day 2+: Re-solve with warmstart from previous day
- Forecast shifts forward by 1 day each iteration

**Performance:**
- 1st solve: ~30-96s
- Warmstart solves: ~15-50s (30-50% speedup)

**Why Archived:**
- Experimental implementation
- Warmstart investigation complete (see archive/warmstart_investigation_2025_10/)
- Daily replanning not current operational requirement
- Complexity not justified by use case

**Historical Context:**
- Built Oct 2025 during warmstart performance research
- Validated warmstart hint generation
- See docs/lessons_learned/warmstart_investigation_2025_10.md

**When to Use:**
- Daily operational replanning (future feature)
- Warmstart algorithm research
- Rolling horizon pattern reference

---

### 5. `window_config.py` (13K, 336 lines)

**Status:** SUPPORTING MODULE (Rolling Horizon Only)

**Purpose:** Configuration and result structures for rolling horizon solver

**Classes:**
- `WindowConfig`: Configuration for a single window
- `WindowSolution`: Result from solving a window
- `RollingHorizonResult`: Combined multi-window result

**Functions:**
- `create_windows()`: Generate overlapping windows

**Why Archived:**
- Only used by rolling_horizon_solver.py
- No longer needed with SlidingWindowModel
- No active use cases

**When to Use:**
- With rolling_horizon_solver.py if reactivated
- Reference for window-based decomposition

---

### 6. `legacy_to_unified_converter.py` (9.4K, 246 lines)

**Status:** BACKWARD COMPATIBILITY (Pre-Unified Format)

**Purpose:** Convert legacy data structures to unified node model

**Conversions:**
- ManufacturingSite + Locations → UnifiedNodes
- Routes → UnifiedRoutes
- TruckSchedules → UnifiedTruckSchedules

**Why Archived:**
- "Legacy" explicitly in filename
- UnifiedNode format is now standard
- Conversion no longer needed (all data in unified format)
- Backward compatibility maintained by UI/parsers

**Historical Context:**
- Bridge between Phase 1 (basic models) and Phase 3 (optimization)
- Enabled smooth migration to unified architecture
- Last used: Oct 2025

**When to Use:**
- Migrating very old data files (pre-Oct 2025)
- Understanding data model evolution
- Reference for format conversion patterns

---

### 7. `batch_extraction.py` (9.8K, 272 lines)

**Status:** COHORT-SPECIFIC UTILITY

**Purpose:** Extract batch-level data from cohort-tracking models (UnifiedNodeModel)

**Functions:**
- `extract_cohort_inventory()`: Get cohort-level inventory
- `create_production_batches()`: Convert production variables to ProductionBatch objects
- `extract_batch_shipments()`: Link shipments to specific batches
- `extract_demand_from_cohort()`: Track demand satisfaction by cohort

**Why Archived:**
- Cohort tracking specific (not used by SlidingWindowModel)
- SlidingWindowModel uses aggregate flows
- Batch-level tracking via post-processing (src/analysis/lp_fefo_allocator.py)

**Historical Context:**
- Built Oct 2025 for UnifiedNodeModel
- Enabled UI batch tracking display
- Replaced by FEFO allocation in SlidingWindowModel

**When to Use:**
- With UnifiedNodeModel if reactivated
- Reference for batch extraction algorithms
- Understanding cohort → batch mapping

---

## Performance Comparison

| Model | Horizon | Variables | Solve Time | Status |
|-------|---------|-----------|------------|--------|
| **SlidingWindowModel** | 4 weeks | ~11,000 | **5-7s** | ✅ PRODUCTION |
| UnifiedNodeModel | 4 weeks | ~500,000 | 300-500s | ⚠️ ARCHIVED |
| VerifiedSlidingWindow | 4 weeks | ~2,000 | N/A | 🧪 INCOMPLETE |
| RollingHorizon | 12 weeks | Varies | 60-180s | ⏸️ INACTIVE |
| DailyRolling | 4 weeks | ~11,000 | 15-96s | 🔬 EXPERIMENTAL |

**Speedup:** SlidingWindowModel is **60-80× faster** than UnifiedNodeModel

---

## Migration Guide

**From UnifiedNodeModel:**
```python
# OLD (archived)
from src.optimization.unified_node_model import UnifiedNodeModel
model = UnifiedNodeModel(nodes, routes, ...)

# NEW (production)
from src.optimization.sliding_window_model import SlidingWindowModel
model = SlidingWindowModel(nodes, routes, ...)
```

**Key Differences:**
1. **Variables:** Aggregate flows (not cohorts)
2. **Inventory:** 3-tuple `(node, product, date)` not 6-tuple
3. **Shelf life:** Sliding window constraints (implicit age)
4. **Batch tracking:** Post-processing via FEFO allocation
5. **Performance:** 60-80× faster, 46× fewer variables

**Result Interface:** Identical (`OptimizationSolution` Pydantic schema)

---

## Technical Documentation

**Archived Documentation:**
- `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md` → moved to this archive
- Detailed mathematical formulation of cohort-tracking approach
- Complete constraint documentation
- Development history and design decisions

**Current Documentation:**
- `docs/ARCHITECTURE.md` - SlidingWindowModel architecture
- `docs/TESTING_GUIDE.md` - Testing approach and standards
- `CLAUDE.md` - Project overview (updated for SlidingWindowModel)

---

## Related Archives

**Investigations:**
- `archive/warmstart_investigation_2025_10/` - Warmstart performance research
- `archive/sliding_window_debug_2025_10_27/` - Sliding window development debug
- `archive/initial_inventory_debug_2025_11/` - Initial inventory handling fixes

**Tests:**
- `archive/tests_unified_node_model_2025_11/` - All UnifiedNodeModel tests (20 files)
- Baseline, labor, inventory, warmstart tests migrated to SlidingWindowModel

**Debug Scripts:**
- `archive/debug_scripts/` - 292 troubleshooting scripts from Phase 1-3

---

## Restoration Instructions

**If you need to restore any of these models:**

```bash
# 1. Copy file back to src/optimization/
cp archive/optimization_models_deprecated_2025_11/<filename> src/optimization/

# 2. Update src/optimization/__init__.py
# Add appropriate import/export

# 3. Restore tests
cp archive/tests_unified_node_model_2025_11/test_*.py tests/

# 4. Install dependencies
# (All dependencies already in requirements.txt)

# 5. Run tests
pytest tests/test_<modelname>*.py -v
```

**Note:** Restoring will require resolving imports and dependencies that may have been removed during cleanup.

---

## Lessons Learned

### What Worked Well
1. **Incremental development:** VerifiedSlidingWindow validated formulation step-by-step
2. **Cohort tracking:** UnifiedNodeModel provided explicit batch traceability
3. **Comprehensive testing:** 40+ tests ensured robust migration
4. **Performance benchmarking:** Clear 60-80× speedup measurement

### What Didn't Work
1. **O(H³) complexity:** Cohort variables exploded with horizon length
2. **Rolling horizon:** Complexity not justified by use case at current scale
3. **Daily replanning:** Operational requirement unclear, overhead high

### Key Insights
1. **Aggregate flows sufficient:** Batch-level decisions via post-processing
2. **Sliding windows work:** Implicit age tracking maintains accuracy
3. **Warmstart limited impact:** 30-50% speedup not enough for O(H³) models
4. **Simplicity wins:** Fewer variables = faster solves = better UX

---

## Archive Maintenance

**Do Not Delete:** These files are historical reference and may be needed for:
- Research and education
- Troubleshooting edge cases
- Validating SlidingWindowModel behavior
- Future features requiring batch-level tracking

**Update Frequency:** Read-only archive (no maintenance needed)

**Last Updated:** November 9, 2025
