# D-1/D0 Timing Constraint Performance Diagnosis

## Executive Summary

The integrated production-distribution model exhibits **super-linear solve time growth** as destinations increase, despite linear growth in model size. The bottleneck is **NOT** the D-1/D0 timing constraints themselves, but rather the **dense constraint coupling** they create between production, truck loading, and shipment variables.

### Performance Cliff

| Destinations | Variables | Constraints | Solve Time | Status |
|--------------|-----------|-------------|------------|---------|
| 2            | 4,140     | 1,029       | 0.27s      | Optimal |
| 3            | 4,290     | 1,099       | 0.29s      | Optimal |
| 4            | 4,440     | 1,185       | 0.41s      | Optimal |
| 5            | 4,855     | 1,321       | 2.04s      | Optimal (5x slower!) |
| 6            | 5,010     | 1,379       | 9.70s      | Optimal (24x slower!) |
| 7            | 5,165     | 1,445       | >60s       | Timeout |
| 9            | ~5,500    | ~1,600      | >180s      | Timeout |

**Key observation:** Model size grows linearly (~3% per destination), but solve time grows exponentially (5x jump at 5 destinations, 24x at 6 destinations).

## Root Cause Analysis

### 1. LP Relaxation Quality: NOT THE ISSUE

LP relaxation is VERY tight across all problem sizes:

| Destinations | LP Objective | MIP Objective | Gap   |
|--------------|--------------|---------------|-------|
| 2            | $293,531     | $293,997      | 0.16% |
| 3            | $471,394     | $471,796      | 0.09% |
| 4            | $756,167     | $757,016      | 0.11% |
| 5            | $780,584     | $782,201      | 0.21% |

**Conclusion:** The LP relaxation is strong (<0.25% gap). The problem is NOT weak bounds on binary variables.

### 2. Constraint Count: NOT THE ISSUE

Constraint growth is linear and well-distributed:

| Constraint Type             | 2 Dest | 7 Dest | Growth |
|-----------------------------|--------|--------|--------|
| demand_satisfaction_con     | 140    | 463    | 3.31x  |
| truck_morning_timing_con    | 340    | 360    | 1.06x  |
| truck_afternoon_timing_con  | 60     | 70     | 1.17x  |
| truck_route_linking_con     | 16     | 51     | 3.19x  |
| flow_conservation_con       | 80     | 85     | 1.06x  |
| truck_capacity_con          | 176    | 187    | 1.06x  |

The timing constraints (morning + afternoon) grow only ~6%, not exponentially.

**Conclusion:** The number of timing constraints is NOT the bottleneck.

### 3. Dense Constraint Coupling: THE ACTUAL PROBLEM

The timing constraints create a **dense coupling pattern** between variables:

```
truck_load[truck, dest, prod, date] ≤ production[date-1, prod]  (morning trucks)
truck_load[truck, dest, prod, date] ≤ production[date-1, prod] + production[date, prod]  (afternoon)
```

This couples `truck_load` variables to `production` variables, which then propagates through:

1. **Truck-route linking constraint** (equality):
   ```
   sum(shipment[route, prod, date] for all routes to dest) ==
   sum(truck_load[truck, dest, prod, date] for all trucks to dest)
   ```

2. **Flow conservation constraint**:
   ```
   production[date, prod] >= sum(shipment[route, prod, ...] departing on date)
   ```

3. **Demand satisfaction constraint**:
   ```
   sum(shipment[route, prod, delivery_date] arriving at dest) >= demand[dest, prod, delivery_date]
   ```

**Result:** The timing constraints create an indirect coupling from `production` → `truck_load` → `shipment` → `demand`, forming a **densely interconnected constraint system**.

### 4. Why This Causes Exponential Solve Time

Each destination adds:
- More `shipment` variables (5 routes × 5 products × 16 dates = +400 variables)
- More `truck_load` variables (no growth if trucks already defined)
- More demand satisfaction constraints (+70 constraints)
- More truck-route linking constraints (+3 constraints × 16 dates = +48 constraints)

