# Cost Calculation Module

Complete guide to the cost calculation system for total cost to serve analysis.

## Table of Contents

1. [Overview](#overview)
2. [Cost Components](#cost-components)
3. [Data Models](#data-models)
4. [Cost Calculators](#cost-calculators)
5. [Business Rules](#business-rules)
6. [Usage Examples](#usage-examples)
7. [API Reference](#api-reference)

---

## Overview

The cost calculation module computes the **total cost to serve** by aggregating four cost components:

1. **Labor Costs** - Manufacturing labor (fixed hours, overtime, non-fixed days)
2. **Production Costs** - Per-unit production costs
3. **Transport Costs** - Route-based transport costs
4. **Waste Costs** - Expired inventory and unmet demand penalties

**Purpose:** Provide comprehensive cost visibility for production-distribution decisions and enable cost-based optimization.

**Module Location:** `src/costs/`

**Key Files:**
- `src/costs/cost_breakdown.py` - Cost breakdown data models
- `src/costs/labor_cost_calculator.py` - Labor cost calculation
- `src/costs/production_cost_calculator.py` - Production cost calculation
- `src/costs/transport_cost_calculator.py` - Transport cost calculation
- `src/costs/waste_cost_calculator.py` - Waste cost calculation
- `src/costs/cost_calculator.py` - Cost aggregator

---

## Cost Components

### 1. Labor Costs

**What:** Manufacturing labor expenses for production.

**Components:**
- **Fixed hours cost:** Regular labor hours at standard rate
- **Overtime cost:** Hours beyond fixed allocation at premium rate
- **Non-fixed labor cost:** Weekend/holiday labor with minimum hour commitment

**Typical Proportion:** 5-10% of total cost

**Inputs:**
- ProductionSchedule (quantities by date)
- LaborCalendar (rates and fixed hours by date)

**Key Driver:** Production timing (weekdays cheaper than weekends)

### 2. Production Costs

**What:** Direct costs of manufacturing products.

**Components:**
- Per-unit production cost × units produced

**Typical Proportion:** 70-80% of total cost

**Inputs:**
- ProductionSchedule (batches and quantities)
- CostStructure (production_cost_per_unit)

**Key Driver:** Total volume produced

### 3. Transport Costs

**What:** Costs of shipping products through distribution network.

**Components:**
- Route-based costs (per unit × route cost)
- Cumulative across multi-leg routes

**Typical Proportion:** 10-15% of total cost

**Inputs:**
- List[Shipment] (with routes)

**Key Driver:** Route complexity and distance

### 4. Waste Costs

**What:** Costs of inefficiency and demand gaps.

**Components:**
- **Expired inventory:** Units that exceeded shelf life (production cost × waste multiplier)
- **Unmet demand:** Shortage penalty for demand not satisfied

**Typical Proportion:** 0-5% of total cost (target: minimize)

**Inputs:**
- Forecast (expected demand)
- List[Shipment] (actual fulfillment)
- Optional: expired_units dict (requires shelf life tracking - Phase 3)

**Key Driver:** Forecast accuracy and production-demand matching

---

## Data Models

All data models located in `src/costs/cost_breakdown.py`.

### LaborCostBreakdown

Detailed labor cost breakdown by date.

```python
from src.costs import LaborCostBreakdown

breakdown = LaborCostBreakdown(
    total_cost=1250.00,
    fixed_hours_cost=800.00,
    overtime_cost=350.00,
    non_fixed_labor_cost=100.00,
    total_hours=20.5,
    fixed_hours=16.0,
    overtime_hours=2.5,
    non_fixed_hours=2.0,
    daily_breakdown={
        date(2025, 1, 15): {
            "total_hours": 14.0,
            "fixed_hours": 12.0,
            "overtime_hours": 2.0,
            "fixed_cost": 600.0,
            "overtime_cost": 150.0,
            "total_cost": 750.0
        }
    }
)
```

**Key Fields:**
- `total_cost`: Total labor cost across all dates
- `fixed_hours_cost`: Cost of fixed hours (regular rate)
- `overtime_cost`: Cost of overtime hours (premium rate)
- `non_fixed_labor_cost`: Cost of non-fixed labor days (weekend/holiday, minimum 4h)
- `total_hours`: Total labor hours used
- `daily_breakdown`: Cost breakdown by date

### ProductionCostBreakdown

Detailed production cost breakdown by product.

```python
from src.costs import ProductionCostBreakdown

breakdown = ProductionCostBreakdown(
    total_cost=17920.00,
    total_units_produced=22400.0,
    average_cost_per_unit=0.80,
    cost_by_product={
        "PROD1": 4480.00,
        "PROD2": 13440.00
    },
    cost_by_date={
        date(2025, 1, 15): 8960.00,
        date(2025, 1, 16): 8960.00
    },
    batch_details=[
        {
            "batch_id": "BATCH-001",
            "product_id": "PROD1",
            "quantity": 5600.0,
            "cost_per_unit": 0.80,
            "total_cost": 4480.00
        }
    ]
)
```

**Key Fields:**
- `total_cost`: Total production cost across all batches
- `total_units_produced`: Total units produced
- `average_cost_per_unit`: Average production cost per unit
- `cost_by_product`: Cost breakdown by product
- `cost_by_date`: Cost breakdown by production date
- `batch_details`: Per-batch cost details

### TransportCostBreakdown

Detailed transport cost breakdown by route.

```python
from src.costs import TransportCostBreakdown

breakdown = TransportCostBreakdown(
    total_cost=3060.00,
    total_units_shipped=5600.0,
    average_cost_per_unit=0.546,
    cost_by_route={
        "6122 → 6125 → 6103": 1500.00,
        "6122 → 6104 → 6101": 1560.00
    },
    shipment_details=[
        {
            "shipment_id": "SHIP-001",
            "product_id": "PROD1",
            "quantity": 3000.0,
            "route": "6122 → 6125 → 6103",
            "cost_per_unit": 0.50,
            "total_cost": 1500.00
        }
    ]
)
```

**Key Fields:**
- `total_cost`: Total transport cost across all shipments
- `total_units_shipped`: Total units shipped
- `average_cost_per_unit`: Average transport cost per unit
- `cost_by_route`: Cost breakdown by route path
- `shipment_details`: Per-shipment cost details

### WasteCostBreakdown

Detailed waste cost breakdown.

```python
from src.costs import WasteCostBreakdown

breakdown = WasteCostBreakdown(
    total_cost=720.00,
    expired_units=100.0,
    expired_cost=120.00,  # 100 × ($0.80 × 1.5 multiplier)
    unmet_demand_units=400.0,
    unmet_demand_cost=600.00,  # 400 × $1.50 shortage penalty
    waste_by_location={
        "6103": 120.00,  # Expired inventory
        "6101": 600.00   # Unmet demand
    },
    waste_by_product={
        "PROD1": 600.00
    },
    waste_details=[
        {
            "location_id": "6103",
            "units_expired": 100.0,
            "cost_per_unit": 1.20,
            "total_cost": 120.00
        }
    ]
)
```

**Key Fields:**
- `total_cost`: Total waste cost
- `expired_units`: Units that expired (shelf life)
- `expired_cost`: Cost of expired inventory
- `unmet_demand_units`: Units of unmet demand
- `unmet_demand_cost`: Opportunity cost of unmet demand
- `waste_by_location`: Waste breakdown by location
- `waste_by_product`: Waste breakdown by product

### TotalCostBreakdown

Aggregated cost breakdown across all components.

```python
from src.costs import TotalCostBreakdown

total = TotalCostBreakdown(
    total_cost=22380.00,
    labor=labor_breakdown,
    production=production_breakdown,
    transport=transport_breakdown,
    waste=waste_breakdown,
    cost_per_unit_delivered=3.996  # Total cost / units delivered
)
```

**Key Fields:**
- `total_cost`: Total cost to serve (sum of all components)
- `labor`: LaborCostBreakdown
- `production`: ProductionCostBreakdown
- `transport`: TransportCostBreakdown
- `waste`: WasteCostBreakdown
- `cost_per_unit_delivered`: Average cost per unit delivered to customer

**Key Methods:**
- `get_cost_proportions()` - Returns proportion of each cost component (0.0 to 1.0)

**Example:**
```python
proportions = total.get_cost_proportions()
# Returns: {
#     "labor": 0.036,      # 3.6%
#     "production": 0.801, # 80.1%
#     "transport": 0.137,  # 13.7%
#     "waste": 0.027       # 2.7%
# }
```

---

## Cost Calculators

All cost calculators located in `src/costs/`.

### LaborCostCalculator

Calculates labor costs from production schedule and labor calendar.

**File:** `src/costs/labor_cost_calculator.py`

**Purpose:** Compute labor costs accounting for fixed hours, overtime, and non-fixed labor days (weekends/holidays).

**Key Concept:** Uses actual rates from LaborCalendar, **not** CostStructure defaults.

**Algorithm:**

For each production date:
1. Get labor day from calendar
2. Calculate production hours needed = quantity / 1400 units/hour
3. Allocate hours to cost categories:
   - **Fixed day:** Fixed hours at regular rate + overtime at premium rate
   - **Non-fixed day:** Pay max(actual hours, minimum hours) at non-fixed rate
4. Aggregate across all dates

**Example:**

```python
from src.costs import LaborCostCalculator

calculator = LaborCostCalculator(labor_calendar)
breakdown = calculator.calculate_labor_cost(production_schedule)

print(f"Total labor cost: ${breakdown.total_cost:,.2f}")
print(f"  Fixed hours: ${breakdown.fixed_hours_cost:,.2f} ({breakdown.fixed_hours:.1f}h)")
print(f"  Overtime: ${breakdown.overtime_cost:,.2f} ({breakdown.overtime_hours:.1f}h)")
print(f"  Non-fixed: ${breakdown.non_fixed_labor_cost:,.2f} ({breakdown.non_fixed_hours:.1f}h)")
```

**Constants:**
- `UNITS_PER_HOUR = 1400` - Production rate

### ProductionCostCalculator

Calculates production costs from production batches.

**File:** `src/costs/production_cost_calculator.py`

**Purpose:** Compute per-unit production costs across all batches.

**Algorithm:**

For each production batch:
1. Get per-unit production cost from cost structure
2. Calculate batch cost = quantity × cost_per_unit
3. Aggregate by product and date

**Example:**

```python
from src.costs import ProductionCostCalculator

calculator = ProductionCostCalculator(cost_structure)
breakdown = calculator.calculate_production_cost(production_schedule)

print(f"Total production cost: ${breakdown.total_cost:,.2f}")
print(f"Units produced: {breakdown.total_units_produced:,.0f}")
print(f"Cost per unit: ${breakdown.average_cost_per_unit:.2f}")

print("\nCost by product:")
for product_id, cost in breakdown.cost_by_product.items():
    print(f"  {product_id}: ${cost:,.2f}")
```

### TransportCostCalculator

Calculates transport costs from shipments and routes.

**File:** `src/costs/transport_cost_calculator.py`

**Purpose:** Compute route-based transport costs across all shipments.

**Algorithm:**

For each shipment:
1. Get route from shipment
2. Calculate cost = quantity × route.total_cost
3. Aggregate by route and overall

**Note:** Individual leg costs not tracked in current model (route.total_cost is cumulative).

**Example:**

```python
from src.costs import TransportCostCalculator

calculator = TransportCostCalculator()
breakdown = calculator.calculate_transport_cost(shipments)

print(f"Total transport cost: ${breakdown.total_cost:,.2f}")
print(f"Units shipped: {breakdown.total_units_shipped:,.0f}")
print(f"Cost per unit: ${breakdown.average_cost_per_unit:.2f}")

print("\nCost by route:")
for route, cost in breakdown.cost_by_route.items():
    print(f"  {route}: ${cost:,.2f}")
```

### WasteCostCalculator

Calculates waste costs from expired inventory and unmet demand.

**File:** `src/costs/waste_cost_calculator.py`

**Purpose:** Compute costs of inefficiency and demand gaps.

**Algorithm:**

**Unmet Demand:**
1. Compare forecast to shipments by (location, date, product)
2. Calculate gap: unmet = max(0, forecast - shipped)
3. Cost = unmet × shortage_penalty_per_unit

**Expired Inventory (Phase 3):**
1. Receive dict of location_id → units expired
2. Cost per unit = production_cost_per_unit × waste_cost_multiplier
3. Cost = expired × cost_per_unit

**Example:**

```python
from src.costs import WasteCostCalculator

calculator = WasteCostCalculator(cost_structure)
breakdown = calculator.calculate_waste_cost(
    forecast=forecast,
    shipments=shipments,
    expired_units={"6103": 100.0}  # Optional, requires shelf life tracking
)

print(f"Total waste cost: ${breakdown.total_cost:,.2f}")
print(f"  Expired inventory: {breakdown.expired_units:.0f} units (${breakdown.expired_cost:,.2f})")
print(f"  Unmet demand: {breakdown.unmet_demand_units:.0f} units (${breakdown.unmet_demand_cost:,.2f})")
```

### CostCalculator

Aggregates all cost components into total cost to serve.

**File:** `src/costs/cost_calculator.py`

**Purpose:** Coordinate individual cost calculators and provide total cost breakdown.

**Algorithm:**

1. Calculate labor costs (LaborCostCalculator)
2. Calculate production costs (ProductionCostCalculator)
3. Calculate transport costs (TransportCostCalculator)
4. Calculate waste costs (WasteCostCalculator)
5. Sum to get total cost
6. Calculate cost per unit delivered

**Example:**

```python
from src.costs import CostCalculator

calculator = CostCalculator(cost_structure, labor_calendar)
total = calculator.calculate_total_cost(
    production_schedule=schedule,
    shipments=shipments,
    forecast=forecast,
    expired_units=None  # Optional
)

print(f"Total Cost to Serve: ${total.total_cost:,.2f}")
print(f"  Labor: ${total.labor.total_cost:,.2f}")
print(f"  Production: ${total.production.total_cost:,.2f}")
print(f"  Transport: ${total.transport.total_cost:,.2f}")
print(f"  Waste: ${total.waste.total_cost:,.2f}")
print(f"\nCost per unit delivered: ${total.cost_per_unit_delivered:.2f}")

# Analyze cost proportions
proportions = total.get_cost_proportions()
print("\nCost Proportions:")
for component, proportion in proportions.items():
    print(f"  {component.capitalize()}: {proportion:.1%}")
```

---

## Business Rules

### 1. Labor Cost Rules

#### Fixed Labor Days (Weekdays)

**Rule:** Labor days with fixed hour allocation.

**Cost Calculation:**
- Hours ≤ fixed_hours: `cost = hours × regular_rate`
- Hours > fixed_hours: `cost = (fixed_hours × regular_rate) + ((hours - fixed_hours) × overtime_rate)`

**Example:**
- Fixed hours: 12h at $50/h
- Overtime rate: $75/h
- Production requires 13 hours
- Cost = (12 × $50) + (1 × $75) = $600 + $75 = $675

#### Non-Fixed Labor Days (Weekends/Holidays)

**Rule:** Labor days without fixed allocation (weekend/holiday production).

**Minimum Hour Commitment:** Must pay for minimum hours even if production requires less.

**Cost Calculation:**
- `cost = max(actual_hours, minimum_hours) × non_fixed_rate`

**Example:**
- Minimum hours: 4h
- Non-fixed rate: $100/h
- Production requires 3 hours
- Cost = max(3, 4) × $100 = 4 × $100 = $400 (pay for 4h even though only 3h used)

#### Labor Rate Source

**Critical Rule:** Use rates from LaborCalendar, **not** CostStructure.

**Reason:** Labor calendar has actual daily rates (varies by day). CostStructure has defaults only.

### 2. Production Cost Rules

**Rule:** Fixed per-unit production cost.

**Cost Calculation:**
- `cost = quantity × production_cost_per_unit`

**Example:**
- Production: 22,400 units
- Cost per unit: $0.80
- Total cost = 22,400 × $0.80 = $17,920

**Future (Phase 4):** May include setup costs, economies of scale, batch-dependent costs.

### 3. Transport Cost Rules

**Rule:** Route-based costs (cumulative across multi-leg routes).

**Cost Calculation:**
- `cost = quantity × route.total_cost`

**Example:**
- Shipment: 3,000 units
- Route: 6122 → 6125 → 6103 (cost $0.50/unit)
- Total cost = 3,000 × $0.50 = $1,500

**Note:** Individual leg costs not tracked in current model. Route provides total cumulative cost.

### 4. Waste Cost Rules

#### Expired Inventory Cost

**Rule:** Cost of units that exceeded shelf life (requires Phase 3 shelf life tracking).

**Cost Calculation:**
- `cost_per_unit = production_cost_per_unit × waste_cost_multiplier`
- `cost = expired_units × cost_per_unit`

**Example:**
- Expired: 100 units
- Production cost: $0.80/unit
- Waste multiplier: 1.5
- Cost = 100 × ($0.80 × 1.5) = 100 × $1.20 = $120

**Rationale:** Waste cost > production cost (includes handling, disposal, opportunity cost).

#### Unmet Demand Cost

**Rule:** Penalty for demand not satisfied (shortage/stockout).

**Cost Calculation:**
- `cost = unmet_demand_units × shortage_penalty_per_unit`

**Example:**
- Forecast: 3,000 units
- Shipped: 2,600 units
- Unmet: 400 units
- Shortage penalty: $1.50/unit
- Cost = 400 × $1.50 = $600

**Rationale:** Represents lost revenue, customer dissatisfaction, and potential future lost sales.

### 5. Cost Aggregation Rules

**Total Cost to Serve:**
- `total_cost = labor_cost + production_cost + transport_cost + waste_cost`

**Cost Per Unit Delivered:**
- `cost_per_unit = total_cost / total_units_shipped`
- Used for profitability analysis and pricing decisions

**Typical Cost Proportions (well-optimized plan):**
- Production: 70-80%
- Transport: 10-15%
- Labor: 5-10%
- Waste: 0-5% (target: minimize)

**High-Level Targets:**
- Labor cost < 10% (efficient production scheduling)
- Waste cost < 5% (good forecast accuracy, shelf life management)
- Total cost per unit < product selling price (profitable operations)

---

## Usage Examples

### Example 1: Calculate Total Cost to Serve

```python
from src.costs import CostCalculator
from datetime import date

# Initialize calculator
calculator = CostCalculator(cost_structure, labor_calendar)

# Calculate total cost
total = calculator.calculate_total_cost(
    production_schedule=schedule,
    shipments=shipments,
    forecast=forecast
)

# Display summary
print("=" * 60)
print(f"TOTAL COST TO SERVE: ${total.total_cost:,.2f}")
print("=" * 60)
print(f"Labor:      ${total.labor.total_cost:,.2f}")
print(f"Production: ${total.production.total_cost:,.2f}")
print(f"Transport:  ${total.transport.total_cost:,.2f}")
print(f"Waste:      ${total.waste.total_cost:,.2f}")
print("=" * 60)
print(f"Cost per unit delivered: ${total.cost_per_unit_delivered:.2f}")
```

### Example 2: Analyze Labor Cost Breakdown

```python
from src.costs import LaborCostCalculator

calculator = LaborCostCalculator(labor_calendar)
labor = calculator.calculate_labor_cost(production_schedule)

print("LABOR COST BREAKDOWN")
print(f"Total: ${labor.total_cost:,.2f}")
print(f"\nHours:")
print(f"  Fixed:     {labor.fixed_hours:.1f}h @ ${labor.fixed_hours_cost/labor.fixed_hours:.0f}/h = ${labor.fixed_hours_cost:,.2f}")
print(f"  Overtime:  {labor.overtime_hours:.1f}h @ premium = ${labor.overtime_cost:,.2f}")
print(f"  Non-fixed: {labor.non_fixed_hours:.1f}h @ premium = ${labor.non_fixed_labor_cost:,.2f}")

print(f"\nDaily breakdown:")
for prod_date, breakdown in labor.daily_breakdown.items():
    day_name = prod_date.strftime("%A")
    print(f"  {prod_date} ({day_name}): ${breakdown['total_cost']:,.2f}")
    print(f"    Fixed: {breakdown['fixed_hours']:.1f}h, OT: {breakdown['overtime_hours']:.1f}h")
```

### Example 3: Compare Cost Scenarios

```python
# Scenario 1: Weekday production only
schedule1 = create_weekday_schedule()
total1 = calculator.calculate_total_cost(
    production_schedule=schedule1,
    shipments=shipments1,
    forecast=forecast
)

# Scenario 2: Includes weekend production
schedule2 = create_weekend_schedule()
total2 = calculator.calculate_total_cost(
    production_schedule=schedule2,
    shipments=shipments2,
    forecast=forecast
)

# Compare
print("SCENARIO COMPARISON")
print(f"Weekday only: ${total1.total_cost:,.2f} (labor: ${total1.labor.total_cost:,.2f})")
print(f"With weekend: ${total2.total_cost:,.2f} (labor: ${total2.labor.total_cost:,.2f})")
print(f"Difference:   ${total2.total_cost - total1.total_cost:,.2f}")
```

### Example 4: Analyze Transport Costs by Route

```python
from src.costs import TransportCostCalculator

calculator = TransportCostCalculator()
transport = calculator.calculate_transport_cost(shipments)

print("TRANSPORT COST BY ROUTE")
print(f"Total: ${transport.total_cost:,.2f} ({transport.total_units_shipped:,.0f} units)\n")

# Sort routes by cost (highest first)
sorted_routes = sorted(transport.cost_by_route.items(), key=lambda x: x[1], reverse=True)

for route, cost in sorted_routes:
    # Find shipments on this route
    route_shipments = [s for s in shipments if " → ".join(s.route.path) == route]
    total_units = sum(s.quantity for s in route_shipments)
    cost_per_unit = cost / total_units if total_units > 0 else 0

    print(f"{route}:")
    print(f"  Total cost: ${cost:,.2f}")
    print(f"  Units: {total_units:,.0f}")
    print(f"  Cost/unit: ${cost_per_unit:.3f}")
    print(f"  Shipments: {len(route_shipments)}")
    print()
```

### Example 5: Track Waste Costs

```python
from src.costs import WasteCostCalculator

calculator = WasteCostCalculator(cost_structure)
waste = calculator.calculate_waste_cost(
    forecast=forecast,
    shipments=shipments
)

print("WASTE COST ANALYSIS")
print(f"Total waste cost: ${waste.total_cost:,.2f}\n")

if waste.unmet_demand_units > 0:
    print(f"Unmet Demand:")
    print(f"  Units: {waste.unmet_demand_units:,.0f}")
    print(f"  Cost: ${waste.unmet_demand_cost:,.2f}")
    print(f"  Locations affected: {len(waste.waste_by_location)}")

if waste.expired_units > 0:
    print(f"\nExpired Inventory:")
    print(f"  Units: {waste.expired_units:,.0f}")
    print(f"  Cost: ${waste.expired_cost:,.2f}")

# Action items
if waste.total_cost > 0:
    waste_pct = waste.total_cost / total.total_cost
    print(f"\n⚠️ Waste represents {waste_pct:.1%} of total cost")
    if waste_pct > 0.05:
        print("  → High waste! Review forecast accuracy and production-demand matching")
```

### Example 6: Daily Labor Cost Report

```python
from src.costs import LaborCostCalculator

calculator = LaborCostCalculator(labor_calendar)

# Calculate cost for single day
daily_cost = calculator.calculate_daily_labor_cost(
    prod_date=date(2025, 1, 15),
    quantity=18200.0  # 13 hours at 1400 units/hour
)

print("DAILY LABOR COST REPORT")
print(f"Date: {date(2025, 1, 15).strftime('%A, %B %d, %Y')}")
print(f"Quantity: {18200.0:,.0f} units\n")
print(f"Hours needed: {daily_cost['hours_needed']:.1f}h")
print(f"Hours paid: {daily_cost['hours_paid']:.1f}h\n")
print(f"Fixed hours cost: ${daily_cost['fixed_cost']:,.2f}")
print(f"Overtime cost: ${daily_cost['overtime_cost']:,.2f}")
print(f"Non-fixed cost: ${daily_cost['non_fixed_cost']:,.2f}")
print(f"Total cost: ${daily_cost['total_cost']:,.2f}")
```

---

## API Reference

### CostCalculator

#### `__init__(cost_structure: CostStructure, labor_calendar: LaborCalendar)`

Initialize cost calculator.

**Parameters:**
- `cost_structure`: Cost structure with rates and penalties
- `labor_calendar`: Labor calendar with daily rates and fixed hours

#### `calculate_total_cost(...) -> TotalCostBreakdown`

Calculate total cost to serve.

**Parameters:**
- `production_schedule`: ProductionSchedule with batches
- `shipments`: List of shipments with routes
- `forecast`: Demand forecast (for unmet demand calculation)
- `expired_units`: Optional dict of location_id → units expired

**Returns:**
- TotalCostBreakdown with all cost components

#### Individual Cost Methods

- `calculate_labor_cost(production_schedule)` - Labor costs only
- `calculate_production_cost(production_schedule)` - Production costs only
- `calculate_transport_cost(shipments)` - Transport costs only
- `calculate_waste_cost(forecast, shipments, expired_units)` - Waste costs only

### LaborCostCalculator

#### `__init__(labor_calendar: LaborCalendar)`

Initialize labor cost calculator.

#### `calculate_labor_cost(schedule: ProductionSchedule) -> LaborCostBreakdown`

Calculate total labor cost from production schedule.

**Returns:**
- LaborCostBreakdown with detailed breakdown

#### `calculate_daily_labor_cost(prod_date: date, quantity: float) -> Dict[str, float]`

Calculate labor cost for a single production day.

**Returns:**
- Dictionary with cost breakdown (total_cost, fixed_cost, overtime_cost, non_fixed_cost, hours_needed, hours_paid)

**Constants:**
- `UNITS_PER_HOUR = 1400` - Production rate

### ProductionCostCalculator

#### `__init__(cost_structure: CostStructure)`

Initialize production cost calculator.

#### `calculate_production_cost(schedule: ProductionSchedule) -> ProductionCostBreakdown`

Calculate total production cost from production schedule.

**Returns:**
- ProductionCostBreakdown with detailed breakdown

#### Helper Methods

- `calculate_batch_cost(batch)` - Cost for single batch
- `calculate_quantity_cost(quantity)` - Cost for given quantity

### TransportCostCalculator

#### `calculate_transport_cost(shipments: List[Shipment]) -> TransportCostBreakdown`

Calculate total transport cost from shipments.

**Returns:**
- TransportCostBreakdown with detailed breakdown

#### Helper Methods

- `calculate_shipment_cost(shipment)` - Cost for single shipment
- `calculate_route_cost(quantity, route)` - Cost for given quantity on route

### WasteCostCalculator

#### `__init__(cost_structure: CostStructure)`

Initialize waste cost calculator.

#### `calculate_waste_cost(forecast, shipments, expired_units=None) -> WasteCostBreakdown`

Calculate total waste cost.

**Parameters:**
- `forecast`: Demand forecast
- `shipments`: List of shipments
- `expired_units`: Optional dict of location_id → units expired

**Returns:**
- WasteCostBreakdown with detailed breakdown

#### Helper Methods

- `calculate_unmet_demand_penalty(units)` - Penalty for unmet demand

---

## Next Steps

- **Phase 3:** Shelf life tracking for accurate expired inventory costs
- **Phase 3:** Holding costs (storage at hubs, time-based)
- **Phase 4:** Setup costs (batch-dependent production costs)
- **Phase 4:** Economies of scale (volume discounts)
- **Phase 4:** Dynamic transport costs (fuel prices, seasonal rates)

---

**Module Version:** Phase 2 (Basic cost calculation)

**Last Updated:** 2025-10-02

**Related Documentation:**
- `TRUCK_LOADING.md` - Truck loading module
- `MANUFACTURING_SCHEDULE.md` - Labor and production details
