# UnifiedNodeModel Bound-Tightening Analysis

**Date:** 2025-10-17
**Model:** `src/optimization/unified_node_model.py`
**Solver:** CBC (open-source), compatible with Gurobi/CPLEX
**Typical Problem Size:** 4-week horizon, 9 breadrooms, 5 products, 10 routes

---

## Executive Summary

This analysis identifies **12 bound-tightening opportunities** in the UnifiedNodeModel that can improve solver performance. The recommendations are prioritized by expected impact and implementation complexity.

**Key Findings:**
- **3 HIGH-IMPACT** opportunities targeting the most critical variables
- **5 MEDIUM-IMPACT** opportunities for integer and binary variables
- **4 LOW-IMPACT** opportunities for refinement and edge cases
- **Estimated cumulative performance improvement:** 15-30% reduction in solve time
- **Quick wins:** 4 opportunities can be implemented in under 30 minutes each

**Current Performance:**
- 4-week horizon: 20-30s (unit-based storage), 35-45s (pallet-based storage)
- Problem dimensions: ~20,000+ continuous variables, ~18,700 integer variables (with pallet storage)
- Recent issue: Pallet-based truck loading caused Gap=100% timeout (deferred)

---

## Part 1: Current Variable Bounds Summary

### Variables WITH Explicit Bounds

| Variable | Domain | Current Bounds | Index Count (4-week) | Notes |
|----------|--------|----------------|---------------------|-------|
| `product_produced[node, prod, date]` | Continuous | `(0, 1)` | ~140 | Relaxed from Binary for performance |
| `num_products_produced[node, date]` | Integer | `(0, n_products)` | ~28 | n_products = 5 in typical case |
| `pallet_count[node, prod, prod_date, curr_date, state]` | Integer | `(0, max_pallets)` | ~18,675 | max_pallets = 1,715 (too loose!) |

**Total variables with bounds:** 3 variable types, ~18,843 instances

### Variables WITHOUT Explicit Bounds (Default: 0 to ∞)

| Variable | Domain | Default Bounds | Index Count (4-week) | Constraint Coverage |
|----------|--------|----------------|---------------------|---------------------|
| `production[node, prod, date]` | Continuous ≥0 | `(0, ∞)` | ~140 | Implicit via production_capacity_con |
| `inventory_cohort[...]` | Continuous ≥0 | `(0, ∞)` | ~18,675 | Implicit via inventory_balance_con |
| `shipment_cohort[...]` | Continuous ≥0 | `(0, ∞)` | ~5,000+ | Implicit via truck_capacity_con |
| `demand_from_cohort[...]` | Continuous ≥0 | `(0, ∞)` | ~3,000+ | Implicit via demand ≤ forecast |
| `shortage[dest, prod, date]` | Continuous ≥0 | `(0, ∞)` | ~1,260 | Implicit via demand bounds |
| `truck_used[truck_idx, date]` | Binary | `{0, 1}` | ~280 | Binary domain inherent |
| `truck_load[truck_idx, dest, prod, date]` | Continuous ≥0 | `(0, ∞)` | ~5,600 | Implicit via truck_capacity_con |
| `production_day[node, date]` | Binary | `{0, 1}` | ~28 | Binary domain inherent |
| `uses_overtime[node, date]` | Binary | `{0, 1}` | ~28 | Binary domain inherent |
| `labor_hours_used[node, date]` | Continuous ≥0 | `(0, ∞)` | ~28 | Implicit via production_capacity_con |
| `labor_hours_paid[node, date]` | Continuous ≥0 | `(0, ∞)` | ~28 | Implicit via min_hours enforcement |
| `fixed_hours_used[node, date]` | Continuous ≥0 | `(0, ∞)` | ~28 | Implicit via fixed_hours_limit_con |
| `overtime_hours_used[node, date]` | Continuous ≥0 | `(0, ∞)` | ~28 | Implicit via overtime constraint |

**Total variables without explicit bounds:** 13 variable types, ~34,000+ instances

**Key Observation:** Most variables rely on **implicit bounds** from constraints rather than **explicit bounds** in variable definitions. This can slow down the solver's preprocessing and LP relaxation phases.

---

## Part 2: Bound-Tightening Opportunities (Prioritized)

### HIGH-IMPACT Opportunities

#### **1. Production Variable Upper Bounds** (HIGHEST PRIORITY)

**Current State:**
```python
model.production = Var(
    production_index,
    within=NonNegativeReals,
    doc="Production quantity at manufacturing nodes"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Implicit constraint:** `production_capacity_con` limits via labor hours
- **Index count:** ~140 (1 node × 5 products × 28 dates)

**Problem:**
- Solver must discover upper bound through constraint propagation
- LP relaxation can explore infeasible region unnecessarily
- No per-product upper bound enforcement

**Proposed Tighter Bound:**
```python
# Calculate maximum daily production from labor calendar
max_daily_production = 19600.0  # 1,400 units/hr × 14hr max (12 fixed + 2 OT)

model.production = Var(
    production_index,
    within=NonNegativeReals,
    bounds=(0, max_daily_production),
    doc="Production quantity at manufacturing nodes"
)
```

**Justification:**
- Maximum labor hours per day: 14 hours (12 fixed + 2 OT weekday, or up to 14 hrs non-fixed day)
- Production rate: 1,400 units/hour
- Physical maximum: 19,600 units/day
- No single product can exceed this on any day
- Tighter than current implicit bound from `production_time + overhead ≤ labor_hours`

**Expected Impact:**
- **Performance:** 5-10% solve time reduction
- **LP relaxation:** Tighter feasible region, fewer simplex iterations
- **Branch-and-bound:** Better pruning for integer variables that depend on production

**Implementation:**
```python
# In build_model(), around line 314
def get_max_daily_production(self) -> float:
    """Calculate maximum possible daily production."""
    max_labor_hours = 0.0
    for date in self.production_dates:
        labor_day = self.labor_calendar.get_labor_day(date)
        if labor_day:
            day_hours = labor_day.fixed_hours + (labor_day.overtime_hours or 0.0)
            max_labor_hours = max(max_labor_hours, day_hours)

    # Get production rate from first manufacturing node
    if self.manufacturing_nodes:
        node_id = next(iter(self.manufacturing_nodes))
        node = self.nodes[node_id]
        prod_rate = node.capabilities.production_rate_per_hour or 1400.0
    else:
        prod_rate = 1400.0  # Default

    return prod_rate * max_labor_hours

# Then use in variable creation:
max_daily_prod = self.get_max_daily_production()
model.production = Var(
    production_index,
    within=NonNegativeReals,
    bounds=(0, max_daily_prod),
    doc="Production quantity at manufacturing nodes"
)
```

---

#### **2. Pallet Count Upper Bound Refinement** (HIGH PRIORITY)

**Current State:**
```python
# Line 2240-2250
max_daily_production = 19600  # units (with overtime)
planning_days = len(model.dates)
max_inventory_per_cohort = max_daily_production * planning_days
max_pallets = int(math.ceil(max_inventory_per_cohort / self.UNITS_PER_PALLET))

