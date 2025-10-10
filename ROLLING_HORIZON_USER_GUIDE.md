# Rolling Horizon Solver - User Guide

## Overview

The Rolling Horizon Solver enables solving large-scale production planning problems (weeks to months) that are completely infeasible with single-shot optimization. It combines two powerful techniques:

1. **Rolling Horizon:** Break large problems into overlapping windows
2. **Temporal Aggregation:** Reduce time granularity to decrease binary variables

## Quick Start

### Basic Usage

```python
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.time_period import BucketGranularity, VariableGranularityConfig
from src.optimization import RollingHorizonSolver

# Load data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next(loc for loc in locations if loc.type == 'manufacturing')
forecast = forecast_parser.parse_forecast()

# Create solver
solver = RollingHorizonSolver(
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    window_size_days=28,  # 4 weeks
    overlap_days=7,  # 1 week
    time_limit_per_window=180,  # 3 minutes per window
)

# Configure temporal aggregation (RECOMMENDED)
granularity_config = VariableGranularityConfig(
    near_term_days=7,  # Week 1: daily precision
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,  # Rest: 3-day buckets
)

# Solve
result = solver.solve(
    forecast=forecast,
    granularity_config=granularity_config,
    solver_name='cbc',
    verbose=True
)

# Check results
if result.all_feasible:
    print(f"✅ Success! Cost: ${result.total_cost:,.2f}")
    print(f"Solve time: {result.total_solve_time:.1f}s")
    print(f"Windows: {result.num_windows}")
else:
    print(f"❌ Some windows infeasible: {result.infeasible_windows}")
```

## Configuration Guide

### Window Configuration

**Window Size** (`window_size_days`)
- **14 days (2 weeks):** Many small windows, faster per-window, more overhead
- **21 days (3 weeks):** Balanced approach, good for medium horizons
- **28 days (4 weeks):** Recommended for long horizons, fewer windows
- **35+ days:** May timeout even with aggregation

**Overlap** (`overlap_days`)
- **3-5 days:** Minimal overlap, faster, less lookahead
- **7 days (1 week):** Recommended balance
- **14 days (2 weeks):** Maximum lookahead, slower, better quality

**Rule of Thumb:** Overlap should be 20-35% of window size.

### Temporal Aggregation Strategies

#### Strategy 1: Balanced (Recommended)

```python
VariableGranularityConfig(
    near_term_days=7,  # Week 1 daily
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)
```

**Best for:** Most production planning problems
**Performance:** 5-15s per window (21-28 day windows)
**Quality:** Excellent near-term precision, good far-term

#### Strategy 2: Speed-Optimized

```python
VariableGranularityConfig(
    near_term_days=0,  # No daily period
    near_term_granularity=BucketGranularity.THREE_DAY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)
```

**Best for:** Very long horizons (6+ months), rough planning
**Performance:** 2-5s per window
**Quality:** Good approximation, may miss day-specific patterns

#### Strategy 3: Quality-Optimized

```python
VariableGranularityConfig(
    near_term_days=14,  # 2 weeks daily
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.TWO_DAY,
)
```

**Best for:** Short-medium horizons (4-12 weeks), high precision needed
**Performance:** 15-30s per window
**Quality:** Excellent throughout

### Solver Parameters

**Time Limit Per Window** (`time_limit_per_window`)
- **60s:** Minimum for 21-28 day windows with aggregation
- **120s:** Safe default
- **180s:** Generous, handles difficult windows
- **300s:** Maximum recommended

**MIP Gap** (`mip_gap`)
- **0.01 (1%):** Default, near-optimal solutions
- **0.05 (5%):** Faster, acceptable for production
- **0.10 (10%):** Very fast, rough solutions

**Allow Shortages** (`allow_shortages`)
- **True (recommended):** Solver can report infeasible demand explicitly
- **False:** Solver fails if any demand cannot be met

## Performance Expectations

### Problem Size vs Solve Time

| Horizon | Windows | Per-Window Time | Total Time | Status |
|---------|---------|-----------------|------------|--------|
| 3 weeks (21 days) | 1 | 5-15s | 5-15s | ✅ |
| 6 weeks (42 days) | 2-3 | 5-15s | 15-45s | ✅ |
| 12 weeks (84 days) | 4-5 | 5-15s | 30-75s | ✅ |
| 29 weeks (203 days) | 7-8 | 10-20s | 70-160s | ✅ |

*Assumes: 28-day windows, 7-day overlap, balanced aggregation strategy*

### Without Rolling Horizon

| Horizon | Binary Vars | Solve Time | Status |
|---------|-------------|------------|--------|
| 14 days | ~200 | 2-3s | ✅ Feasible |
| 21 days | ~300 | >60s | ❌ Timeout |
| 42 days | ~600 | Infeasible | ❌ |
| 203 days | ~2,856 | Infeasible | ❌ |

