# Sparse Indexing Performance Analysis

## Executive Summary

**Implementation:** Successfully implemented sparse truck variable indexing to eliminate 72.7% of truck_load variables that were previously created but always forced to zero.

**Result:** Sparse indexing provides **modest improvement** for small horizons but **does NOT solve the fundamental performance cliff** at 3+ weeks.

**Conclusion:** Symmetry-breaking constraints or alternative approaches (aggregation, fix-and-optimize) are required to make the full 29-week dataset solvable.

---

## Problem Identified

**Wasteful Variable Creation:**
- 73% of truck_load variables were created for invalid truck→destination pairs
- Example: `truck_load[truck_0, 6104, *, *]` created even though truck_0 only serves 6125
- These variables were always forced to zero by constraints but still consumed solver resources

**Root Cause:**
- Dense indexing: Created variables for ALL (truck × destination × product × date) combinations
- Sparse indexing: Create variables ONLY for valid (truck, destination) pairs based on truck schedules

---

## Implementation Details

### Changes to `src/optimization/integrated_model.py`

**1. Valid Truck-Destination Pair Enumeration (lines 799-815):**
```python
# SPARSE INDEXING: Create list of valid (truck, destination) pairs
valid_truck_dest_pairs = []
for truck_idx in self.truck_indices:
    truck = self.truck_by_index[truck_idx]
    # Primary destination
    valid_dests = {truck.destination_id}
    # Intermediate stops (e.g., Lineage on Wednesday route)
    if truck_idx in self.trucks_with_intermediate_stops:
        valid_dests.update(self.trucks_with_intermediate_stops[truck_idx])

    for dest in valid_dests:
        valid_truck_dest_pairs.append((truck_idx, dest))
```

**2. Sparse Variable Definition (lines 826-839):**
```python
# Before (dense):
model.truck_load = Var(
    model.trucks,              # 11 trucks
    model.truck_destinations,  # 4 destinations
    model.products,
    model.dates,
    ...
)
# Creates 11 × 4 × products × dates variables

# After (sparse):
model.truck_load = Var(
    valid_truck_dest_pairs,    # Only 12 valid pairs
    model.products,
    model.dates,
    ...
)
# Creates 12 × products × dates variables (72.7% reduction)
```

**3. Updated Constraints:**
- `truck_capacity_rule` - Only sum over destinations the truck actually serves
- `truck_route_linking_rule` - Iterate over valid pairs only
- `truck_d0_timing_rule`, `truck_d1_timing_rule` - Filter by valid pairs
- Objective function - Sum only over valid truck-destination combinations
- Solution extraction - Extract values only for valid pairs

**4. Verification:**
- All 432 tests pass ✅
- Same optimal objective values as before ✅
- Correct solution structure ✅

---

## Performance Results

### Model Size Comparison (2-week horizon)

| Metric | Dense Indexing | Sparse Indexing | Reduction |
|--------|----------------|-----------------|-----------|
| **truck_load variables** | 3,960 | 1,080 | **72.7%** ✅ |
| **Total variables** | 6,588 | 3,708 | **43.7%** ✅ |
| **Binary variables** | 216 | 216 | 0% |
| **Constraints** | ~1,800 | ~1,800 | ~0% |

### Solve Time Comparison

| Horizon | Dense Time | Sparse Time | Speedup | Status |
|---------|------------|-------------|---------|--------|
| **1 week** | 1.42s | 1.07s | **1.33x** ✅ | Optimal |
| **2 weeks** | 2.79s | 2.97s | **0.94x** ❌ | Optimal |
| **3 weeks** | >120s timeout | >90s timeout | **No improvement** ❌ | Timeout |

### Key Findings

1. **Week 1: Modest Speedup**
   - 1.33x faster (1.42s → 1.07s)
   - Variable reduction helps slightly

