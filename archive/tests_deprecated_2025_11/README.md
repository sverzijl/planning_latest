# Archived Test Files - November 2025

**Date Archived:** 2025-11-10
**Reason:** Tests for deprecated optimization models archived in optimization_models_deprecated_2025_11/

## Archived Test Files

### 1. test_warmstart_baseline.py
**Tested:** `src.optimization.unified_node_model.solve_weekly_pattern_warmstart()`
**Status:** Module archived - UnifiedNodeModel deprecated in favor of SlidingWindowModel

### 2. test_warmstart_enhancements.py
**Tested:** UnifiedNodeModel warmstart enhancements
**Status:** Module archived

### 3. test_warmstart_generator.py
**Tested:** `WarmstartGenerator` class
**Status:** Class doesn't exist - warmstart_generator.py now has functions only

### 4. test_weekly_pattern_warmstart.py
**Tested:** Weekly pattern warmstart for UnifiedNodeModel
**Status:** Module archived

### 5. test_daily_rolling_solver.py
**Tested:** `src.optimization.daily_rolling_solver.DailyRollingSolver`
**Status:** Module archived to optimization_models_deprecated_2025_11/

## Context

These tests were part of the UnifiedNodeModel implementation which used explicit age-cohort tracking. The SlidingWindowModel (current implementation) uses state-based aggregate flows with sliding window shelf life constraints instead, achieving 60-220× speedup.

See `archive/optimization_models_deprecated_2025_11/README.md` for details on the deprecated models.

## Restoration

If these models need to be restored:
1. Restore corresponding module from `archive/optimization_models_deprecated_2025_11/`
2. Restore test files from this archive
3. Update imports if module structure changed