### Binary Variable Reduction

**Without aggregation:**
- 21-day window: 300 binary vars → >60s timeout

**With 3-day aggregation:**
- 21-day window: ~100 binary vars → 5-15s ✅
- **67% reduction in binary variables**

**With variable granularity (week 1 daily, rest 3-day):**
- 21-day window: 7 + 5 = 12 periods → ~130 binary vars → 8-20s ✅
- **57% reduction in binary variables**

## Interpreting Results

### RollingHorizonResult

```python
result = solver.solve(...)

# Check feasibility
if result.all_feasible:
    print("All windows solved")
else:
    print(f"Infeasible windows: {result.infeasible_windows}")

# Performance metrics
print(f"Total solve time: {result.total_solve_time:.1f}s")
print(f"Average per window: {result.average_solve_time_per_window:.1f}s")
print(f"Number of windows: {result.num_windows}")

# Solution quality
print(f"Total cost: ${result.total_cost:,.2f}")
print(f"Production days: {len(result.complete_production_plan)}")
print(f"Total shipments: {len(result.complete_shipment_plan)}")

# Per-window details
for ws in result.window_results:
    print(f"{ws.window_id}: {ws.solve_time_seconds:.1f}s, ${ws.total_cost:,.0f}")
```

### Production Plan

```python
# Access complete production plan (stitched across windows)
for prod_date, products in sorted(result.complete_production_plan.items()):
    total = sum(products.values())
    print(f"{prod_date}: {total:,.0f} units")

# Calculate total production
total_production = sum(
    sum(products.values())
    for products in result.complete_production_plan.values()
)
```

### Shipment Plan

```python
# Access shipments
for shipment in result.complete_shipment_plan:
    print(f"{shipment.delivery_date}: {shipment.quantity:,.0f} units to {shipment.destination_id}")

# Calculate demand satisfaction
total_shipped = sum(s.quantity for s in result.complete_shipment_plan)
satisfaction_pct = total_shipped / total_demand * 100
print(f"Demand satisfaction: {satisfaction_pct:.1f}%")
```

## Troubleshooting

### Problem: Windows timing out

**Symptoms:** Solve time exceeds `time_limit_per_window`

**Solutions:**
1. Use coarser temporal aggregation (weekly buckets)
2. Reduce window size (28 → 21 days)
3. Increase time limit (120 → 180s)
4. Relax MIP gap (1% → 5%)

### Problem: Some windows infeasible

**Symptoms:** `result.all_feasible == False`

**Solutions:**
1. Enable `allow_shortages=True` to identify demand issues
2. Check capacity in infeasible window dates
3. Increase window size for more flexibility
4. Review initial inventory for first window
5. Check for data issues (missing routes, impossible demands)

### Problem: Poor demand satisfaction

**Symptoms:** `<95%` of demand met

**Solutions:**
1. Review shortage variables to identify bottlenecks
2. Check capacity constraints (production, trucks)
3. Verify route availability and shelf life limits
4. Increase window overlap for better coordination

### Problem: High solve time variance across windows

**Symptoms:** Some windows solve in 5s, others in 60s

**Solutions:**
1. Identify problem windows and examine their characteristics
2. Windows with high utilization are naturally slower
3. Public holidays reduce capacity → harder windows
4. Consider uniform temporal aggregation (no variable granularity)

### Problem: Large cost differences between windows

**Symptoms:** Window costs vary by 10x

**Solutions:**
1. Normal - reflects demand variation across time
2. Check for unrealistic shortcuts (excess inventory)
3. Review ending inventory values (too high?)
4. Verify cost parameters are correct

## Advanced Usage

### Custom Initial Inventory

```python
initial_inventory = {
    ('6103', 'P1'): 500,  # 500 units of P1 at destination 6103
    ('6105', 'P2'): 300,
}

result = solver.solve(
    forecast=forecast,
    initial_inventory=initial_inventory,
    ...
)
```

### Different Aggregation Per Window

```python
# Create custom solver that varies aggregation by window
class AdaptiveRollingHorizonSolver(RollingHorizonSolver):
    def _solve_window(self, window, granularity_config, solver_name, verbose):
        # Use finer granularity for near-term windows
        if window.is_first_window:
            granularity = VariableGranularityConfig(
                near_term_days=14,
                near_term_granularity=BucketGranularity.DAILY,
                far_term_granularity=BucketGranularity.TWO_DAY,
            )
        else:
            granularity = granularity_config

        return super()._solve_window(window, granularity, solver_name, verbose)
```

### Extracting Window-Specific Results