2. **Week 2: Slight Slowdown**
   - 0.94x slower (2.79s → 2.97s)
   - Could be solver randomness or different branching decisions
   - Variable reduction offset by other factors

3. **Week 3: Still Hits Performance Cliff**
   - Still cannot solve within reasonable time
   - Sparse indexing did NOT eliminate the exponential growth
   - Symmetry remains the dominant bottleneck

---

## Why Sparse Indexing Isn't Enough

### The Symmetry Problem Remains

**Symmetric Truck Assignments:**
- Destination 6125: **5 trucks** → 5! = **120 equivalent orderings**
- Destination 6104: **3 trucks** → 3! = **6 equivalent orderings**
- Destination 6110: **3 trucks** → 3! = **6 equivalent orderings**

**Example:**
```
# Both solutions are equivalent (same cost, same constraints):

Solution A:
  truck_load[truck_0, 6125, 168846, 2025-06-03] = 5000
  truck_load[truck_1, 6125, 168846, 2025-06-03] = 0

Solution B:
  truck_load[truck_0, 6125, 168846, 2025-06-03] = 0
  truck_load[truck_1, 6125, 168846, 2025-06-03] = 5000

# CBC explores BOTH branches despite identical cost!
```

**Impact:**
- Sparse indexing reduced the NUMBER of variables
- But did NOT reduce the NUMBER of symmetric solutions
- Solver still explores factorial orderings of truck assignments
- This creates exponential growth: 2.92x slowdown per week

---

## Recommendations

### 1. **Implement Symmetry-Breaking Constraints** (Next Step)

**Lexicographic Ordering:**
```python
# For trucks serving same destination on same day:
# Force trucks to be used in numerical order

if truck_used[i, date] == 0:
    then truck_used[i+1, date] == 0

# Example: If truck_0 is not used, truck_1 cannot be used
# Eliminates all 120 orderings except one canonical ordering
```

**Expected Impact:**
- 3-5x speedup on top of current sparse indexing
- Week 3: ~90s → ~20-30s
- Week 6: May become solvable in 2-3 minutes

**Implementation Complexity:** Medium (requires Pyomo disjunctive constraints or big-M formulation)

### 2. **Aggregation Approach** (Alternative)

**Concept:**
- Don't model individual truck assignments
- Model only total shipments to each destination
- Post-process: Assign products to specific trucks using greedy heuristic

**Expected Impact:**
- 10-100x speedup (eliminates all truck symmetry)
- Full 29-week dataset may become solvable in minutes

**Trade-off:**
- Simpler optimization problem
- May miss some truck loading optimizations
- Requires post-processing step

### 3. **Fix-and-Optimize** (Hybrid Approach)

**Concept:**
- Phase 1: Use heuristic to pre-assign trucks (greedy fill)
- Phase 2: Fix truck assignments, optimize production quantities (LP)
- Phase 3: Local search to improve truck assignments

**Expected Impact:**
- 100-1000x speedup (converts MIP to LP)
- Guaranteed fast solve times
- Near-optimal solutions with good heuristics

**Trade-off:**
- Not guaranteed globally optimal
- Requires heuristic development

### 4. **Commercial Solver** (If Available)

**Options:**
- Gurobi (academic license available)
- CPLEX (academic license available)

**Expected Impact:**
- 5-10x faster than CBC on same problem
- Better symmetry detection and handling
- More advanced presolve and cutting planes

**Cost:**
- Free for academic use
- Commercial licenses: $5k-50k/year

---

## Conclusion

**Sparse indexing was a good optimization:**
- ✅ Eliminates wasteful variables (72.7% reduction)
- ✅ Cleaner model structure
- ✅ Modest speedup for 1-week horizon (1.33x)
- ✅ All tests pass, correctness verified

**But it's not sufficient for the full dataset:**
- ❌ Week 3+ still hit performance cliff
- ❌ Symmetry problem remains the dominant bottleneck
- ❌ 29-week dataset still infeasible with CBC