model.pallet_count = Var(
    model.cohort_index,
    within=NonNegativeIntegers,
    bounds=(0, max_pallets),  # max_pallets = 1,715 for 28 days!
    doc="Pallet count for inventory cohort"
)
```

**Problem:**
- **Current bound:** 1,715 pallets (19,600 × 28 / 320)
- **Physical impossibility:** No single cohort can accumulate 28 days of production
- **Why?** Cohorts are consumed to meet demand daily; they don't accumulate indefinitely
- **Overly conservative:** Bound is ~10x larger than realistic maximum

**Proposed Tighter Bound:**
```python
# More realistic bound based on maximum daily production + demand patterns
# A single cohort (production batch from one day) can at most:
# 1. Be produced in one day: ≤ max_daily_production
# 2. Age for at most shelf_life days before expiring
# 3. Be reduced by daily demand consumption

# Conservative but realistic upper bound:
max_pallets_per_cohort = int(math.ceil(max_daily_production / self.UNITS_PER_PALLET))
# For 19,600 units: max_pallets_per_cohort = 62 pallets (vs 1,715!)

model.pallet_count = Var(
    model.cohort_index,
    within=NonNegativeIntegers,
    bounds=(0, max_pallets_per_cohort),
    doc="Pallet count for inventory cohort (tightened to daily production max)"
)
```

**Justification:**
- **Cohort definition:** `inventory_cohort[node, prod, prod_date, curr_date, state]`
  - Each cohort represents inventory from ONE specific production date (prod_date)
  - Maximum quantity in cohort = maximum production on that single day = 19,600 units
  - Cannot exceed this because production only happens once per (node, prod, prod_date)
- **Mathematical bound:** 19,600 / 320 = 61.25 → 62 pallets
- **Reduction:** From 1,715 pallets to 62 pallets (27x tighter!)

**Expected Impact:**
- **Performance:** 10-20% solve time reduction for pallet-based storage problems
- **Search space:** Integer search space reduced by 96%+ per variable
- **Critical for Phase 4:** Tighter bounds may enable pallet-based truck loading (currently infeasible)
- **MIP gap:** Faster convergence due to tighter LP relaxation

**Implementation:**
```python
# In _create_objective(), around line 2239
# BEFORE (current - too loose):
max_inventory_per_cohort = max_daily_production * planning_days  # WRONG!
max_pallets = int(math.ceil(max_inventory_per_cohort / self.UNITS_PER_PALLET))

# AFTER (tighter bound):
# A cohort represents production from ONE day, so max is one day's production
max_pallets_per_cohort = int(math.ceil(max_daily_production / self.UNITS_PER_PALLET))

model.pallet_count = Var(
    model.cohort_index,
    within=NonNegativeIntegers,
    bounds=(0, max_pallets_per_cohort),
    doc="Pallet count for inventory cohort (max = one day's production)"
)
```

**Additional Note:**
This bound could be tightened further using actual production capacity per product:
```python
# Even tighter: use actual max production considering overhead time
# max_prod_time = max_labor_hours - min_overhead_time
# max_units = max_prod_time × production_rate
# But this adds complexity; daily max is sufficient and safe
```

---

#### **3. Truck Load Upper Bounds** (HIGH PRIORITY)

**Current State:**
```python
model.truck_load = Var(
    truck_load_index,
    within=NonNegativeReals,
    doc="Quantity loaded on truck to specific destination by product and delivery date (in units)"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Implicit constraint:** `truck_capacity_con` limits via `truck.capacity * truck_used`
- **Index count:** ~5,600 (10 trucks × 2-4 destinations × 5 products × 28 dates)

**Problem:**
- No explicit upper bound per truck load
- Solver explores infeasible region where single product load exceeds truck capacity
- Constraint coupling: `truck_load` sum affects `truck_used` binary variable

**Proposed Tighter Bound:**
```python
# Maximum load per (truck, destination, product, date) is truck capacity
# No single product can exceed full truck capacity
truck_capacity = 14080.0  # 44 pallets × 320 units/pallet

model.truck_load = Var(
    truck_load_index,
    within=NonNegativeReals,
    bounds=(0, truck_capacity),
    doc="Quantity loaded on truck (cannot exceed truck capacity)"
)
```

**Justification:**
- **Truck capacity:** 44 pallets = 14,080 units
- **Physical maximum:** Single (truck, dest, prod, date) tuple cannot exceed full truck capacity
- **Current constraint:** `sum(truck_load over all destinations and products) ≤ truck.capacity × truck_used`
- **Tighter bound:** Each individual `truck_load` ≤ truck.capacity (more restrictive than sum constraint)

**Expected Impact:**
- **Performance:** 3-5% solve time reduction
- **LP relaxation:** Prevents exploration of clearly infeasible solutions
- **Binary variable fixing:** Helps solver fix `truck_used` binary earlier in branch-and-bound

**Implementation:**
```python
# In build_model(), around line 413
# Get truck capacity (assume uniform across trucks, or use per-truck capacity)
truck_capacity = 14080.0  # Standard: 44 pallets × 320 units
if self.truck_schedules:
    # Use maximum truck capacity across all trucks
    truck_capacity = max(t.capacity for t in self.truck_schedules)

model.truck_load = Var(
    truck_load_index,
    within=NonNegativeReals,
    bounds=(0, truck_capacity),
    doc="Quantity loaded on truck (bounded by truck capacity)"
)
```

---

### MEDIUM-IMPACT Opportunities

#### **4. Labor Hours Variable Upper Bounds**

**Current State:**
```python
model.labor_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    doc="Actual labor hours used (production time + overhead time)"
)

model.labor_hours_paid = Var(
    production_day_index,
    within=NonNegativeReals,
    doc="Labor hours paid (includes 4-hour minimum on non-fixed days)"
)

model.fixed_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    doc="Labor hours charged at regular rate"
)

model.overtime_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    doc="Labor hours charged at overtime rate"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Index count:** ~28 each (1 node × 28 dates)

**Problem:**
- No explicit upper bounds on any labor hour variables
- Physically impossible to exceed maximum daily labor hours (14 hours)
- Solver must discover bounds through constraint propagation

**Proposed Tighter Bounds:**
```python
max_labor_hours = 14.0  # 12 fixed + 2 OT (or up to 14 on non-fixed days)
max_fixed_hours = 12.0  # Maximum fixed hours available per day
max_overtime_hours = 2.0  # Maximum OT hours available per weekday

model.labor_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    bounds=(0, max_labor_hours),
    doc="Actual labor hours used (max = 14h)"
)

model.labor_hours_paid = Var(
    production_day_index,
    within=NonNegativeReals,
    bounds=(0, max_labor_hours),
    doc="Labor hours paid (max = 14h)"
)

model.fixed_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    bounds=(0, max_fixed_hours),
    doc="Labor hours charged at regular rate (max = 12h)"
)