```python
result = solver.solve(...)

# Get results for specific window
window_2 = result.window_results[1]  # Second window

print(f"Window 2 production:")
for date, products in window_2.production_by_date_product.items():
    print(f"  {date}: {sum(products.values()):,.0f} units")

print(f"Window 2 ending inventory:")
for (dest, prod), qty in window_2.ending_inventory.items():
    print(f"  {dest} - {prod}: {qty:,.0f} units")
```

## Validation Checklist

Before using results in production:

- [ ] `result.all_feasible == True`
- [ ] `result.total_solve_time < target` (e.g., <300s)
- [ ] Demand satisfaction ≥ 95%
- [ ] Production/demand ratio reasonable (0.95 - 1.10)
- [ ] No excessive inventory buildup
- [ ] Cost magnitude reasonable
- [ ] All shipments have valid delivery dates
- [ ] Inventory continuity validated (no gaps)

## Recommended Configurations

### For Daily Production Use (29 weeks)

```python
solver = RollingHorizonSolver(
    window_size_days=28,
    overlap_days=7,
    time_limit_per_window=180,
    mip_gap=0.01,
    allow_shortages=True,
)

granularity_config = VariableGranularityConfig(
    near_term_days=7,
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)

result = solver.solve(forecast, granularity_config=granularity_config)
```

**Expected:** 70-160s total, 99%+ demand satisfaction

### For Weekly Review (12 weeks)

```python
solver = RollingHorizonSolver(
    window_size_days=21,
    overlap_days=7,
    time_limit_per_window=120,
    mip_gap=0.05,
    allow_shortages=True,
)

granularity_config = VariableGranularityConfig(
    near_term_days=14,
    near_term_granularity=BucketGranularity.DAILY,
    far_term_granularity=BucketGranularity.TWO_DAY,
)

result = solver.solve(forecast, granularity_config=granularity_config)
```

**Expected:** 30-75s total, 99%+ demand satisfaction

### For Quick What-If Analysis (6 weeks)

```python
solver = RollingHorizonSolver(
    window_size_days=21,
    overlap_days=5,
    time_limit_per_window=60,
    mip_gap=0.10,
    allow_shortages=True,
)

# Uniform 3-day aggregation for speed
granularity_config = VariableGranularityConfig(
    near_term_days=0,
    near_term_granularity=BucketGranularity.THREE_DAY,
    far_term_granularity=BucketGranularity.THREE_DAY,
)

result = solver.solve(forecast, granularity_config=granularity_config)
```

**Expected:** 10-20s total, 95%+ demand satisfaction

## Comparison to Single-Shot Optimization

| Feature | Single-Shot | Rolling Horizon |
|---------|-------------|-----------------|
| Max feasible horizon | ~14 days | Unlimited |
| Solve time (29 weeks) | Infeasible | 1-3 minutes |
| Binary variables | All periods | Per window |
| Memory usage | Very high | Moderate |
| Solution quality | Optimal (when feasible) | Near-optimal |
| Temporal aggregation | Compatible | Compatible |
| Inventory handoff | N/A | Automated |
| Parallelization | No | Possible (future) |

## Tips for Best Results

1. **Start with default configuration** - Works for most problems
2. **Use temporal aggregation** - Always apply 3-day aggregation minimum
3. **Monitor per-window performance** - Identify problem windows early
4. **Allow shortages initially** - Understand capacity vs demand
5. **Tune window size** - Larger windows = fewer solves, but slower per-window
6. **Validate solutions** - Check demand satisfaction and cost reasonableness
7. **Save results** - Store complete plans for analysis and comparison

## Getting Help

If you encounter issues:

1. Check error messages in `result.window_results[i].optimization_result.infeasibility_message`
2. Enable `verbose=True` for detailed progress
3. Review window-specific statistics for anomalies
4. Test with smaller horizon first (6 weeks)
5. Try different aggregation strategies
6. Consult `ROLLING_HORIZON_IMPLEMENTATION_STATUS.md` for technical details

## Files and Documentation

- **User Guide:** `ROLLING_HORIZON_USER_GUIDE.md` (this file)
- **Implementation Status:** `ROLLING_HORIZON_IMPLEMENTATION_STATUS.md`
- **Code:**
  - `src/optimization/rolling_horizon_solver.py`
  - `src/optimization/window_config.py`
  - `src/models/time_period.py`
  - `src/models/forecast_aggregator.py`

- **Tests:**
  - `test_rolling_horizon_6weeks_aggregated.py`
  - `test_rolling_horizon_29weeks.py`
  - `test_temporal_aggregation_week3.py`

## Next Steps

1. Run `test_rolling_horizon_6weeks_aggregated.py` to validate setup
2. Run `test_rolling_horizon_29weeks.py` for full dataset validation
3. Customize configuration for your specific needs
4. Integrate into production workflow
5. Monitor performance and adjust parameters as needed
