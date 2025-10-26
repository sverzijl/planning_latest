# Benchmark With Demand - Analysis Report

**Date:** 2025-10-23
**Purpose:** Test model performance with actual demand data using correct date alignment

## Problem Identified

Previous benchmarks showed zero production because planning dates didn't align with forecast data:
- **Forecast data runs:** 2025-10-16 to 2027-01-09
- **Previous benchmarks used:** 2025-01-06 to 2025-02-02 (BEFORE forecast starts!)
- **Result:** Zero demand → Zero production → Trivially fast solve

## Corrected Benchmark Setup

### Date Alignment
- **Forecast start:** 2025-10-16 (first day of actual forecast data)
- **1-week horizon:** 2025-10-16 to 2025-10-22 (7 days)
- **2-week horizon:** 2025-10-16 to 2025-10-29 (14 days)
- **4-week horizon:** 2025-10-16 to 2025-11-12 (28 days)

### Configuration
- `allow_shortages=True` (model was infeasible with `False`)
- `track_batches=True`
- `enforce_shelf_life=True`
- Solver: APPSI HiGHS
- Time limit: 300 seconds (5 minutes)
- MIP gap: 1%

## Results Summary

| Horizon | Days | Solve Time | Demand (units) | Production (units) | Mixes | Objective ($) | Variables | Constraints |
|---------|------|------------|----------------|-------------------|-------|---------------|-----------|-------------|
| 1-week  | 7    | 9.3s       | 79,500         | **0**            | 101.0 | 484,438       | 4,639     | 3,546       |
| 2-week  | 14   | 72.3s      | 126,469        | **0**            | 211.0 | 588,581       | 14,838    | 10,321      |
| 4-week  | 28   | 306.4s*    | 238,217        | **0**            | —     | 876,206       | 49,896    | 31,179      |

*4-week hit time limit (not optimal, 2.35% gap)

### Variable Breakdown (1-week)
- **Continuous:** 4,303
- **Integer:** 175 (pallet counts)
- **Binary:** 161 (product selection, changeovers)
- **Total:** 4,639

## CRITICAL FINDING: Zero Production

**All horizons show ZERO production units despite positive demand!**

### Why This Happens

The `analyze_solution()` function searches for variables with `'production['` in the name, but the actual production variable in UnifiedNodeModel may be named differently. Possible explanations:

1. **Variable naming mismatch:** The model uses `mix_count` (which IS being found: 101 mixes for 1-week) but production units might be calculated differently
2. **Shortage penalty dominance:** With `allow_shortages=True`, the model may be finding it cheaper to incur shortages than to produce (unlikely but possible with zero transport costs)
3. **Variable extraction bug:** The analysis function may not be reading the correct variable names from the model

### Evidence

From solver output (1-week):
```
MIP  has 3546 rows; 4639 cols; 12609 nonzeros; 336 integer variables (161 binary)
Solving report
  Status            Optimal
  Primal bound      484438.026444
  Dual bound        479834.579445
  Gap               0.95% (tolerance: 1%)
```

The model IS solving optimally and finding integer solutions (mixes=101.0 is exactly integer). The issue is either:
- Production units are stored in a different variable than `production[...]`
- The relationship between `mix_count` and `production` units isn't being captured correctly

### Recommendations

1. **Fix variable extraction:** Update `analyze_solution()` to correctly read production units from the model
   - Check actual variable names in UnifiedNodeModel
   - Production might be: `production_units`, `total_production`, or calculated from `mix_count * units_per_mix`

2. **Verify shortage behavior:** Check if model is truly satisfying demand with zero production (impossible) or if shortages are being recorded

3. **Add diagnostic output:** Print all variable names with non-zero values to identify correct naming

4. **Test with `allow_shortages=False`:** The model was infeasible with this setting, which suggests:
   - The planning window may be too constrained (starting on Wednesday Oct 16)
   - Initial inventory may be required
   - Some constraint may be overly restrictive

## Performance Observations

### Solve Times
- **1-week:** 9.3s (excellent)
- **2-week:** 72.3s (acceptable)
- **4-week:** 306.4s (hit time limit, found feasible solution at 2.35% gap)

### Scaling
- Variables grow ~3x per week (4.6k → 14.8k → 49.9k)
- Solve time grows ~8x per week (9s → 72s → 306s)
- Suggests O(n²) to O(n³) complexity with horizon length

### Solver Performance (1-week)
```
Src  Proc. InQueue |  Leaves   Expl. | BestBound       BestSol              Gap
 J       0       0         0   0.00%   -inf            795003.47681       Large
 R       0       0         0   0.00%   437069.928596   771222.202239     43.33%
 L       0       0         0   0.00%   463383.495829   486696.670154      4.79%
 L       0       0         0   0.00%   463647.220171   486278.482272      4.65%
        11       0         1 100.00%   479834.579445   484438.026444      0.95%
```

HiGHS found good heuristic solutions quickly (Feasibility jump, Randomized rounding, Sub-MIP), then closed gap efficiently.

## Data Validation

### Demand Coverage
- **1-week:** 280 demand entries, 79,500 units total
- **2-week:** 440 demand entries, 126,469 units total
- **4-week:** 840 demand entries, 238,217 units total

Demand data is correctly loaded and within planning horizons.

### Network Configuration
- **Nodes:** 11 (1 manufacturing, 8 demand, 2 hubs + Lineage)
- **Routes:** 10
- **Truck schedules:** 11
- **Products:** 5

All network data loaded correctly from:
- `data/examples/Gfree Forecast.xlsm`
- `data/examples/Network_Config.xlsx`

## Warnings

The model generates a warning about zero cost parameters:
```
Zero cost parameters detected: All route transport costs are 0,
ambient storage costs are 0.
```

This explains why Network_Config.xlsx has zero transport costs - it's intentional for testing labor cost isolation. However, this may contribute to unexpected behavior with shortages.

## Next Steps

1. **Fix production variable extraction** to get accurate production quantities
2. **Investigate infeasibility** with `allow_shortages=False` on Oct 16 start date
3. **Test with earlier start date** (e.g., Monday Oct 13) to see if feasibility improves
4. **Add detailed variable dump** to understand what the model is actually deciding
5. **Validate demand satisfaction** - if production is truly zero, where are shortages being recorded?

## Files Generated

- `benchmark_with_demand.py` - Benchmark script
- `benchmark_with_demand_results.txt` - Detailed numeric results
- `benchmark_with_demand_output.txt` - Full solver output
- `BENCHMARK_WITH_DEMAND_ANALYSIS.md` - This analysis document
