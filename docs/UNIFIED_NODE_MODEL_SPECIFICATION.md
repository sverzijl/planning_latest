# UnifiedNodeModel: Comprehensive Technical Specification

**IMPORTANT MAINTENANCE REQUIREMENT:**
This documentation must be updated whenever changes are made to `src/optimization/unified_node_model.py`. Keep this document synchronized with the actual implementation to serve as the authoritative reference for model behavior.

**Last Updated:** 2025-10-18
**Model Version:** UnifiedNodeModel (Phase 3 - Primary Optimization Approach)
**Location:** `src/optimization/unified_node_model.py`

---

## Table of Contents

1. [High-Level Purpose](#1-high-level-purpose)
2. [Decision Variables](#2-decision-variables)
3. [Constraints](#3-constraints)
4. [Objective Function](#4-objective-function)
5. [Key Design Patterns & Intricacies](#5-key-design-patterns--intricacies)
6. [What the Solver Does](#6-what-the-solver-does)
7. [Performance Characteristics](#7-performance-characteristics)

---

## 1. HIGH-LEVEL PURPOSE

This model solves an **integrated production-distribution planning problem for perishable gluten-free bread** across a multi-echelon network. It determines:

- **When and how much to produce** at manufacturing sites
- **How to route product** through a hub-and-spoke distribution network
- **How to manage inventory** with complex shelf life rules (frozen, ambient, thawed states)
- **How to allocate labor** (regular hours vs. overtime vs. weekend premium)
- **How to load trucks** subject to day-specific scheduling constraints

The objective is to **minimize total cost** (production + labor + transport + storage + shortage penalties) while meeting customer demand at breadroom locations.

---

## 2. DECISION VARIABLES

### 2.1 Production Variables

**`production[node_id, product, date]`** (continuous, ≥0)
- Units produced at each manufacturing node on each date
- Bounded by maximum daily production capacity (typically ~19,600 units with overtime)
- Only created for nodes with `can_produce()` capability

### 2.2 Inventory Variables (Cohort-Based Tracking)

When batch tracking is enabled (`use_batch_tracking=True`):

**`inventory_cohort[node_id, product, prod_date, curr_date, state]`** (continuous, ≥0)
- Inventory at each node, broken down by:
  - **Production date** (`prod_date`): When the batch was produced (age-cohort tracking)
  - **Current date** (`curr_date`): The date being planned
  - **State**: `'frozen'`, `'ambient'`, or `'thawed'`
- Enables **shelf life tracking**: a cohort produced on Day 1 stored in ambient has only 17 days before expiration
- Bounded by maximum daily production OR initial inventory (whichever is larger)

**`pallet_count[node_id, product, prod_date, curr_date, state]`** (integer, ≥0)
- Number of **full pallets** occupied by inventory cohort
- Used for accurate storage cost calculation (partial pallets cost same as full pallets)
- Enforced via ceiling constraint: `pallet_count × 320 ≥ inventory_qty`
- Cost minimization drives this to the **minimum feasible value** (ceiling rounding)
- Only created when pallet-based storage costs are configured (non-zero)

### 2.3 Shipment Variables (Cohort-Based)

**`shipment_cohort[origin, destination, product, prod_date, delivery_date, arrival_state]`** (continuous, ≥0)
- Shipments on each route, tracking:
  - **Production date** of the shipped batch
  - **Delivery date** (arrival at destination)
  - **Arrival state** (determined by route transport mode + destination storage capability)
- Example: frozen product shipped to ambient-only destination arrives in `'ambient'` state (thawed)
- Bounded by minimum of truck capacity (14,080 units) and maximum cohort size

### 2.4 Demand Variables

**`demand_from_cohort[node_id, product, prod_date, demand_date]`** (continuous, ≥0)
- Demand satisfied from specific production cohort
- Enables shelf life enforcement: only cohorts within acceptable age can fulfill demand
- Links inventory to demand satisfaction

**`shortage[node_id, product, date]`** (continuous, ≥0) — *if shortages allowed*
- Unmet demand (penalized heavily in objective)
- Only created when `allow_shortages=True`

### 2.5 Truck Variables

**`truck_used[truck_idx, date]`** (binary)
- Whether truck is used on a specific date
- Enforces day-of-week constraints (e.g., truck only runs Monday-Friday)

**`truck_load[truck_idx, destination, product, delivery_date]`** (continuous, ≥0)
- Quantity loaded on each truck to each destination
- **Note**: Uses continuous units (not integer pallets) for tractability
- Bounded by truck capacity (14,080 units = 44 pallets)
- **Pallet-level enforcement deferred to Phase 4** (makes MIP intractable for CBC solver)

### 2.6 Changeover Tracking Variables

**`production_day[node_id, date]`** (binary)
- Whether ANY production occurs on this date
- Used to calculate startup/shutdown overhead

**`product_produced[node_id, product, date]`** (relaxed binary, [0,1])
- Indicator: 1 if this specific product is produced
- **Relaxed from binary to continuous** for performance (constraints ensure integer behavior)

**`num_products_produced[node_id, date]`** (integer, ≥0)
- Count of distinct products made on this date
- Used for changeover time calculation: `(num_products - 1) × changeover_hours`

### 2.7 Labor Cost Variables

**`labor_hours_used[node_id, date]`** (continuous, ≥0)
- Actual labor hours consumed (production time + overhead)

**`labor_hours_paid[node_id, date]`** (continuous, ≥0)
- Hours paid for (includes 4-hour minimum on weekends/holidays)

**`fixed_hours_used[node_id, date]`** (continuous, ≥0)
- Hours charged at regular rate (only on weekdays)

**`overtime_hours_used[node_id, date]`** (continuous, ≥0)
- Hours charged at overtime premium rate

**`uses_overtime[node_id, date]`** (binary)
- Indicator for piecewise cost structure enforcement

---

## 3. CONSTRAINTS

### 3.1 Unified Inventory Balance Constraint *(Core Constraint)*

**For each cohort at each node on each date:**

```
inventory_cohort[t] = inventory_cohort[t-1]
                    + production_inflow (if manufacturing node AND prod_date=curr_date)
                    + arrivals_in_state (shipments arriving in this state)
                    - departures_in_state (shipments departing from this state)
                    - demand_consumption (if demand node)
```

**Key intricacies:**

- **Production inflow**: Only adds to cohort when `prod_date == curr_date` and state matches node's production state (e.g., manufacturing produces in `'ambient'` state)
- **State transitions**: Handled implicitly via arrival state determination
  - Frozen transport → Ambient storage = arrives as `'ambient'` (thawed)
  - Ambient transport → Frozen storage = arrives as `'frozen'` (re-frozen)
- **Departure state matching**: Frozen routes ship from frozen inventory, ambient routes from ambient inventory
- **Initial inventory**: At `t=0` (first planning date), uses provided initial inventory values (with production date set to 1 day before planning starts)

**State Transition Logic:**

The `_determine_arrival_state()` method implements:
- Ambient transport + Ambient node → `'ambient'` (no change)
- Ambient transport + Frozen node → `'frozen'` (freeze, reset to 120d)
- Frozen transport + Frozen node → `'frozen'` (no change)
- Frozen transport + Ambient node → `'ambient'` (thaw immediately, 14d shelf life)

### 3.2 Demand Satisfaction Constraints

**Demand Allocation:**
```
sum(demand_from_cohort[node, product, prod_date, demand_date]
    for all prod_dates)
    + shortage[node, product, demand_date] (if allowed)
    = demand[node, product, demand_date]
```

**Demand-Inventory Linking:**
```
demand_from_cohort[node, prod, prod_date, demand_date]
    <= inventory_cohort[node, prod, prod_date, demand_date, state]
```
- **Critical**: Uses **beginning-of-day** inventory (before consumption)
- Prevents circular dependency bug (previous versions used end-of-day inventory, causing 2x production requirement)

**Shelf Life Enforcement** *(if enabled)*:
- Cohorts only created if `(demand_date - prod_date).days <= shelf_life`
- Shelf life depends on state:
  - Frozen: 120 days
  - Ambient: 17 days
  - Thawed (frozen product that entered ambient storage): 14 days

### 3.3 Production Capacity Constraints

**For each manufacturing node on each date:**
```
production_time + overhead_time <= available_labor_hours
```

**Where:**
- **Production time** = `total_quantity / production_rate_per_hour`
- **Overhead time** =
  ```
  (startup_hours + shutdown_hours - changeover_hours) × production_day
  + changeover_hours × num_products_produced
  ```
  - This formulation correctly models:
    - 0 products: overhead = 0
    - 1 product: overhead = startup + shutdown (e.g., 0.5h + 0.5h = 1h)
    - N products: overhead = startup + shutdown + (N-1) × changeover

**Labor calendar integration:**
- Weekdays: `available_hours = fixed_hours + overtime_hours` (e.g., 12h + 2h = 14h)
- Weekends/holidays: Uses configured non-fixed day hours

**Overhead parameters** (configurable via `NodeCapabilities`):
- `daily_startup_hours` (default: 0.5h)
- `daily_shutdown_hours` (default: 0.5h)
- `default_changeover_hours` (default: 1.0h)

### 3.4 Changeover Tracking Constraints

**Binary Linking (Big-M):**
```
production[node, product, date] <= M × product_produced[node, product, date]
```
- Forces `product_produced = 1` when production > 0
- M = maximum daily production capacity (calculated, not hardcoded)

**Product Counting:**
```
num_products_produced[node, date] = sum(product_produced[node, product, date])
```

**Production Day Linking:**
```
num_products_produced <= |products| × production_day  (forces production_day=1 if any production)
production_day <= num_products_produced  (forces production_day=0 if no production)
```

### 3.5 Labor Cost Constraints *(Piecewise Model)*

**Hour Calculation:**
```
labor_hours_used[node, date] = production_time + overhead_time
```

**Fixed Day Constraints:**
```
fixed_hours_used <= available_fixed_hours (e.g., 12h)
overtime_hours_used = labor_hours_used - fixed_hours_used
fixed_hours_used ≥ 0
overtime_hours_used ≥ 0
```

**Non-Fixed Day Constraints:**
```
fixed_hours_used = 0  (all hours at premium rate)
labor_hours_paid ≥ labor_hours_used
labor_hours_paid ≥ 4.0 × production_day  (4-hour minimum payment)
```

**Piecewise Enforcement:**
- Binary `uses_overtime` triggers when hours exceed fixed hours
- Ensures correct cost calculation: regular rate for first 12h, overtime rate for excess

**Cost Calculation:**
- Fixed day: `regular_rate × fixed_hours + overtime_rate × overtime_hours`
- Non-fixed day: `non_fixed_rate × labor_hours_paid`

### 3.6 Truck Constraints

**Route-Truck Linking:**
```
sum(shipment_cohort on route) = sum(truck_load for trucks serving route)
```
- Forces shipments to use scheduled trucks (can't ship without a truck!)
- Handles intermediate stops: one truck can deliver to multiple destinations

**Truck Availability (Day-of-Week):**
```
truck_used[truck_idx, date] = 0  if truck doesn't run on this day-of-week
```
- Example: Monday afternoon truck to 6104 only runs on Mondays
- Example: Wednesday morning truck to Lineage only runs on Wednesdays

**Truck Capacity:**
```
sum(truck_load[truck_idx, all destinations, all products, delivery dates from this departure])
    <= truck.capacity × truck_used[truck_idx, departure_date]
```
- **Key**: Sums loads across ALL deliveries from a single physical truck departure
- Handles intermediate stops correctly (Wednesday truck drops at Lineage AND 6125)
- Capacity enforced at **unit level** (not pallet level, for tractability)

**Note on Pallet-Level Truck Constraints:**
- Attempted in Phase 4 but confirmed intractable for CBC solver
- Added ~1,740 integer `truck_pallet_load` variables (9% increase)
- Result: Gap=100% after 300s, no integer-feasible solution found
- Root cause: MIP too complex for open-source solver
- Current approach: Unit-based capacity (acceptable approximation)
- Future: Requires commercial solver (Gurobi/CPLEX) or alternative formulation

### 3.7 Pallet Storage Cost Constraint

**Pallet Ceiling Constraint:**
```
pallet_count[cohort] × 320 ≥ inventory_cohort[cohort]
```
- Enforces: 50 units requires 1 full pallet, not 0.156 pallets
- Cost minimization in objective drives `pallet_count` to **ceiling value**
- Example: 350 units → requires 2 pallets (not 1.094)

**Adaptive Bounds:**
- Old (wrong): `max_pallets = ceil((daily_production × planning_days) / 320)` → 1,715 pallets
- New (correct): `max_pallets = ceil(max(daily_production, initial_inventory) / 320)` → 62 pallets
- Tighter bounds improve solver performance

---

## 4. OBJECTIVE FUNCTION *(Minimize Total Cost)*

```
Total Cost = Production Cost
           + Labor Cost
           + Transport Cost
           + Holding Cost
           + Shortage Penalty
```

### 4.1 Production Cost

```
sum(production[node, product, date] × production_cost_per_unit)
```
- Simple variable cost per unit produced

### 4.2 Labor Cost *(Piecewise with Overhead)*

**For fixed days (weekdays):**
```
cost = regular_rate × fixed_hours_used
     + overtime_rate × overtime_hours_used
```
- Example: 12h @ $20/h + 2h @ $30/h = $240 + $60 = $300

**For non-fixed days (weekends/holidays):**
```
cost = non_fixed_rate × labor_hours_paid
```
- Includes 4-hour minimum payment enforcement
- Example: 3h production → pay for 4h @ $40/h = $160

**Key Features:**
- Overhead time included in labor hours (startup + shutdown + changeover)
- Piecewise cost structure enforced via decision variables
- Accurate representation of business labor cost rules

### 4.3 Transport Cost

```
sum(shipment_cohort × route.cost_per_unit)
```
- Sums across all cohort shipments on all routes
- Frozen routes typically cost more than ambient

### 4.4 Holding Cost *(Pallet-Based with Ceiling)*

**If pallet-based costs configured:**
```
holding_cost = sum(
    fixed_cost_per_pallet × pallet_count  (one-time charge)
  + frozen_rate_per_pallet_day × pallet_count  (if frozen state)
  + ambient_rate_per_pallet_day × pallet_count  (if ambient/thawed state)
)
```

**Key properties:**
- Sums across ALL cohorts at ALL nodes across ALL dates
- Ceiling rounding enforced: 1 unit = 1 pallet cost
- Cost minimization drives solver to find minimum feasible `pallet_count`

**Fallback to unit-based costs:**
- If pallet costs are zero, uses legacy `cost_per_unit_day × inventory_qty`
- Provides backward compatibility

**Configuration Precedence:**
1. Pallet-based costs (if any pallet rate > 0)
2. Unit-based costs (if pallet rates = 0 and unit rates > 0)
3. No holding cost (if all rates = 0)

**Performance Tradeoff:**
- Pallet-based: More accurate, slower solve (35-45s for 4-week horizon)
- Unit-based: Less accurate, faster solve (20-30s for 4-week horizon)
- Recommendation: Use unit-based for testing, pallet-based for production

### 4.5 Shortage Penalty

```
shortage_penalty_per_unit × shortage[node, product, date]
```
- Very high penalty (e.g., $1000/unit) to incentivize demand satisfaction
- Only active when `allow_shortages=True`

---

## 5. KEY DESIGN PATTERNS & INTRICACIES

### 5.1 Age-Cohort Inventory Tracking

**Why**: Enables accurate shelf life management for perishable goods
**How**: Each unit of inventory tagged with production date and state
**Benefit**: Can enforce "no product older than 7 days delivered to breadrooms"
**Cost**: Increases variables dramatically (e.g., 18,675 pallet count variables for 4-week horizon)

### 5.2 State Transition Logic

**Automatic state transitions based on route + destination:**
- Frozen route → Frozen storage: stays `'frozen'` (120-day shelf life)
- Frozen route → Ambient storage: becomes `'ambient'` (14-day thawed shelf life)
- Ambient route → Frozen storage: becomes `'frozen'` (re-freezes, resets to 120 days)
- Ambient route → Ambient storage: stays `'ambient'` (17-day shelf life)

**Critical for WA route (6130):**
- Product ships frozen from manufacturing to Lineage buffer
- Lineage ships frozen to 6130
- 6130 (ambient-only storage) receives frozen → thaws on arrival
- Shelf life resets to 14 days upon thawing

### 5.3 Sparse Index Sets

**Problem**: Full Cartesian product would create millions of variables
**Solution**: Only create variables for **valid cohorts**
- Cohorts beyond shelf life: excluded (e.g., 30-day-old ambient product)
- Shipments departing outside planning horizon: excluded
- Demand from future production: excluded (can't satisfy today's demand with tomorrow's production)

**Performance impact**: Reduces variables by ~70-90%

### 5.4 Truck Routing Complexity

**Intermediate stops (Wednesday Lineage route):**
- Single truck departure serves TWO destinations: Lineage + 6125
- Capacity shared across both deliveries
- Different delivery dates: Lineage arrives earlier than 6125

**Day-specific routing:**
- Monday PM: 6122 → 6104
- Tuesday PM: 6122 → 6110
- Wednesday AM: 6122 → Lineage → 6125
- Wednesday PM: 6122 → 6104
- Thursday PM: 6122 → 6110
- Friday PM: 6122 → 6110 **AND** 6122 → 6104 (TWO trucks!)

### 5.5 Pallet-Level Cost Granularity

**Why needed**: Business rule states "partial pallets occupy full pallet space in storage"
- 50 units = 1 pallet in storage costs
- 350 units = 2 pallets in storage costs (not 1.094)

**How enforced**: Integer `pallet_count` variables with ceiling constraint
**Performance cost**: Adds ~18,675 integer variables → 2x solve time (20s → 40s for 4-week horizon)
**Tradeoff**: More accurate cost representation vs. longer solve time

**Not enforced for trucks** (Phase 4 deferred):
- Truck pallet-level enforcement attempted but made problem intractable
- CBC solver couldn't find integer solution in 300s (Gap=100%)
- Current: Unit-based truck capacity (acceptable approximation)

### 5.6 Weekend Enforcement

**Business rule**: No production on weekends unless explicitly scheduled
**Implementation**:
- Labor calendar marks weekends as non-fixed days
- Production capacity constraint: if no labor hours available → production = 0
- Truck constraints: weekend trucks only if explicitly scheduled

### 5.7 Initial Inventory Handling

**Challenge**: Initial inventory may exist before planning horizon starts
**Solution**:
- Assign production date = 1 day before planning start (or snapshot date - 1)
- Mark clearly as "pre-existing stock" (not Day 1 production)
- Include in cohort indices (extended production date range)
- Enables shipping existing stock without producing it

**Example**:
- Planning starts April 1
- Initial inventory of 5000 units at 6122
- Assigned `prod_date = March 31`
- Can be shipped on April 1+ without additional production

### 5.8 Adaptive Variable Bounds *(Performance Optimization)*

- **Production**: Bounded by max daily capacity (avoids unbounded search)
- **Inventory cohorts**: Bounded by `max(daily_production, max_initial_inventory)`
  - Handles edge case: initial inventory exceeds daily production
- **Pallet counts**: Bounded by `ceil(max_inventory_cohort / 320)`
  - OLD (wrong): Used cumulative production → 1,715 pallets (too loose!)
  - NEW (correct): Single cohort = single day production → 62 pallets (tight!)
- **Shipments**: Bounded by `min(max_cohort_size, truck_capacity)`

**Impact**: Tighter bounds → faster solver convergence

### 5.9 No Virtual Locations

**Legacy IntegratedProductionDistributionModel bug**: Used virtual "6122_Storage" location separate from manufacturing
**UnifiedNodeModel fix**: Single node "6122" with both production AND storage capabilities
**Benefit**: Eliminates bypass bug, simplifies constraints, reduces variables

### 5.10 Generalized Truck Constraints

**Legacy limitation**: Truck constraints hardcoded for manufacturing origin only
**UnifiedNodeModel enhancement**: Trucks can constrain ANY route based on `origin_node_id`
**Benefit**: Enables hub-to-spoke truck scheduling, not just manufacturing-to-hub

---

## 6. WHAT THE SOLVER DOES

Given all the above, the Pyomo solver (CBC, Gurobi, CPLEX, etc.) searches for values of all decision variables that:

1. **Satisfy all constraints** (feasibility)
2. **Minimize total cost** (optimality)
3. **Respect integer/binary variable types** (MIP solution)

**Typical solve process:**
1. Build LP relaxation (ignore integer constraints)
2. Solve LP relaxation (gets lower bound)
3. Branch-and-bound search for integer-feasible solution
4. Continue until MIP gap < tolerance (e.g., 1%)

**Output:**
- Optimal production schedule (when/how much to produce each day)
- Optimal distribution plan (which routes, which trucks, which dates)
- Optimal inventory positioning (how much to hold at each node)
- Labor allocation (regular hours vs. overtime vs. weekend)
- Total cost breakdown (production, labor, transport, storage, penalties)
- 100% demand satisfaction (or identifies shortages if demand infeasible)

---

## 7. PERFORMANCE CHARACTERISTICS

### 7.1 Solve Time (4-week horizon with CBC solver)

**With pallet-based storage costs:**
- Solve time: 35-45 seconds
- Integer variables: ~18,675 pallet counts + ~28 labor binaries + changeover tracking
- MIP gap: <1%

**Without pallet-based storage costs:**
- Solve time: 20-30 seconds
- Integer variables: ~28 labor binaries + changeover tracking (no pallet variables)
- MIP gap: <1%

**Integration test timeout:**
- Maximum allowed: 120 seconds
- Expected: <30 seconds (with unit-based costs)
- Default configuration uses unit-based costs to ensure fast solve times

### 7.2 Scalability

**4-week horizon (typical):**
- Planning dates: 28 days
- Products: 5 SKUs
- Nodes: ~10 locations
- Routes: ~10 route legs
- Variables: ~20,000-40,000 (depending on pallet cost configuration)
- Constraints: ~10,000-15,000

**8-week horizon (stress test):**
- Variables: ~40,000-80,000
- Solve time: 60-120 seconds (CBC)
- May require commercial solver for acceptable performance

### 7.3 Solver Recommendations

**For development/testing (fast feedback):**
- Use CBC (open-source, bundled)
- Disable pallet-based storage costs (set to 0.0)
- Enable unit-based costs for approximate storage cost
- Solve time: 20-30s for 4-week horizon

**For production optimization (cost accuracy):**
- Use Gurobi or CPLEX (commercial, licensed)
- Enable pallet-based storage costs
- Longer solve times acceptable for better cost representation
- Solve time: 10-20s for 4-week horizon (Gurobi)

**For large problems (8+ weeks or high SKU count):**
- Gurobi or CPLEX required
- Consider rolling horizon approach (optimize 4 weeks, implement 1 week, re-plan)
- Enable aggressive heuristics for faster initial feasible solutions

### 7.4 Known Performance Bottlenecks

**Pallet-level truck loading** (Phase 4 - deferred):
- Adds ~1,740 integer `truck_pallet_load` variables
- CBC: Gap=100% after 300s (intractable)
- Current workaround: Unit-based truck capacity
- Future: Requires commercial solver or alternative formulation

**Large initial inventory:**
- If initial inventory > daily production, requires looser variable bounds
- Increases search space, slower convergence
- Workaround: Adaptive bounds handle this automatically

**High SKU count:**
- Variables scale linearly with number of products
- 10 products → ~2x variables vs. 5 products
- Solve time scales super-linearly (MIP complexity)

---

## Change Log

### 2025-10-18: Initial Documentation
- Created comprehensive technical specification
- Documented all decision variables, constraints, objective function
- Added design pattern explanations and performance characteristics
- Established maintenance requirement for synchronization with code changes

---

## References

- **Source Code**: `src/optimization/unified_node_model.py`
- **Project Documentation**: `CLAUDE.md`
- **Excel Template Specification**: `data/examples/EXCEL_TEMPLATE_SPEC.md`
- **Manufacturing Operations**: `data/examples/MANUFACTURING_SCHEDULE.md`
- **Network Topology**: `data/examples/NETWORK_ROUTES.md`
- **Integration Test**: `tests/test_integration_ui_workflow.py`
