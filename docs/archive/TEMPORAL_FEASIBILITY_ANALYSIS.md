# Temporal Feasibility Analysis

## Question

**Will the model manufacture product that is impossible to ship to its destination before it is needed?**

## Answer

**NO** - The model has multiple safeguards that prevent manufacturing products that cannot arrive on time.

---

## How the Model Enforces Temporal Feasibility

### 1. Automatic Planning Horizon Extension

**Location:** `src/optimization/integrated_model.py:_calculate_required_planning_horizon()`

The model automatically extends the planning horizon backward to ensure production can occur early enough:

```python
def _calculate_required_planning_horizon(self) -> Tuple[Date, Date]:
    """
    Calculate required planning horizon accounting for transit times AND
    truck loading timing.
    """
    earliest_delivery = min(e.forecast_date for e in self.forecast.entries)
    latest_delivery = max(e.forecast_date for e in self.forecast.entries)

    # Find maximum transit time across all enumerated routes
    max_transit_days = max(r.total_transit_days for r in self.enumerated_routes)

    # Calculate earliest start date needed
    required_start = earliest_delivery - timedelta(days=max_transit_days) - timedelta(days=1)

    return (required_start, latest_delivery)
```

**Example:**
- Earliest demand: June 10
- Route transit time: 3 days
- Morning truck requires D-1 production: 1 extra day
- **Planning horizon starts:** June 6 (10 - 3 - 1)

This ensures production can start early enough to satisfy early demand.

---

### 2. Shipment Variables Indexed by DELIVERY DATE

**Location:** `src/optimization/integrated_model.py` line 820-825

```python
model.shipment = Var(
    model.routes,
    model.products,
    model.dates,  # Use all dates as potential DELIVERY dates
    within=NonNegativeReals,
    doc="Shipment quantity by route, product, and delivery date"
)
```

**Key insight:** Shipments are indexed by when they ARRIVE, not when they depart. This makes it impossible to model a shipment that arrives late.

---

### 3. Inventory Balance Constraint (The Key Enforcement Mechanism)

**Location:** `src/optimization/integrated_model.py` lines 1040-1096

```python
def inventory_balance_rule(model, dest, prod, date):
    """
    Inventory balance at each destination:
    inventory[t] = inventory[t-1] + arrivals[t] - demand[t] - shortage[t]
    """
    # Sum of shipments arriving on THIS date
    arrivals = sum(
        model.shipment[r, prod, date]
        for r in route_list
    )

    demand_qty = self.demand.get((dest, prod, date), 0.0)
    shortage_qty = model.shortage[dest, prod, date] if allow_shortages else 0

    # Balance equation
    return model.inventory[dest, prod, date] == (
        prev_inventory + arrivals - demand_qty - shortage_qty
    )
```

**Combined with:**

```python
model.inventory = Var(
    model.inventory_index,
    within=NonNegativeReals,  # ← CANNOT GO NEGATIVE
    doc="Inventory at destination at end of date"
)
```

**Why this prevents late arrivals:**

If demand is on date D and no shipment arrives by date D:
```
inventory[D] = prev_inventory + 0 - demand[D] - shortage
             = prev_inventory - demand[D] - shortage

If prev_inventory = 0 and shortage = 0 (not allowed):
inventory[D] = -demand[D]  ← INFEASIBLE (inventory must be >= 0)
```

**The model is FORCED to ship products that arrive on or before the demand date.**

---

### 4. Production-to-Truck Timing Constraints

**Location:** `src/optimization/integrated_model.py` lines 1339-1380

These constraints ensure trucks can only load production that has already occurred:

