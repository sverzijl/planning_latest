# Warmstart Quick Reference Card

**One-page guide to campaign-based warmstart for faster MIP solving**

---

## What is Warmstart?

Warmstart provides the MIP solver with an initial production schedule hint to start from, reducing solve time by 20-40% for large planning horizons.

**When to use:** 3+ week horizons, 5+ products, solve time >30s, steady demand

**When NOT to use:** Small problems (<2 weeks), sporadic demand, solve time <15s

---

## How to Enable

### Simple (Auto-Generated Campaign Pattern)

```python
result = model.solve(
    solver_name='cbc',
    use_warmstart=True,  # <--- Enable warmstart
)
```

### Advanced (Custom Parameters)

```python
from src.optimization.warmstart_generator import generate_campaign_warmstart

hints = generate_campaign_warmstart(
    demand_forecast=demand_dict,
    manufacturing_node_id='6122',
    products=['PROD_A', 'PROD_B', 'PROD_C'],
    start_date=date(2025, 10, 13),
    end_date=date(2025, 11, 9),
    max_daily_production=19600,
    target_skus_per_weekday=2,  # Default: 3
    freshness_days=5,            # Default: 7
)

result = model.solve(
    solver_name='cbc',
    use_warmstart=True,
    warmstart_hints=hints,  # <--- Custom hints
)
```

---

## Expected Performance

| Problem Size | Baseline | Warmstart | Speedup |
|--------------|----------|-----------|---------|
| 2 weeks, 5 SKUs | 15s | 12s | 20% |
| 4 weeks, 5 SKUs | 45s | 30-35s | 25-33% |
| 8 weeks, 5 SKUs | 180s | 120s | 33% |

**Overhead:** <1 second (negligible)

---

## Configuration Options

### Parameters

**target_skus_per_weekday** (default: 3)
- Number of SKUs produced per weekday
- Lower = fewer changeovers, longer campaigns
- Higher = more frequent production, fresher stock
- Range: 1-5

**freshness_days** (default: 7)
- Demand aggregation window for pattern generation
- Lower = more frequent production cycles
- Higher = more flexible production scheduling
- Range: 5-14

**fixed_labor_days** (optional)
- Set of dates with fixed labor (Mon-Fri typically)
- If None, assumes Mon-Fri are fixed labor days
- Excludes weekends and holidays automatically

---

## Troubleshooting

### Issue: Warmstart Makes Solving SLOWER

**Symptoms:** Solve time increases by 5-15%

**Solution:** Disable warmstart for this problem
```python
result = model.solve(use_warmstart=False)
```

**Likely Causes:**
- Problem too small (overhead exceeds benefit)
- Demand pattern too irregular for campaign approach
- Warmstart pattern is poor quality

---

### Issue: No Performance Improvement

**Symptoms:** Solve time unchanged with/without warmstart

**Diagnosis:** Check solver logs
```python
result = model.solve(use_warmstart=True, tee=True)
```

**Look for:**
- "MIPStart values provided" (good - warmstart received)
- "MIPStart values rejected" (warmstart infeasible)
- No warmstart message (warmstart not passed - BUG)

**Solution:** Verify solver flag in base_model.py (line 290)
```python
results = solver.solve(
    self.model,
    warmstart=use_warmstart,  # <<<--- Must be present
    tee=tee,
)
```

---

### Issue: Warmstart Generation Fails

**Symptoms:** Warning: "Warmstart generation failed"

**Common Causes:**
1. No demand data for products
2. Planning horizon < 7 days
3. Invalid manufacturing node ID

**Solution:** Check input data
```python
# Verify demand exists
total_demand = sum(qty for (loc, prod, date), qty in demand_forecast.items())
print(f"Total demand: {total_demand}")

# Verify planning horizon
planning_days = (end_date - start_date).days + 1
print(f"Planning horizon: {planning_days} days")
```

**Fallback:** Solver proceeds without warmstart (no crash)

---

## Performance Tuning Tips

### 1. Adjust SKU Loading

**Problem:** Too many changeovers
```python
hints = generate_campaign_warmstart(..., target_skus_per_weekday=2)
```

**Problem:** Not enough production frequency
```python
hints = generate_campaign_warmstart(..., target_skus_per_weekday=4)
```

### 2. Tune Freshness Window

**Problem:** Stock aging issues
```python
hints = generate_campaign_warmstart(..., freshness_days=5)  # Tighter
```