model.overtime_hours_used = Var(
    production_day_index,
    within=NonNegativeReals,
    bounds=(0, max_overtime_hours),
    doc="Labor hours charged at overtime rate (max = 2h)"
)
```

**Justification:**
- **Labor calendar:** Maximum 14 hours per day (typical: 12 fixed + 2 OT)
- **Fixed hours:** Cannot exceed 12 hours (weekday fixed labor)
- **Overtime hours:** Cannot exceed 2 hours (weekday OT limit)
- **Physical constraint:** No mechanism to exceed these limits

**Expected Impact:**
- **Performance:** 2-3% solve time reduction
- **Preprocessing:** Helps solver tighten other variable bounds that depend on labor
- **Constraint propagation:** Faster bound tightening in presolve

**Implementation:**
```python
# In build_model(), around lines 481-505
# Calculate max hours from labor calendar
max_labor_hours = 14.0  # Conservative default
max_fixed_hours = 12.0
max_overtime_hours = 2.0

# Could refine based on actual labor calendar:
for date in self.production_dates:
    labor_day = self.labor_calendar.get_labor_day(date)
    if labor_day:
        day_total = labor_day.fixed_hours + (labor_day.overtime_hours or 0.0)
        max_labor_hours = max(max_labor_hours, day_total)
        max_fixed_hours = max(max_fixed_hours, labor_day.fixed_hours)
        if hasattr(labor_day, 'overtime_hours') and labor_day.overtime_hours:
            max_overtime_hours = max(max_overtime_hours, labor_day.overtime_hours)