```python
def truck_morning_timing_agg_rule(model, truck_idx, dest, delivery_date):
    """Morning trucks: load on DELIVERY_DATE <= D-1 production on DEPARTURE_DATE"""
    # Calculate when truck departs to arrive on delivery_date
    transit_days = self._get_truck_transit_days(truck_idx, dest)
    departure_date = delivery_date - timedelta(days=transit_days)

    # Morning trucks load D-1 production (day before departure)
    d_minus_1 = departure_date - timedelta(days=1)

    # Truck load must come from previous day's production
    return (sum(model.truck_load[truck_idx, dest, p, delivery_date] for p in model.products) <=
            sum(model.production[d_minus_1, p] for p in model.products))
```

**Example:**
- Demand on June 10
- Transit time: 2 days
- Truck must depart: June 8
- Morning truck loads: June 7 production
- **Production must occur by:** June 7

If production happens on June 9, the constraint would be violated (can't load future production).

---

### 5. Flow Conservation Constraint

**Location:** `src/optimization/integrated_model.py` lines 1100-1124

```python
def flow_conservation_rule(model, prod_date, prod):
    """Production on prod_date >= shipments departing on prod_date"""
    total_shipments = 0
    for r in model.routes:
        transit_days = self.route_transit_days[r]
        for delivery_date in model.dates:
            # Calculate when shipment departs
            departure_date = delivery_date - timedelta(days=transit_days)

            # If shipment departs on prod_date, include it
            if departure_date == prod_date:
                total_shipments += model.shipment[r, prod, delivery_date]

    return model.production[prod_date, prod] >= total_shipments
```

This ensures production is sufficient for all shipments that need to depart on that production date.

---

## How the Constraints Work Together

### Example: Demand on June 10 for 1,000 units

**Scenario:** Can the model produce on June 9 and ship by morning truck?

1. **Demand constraint:**
   ```
   inventory[June 10] = inventory[June 9] + arrivals[June 10] - demand[June 10]
   inventory[June 10] >= 0 (non-negativity)
   Therefore: arrivals[June 10] >= demand[June 10] = 1,000
   ```
   ✅ Forces arrival by June 10

2. **Truck timing:**
   ```
   Truck departs June 8 (2-day transit to arrive June 10)
   Morning truck loads: June 7 production
   Afternoon truck loads: June 7 OR June 8 production
   ```
   ❌ Production on June 9 cannot be loaded

3. **Flow conservation:**
   ```
   production[June 7] >= shipments departing June 8
   ```
   ✅ Ensures production happens before departure

**Conclusion:** Model CANNOT produce on June 9 for June 10 delivery. Must produce by June 7 (morning truck) or June 8 (afternoon truck).

---

## Edge Cases & Warnings

### Edge Case 1: User-Specified Planning Horizon Too Short

If a user manually restricts the planning horizon:

```python
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    start_date=date(2025, 6, 9),  # Too late!
    end_date=date(2025, 6, 15),
    ...
)
```

**The model will warn:**

```python
warnings.warn(
    f"\nPlanning horizon may be insufficient:\n"
    f"  Current start: {final_start}\n"
    f"  Required start: {required_start} ({days_short} days earlier)\n"
    f"  Max transit time: {max_transit} days\n"
    f"  Early demand (on {forecast_start}) cannot be satisfied.\n"
    f"  Solution: Extend planning horizon or accept reduced demand satisfaction."
)
```

**What happens:**
- Early demand becomes infeasible (cannot satisfy inventory balance)
- Model will either:
  - Find infeasible if `allow_shortages=False`
  - Create shortages if `allow_shortages=True`
- **The model will NOT create impossible production schedules**

### Edge Case 2: Shelf Life Filtering

If a route takes longer than product shelf life:

```python
if self.enforce_shelf_life:
    # Filter routes with transit time > max_product_age_days
    valid_routes = [r for r in routes if r.total_transit_days <= 10]
```

**What happens:**
- Long routes are excluded from route enumeration
- Distant destinations may become unreachable
- Model creates shortage or finds infeasible
- **The model will NOT ship products that expire in transit**

---

## Validation During Model Build

The model includes comprehensive validation:

```python
def _validate_feasibility(self) -> None:
    """
    Validate problem feasibility before building optimization model.
    """
    # Check 1: Route coverage
    for dest in self.destinations:
        if dest not in self.routes_to_destination:
            warnings.warn(f"No valid routes to destination {dest}")

    # Check 2: Production capacity
    weekly_capacity = sum(labor.fixed_hours for labor in weekly_labor) * production_rate
    if weekly_demand > weekly_capacity:
        warnings.warn("Demand exceeds regular capacity")

    # Check 3: Shelf life constraints
    if self.enforce_shelf_life:
        for dest in unreachable_destinations:
            warnings.warn(f"Destination {dest} unreachable within shelf life")
```

---

## Conclusion

### Question: Can the model manufacture products that cannot arrive on time?

**Answer: NO**

### Enforcement Mechanisms:

1. ✅ **Planning horizon auto-extension** - Ensures early production is possible
2. ✅ **Inventory non-negativity** - Forces arrivals by demand date
3. ✅ **Truck timing constraints** - Prevents loading future production
4. ✅ **Flow conservation** - Ensures production before departure
5. ✅ **Shipment indexing by delivery date** - Fundamentally prevents modeling late arrivals

### What Happens if Temporal Infeasibility Exists:

**If `allow_shortages=False` (default):**
- Model finds INFEASIBLE
- Solver returns "no solution found"
- User is alerted to fix planning horizon or capacity

**If `allow_shortages=True`:**
- Model creates shortage variables
- Shortage penalty in objective function
- Solution shows which demand cannot be met
- **Still cannot create impossible shipments**

### Safeguards:

1. Automatic planning horizon calculation
2. Warnings when user-specified dates are insufficient
3. Pre-solve feasibility validation
4. Shelf life enforcement (optional but recommended)

---

## Recommendations

### For Users:

1. **Let the model auto-calculate planning horizon** (don't manually restrict)
   ```python
   model = IntegratedProductionDistributionModel(
       forecast=forecast,
       # Don't specify start_date/end_date
       # Let model calculate based on transit times
   )
   ```

2. **Enable feasibility validation** (enabled by default)
   ```python
   model = IntegratedProductionDistributionModel(
       forecast=forecast,
       validate_feasibility=True,  # Default
       ...
   )
   ```

3. **Use allow_shortages during development**
   ```python
   model = IntegratedProductionDistributionModel(
       forecast=forecast,
       allow_shortages=True,  # Helps diagnose capacity issues
       ...
   )
   ```
   Then check shortage variables to identify infeasibility causes.

4. **Enforce shelf life constraints**
   ```python
   model = IntegratedProductionDistributionModel(
       forecast=forecast,
       enforce_shelf_life=True,  # Filters infeasible routes
       max_product_age_days=10,  # Bread shelf life
       ...
   )
   ```

### For Developers:

The model is **structurally sound** with respect to temporal feasibility. No changes needed.

**Optional enhancement:** Add explicit constraint to forbid shipments after demand date:
```python
# Not necessary (already enforced by inventory balance)
# but could be added for explicitness:
def no_late_shipments_rule(model, route, prod, date):
    """Forbid shipments arriving after demand date."""
    dest = route_destination[route]
    if (dest, prod, date) not in self.demand:
        # No demand on this date, shipment would arrive late
        return model.shipment[route, prod, date] == 0
    return Constraint.Skip
```

However, this is **redundant** given the inventory balance constraint.

---

## Summary

The model has **robust temporal feasibility enforcement** through:
- Mathematical constraints (inventory balance, flow conservation, timing)
- Automatic planning horizon calculation
- Validation and warnings
- Structural design (delivery date indexing)

**It is mathematically impossible for the model to produce shipments that arrive after they are needed** (except as explicit shortages if allowed).

The user can trust that any feasible solution respects all temporal constraints and delivery timing requirements.