**Problem:** Too frequent production
```python
hints = generate_campaign_warmstart(..., freshness_days=10)  # Relaxed
```

### 3. Benchmark Effectiveness

```python
import time

# Without warmstart
start = time.time()
result_baseline = model.solve(use_warmstart=False)
time_baseline = time.time() - start

# With warmstart
start = time.time()
result_warmstart = model.solve(use_warmstart=True)
time_warmstart = time.time() - start

# Calculate speedup
speedup = (time_baseline - time_warmstart) / time_baseline * 100
print(f"Speedup: {speedup:.1f}%")

if speedup >= 20:
    print("✅ WARMSTART EFFECTIVE - Keep enabled")
elif speedup > 0:
    print("~ WARMSTART MARGINAL - Test more scenarios")
else:
    print("❌ WARMSTART INEFFECTIVE - Disable for this problem")
```

---

## Technical Details

### Variables Warmstarted

**Only binary variables:**
- `product_produced[node, product, date]` ∈ {0, 1}

**NOT warmstarted:**
- Continuous variables (production quantities, inventory, shipments)
- Derived integer variables (num_products_produced, production_day)
- Pallet count variables

**Rationale:** CBC warmstart for continuous variables less effective

### Validation Checks

Automatic validation before application:
1. ✅ All hint values are binary (0 or 1)
2. ✅ All dates within planning horizon
3. ✅ All products in product list
4. ✅ At least one hint per product

Invalid hints logged and skipped gracefully.

### Solver Compatibility

| Solver | Support | Notes |
|--------|---------|-------|
| CBC | Limited | Binary/integer variables only |
| GLPK | Limited | Similar to CBC |
| Gurobi | Excellent | Full MIP start support |
| CPLEX | Excellent | Full MIP start support |

---

## FAQ

**Q: Does warmstart change the optimal solution?**
A: No. Warmstart only affects speed, not the final result.

**Q: Can I reuse warmstart from a previous solve?**
A: Not yet (Phase 4 feature). Currently generates fresh each time.

**Q: What if my demand is sporadic?**
A: Warmstart may not help. Use benchmarking to verify benefit.

**Q: Does warmstart work for weekend production?**
A: Yes. If demand exceeds weekday capacity, algorithm adds weekend hints.

**Q: Can I manually edit warmstart hints?**
A: Yes. Pass custom hints dictionary to `solve()` method.

---

## Getting Help

**Documentation:**
- User Guide: `docs/features/WARMSTART_USER_GUIDE.md`
- Technical Spec: `docs/WARMSTART_DESIGN_SPECIFICATION.md`
- Validation Report: `docs/WARMSTART_VALIDATION_REPORT.md`

**Code:**
- Algorithm: `src/optimization/warmstart_generator.py`
- Integration: `src/optimization/unified_node_model.py`
- Tests: `tests/test_unified_warmstart_integration.py`

**Support:**
- File GitHub issue with label `warmstart`
- Include problem size and solver logs
- Attach benchmark results if available

---

## Cheat Sheet

```python
# ENABLE WARMSTART (SIMPLE)
result = model.solve(use_warmstart=True)

# DISABLE WARMSTART
result = model.solve(use_warmstart=False)

# CUSTOM CAMPAIGN PATTERN
from src.optimization.warmstart_generator import generate_campaign_warmstart
hints = generate_campaign_warmstart(
    demand_forecast=demand,
    manufacturing_node_id='6122',
    products=products,
    start_date=start,
    end_date=end,
    max_daily_production=19600,
    target_skus_per_weekday=3,
    freshness_days=7,
)
result = model.solve(use_warmstart=True, warmstart_hints=hints)

# BENCHMARK WARMSTART
import time
start = time.time()
result = model.solve(use_warmstart=True)
solve_time = time.time() - start
print(f"Solve time: {solve_time:.1f}s")

# CHECK SOLVER LOGS
result = model.solve(use_warmstart=True, tee=True)
# Look for "MIPStart values provided" message

# VALIDATE HINTS
from src.optimization.warmstart_generator import validate_warmstart_hints
validate_warmstart_hints(hints, products, start_date, end_date)
```

---

**Version:** 1.0
**Date:** 2025-10-19
**Status:** Production Ready
**See Also:** `docs/features/WARMSTART_USER_GUIDE.md` for complete documentation
