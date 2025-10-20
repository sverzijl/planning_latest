# Warmstart User Guide

**Feature:** Campaign-Based Warmstart for Binary MIP Variables
**Status:** Production Ready (2025-10-19)
**Expected Benefit:** 20-40% faster solve times for large optimization problems

---

## What is Warmstart?

**Warmstart** is an optimization technique that provides the solver with an initial "hint" solution to start from, rather than starting completely from scratch. This can significantly reduce the time it takes to find an optimal solution.

**Analogy:** Think of it like GPS navigation - if you give the GPS a suggested route to start with, it can often find the best route faster than if it has to explore all possibilities from zero.

---

## When to Use Warmstart

### RECOMMENDED for:

- Large planning horizons (3+ weeks or 21+ days)
- Problems with many products (5+ SKUs)
- Situations where solve time is a bottleneck
- Production planning with steady, predictable demand patterns
- Cases where you're willing to accept 1-2 seconds of overhead for potential significant speedup

### NOT RECOMMENDED for:

- Small problems (< 2 weeks, < 3 products) - overhead may exceed benefit
- Highly variable or sporadic demand patterns
- Quick experiments or testing where fast turnaround is critical
- Cases where solve time is already acceptable (<30 seconds)

---

## How to Enable Warmstart

### Option 1: In Python Code

```python
from src.optimization.unified_node_model import UnifiedNodeModel

# Create model as usual
model = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=truck_schedules,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

# Solve with warmstart enabled
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=300,
    mip_gap=0.01,
    use_warmstart=True,  # <--- ENABLE WARMSTART
    tee=False,
)
```

### Option 2: Custom Warmstart Hints

If you have domain knowledge about a good production schedule, you can provide custom hints:

```python
from src.optimization.warmstart_generator import generate_campaign_warmstart

# Generate custom hints
custom_hints = generate_campaign_warmstart(
    demand_forecast=demand_dict,
    manufacturing_node_id='6122',
    products=['PROD_001', 'PROD_002', 'PROD_003'],
    start_date=date(2025, 10, 13),
    end_date=date(2025, 11, 9),
    max_daily_production=19600,
    target_skus_per_weekday=3,  # Produce 3 SKUs per weekday
    freshness_days=7,  # Weekly production requirement
)

# Solve with custom hints
result = model.solve(
    solver_name='cbc',
    use_warmstart=True,
    warmstart_hints=custom_hints,  # <--- CUSTOM HINTS
)
```

---

## How It Works

### Algorithm: DEMAND_WEIGHTED Campaign Pattern

The warmstart generator analyzes demand and creates a weekly production campaign:

1. **Aggregate weekly demand** by product
2. **Calculate demand share** (percentage of total demand)
3. **Allocate production days** proportionally:
   - High-demand products get more weekdays (e.g., 5 days/week)
   - Medium-demand products get moderate days (e.g., 3 days/week)
   - Low-demand products get fewer days (e.g., 1 day/week)
4. **Balance weekday loading** (target: 2-3 SKUs per weekday)
5. **Minimize weekend production** (use only if capacity insufficient)
6. **Extend pattern** across multi-week planning horizon

### Example Pattern

For 5 products with varying demand:

```
Product   Demand Share   Weekdays/Week   Pattern
PROD_001  35%            5 days          Mon, Tue, Wed, Thu, Fri
PROD_002  25%            4 days          Mon, Tue, Thu, Fri
PROD_003  20%            3 days          Mon, Wed, Fri
PROD_004  15%            2 days          Tue, Thu
PROD_005  5%             1 day           Wed
```

Result: Balanced loading with ~3 SKUs per weekday, zero weekend production.

---

## Performance Expectations

### Warmstart Overhead

- **Generation time:** < 1 second (negligible)
- **Application time:** < 0.1 seconds
- **Total overhead:** ~1 second

### Expected Speedup

| Problem Size | Without Warmstart | With Warmstart | Speedup |
|--------------|-------------------|----------------|---------|
| 2-week, 3 products | 15 seconds | 12 seconds | 20% |
| 4-week, 5 products | 120 seconds | 70-90 seconds | 25-40% |
| 8-week, 5 products | >300 seconds (timeout) | 180-240 seconds | 20-40% |

**Note:** Actual speedup depends on problem characteristics, solver version, and hardware.

---

## Troubleshooting

### Issue: Warmstart Makes Solving SLOWER

**Symptoms:**
- Solve time increases by 5-15% with warmstart enabled
- CBC solver logs show warmstart rejected or ignored

**Possible Causes:**
1. Warmstart pattern is poor quality for your specific problem
2. Problem is too small (warmstart overhead exceeds benefit)
3. Demand pattern is too irregular for campaign approach

**Solution:**
Disable warmstart and use default CBC behavior:
```python
result = model.solve(use_warmstart=False)
```

---

### Issue: Warmstart Doesn't Speed Up Solve

**Symptoms:**
- Solve time is the same with/without warmstart
- CBC logs don't mention warmstart

**Diagnosis:**
Run with `tee=True` to see CBC output:
```python
result = model.solve(use_warmstart=True, tee=True)
```