**Next Steps (in priority order):**

1. **Implement lexicographic symmetry-breaking** (best effort/reward ratio)
   - Expected 3-5x additional speedup
   - May make 6-8 weeks solvable
   - Still may not reach 29 weeks

2. **Implement aggregation or fix-and-optimize** (if full dataset needed)
   - Expected 10-1000x speedup
   - High confidence of solving full 29 weeks
   - May sacrifice some optimality

3. **Evaluate commercial solver** (if budget allows)
   - Easiest to implement (just change solver name)
   - 5-10x speedup
   - Combine with symmetry-breaking for best results

4. **Rolling horizon** (production-ready fallback)
   - Solve 4-6 week windows sequentially
   - Guaranteed solve time (<5 min total)
   - Practical for real-world use

---

## Technical Details

### Valid Truck-Destination Pairs

For the current truck schedule, there are only **12 valid pairs** out of 44 possible (11 trucks × 4 destinations):

```
Truck 0 → 6125
Truck 1 → 6125
Truck 2 → 6125
Truck 3 → 6125
Truck 4 → 6125
Truck 5 → 6104
Truck 6 → 6110
Truck 7 → 6104
Truck 8 → 6110
Truck 9 → 6110
Truck 10 → 6104
Truck 2 (Wed) → Lineage (intermediate stop)
```

**Dense indexing:** Created variables for all 44 combinations
**Sparse indexing:** Creates variables only for these 12 valid pairs

### Solver Output Analysis (3-week test)

```
Presolve: 1200 rows, 2746 columns, 7047 elements
Binary variables: 138 (after presolve from 300)
Continuous objective: $935,658 (LP relaxation)
Feasibility pump found: $937,562 after 2.54s
Still searching for optimality at 90s...
```

**Observations:**
- LP relaxation solves quickly (0.09s)
- Found feasible solution fast (2.54s)
- Gap to optimality: ~0.2% ($937,562 vs $935,658)
- Cannot prove optimality due to symmetry exploration

---

## Files Modified

1. **`src/optimization/integrated_model.py`**
   - Added `valid_truck_dest_pairs` enumeration
   - Changed `truck_load` variable indexing from dense to sparse
   - Updated 6+ constraint functions
   - Updated objective function
   - Updated solution extraction

2. **Test Scripts Created:**
   - `verify_sparse_indexing.py` - Verification (72.7% reduction, tests pass)
   - `test_sparse_quick.py` - Quick 1-2 week comparison
   - `test_3week_sparse.py` - Deep dive on week 3 performance

3. **Documentation:**
   - This file (`SPARSE_INDEXING_RESULTS.md`)
   - Updated comments in `integrated_model.py`

---

## Appendix: Performance Data

### Detailed Results

**1-Week Horizon:**
- Variables: 2,196 (660 truck_load)
- Constraints: 1,098
- Binary: 132
- Solve time: 1.07s
- Status: Optimal
- Objective: $170,900.17

**2-Week Horizon:**
- Variables: 3,708 (1,080 truck_load)
- Constraints: 1,802
- Binary: 216
- Solve time: 2.97s
- Status: Optimal
- Objective: $483,385.13

**3-Week Horizon:**
- Variables: 5,220 (1,500 truck_load)
- Constraints: 2,505
- Binary: 300
- Solve time: >90s
- Status: Timeout (feasible solution found: $937,562, gap ~0.2%)

### Extrapolation

If we assume sparse indexing provides consistent 1.3x speedup and the exponential growth rate remains 2.92x per week:

```
Dense indexing estimate (from earlier):
  Week 29: ~11,557,813,982,587 seconds (impractical)

Sparse indexing estimate:
  Week 29: ~11,557,813,982,587 / 1.3 ≈ 8,890,626,140,000 seconds
  Still impractical (281,000 years)
```

**Conclusion:** Exponential growth dominates any constant factor improvement. Must address symmetry or change approach.