The constraint matrix becomes **increasingly dense** as more shipment and truck_load variables participate in multiple constraint types simultaneously. This forces the MIP solver to:

1. **Explore more branch-and-bound nodes** despite tight LP relaxation
2. **Perform more constraint propagation** to maintain feasibility
3. **Encounter more fractional solutions** in intermediate nodes that require further branching

The solver is effectively solving a **combinatorial assignment problem** (which shipments go on which trucks on which days) with complex feasibility requirements (production timing, truck capacity, demand satisfaction).

## Evidence

### Constraint Participation Analysis

Variables appearing in multiple constraint types create coupling:

| Variable     | Appears In                                      | Coupling Impact |
|--------------|-------------------------------------------------|-----------------|
| `truck_load` | timing, capacity, truck-route linking           | HIGH            |
| `production` | timing, flow conservation                       | MEDIUM          |
| `shipment`   | truck-route linking, flow conservation, demand  | HIGH            |

As destinations increase, the **number of cross-constraint variable participations** grows super-linearly, not linearly.

### Example Constraint Coupling

For destination 6104 on date 2025-06-04:

**Truck-route linking** (equality constraint):
```
shipment[route_0, ...] + shipment[route_1, ...] + shipment[route_2, ...] ==
  truck_load[truck_5, 6104, ...] + truck_load[truck_7, 6104, ...] + truck_load[truck_10, 6104, ...]
```

Each `truck_load` variable is ALSO constrained by timing:
```
truck_load[truck_7, 6104, prod, 2025-06-04] <= production[2025-06-03, prod] + production[2025-06-04, prod]
```

And production is constrained by flow conservation:
```
production[2025-06-04, prod] >= sum(all shipments departing on 2025-06-04)
```

**This creates circular coupling:** shipment → truck_load → production → shipment

## Why the Full Dataset (207 days, 9 destinations) Times Out

Full dataset characteristics:
- 207 days × 9 destinations × 5 products = 9,315 demand points
- ~45 routes (5 per destination × 9 destinations)
- ~2,000 production dates × products
- ~150,000+ constraint participations

Estimated model size:
- ~15,000 variables
- ~10,000 constraints
- But with **extremely dense coupling** through timing constraints

The solver must explore a massive search tree because:
1. Production decisions affect truck loading through timing constraints
2. Truck loading affects shipments through truck-route linking
3. Shipments affect production through flow conservation
4. All of this interacts with binary truck_used variables

## Recommended Solutions

### Option 1: Aggregate Timing Constraints (RECOMMENDED)

Instead of:
```python
truck_load[truck, dest, prod, date] <= production[date-1, prod]  # Per product
```

Aggregate over products:
```python
sum(truck_load[truck, dest, prod, date] for prod) <= sum(production[date-1, prod] for prod)
```

**Benefits:**
- Reduces timing constraints from (trucks × destinations × products × dates) to (trucks × destinations × dates)
- Eliminates per-product coupling
- Still enforces the physical constraint (can't load what hasn't been produced)

**Drawback:**
- Slightly weaker formulation (allows unrealistic product swaps in edge cases)
- May allow solutions where truck loads product A but production was all product B

### Option 2: Eliminate truck_load Variable (AGGRESSIVE)

Directly link production to shipments without intermediate truck_load variable:

```python
# Morning shipments from manufacturing depart on date d, use production from date d-1
for date in dates:
    for prod in products:
        morning_shipments_on_date_d = sum(shipment[route, prod, delivery_date]
            for route in morning_truck_routes
            for delivery_date where (delivery_date - transit_days) == date)

        morning_shipments_on_date_d <= production[date-1, prod]
```

**Benefits:**
- Removes truck_load variables entirely (saves ~3,500 variables)
- Removes truck-route linking constraints
- Directly couples production to shipments

**Drawbacks:**
- Loses ability to model truck capacity per truck
- Harder to interpret solutions
- More complex constraint formulation

### Option 3: Time-Aggregated Model (ALTERNATIVE FORMULATION)

Instead of day-by-day decisions, solve weekly planning periods:

- Production: Weekly totals
- Shipments: Weekly totals by route
- Truck usage: Average utilization

**Benefits:**
- Dramatically reduces time dimension (207 days → ~30 weeks)
- Reduces variables and constraints by ~80%

**Drawbacks:**
- Less granular decisions
- Cannot capture day-specific truck schedules accurately
- Requires post-processing to create daily schedules

### Option 4: Preprocessing - Fix Binary Variables (HEURISTIC)

Solve a relaxed version first, then fix fractional truck_used variables:

1. Solve LP relaxation
2. Fix truck_used[truck, date] = 1 if LP value > 0.5
3. Solve MIP with fixed binaries

**Benefits:**
- Faster solve (fewer binary decisions)
- Likely to find good solutions quickly

**Drawbacks:**
- Not guaranteed optimal
- May fix incorrect truck assignments

### Option 5: Decomposition (ADVANCED)

Separate production and distribution into two stages:

**Stage 1:** Production planning
- Minimize production cost + inventory holding
- Meet total demand by delivery date
- Output: production[date, product]

**Stage 2:** Distribution planning (given production)
- Take production from Stage 1 as input
- Minimize transport cost
- Assign shipments to trucks and routes
- Timing constraints become data, not constraints

**Benefits:**
- Breaks dense coupling
- Each subproblem much faster
- Can iterate if needed

**Drawbacks:**
- Not globally optimal (loses cost trade-offs)
- Requires iteration logic
- More complex implementation

## Immediate Actions

### Test Option 1: Aggregated Timing Constraints

Modify timing constraints in `integrated_model.py` lines 1120-1167:

**Current (per-product):**
```python
def truck_morning_timing_rule(model, truck_idx, dest, departure_date, prod):
    truck = self.truck_by_index[truck_idx]
    if truck.departure_type != 'morning':
        return Constraint.Skip

    d_minus_1 = departure_date - timedelta(days=1)
    if d_minus_1 not in model.dates:
        return model.truck_load[truck_idx, dest, prod, departure_date] == 0

    return model.truck_load[truck_idx, dest, prod, departure_date] <= model.production[d_minus_1, prod]
```

**Proposed (aggregated):**
```python
def truck_morning_timing_rule(model, truck_idx, dest, departure_date):
    truck = self.truck_by_index[truck_idx]
    if truck.departure_type != 'morning':
        return Constraint.Skip

    d_minus_1 = departure_date - timedelta(days=1)
    if d_minus_1 not in model.dates:
        return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

    return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
            sum(model.production[d_minus_1, p] for p in model.products))
```

**Expected improvement:** 5x reduction in timing constraints (340 → 68 for morning trucks)

### Test Option 4: Fix Truck Usage Heuristically

For testing only, pre-fix all trucks to run every day:

```python
for truck_idx in model.trucks:
    for date in model.dates:
        model.truck_used[truck_idx, date].fix(1)
```

This eliminates binary variables from the problem, converting it to pure LP.

**Expected improvement:** Should solve in <1s for full dataset if binaries are the issue

## Testing Plan

1. **Baseline:** Confirm 6 destinations takes 9.7s (DONE)
2. **Test aggregated timing:** Implement Option 1, measure solve time
3. **Test fixed binaries:** Implement Option 4, measure solve time
4. **Analyze results:** Determine if timing constraint coupling or binary branching is dominant factor
5. **Choose solution:** Based on test results and accuracy requirements

## Success Criteria

Target: Full dataset (207 days, 9 destinations, 5 products) solves in <60 seconds

- **Acceptable:** 30-60 seconds
- **Good:** 10-30 seconds
- **Excellent:** <10 seconds

Current baseline: >600 seconds (timeout)

## Files for Implementation

- **src/optimization/integrated_model.py** (lines 1120-1167): Timing constraint formulation
- **test_performance_diagnostic.py**: Progressive test suite
- **test_model_diagnostics.py**: Constraint analysis
- **test_lp_relaxation.py**: LP relaxation quality testing
- **test_constraint_analysis.py**: Coupling pattern analysis