Look for messages like:
- "MIPStart values provided" (good - warmstart received)
- "MIPStart values rejected" (warmstart infeasible)
- No warmstart message (warmstart not passed to solver - BUG)

**Solution:**
If no warmstart message appears, check that `base_model.py` passes `warmstart=use_warmstart` to `solver.solve()`. This was a critical fix applied on 2025-10-19.

---

### Issue: Warmstart Generation Fails

**Symptoms:**
- Warning: "Warmstart generation failed - <error>"
- Solver proceeds without warmstart

**Possible Causes:**
1. No demand data for products in forecast
2. Planning horizon < 7 days
3. Invalid manufacturing node ID

**Solution:**
1. Check that forecast contains demand > 0 for at least one product
2. Ensure planning horizon is at least 7 days (weekly pattern requirement)
3. Verify manufacturing node ID matches node in network

**Graceful Fallback:**
Even if warmstart generation fails, the solver will proceed normally without hints (no crash, just no speedup).

---

## Advanced Usage

### Benchmarking Warmstart Effectiveness

To measure warmstart benefit for your specific problem:

```python
import time

# Run WITHOUT warmstart
start = time.time()
result_baseline = model.solve(use_warmstart=False)
time_baseline = time.time() - start

# Run WITH warmstart
start = time.time()
result_warmstart = model.solve(use_warmstart=True)
time_warmstart = time.time() - start

# Calculate speedup
if time_warmstart < time_baseline:
    speedup = (time_baseline - time_warmstart) / time_baseline * 100
    print(f"Warmstart speedup: {speedup:.1f}% faster ({time_warmstart:.1f}s vs {time_baseline:.1f}s)")
else:
    print(f"Warmstart slower: use_warmstart=False recommended")
```

### Tuning Campaign Pattern

You can adjust the campaign pattern parameters:

```python
from src.optimization.warmstart_generator import generate_campaign_warmstart

# More SKUs per day (less changeovers, but more WIP)
hints_dense = generate_campaign_warmstart(
    ...,
    target_skus_per_weekday=4,  # Default: 3
)

# Stricter freshness (more frequent production)
hints_fresh = generate_campaign_warmstart(
    ...,
    freshness_days=5,  # Default: 7
)
```

**When to tune:**
- `target_skus_per_weekday`: Increase if you have excess capacity, decrease if changeover time is a bottleneck
- `freshness_days`: Decrease for tighter shelf life requirements, increase for more production flexibility

---

## FAQ

### Q: Does warmstart change the optimal solution?

**A:** No. Warmstart only affects HOW FAST the solver finds the optimal solution, not WHAT the optimal solution is. The final result is mathematically identical (or very close if you hit MIP gap tolerance).

### Q: Can I use warmstart with Gurobi or CPLEX?

**A:** Yes! The warmstart implementation uses standard Pyomo API that works with all commercial solvers. Gurobi and CPLEX typically benefit even more from warmstart than CBC.

### Q: What if my demand is very sporadic?

**A:** The DEMAND_WEIGHTED algorithm works best for steady demand patterns. For sporadic demand, warmstart may not be effective. Test with benchmarking (see Advanced Usage) to verify.

### Q: Can I reuse warmstart from a previous solve?

**A:** Not directly in the current implementation. However, you can extract the `product_produced` variable values from a solved model and pass them as custom hints to the next solve (rolling horizon warmstart - Phase 4 feature).

### Q: Does warmstart work for weekend production?

**A:** Yes. If total demand exceeds weekday capacity, the algorithm adds weekend production hints for the highest-demand product. However, the solver may still find a better solution without weekend production if possible.

---

## Technical Details

### Variables Warmstarted

Only **binary `product_produced[node, product, date]` variables** receive warmstart hints:

```python
# Warmstart sets:
product_produced['6122', 'PROD_001', date(2025, 10, 20)] = 1  # Produce
product_produced['6122', 'PROD_002', date(2025, 10, 20)] = 0  # Don't produce
```

**NOT warmstarted:**
- Continuous variables (production quantities, inventory, shipments)
- Derived integer variables (num_products_produced, production_day)
- Pallet count variables

**Rationale:** CBC warmstart for continuous variables is less effective and often ignored by the solver.

### Validation

Warmstart hints are validated before application:

1. All hint values are binary (0 or 1)
2. All dates are within planning horizon
3. All products are in product list
4. At least one hint per product (ensures weekly production)

Invalid hints are logged and skipped gracefully.

### Solver Compatibility

| Solver | Warmstart Support | Notes |
|--------|-------------------|-------|
| CBC | Limited | Only binary/integer variables benefit |
| GLPK | Limited | Similar to CBC |
| Gurobi | Excellent | Advanced MIP start features |
| CPLEX | Excellent | Advanced MIP start features |

---

## Getting Help

- **Technical Documentation:** `docs/UNIFIED_NODE_MODEL_SPECIFICATION.md` (Section 5)
- **Validation Report:** `docs/WARMSTART_VALIDATION_REPORT.md`
- **Test Suite:** `tests/test_unified_warmstart_integration.py`
- **Source Code:** `src/optimization/warmstart_generator.py`

For issues or questions, contact the development team or file an issue in the project repository.

---

**Last Updated:** 2025-10-19
**Version:** 1.0
**Status:** Production Ready