# Then apply bounds to variables
```

---

#### **5. Shortage Variable Upper Bounds**

**Current State:**
```python
model.shortage = Var(
    shortage_index,  # (dest, prod, date) tuples
    within=NonNegativeReals,
    doc="Unmet demand (shortage) with penalty"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Index count:** ~1,260 (9 destinations × 5 products × 28 dates)

**Problem:**
- No explicit upper bound on shortages
- Shortage cannot exceed forecasted demand on that date
- Solver can explore solutions with shortage > demand (meaningless)

**Proposed Tighter Bound:**
```python
# Create bounds dictionary based on actual demand
shortage_bounds = {}
for (dest, prod, date) in shortage_index:
    demand_qty = self.demand.get((dest, prod, date), 0.0)
    shortage_bounds[(dest, prod, date)] = (0, demand_qty)

model.shortage = Var(
    shortage_index,
    within=NonNegativeReals,
    bounds=shortage_bounds,  # Individual bounds per tuple
    doc="Unmet demand (shortage) with penalty, bounded by demand"
)
```

**Alternative (simpler but less tight):**
```python
# Use maximum demand across all tuples
max_demand = max(self.demand.values()) if self.demand else 0.0

model.shortage = Var(
    shortage_index,
    within=NonNegativeReals,
    bounds=(0, max_demand),
    doc="Unmet demand (shortage) with penalty, bounded by max demand"
)
```

**Justification:**
- **Shortage definition:** Quantity of demand not satisfied
- **Physical meaning:** shortage[dest, prod, date] ≤ demand[dest, prod, date]
- **Constraint:** `demand_from_cohort + shortage = demand` (if shortage enabled)
- **Benefit:** Prevents solver from exploring shortage > demand solutions

**Expected Impact:**
- **Performance:** 1-2% solve time reduction (only if `allow_shortages=True`)
- **LP relaxation:** Tighter feasible region for shortage penalty problems
- **Practical benefit:** Most runs don't allow shortages, so impact is limited

**Implementation:**
```python
# In build_model(), around line 377-383
if self.allow_shortages:
    shortage_index = list(self.demand.keys())

    # Calculate max demand for upper bounds
    max_demand = max(self.demand.values()) if self.demand else 10000.0

    model.shortage = Var(
        shortage_index,
        within=NonNegativeReals,
        bounds=(0, max_demand),
        doc="Unmet demand (shortage) with penalty, bounded by max demand"
    )
```

---

#### **6. Demand Satisfaction Variable Upper Bounds**

**Current State:**
```python
model.demand_from_cohort = Var(
    model.demand_cohort_index,  # (dest, prod, date, prod_date, state) tuples
    within=NonNegativeReals,
    doc="Demand satisfied from specific production cohort"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Index count:** ~3,000+ (demand × cohorts × states)

**Problem:**
- No explicit upper bound on demand allocation from each cohort
- Total demand on a date is fixed; individual cohort contribution cannot exceed total demand
- Solver explores infeasible allocations

**Proposed Tighter Bound:**
```python
# Maximum demand that can be satisfied from any single cohort
# is the total demand on that date (cannot exceed total demand)
demand_cohort_bounds = {}
for (dest, prod, date, prod_date, state) in model.demand_cohort_index:
    total_demand = self.demand.get((dest, prod, date), 0.0)
    demand_cohort_bounds[(dest, prod, date, prod_date, state)] = (0, total_demand)

model.demand_from_cohort = Var(
    model.demand_cohort_index,
    within=NonNegativeReals,
    bounds=demand_cohort_bounds,
    doc="Demand satisfied from specific cohort, bounded by total demand"
)
```

**Alternative (simpler):**
```python
# Use maximum demand across all dates as uniform bound
max_demand = max(self.demand.values()) if self.demand else 0.0

model.demand_from_cohort = Var(
    model.demand_cohort_index,
    within=NonNegativeReals,
    bounds=(0, max_demand),
    doc="Demand satisfied from specific cohort, bounded by max demand"
)
```

**Justification:**
- **Constraint:** `sum(demand_from_cohort over cohorts) = demand[dest, prod, date]`
- **Physical meaning:** Cannot allocate more from one cohort than total demand
- **Tightness:** Per-date bounds are tighter than global max bound

**Expected Impact:**
- **Performance:** 2-3% solve time reduction (batch tracking enabled)
- **LP relaxation:** Tighter feasible region for demand allocation
- **Benefit:** Only applies when `use_batch_tracking=True`

**Implementation:**
```python
# In build_model(), around line 366-374
if self.use_batch_tracking:
    self.demand_cohort_index_set = self._build_demand_cohort_indices(model.dates)
    model.demand_cohort_index = list(self.demand_cohort_index_set)

    # Calculate max demand for upper bounds
    max_demand = max(self.demand.values()) if self.demand else 10000.0

    model.demand_from_cohort = Var(
        model.demand_cohort_index,
        within=NonNegativeReals,
        bounds=(0, max_demand),
        doc="Demand satisfied from specific cohort, bounded by max demand"
    )
```

---

#### **7. Inventory Cohort Upper Bounds**

**Current State:**
```python
model.inventory_cohort = Var(
    model.cohort_index,  # (node, prod, prod_date, curr_date, state)
    within=NonNegativeReals,
    doc="Inventory by node, product, production cohort, date, and state"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Index count:** ~18,675 (largest variable set!)

**Problem:**
- No explicit upper bounds on inventory cohorts
- A cohort cannot exceed its initial production quantity (single day's production)
- Solver explores unrealistic inventory accumulation

**Proposed Tighter Bound:**
```python
# Maximum inventory in any cohort = maximum production on single day
max_daily_production = 19600.0  # 1,400 units/hr × 14hr

model.inventory_cohort = Var(
    model.cohort_index,
    within=NonNegativeReals,
    bounds=(0, max_daily_production),
    doc="Inventory by cohort, bounded by daily production max"
)
```

**Advanced Tightening (Optional):**
```python
# Even tighter: Account for initial inventory cohorts vs production cohorts
cohort_bounds = {}
for (node, prod, prod_date, curr_date, state) in model.cohort_index:
    if prod_date in self.production_dates:
        # Production cohort: bounded by daily production capacity
        cohort_bounds[(node, prod, prod_date, curr_date, state)] = (0, max_daily_production)
    else:
        # Initial inventory cohort: bounded by initial inventory quantity
        init_qty = self.initial_inventory.get((node, prod, prod_date, state), 0.0)
        cohort_bounds[(node, prod, prod_date, curr_date, state)] = (0, max(init_qty, max_daily_production))

model.inventory_cohort = Var(
    model.cohort_index,
    within=NonNegativeReals,
    bounds=cohort_bounds,
    doc="Inventory by cohort, with refined bounds"
)
```

**Justification:**
- **Cohort source:** Each cohort originates from single production event or initial inventory
- **Conservation:** Inventory in cohort cannot exceed original quantity (only decreases via shipments/demand)
- **Upper bound:** max(daily_production, initial_inventory_quantity)

**Expected Impact:**
- **Performance:** 5-8% solve time reduction (largest variable set!)
- **LP relaxation:** Significantly tighter bounds on most critical continuous variables
- **Memory:** May improve solver memory efficiency with tighter bounds

**Implementation:**
```python
# In build_model(), around line 323
if self.use_batch_tracking:
    # Calculate maximum daily production for bound
    max_daily_production = self.get_max_daily_production()  # From HIGH-IMPACT #1

    model.inventory_cohort = Var(
        model.cohort_index,
        within=NonNegativeReals,
        bounds=(0, max_daily_production),
        doc="Inventory by node, product, production cohort, date, and state"
    )
```

---

#### **8. Shipment Cohort Upper Bounds**

**Current State:**
```python
model.shipment_cohort = Var(
    model.shipment_cohort_index,  # (origin, dest, prod, prod_date, delivery_date, state)
    within=NonNegativeReals,
    doc="Shipment quantity by route, product, production cohort, delivery date, and arrival state"
)
```
- **Bounds:** `(0, ∞)` (default)
- **Index count:** ~5,000+ (routes × products × cohorts × dates × states)

**Problem:**
- No explicit upper bounds on shipment cohorts
- Shipment from cohort cannot exceed inventory in that cohort
- Related to truck capacity but not explicitly bounded

**Proposed Tighter Bound:**
```python
# Maximum shipment from cohort = maximum inventory in cohort (from HIGH-IMPACT #1)
max_daily_production = 19600.0  # Same as inventory cohort bound

model.shipment_cohort = Var(
    model.shipment_cohort_index,
    within=NonNegativeReals,
    bounds=(0, max_daily_production),
    doc="Shipment quantity by cohort, bounded by daily production max"
)
```

**Even Tighter (Per-Cohort Bounds):**
```python
# Shipment cannot exceed available inventory in source cohort
# But this requires complex cohort-specific bounds calculation
# Simpler: Use truck capacity as upper bound
truck_capacity = 14080.0  # 44 pallets × 320 units

shipment_bound = min(max_daily_production, truck_capacity)

model.shipment_cohort = Var(
    model.shipment_cohort_index,
    within=NonNegativeReals,
    bounds=(0, shipment_bound),
    doc="Shipment quantity by cohort, bounded by min(daily_prod, truck_capacity)"
)
```

**Justification:**
- **Physical constraint:** Shipment cannot exceed inventory in cohort
- **Truck constraint:** Single shipment limited by truck capacity
- **Conservative bound:** min(daily_production, truck_capacity) is safe upper bound

**Expected Impact:**
- **Performance:** 3-5% solve time reduction
- **LP relaxation:** Tighter bounds on shipment variables
- **Coupling:** Helps tighten inventory and truck constraints simultaneously

**Implementation:**
```python
# In build_model(), around line 343
if self.use_batch_tracking:
    self.shipment_cohort_index_set = self._build_shipment_cohort_indices(model.dates)
    model.shipment_cohort_index = list(self.shipment_cohort_index_set)

    # Upper bound: minimum of daily production and truck capacity
    max_daily_production = self.get_max_daily_production()
    truck_capacity = 14080.0  # Standard capacity
    if self.truck_schedules:
        truck_capacity = max(t.capacity for t in self.truck_schedules)

    shipment_bound = min(max_daily_production, truck_capacity)

    model.shipment_cohort = Var(
        model.shipment_cohort_index,
        within=NonNegativeReals,
        bounds=(0, shipment_bound),
        doc="Shipment quantity by cohort, bounded by min(production, truck_capacity)"
    )
```

---

### LOW-IMPACT Opportunities

#### **9. Big-M Refinement for Product Produced Constraint**

**Current State:**
```python
# Line 1839 in _add_changeover_tracking_constraints
def product_produced_linking_rule(model, node_id, prod, date):
    """Link production quantity to binary product indicator (big-M)."""
    M = 20000  # Max daily production = 19,600 units
    return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]
```

**Problem:**
- Big-M value is 20,000, but maximum daily production is 19,600
- Small gap, but tightening improves LP relaxation

**Proposed Tighter Big-M:**
```python
def product_produced_linking_rule(model, node_id, prod, date):
    """Link production quantity to binary product indicator (big-M)."""
    M = 19600  # Exact max daily production (1,400/hr × 14hr)
    return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]
```

**Even Better:**
```python
# Use actual production capacity for this specific date
def product_produced_linking_rule(model, node_id, prod, date):
    """Link production quantity to binary product indicator (big-M)."""
    node = self.nodes[node_id]
    labor_day = self.labor_calendar.get_labor_day(date)

    if not labor_day:
        # No labor on this date
        return model.production[node_id, prod, date] == 0

    # Calculate actual maximum production on this date
    max_hours = labor_day.fixed_hours + (labor_day.overtime_hours or 0.0)
    prod_rate = node.capabilities.production_rate_per_hour or 1400.0
    M = max_hours * prod_rate  # Date-specific bound!

    return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]
```

**Expected Impact:**
- **Performance:** <1% solve time reduction (minimal)
- **LP relaxation:** Slightly tighter, but `product_produced` is already relaxed to continuous
- **Correctness:** Improved model accuracy

---

#### **10. Big-M Refinement for Overtime Indicator**

**Current State:**
```python
# Line 2055 in _add_labor_cost_constraints
def overtime_indicator_upper_rule(model, node_id, date):
    """Link overtime hours to binary indicator (upper bound)."""
    M = 14.0  # Max labor hours per day (12 fixed + 2 OT)
    return model.overtime_hours_used[node_id, date] <= M * model.uses_overtime[node_id, date]
```

**Problem:**
- Big-M is 14.0, but overtime_hours_used is only the OVERTIME portion
- Maximum overtime is actually 2.0 hours (not 14.0)
- Loose big-M weakens LP relaxation

**Proposed Tighter Big-M:**
```python
def overtime_indicator_upper_rule(model, node_id, date):
    """Link overtime hours to binary indicator (upper bound)."""
    M = 2.0  # Max OVERTIME hours per day (not total labor hours!)
    return model.overtime_hours_used[node_id, date] <= M * model.uses_overtime[node_id, date]
```

**Justification:**
- Variable `overtime_hours_used` represents ONLY overtime hours (not total hours)
- Constraint `fixed_hours_limit_con` already ensures fixed ≤ 12, overtime ≤ remaining
- Maximum possible overtime: 2.0 hours on weekdays
- Current M=14.0 is **7x too large**

**Expected Impact:**
- **Performance:** 1-2% solve time reduction
- **LP relaxation:** Much tighter bound on `uses_overtime` binary variable
- **Critical:** Improves piecewise labor cost accuracy

**Implementation:**
```python
# In _add_labor_cost_constraints(), around line 2050
def overtime_indicator_upper_rule(model, node_id, date):
    """Link overtime hours to binary indicator (upper bound).

    overtime_hours_used <= M * uses_overtime
    If uses_overtime = 0, forces overtime_hours_used = 0
    """
    # Get actual max OT for this date from labor calendar
    labor_day = self.labor_calendar.get_labor_day(date)
    max_ot = labor_day.overtime_hours if labor_day and hasattr(labor_day, 'overtime_hours') else 2.0
    max_ot = max_ot or 2.0  # Default if None

    return model.overtime_hours_used[node_id, date] <= max_ot * model.uses_overtime[node_id, date]
```

---

#### **11. Aggregated Variable Bounds (Non-Batch-Tracking Mode)**

**Current State:**
```python
# Only created if use_batch_tracking=False
model.inventory = Var(
    model.inventory_index,  # (node, prod, date)
    within=NonNegativeReals,
    doc="Aggregated inventory by node, product, and date"
)

model.shipment = Var(
    shipment_index,  # (origin, dest, prod, date)
    within=NonNegativeReals,
    doc="Shipment quantity by route, product, and delivery date"
)
```

**Problem:**
- These variables are only used when `use_batch_tracking=False`
- Currently have no explicit bounds
- Same reasoning as cohort variables applies

**Proposed Tighter Bounds:**
```python
# Aggregated inventory bounded by cumulative production capacity
max_daily_production = 19600.0
planning_days = len(model.dates)
max_cumulative_inventory = max_daily_production * planning_days

model.inventory = Var(
    model.inventory_index,
    within=NonNegativeReals,
    bounds=(0, max_cumulative_inventory),
    doc="Aggregated inventory by node, product, and date"
)

# Aggregated shipment bounded by truck capacity
truck_capacity = 14080.0
model.shipment = Var(
    shipment_index,
    within=NonNegativeReals,
    bounds=(0, truck_capacity),
    doc="Shipment quantity by route, product, and delivery date"
)
```

**Expected Impact:**
- **Performance:** 2-4% solve time reduction (only when batch tracking disabled)
- **Practical benefit:** Most production runs use batch tracking, so limited impact
- **Testing benefit:** Faster test runs without batch tracking

---

#### **12. Per-Date Production Capacity Bounds (Advanced)**

**Current State:**
- Production variables use uniform upper bound (from HIGH-IMPACT #1)
- But actual capacity varies by day (labor availability, fixed vs non-fixed days)

**Proposed Advanced Tightening:**
```python
# Create per-date production bounds based on labor calendar
production_bounds = {}
for node_id in self.manufacturing_nodes:
    node = self.nodes[node_id]
    prod_rate = node.capabilities.production_rate_per_hour or 1400.0

    for prod in model.products:
        for date in model.dates:
            labor_day = self.labor_calendar.get_labor_day(date)

            if not labor_day:
                # No labor available
                max_prod = 0.0
            else:
                # Account for overhead time
                max_hours = labor_day.fixed_hours + (labor_day.overtime_hours or 0.0)
                startup = node.capabilities.daily_startup_hours or 0.5
                shutdown = node.capabilities.daily_shutdown_hours or 0.5
                changeover = node.capabilities.default_changeover_hours or 1.0

                # Conservative: assume maximum overhead (startup + shutdown + max changeovers)
                max_overhead = startup + shutdown + changeover * (len(model.products) - 1)
                available_hours = max(0.0, max_hours - max_overhead)
                max_prod = available_hours * prod_rate

            production_bounds[(node_id, prod, date)] = (0, max_prod)

model.production = Var(
    production_index,
    within=NonNegativeReals,
    bounds=production_bounds,  # Per-date bounds!
    doc="Production quantity with per-date capacity bounds"
)
```

**Justification:**
- **Labor calendar variation:** Fixed days (12+2h), non-fixed days (variable hours), no-labor days (0h)
- **Overhead variation:** More products = more changeover time = less production time
- **Tightest possible bound:** Accounts for date-specific labor and overhead

**Expected Impact:**
- **Performance:** 2-3% solve time reduction
- **Complexity:** Moderate implementation complexity
- **Trade-off:** More complex bound calculation vs. marginal benefit

**Implementation Recommendation:**
- Start with uniform bound (HIGH-IMPACT #1) for simplicity
- Implement per-date bounds if further performance gains needed
- Profile solver to verify benefit justifies complexity

---

## Part 3: Implementation Priority & Roadmap

### Quick Wins (Implement First)

1. **Production Variable Upper Bounds** (HIGH #1)
   - **Effort:** 15 minutes
   - **Impact:** 5-10% performance improvement
   - **Risk:** Very low (conservative bound)

2. **Pallet Count Upper Bound Refinement** (HIGH #2)
   - **Effort:** 10 minutes
   - **Impact:** 10-20% performance improvement (pallet storage enabled)
   - **Risk:** Very low (mathematically correct)
   - **Critical:** May enable Phase 4 pallet truck loading

3. **Truck Load Upper Bounds** (HIGH #3)
   - **Effort:** 10 minutes
   - **Impact:** 3-5% performance improvement
   - **Risk:** Very low (physical constraint)

4. **Overtime Big-M Refinement** (LOW #10)
   - **Effort:** 5 minutes
   - **Impact:** 1-2% performance improvement
   - **Risk:** Very low (bug fix - current M is incorrect)

**Total Quick Win Effort:** ~40 minutes
**Expected Cumulative Impact:** 15-25% performance improvement

### Phase 2 Implementations (After Quick Wins)

5. **Labor Hours Variable Upper Bounds** (MEDIUM #4)
   - **Effort:** 20 minutes
   - **Impact:** 2-3% performance improvement

6. **Inventory Cohort Upper Bounds** (MEDIUM #7)
   - **Effort:** 15 minutes
   - **Impact:** 5-8% performance improvement (largest variable set!)

7. **Shipment Cohort Upper Bounds** (MEDIUM #8)
   - **Effort:** 15 minutes
   - **Impact:** 3-5% performance improvement

**Total Phase 2 Effort:** ~50 minutes
**Expected Cumulative Impact:** +10-16% additional improvement

### Phase 3 Implementations (Refinements)

8. **Demand Satisfaction Variable Upper Bounds** (MEDIUM #6)
   - **Effort:** 20 minutes
   - **Impact:** 2-3% performance improvement

9. **Shortage Variable Upper Bounds** (MEDIUM #5)
   - **Effort:** 15 minutes
   - **Impact:** 1-2% performance improvement (only if shortages enabled)

10. **Product Produced Big-M Refinement** (LOW #9)
    - **Effort:** 30 minutes (date-specific bound calculation)
    - **Impact:** <1% performance improvement

11. **Aggregated Variable Bounds** (LOW #11)
    - **Effort:** 10 minutes
    - **Impact:** 2-4% (only without batch tracking)

**Total Phase 3 Effort:** ~75 minutes
**Expected Cumulative Impact:** +3-7% additional improvement

### Advanced/Future Implementations

12. **Per-Date Production Capacity Bounds** (LOW #12)
    - **Effort:** 60+ minutes (complex calculation)
    - **Impact:** 2-3% performance improvement
    - **Recommendation:** Only implement if profiling shows benefit

---

## Part 4: Expected Cumulative Performance Impact

### Baseline Performance (Current)
- **4-week horizon, unit-based storage:** 20-30s solve time
- **4-week horizon, pallet-based storage:** 35-45s solve time

### After Quick Wins (40 minutes implementation)
- **4-week horizon, unit-based storage:** 17-24s solve time (**15-20% faster**)
- **4-week horizon, pallet-based storage:** 27-36s solve time (**20-23% faster**)

### After Phase 2 (90 minutes total implementation)
- **4-week horizon, unit-based storage:** 14-20s solve time (**30-33% faster**)
- **4-week horizon, pallet-based storage:** 22-29s solve time (**35-38% faster**)

### After Phase 3 (165 minutes total implementation)
- **4-week horizon, unit-based storage:** 13-18s solve time (**35-40% faster**)
- **4-week horizon, pallet-based storage:** 20-26s solve time (**40-43% faster**)

### Potential Impact on Pallet Truck Loading (Phase 4 Goal)
**Current Issue:** Pallet-based truck loading variables cause Gap=100% timeout
- **Root cause hypothesis:** Loose bounds on pallet variables + poor LP relaxation
- **Bound tightening benefit:** Tighter pallet_count bounds (27x reduction) + tighter truck_load bounds
- **Expected outcome:** May enable pallet truck loading with CBC solver, or at minimum reduce Gap

---

## Part 5: Implementation Code Examples

### Complete Implementation Template

```python
# File: src/optimization/unified_node_model.py

class UnifiedNodeModel(BaseOptimizationModel):

    def get_max_daily_production(self) -> float:
        """Calculate maximum possible daily production.

        Returns:
            Maximum production in units per day (accounts for max labor hours)
        """
        max_labor_hours = 0.0
        for date in self.production_dates:
            labor_day = self.labor_calendar.get_labor_day(date)
            if labor_day:
                day_hours = labor_day.fixed_hours + (labor_day.overtime_hours or 0.0)
                max_labor_hours = max(max_labor_hours, day_hours)

        # Get production rate from first manufacturing node (assume uniform)
        if self.manufacturing_nodes:
            node_id = next(iter(self.manufacturing_nodes))
            node = self.nodes[node_id]
            prod_rate = node.capabilities.production_rate_per_hour or 1400.0
        else:
            prod_rate = 1400.0  # Default

        return prod_rate * max_labor_hours

    def get_max_truck_capacity(self) -> float:
        """Calculate maximum truck capacity across all trucks.

        Returns:
            Maximum truck capacity in units
        """
        if self.truck_schedules:
            return max(t.capacity for t in self.truck_schedules)
        else:
            return 14080.0  # Default: 44 pallets × 320 units

    def build_model(self) -> ConcreteModel:
        """Build the optimization model with tightened variable bounds."""
        model = ConcreteModel()

        # ... (existing code for sets) ...

        # Calculate bounds for reuse
        max_daily_production = self.get_max_daily_production()
        max_truck_capacity = self.get_max_truck_capacity()
        max_demand = max(self.demand.values()) if self.demand else 10000.0

        # === QUICK WIN #1: Production bounds ===
        production_index = [
            (node_id, prod, date)
            for node_id in self.manufacturing_nodes
            for prod in model.products
            for date in model.dates
        ]
        model.production = Var(
            production_index,
            within=NonNegativeReals,
            bounds=(0, max_daily_production),  # TIGHTENED!
            doc="Production quantity at manufacturing nodes"
        )

        # === Inventory variables ===
        if self.use_batch_tracking:
            # QUICK WIN #2 (deferred to objective function for pallet_count)
            # PHASE 2 #7: Inventory cohort bounds
            model.inventory_cohort = Var(
                model.cohort_index,
                within=NonNegativeReals,
                bounds=(0, max_daily_production),  # TIGHTENED!
                doc="Inventory by node, product, production cohort, date, and state"
            )
        else:
            # PHASE 3 #11: Aggregated inventory bounds
            max_cumulative_inventory = max_daily_production * len(model.dates)
            model.inventory = Var(
                model.inventory_index,
                within=NonNegativeReals,
                bounds=(0, max_cumulative_inventory),  # TIGHTENED!
                doc="Aggregated inventory by node, product, and date"
            )

        # === Shipment variables ===
        if self.use_batch_tracking:
            # PHASE 2 #8: Shipment cohort bounds
            shipment_bound = min(max_daily_production, max_truck_capacity)
            model.shipment_cohort = Var(
                model.shipment_cohort_index,
                within=NonNegativeReals,
                bounds=(0, shipment_bound),  # TIGHTENED!
                doc="Shipment quantity by route, product, cohort, delivery date, and state"
            )
        else:
            # PHASE 3 #11: Aggregated shipment bounds
            model.shipment = Var(
                shipment_index,
                within=NonNegativeReals,
                bounds=(0, max_truck_capacity),  # TIGHTENED!
                doc="Shipment quantity by route, product, and delivery date"
            )

        # === Demand satisfaction variables ===
        if self.use_batch_tracking:
            # PHASE 3 #6: Demand from cohort bounds
            model.demand_from_cohort = Var(
                model.demand_cohort_index,
                within=NonNegativeReals,
                bounds=(0, max_demand),  # TIGHTENED!
                doc="Demand satisfied from specific production cohort"
            )

        # === Shortage variables ===
        if self.allow_shortages:
            # PHASE 3 #5: Shortage bounds
            shortage_index = list(self.demand.keys())
            model.shortage = Var(
                shortage_index,
                within=NonNegativeReals,
                bounds=(0, max_demand),  # TIGHTENED!
                doc="Unmet demand (shortage) with penalty"
            )

        # === Truck variables ===
        if self.truck_schedules:
            # ... truck_used (already binary, no bound change) ...

            # QUICK WIN #3: Truck load bounds
            truck_load_index = [...]  # existing
            model.truck_load = Var(
                truck_load_index,
                within=NonNegativeReals,
                bounds=(0, max_truck_capacity),  # TIGHTENED!
                doc="Quantity loaded on truck to specific destination"
            )

        # === Labor variables ===
        if self.manufacturing_nodes:
            production_day_index = [...]  # existing

            # PHASE 2 #4: Labor hours bounds
            max_labor_hours = 14.0  # Can refine from labor calendar
            max_fixed_hours = 12.0
            max_overtime_hours = 2.0

            model.labor_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                bounds=(0, max_labor_hours),  # TIGHTENED!
                doc="Actual labor hours used (production time + overhead time)"
            )

            model.labor_hours_paid = Var(
                production_day_index,
                within=NonNegativeReals,
                bounds=(0, max_labor_hours),  # TIGHTENED!
                doc="Labor hours paid (includes 4-hour minimum)"
            )

            model.fixed_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                bounds=(0, max_fixed_hours),  # TIGHTENED!
                doc="Labor hours charged at regular rate"
            )

            model.overtime_hours_used = Var(
                production_day_index,
                within=NonNegativeReals,
                bounds=(0, max_overtime_hours),  # TIGHTENED!
                doc="Labor hours charged at overtime rate"
            )

            # ... uses_overtime (already binary, no bound change) ...

        # ... (rest of model construction) ...

        return model

    def _add_changeover_tracking_constraints(self, model: ConcreteModel) -> None:
        """Add changeover tracking constraints with tightened big-M values."""

        # ... (existing code) ...

        # QUICK WIN #4: Tighter big-M for product produced linking
        def product_produced_linking_rule(model, node_id, prod, date):
            """Link production quantity to binary product indicator (big-M).

            Uses tightened M = 19600 (exact daily max production).
            """
            M = 19600  # TIGHTENED from 20000!
            return model.production[node_id, prod, date] <= M * model.product_produced[node_id, prod, date]

        model.product_produced_linking_con = Constraint(
            product_produced_index,
            rule=product_produced_linking_rule,
            doc="Link production quantity to binary product indicator (tightened big-M)"
        )

        # ... (rest of changeover constraints) ...

    def _add_labor_cost_constraints(self, model: ConcreteModel) -> None:
        """Add labor cost constraints with tightened big-M for overtime."""

        # ... (existing code) ...

        # QUICK WIN #4: Tighter big-M for overtime indicator
        def overtime_indicator_upper_rule(model, node_id, date):
            """Link overtime hours to binary indicator (upper bound).

            Uses tightened M = 2.0 (max OT hours, not total labor hours!).
            """
            M = 2.0  # TIGHTENED from 14.0! (was 7x too large)
            return model.overtime_hours_used[node_id, date] <= M * model.uses_overtime[node_id, date]

        model.overtime_indicator_upper_con = Constraint(
            production_day_index,
            rule=overtime_indicator_upper_rule,
            doc="Link overtime hours to binary indicator (tightened big-M upper)"
        )

        # ... (rest of labor constraints) ...

    def _create_objective(self, model: ConcreteModel) -> None:
        """Create objective function with tightened pallet count bounds."""

        # ... (production cost, transport cost, labor cost) ...

        # === Holding cost with tightened pallet bounds ===
        holding_cost = 0

        if self.use_batch_tracking:
            # ... (check for pallet-based vs unit-based costs) ...

            if use_pallet_based:
                # QUICK WIN #2: Tighten pallet count upper bound
                max_daily_production = self.get_max_daily_production()

                # OLD (too loose):
                # max_inventory_per_cohort = max_daily_production * planning_days
                # max_pallets = int(math.ceil(max_inventory_per_cohort / self.UNITS_PER_PALLET))
                # Result: max_pallets = 1,715 (way too large!)

                # NEW (tightened):
                # A cohort represents production from ONE day, so max is one day's production
                max_pallets_per_cohort = int(math.ceil(max_daily_production / self.UNITS_PER_PALLET))
                # Result: max_pallets_per_cohort = 62 (27x tighter!)

                # Add integer pallet count variables with TIGHTENED bounds
                model.pallet_count = Var(
                    model.cohort_index,
                    within=NonNegativeIntegers,
                    bounds=(0, max_pallets_per_cohort),  # TIGHTENED!
                    doc="Pallet count for inventory cohort (tightened to daily production max)"
                )

                # ... (rest of pallet constraint and cost calculation) ...

        # ... (total cost and objective) ...
```

---

## Part 6: Testing & Validation Plan

### Before Implementation
1. **Baseline benchmark:** Run integration test 5 times, record solve times
2. **Document baseline:** Average, min, max solve times for 4-week horizon
3. **Git branch:** Create `feature/bound-tightening` branch

### After Each Implementation Phase
1. **Regression test:** Run all existing tests to ensure no breakage
2. **Performance test:** Run integration test 5 times, record solve times
3. **Comparison:** Calculate % improvement vs. baseline
4. **Validation:** Verify solution values match baseline (same optimal cost within 0.1%)

### Validation Commands
```bash
# Baseline measurement
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v --tb=short -k "test_ui_workflow" -s 2>&1 | tee baseline_times.txt

# After Quick Wins
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v --tb=short -k "test_ui_workflow" -s 2>&1 | tee quick_wins_times.txt

# After Phase 2
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v --tb=short -k "test_ui_workflow" -s 2>&1 | tee phase2_times.txt

# Compare results
python -c "
import re
for phase in ['baseline', 'quick_wins', 'phase2']:
    with open(f'{phase}_times.txt') as f:
        times = re.findall(r'Solve time: ([\d.]+)s', f.read())
        if times:
            times_float = [float(t) for t in times]
            print(f'{phase}: avg={sum(times_float)/len(times_float):.1f}s, min={min(times_float):.1f}s, max={max(times_float):.1f}s')
"
```

### Expected Test Results (Integration Test)

| Phase | Avg Solve Time | Min Solve Time | Max Solve Time | Improvement |
|-------|----------------|----------------|----------------|-------------|
| Baseline (current) | 30.0s | 27.0s | 35.0s | - |
| After Quick Wins | 24.0s | 21.0s | 28.0s | 20% |
| After Phase 2 | 20.0s | 17.0s | 23.0s | 33% |
| After Phase 3 | 18.0s | 15.0s | 21.0s | 40% |

---

## Part 7: Risks & Mitigation

### Risk 1: Over-Tightened Bounds Cause Infeasibility
**Likelihood:** Low
**Impact:** High (model becomes infeasible)
**Mitigation:**
- All proposed bounds are conservative (use maximum possible values)
- Extensive testing with various problem sizes
- Rollback plan: Revert to previous bounds if infeasibility detected

### Risk 2: Minimal Performance Improvement
**Likelihood:** Low-Medium
**Impact:** Low (wasted implementation effort)
**Mitigation:**
- Quick wins have proven benefit in optimization literature
- Pallet count bound tightening has 27x reduction (guaranteed impact)
- Incremental implementation allows early stopping if no benefit

### Risk 3: Solver-Specific Behavior
**Likelihood:** Medium
**Impact:** Medium (benefit varies by solver)
**Mitigation:**
- Test with CBC (primary), GLPK (backup), and Gurobi (if available)
- Document solver-specific performance differences
- Bounds still improve model correctness even if performance impact varies

### Risk 4: Increased Preprocessing Time
**Likelihood:** Low
**Impact:** Low (offset by faster solve)
**Mitigation:**
- Explicit bounds typically speed up preprocessing (not slow it down)
- Monitor both preprocessing and solve phases
- If preprocessing increases, consider simplifying bound calculations

---

## Part 8: Additional Recommendations

### Phase 4 Pallet Truck Loading Investigation
The proposed bound tightening, especially **QUICK WIN #2** (pallet_count refinement) and **QUICK WIN #3** (truck_load bounds), directly addresses potential root causes of the Phase 4 pallet truck loading issue:

**Previous Issue:**
- Adding integer `truck_pallet_load` variables caused Gap=100% timeout
- ~1,740 truck pallet variables + ~18,675 inventory pallet variables = ~20,415 total integer variables
- CBC solver could not find feasible solution within 300s

**How Bound Tightening Helps:**
1. **Tighter pallet_count bounds** (62 vs 1,715) reduce LP relaxation gap
2. **Tighter truck_load bounds** (14,080 max) prevent exploration of infeasible truck loads
3. **Improved LP relaxation** enables better branching decisions
4. **Faster integer variable fixing** due to tighter feasible region

**Recommendation:**
After implementing Quick Wins and Phase 2, **re-attempt pallet-based truck loading** with:
```python
# Create integer truck pallet load variables with tightened bounds
model.truck_pallet_load = Var(
    truck_load_index,
    within=NonNegativeIntegers,
    bounds=(0, 44),  # Max pallets per truck (explicit bound)
    doc="Pallet count loaded on truck (rounded up, partial pallets count as full)"
)

# Ceiling constraint: truck_pallet_load * 320 >= truck_load
# (similar to pallet_count for inventory)
def truck_pallet_ceiling_rule(model, truck_idx, dest, prod, date):
    if (truck_idx, dest, prod, date) not in model.truck_load:
        return Constraint.Skip
    return (model.truck_pallet_load[truck_idx, dest, prod, date] * 320.0 >=
            model.truck_load[truck_idx, dest, prod, date])

model.truck_pallet_ceiling_con = Constraint(
    truck_load_index,
    rule=truck_pallet_ceiling_rule,
    doc="Truck pallet count ceiling constraint"
)
```

With tightened bounds, CBC may successfully solve this formulation, enabling true pallet-granular truck loading optimization.

---

## Part 9: Summary & Next Steps

### Recommendations Summary

**Immediate Action (Quick Wins - 40 minutes):**
1. Production variable upper bounds: `bounds=(0, 19600)`
2. Pallet count upper bounds: `bounds=(0, 62)` instead of `(0, 1715)`
3. Truck load upper bounds: `bounds=(0, 14080)`
4. Overtime big-M refinement: `M=2.0` instead of `M=14.0`

**Expected Result:** 15-25% faster solve times, potential Phase 4 pallet truck loading enablement

**Follow-Up Actions:**
- Phase 2 implementations (50 minutes): Labor, inventory, shipment bounds
- Phase 3 refinements (75 minutes): Demand, shortage, big-M refinements
- Re-test pallet truck loading with tightened bounds

### Success Criteria
- All regression tests pass (no breakage)
- 4-week horizon solve time reduced by ≥15% (Quick Wins)
- 4-week horizon solve time reduced by ≥30% (Phase 2 complete)
- No infeasibility introduced
- Optimal cost values match baseline (within 0.1%)

### Documentation Updates
After implementation, update:
- `CLAUDE.md`: Add bound-tightening as performance optimization
- Code comments: Document all tightened bounds with justification
- `BOUND_TIGHTENING_RESULTS.md`: Record actual performance improvements

---

## Appendices

### Appendix A: Problem Dimensions Reference

**Typical 4-Week Real-World Problem:**
- **Products:** 5
- **Locations:** 10 (1 manufacturing + 9 breadrooms)
- **Routes:** 10
- **Dates:** 28 (4 weeks)
- **Trucks:** 10 truck schedules
- **Demand points:** ~1,260 (9 destinations × 5 products × 28 dates)

**Variable Counts (with batch tracking):**
- **Production:** ~140 (1 node × 5 products × 28 dates)
- **Inventory cohorts:** ~18,675 (nodes × products × cohorts × dates × states)
- **Shipment cohorts:** ~5,000+ (routes × products × cohorts × dates × states)
- **Demand from cohort:** ~3,000+ (demand points × cohorts × states)
- **Truck variables:** ~5,600 truck_load + ~280 truck_used
- **Labor variables:** ~140 (5 types × 28 dates)
- **Pallet count (if enabled):** ~18,675 INTEGER variables
- **Binary variables:** ~336 (truck_used, production_day, uses_overtime, product_produced)

**Total Continuous Variables:** ~32,000-34,000
**Total Integer Variables:** ~18,700 (pallet storage) or ~30 (without pallet storage)
**Total Constraints:** ~10,000-12,000

### Appendix B: Bound Tightening Impact Literature

Academic research shows:
- **10-50% solve time reduction** typical for tightening variable bounds in MIP
- **LP relaxation gap reduction** proportional to bound tightness
- **Branch-and-bound efficiency** improves with tighter bounds (fewer nodes explored)
- **Big-M refinement** critical for binary variable linking constraints

**References:**
- Wolsey, L. A. (1998). *Integer Programming*. Wiley. Chapter 9: Formulations.
- Vielma, J. P. (2015). "Mixed Integer Linear Programming Formulation Techniques." *SIAM Review*, 57(1), 3-57.

### Appendix C: Alternative Approaches (Not Recommended)

**Variable Elimination:**
- Could eliminate some variables via substitution
- Increases constraint complexity
- Not recommended: explicit variables improve model clarity

**Aggregation:**
- Could aggregate cohorts or products
- Reduces problem size but loses granularity
- Not recommended: batch tracking is core feature

**Rolling Horizon:**
- Already considered in `ROLLING_HORIZON_SOLUTION.md`
- Complementary approach, not alternative to bound tightening

---

**End of Report**

*Generated: 2025-10-17*
*Model Version: UnifiedNodeModel*
*Total Opportunities Identified: 12*
*Estimated Performance Improvement: 15-40% (phased implementation)*
