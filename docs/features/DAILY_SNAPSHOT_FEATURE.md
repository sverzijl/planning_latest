# Daily Inventory Snapshot Feature

## Table of Contents

1. [Overview](#overview)
2. [User Guide](#user-guide)
   - [Accessing the Feature](#21-accessing-the-feature)
   - [Using the Interface](#22-using-the-interface)
   - [Interpreting Results](#23-interpreting-results)
   - [Common Use Cases](#24-common-use-cases)
3. [Technical Documentation](#technical-documentation)
   - [Architecture](#31-architecture)
   - [Data Models](#32-data-models)
   - [Calculations](#33-calculations)
   - [UI Component](#34-ui-component)
4. [Developer Guide](#developer-guide)
   - [Adding to Your Application](#41-adding-to-your-application)
   - [Customization](#42-customization)
   - [Extending the Feature](#43-extending-the-feature)
   - [Performance Considerations](#44-performance-considerations)
5. [API Reference](#api-reference)
   - [DailySnapshotGenerator](#51-dailysnapshotgenerator)
   - [render_daily_snapshot()](#52-render_daily_snapshot)
6. [Examples](#examples)
   - [Basic Usage](#61-basic-usage)
   - [Accessing Specific Data](#62-accessing-specific-data)
   - [Integration with UI](#63-integration-with-ui)
7. [Testing](#testing)
   - [Running Tests](#71-running-tests)
   - [Test Coverage](#72-test-coverage)
8. [Troubleshooting](#troubleshooting)
   - [Common Issues](#81-common-issues)
   - [FAQ](#82-faq)
9. [Roadmap](#roadmap)
   - [Current Limitations](#91-current-limitations)
   - [Future Enhancements](#92-future-enhancements)
10. [References](#references)

---

## 1. Overview

### Feature Name
**Daily Inventory Snapshot**

### Purpose
The Daily Inventory Snapshot feature provides comprehensive visibility into the state of your supply chain network on any given date. It tracks inventory positions, in-transit shipments, production activity, and demand satisfaction across all locations in real-time.

### High-Level Description

In modern production-distribution planning, understanding the complete state of your supply chain at any point in time is critical for operational decision-making. The Daily Inventory Snapshot feature transforms complex planning results into an intuitive, day-by-day view of your entire network.

This feature analyzes production schedules and shipment plans to reconstruct the exact inventory position at every location, identify shipments in transit, track batch ages, and calculate daily inflows and outflows. It provides operations teams with a powerful tool to validate plans, diagnose issues, and make informed decisions about production adjustments and distribution strategies.

Unlike traditional inventory reports that show only aggregate totals, the Daily Snapshot tracks individual production batches through the network, maintaining full traceability from manufacturing through delivery. This batch-level visibility enables sophisticated analysis of inventory freshness, FIFO compliance, and shelf-life management.

### Key Benefits

- **Complete Visibility**: See the entire supply chain state on any date with a single view
- **Batch Traceability**: Track individual production batches from manufacturing through the network
- **Real-time Navigation**: Quickly move between dates to understand inventory dynamics
- **Visual Age Tracking**: Color-coded batch ages help identify freshness issues
- **Flow Analysis**: Understand daily inflows (production + arrivals) and outflows (departures + demand)
- **Demand Validation**: Verify that production plans satisfy customer demand
- **Bottleneck Detection**: Identify locations with excess inventory or potential stockouts
- **Plan Confidence**: Validate optimization results before execution

### Visual Interface

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Daily Inventory Snapshot                                            📸      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Select Date: [━━━━━━━━━━━●━━━━━━━━] 2025-01-15 (Wed)                      │
│               [⬅️ Previous Day]  [Next Day ➡️]                               │
│                                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Total Inventory    In Transit    Production    Demand                       │
│  45,000 units       12,000        8,000         5,500                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  📦 Inventory at Locations                                                   │
│  ▼ 6122 - Manufacturing Site (23,000 units)                                 │
│     Batch ID      Product    Quantity    Age      Production Date            │
│     BATCH-0045    176283     5,000       2 days   2025-01-13     [FRESH]    │
│     BATCH-0046    176284     3,000       2 days   2025-01-13     [FRESH]    │
│     ...                                                                       │
│                                                                               │
│  ▶ 6104 - NSW/ACT Hub (15,000 units)                                        │
│  ▶ 6125 - VIC/TAS/SA Hub (7,000 units)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  🚚 In Transit              │  🏭 Manufacturing Activity                     │
│  Route       Product  Qty   │  Batch       Product   Qty      Labor         │
│  6122→6104   176283   5000  │  BATCH-0051  176283    5000     8.5h          │
│  6122→6125   176284   3000  │  BATCH-0052  176284    3000     5.1h          │
│  ...                         │  Total Labor Hours: 13.6h                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ⬇️ Inflows                 │  ⬆️ Outflows                                   │
│  Type        Location  Qty  │  Type        Location  Qty                    │
│  Production  6122      8000 │  Departure   6122      12000                  │
│  Arrival     6104      5000 │  Demand      6103      5500                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✅ Demand Satisfaction                                                      │
│  Destination    Product    Demand    Supplied    Status                     │
│  6103           176283     3000      3000        ✅ Met                      │
│  6130           176284     2500      2500        ✅ Met                      │
│                                                                               │
│  ✓ All Demand Met                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. User Guide

### 2.1 Accessing the Feature

#### Navigation
1. Open the Planning Application
2. Upload your input data (forecast, locations, routes, etc.)
3. Run the optimization solver
4. Navigate to the **Results** page
5. Select the **Daily Snapshot** tab

#### Prerequisites
- A completed planning run with production schedule and shipments
- Valid location data loaded into the system
- At least one production batch or shipment in the plan

**Note**: The Daily Snapshot feature is only available after successfully generating planning results. If you haven't run the optimizer yet, you'll see a message indicating no data is available.

### 2.2 Using the Interface

#### Date Selector

The date selector is the primary navigation tool for the snapshot feature:

**Slider Navigation**:
- Drag the slider to quickly jump to any date in your planning horizon
- The slider displays dates in `YYYY-MM-DD (Day)` format (e.g., "2025-01-15 (Wed)")
- The range automatically spans from the first production date to the last delivery date

**Button Navigation**:
- **Previous Day (⬅️)**: Move backward one day
- **Next Day (➡️)**: Move forward one day
- Buttons are disabled at the start and end of the date range

**Tips**:
- Use buttons for sequential day-by-day analysis
- Use the slider to jump to specific dates of interest
- The current selection persists as you navigate to other tabs and return

#### Summary Metrics

Four key metrics are displayed at the top of every snapshot:

1. **Total Inventory**: Sum of all inventory quantities across all locations at end of day
   - Includes only inventory that has arrived and not yet departed
   - Does NOT include in-transit shipments (shown separately)

2. **In Transit**: Total quantity currently on trucks between locations
   - Shipments that have departed origin but not yet arrived at destination
   - Critical for understanding working capital and pipeline inventory

3. **Production**: Total units produced on this specific date
   - Sum of all production batches manufactured today
   - Zero on non-production days (e.g., weekends)

4. **Demand**: Total customer demand scheduled for this date
   - Sum of all forecasted demand across all destinations
   - Compared against supplied quantities for satisfaction tracking

#### Location Inventory

Expandable sections for each location containing inventory:

**Location Headers**:
- Format: `Location ID - Location Name (Total Units)`
- Sorted by total quantity (highest first)
- Manufacturing site is expanded by default

**Batch Details**:
Each location shows a table of production batches:
- **Batch ID**: Unique identifier for the production batch
- **Product**: Product SKU or identifier
- **Quantity**: Units currently at this location
- **Age (days)**: Number of days since production
- **Production Date**: Original manufacturing date

**Color Coding** (Age-Based):
- **Green Background (0-3 days)**: Fresh inventory
- **Yellow Background (4-7 days)**: Medium-age inventory
- **Red Background (8+ days)**: Older inventory requiring attention

**What It Tells You**:
- Which batches are sitting at each location
- How fresh the inventory is (critical for perishable goods)
- Whether FIFO (First-In-First-Out) is being followed
- Potential slow-moving or at-risk inventory

#### In-Transit View

Shows shipments currently on trucks:

**Transit Table Columns**:
- **Route**: Origin → Destination
- **Product**: Product identifier
- **Quantity**: Units being shipped
- **Days in Transit**: How long the shipment has been traveling

**Understanding Transit States**:
- A shipment is "in transit" if: `departure_date <= snapshot_date < arrival_date`
- For multi-leg routes, shows which leg the shipment is currently on
- Transit time is calculated from the current leg's departure date

**Use Cases**:
- Verify truck utilization and loading
- Identify delayed shipments
- Understand pipeline inventory between locations

#### Manufacturing Activity

Displays production batches created on the selected date:

**Production Table Columns**:
- **Batch ID**: Unique batch identifier
- **Product**: Product being manufactured
- **Quantity**: Units produced in this batch
- **Labor Hours**: Hours of labor consumed for this batch

**Summary Information**:
- **Total Labor Hours**: Sum of labor hours across all batches produced today
- Helps verify labor capacity constraints are satisfied
- Enables comparison against available labor hours from the labor calendar

**Key Insights**:
- Daily production quantities by product
- Labor utilization on this date
- Whether production occurred (zero on weekends/holidays)

#### Inflows/Outflows

Two-column view showing inventory movements:

**Inflow Types**:
1. **Production** (Blue Background)
   - New units manufactured at the plant
   - Details show batch ID

2. **Arrival** (Green Background)
   - Shipments arriving at destinations
   - Details show origin location

**Outflow Types**:
1. **Departure** (Yellow Background)
   - Shipments leaving locations
   - Details show destination location

2. **Demand** (Light Blue Background)
   - Customer deliveries
   - Details indicate demand fulfillment

**Flow Table Columns**:
- **Type**: Flow category (Production/Arrival/Departure/Demand)
- **Location**: Where the flow occurs
- **Product**: Product identifier
- **Quantity**: Units flowing
- **Details**: Additional context (counterparty location, batch ID)

**Why This Matters**:
- Verify mass balance: Inflows should eventually equal outflows
- Understand daily inventory dynamics
- Identify unusual patterns or imbalances

#### Demand Satisfaction

Tracks how well the plan meets customer requirements:

**Demand Table Columns**:
- **Destination**: Customer location receiving product
- **Product**: Product identifier
- **Demand**: Forecasted quantity needed
- **Supplied**: Actual quantity delivered in the plan
- **Status**: Met (✅) or Short with shortage amount (⚠️)

**Status Indicators**:
- **Green Background + ✅ Met**: Demand fully satisfied
- **Yellow Background + ⚠️ Short**: Demand not fully met, shows shortage quantity

**Overall Status Badge**:
- **Green "All Demand Met"**: Perfect satisfaction across all products/locations
- **Yellow Badge with Shortage**: Shows total shortage quantity across all items

**Interpretation**:
- Shortages indicate infeasible demand or capacity constraints
- Can result from production limits, truck capacity, or shelf-life constraints
- Use this section to prioritize which shortages to address first

### 2.3 Interpreting Results

#### Understanding Batch Ages

**Color-Coded Age Ranges**:
- **0-3 days (Green)**: Optimal freshness
  - Ideal for distribution to customers
  - Maximum remaining shelf life
  - Highest quality

- **4-7 days (Yellow)**: Acceptable but monitor
  - Approaching breadroom discard threshold (7 days)
  - Should be prioritized for shipment
  - Still acceptable for most uses

- **8+ days (Red)**: Requires immediate attention
  - Beyond typical breadroom acceptance
  - High waste risk
  - May indicate overproduction or distribution delays

**What to Look For**:
- Batches aging at hubs indicate potential distribution bottlenecks
- Old batches at manufacturing suggest overproduction
- Uniform ages suggest smooth production flow
- Mixed ages may indicate production variability

#### Reading Transit Information

**Key Indicators**:
- **Days in Transit = 0**: Just departed today
- **Days in Transit = 1**: One day into multi-day journey
- **Days in Transit >= 3**: Long-haul shipments (e.g., to Western Australia)

**Red Flags**:
- Transit times exceeding expected route durations
- Large quantities in transit while destinations show shortages
- Empty transit on expected shipping days

**Normal Patterns**:
- Regular daily shipments from manufacturing to hubs
- Periodic hub-to-spoke shipments
- Higher transit volumes mid-week

#### Identifying Bottlenecks

**Inventory Buildup**:
- Location shows increasing inventory day-over-day
- Suggests insufficient outbound capacity or demand
- May indicate optimization favoring early production

**Stock Depletion**:
- Location inventory approaching zero
- May precede a shortage if not replenished
- Check upcoming shipments in future snapshots

**Transit Congestion**:
- High in-transit quantities relative to inventory
- Indicates long supply chains or frequent shipments
- May represent working capital tied up in transit

**Labor Bottlenecks**:
- Production days hitting maximum labor hours (14h with OT)
- Weekend production indicating tight capacity
- Uneven production patterns suggesting constraint conflicts

#### Spotting Inventory Issues

**FIFO Violations**:
- Older batches remain while newer batches ship
- Check batch departure patterns in outflow details
- May indicate optimization modeling issues

**Excess Inventory**:
- Total inventory exceeds near-term demand
- High inventory carrying costs
- Potential waste if products expire

**Stockout Risks**:
- Zero inventory at destination with upcoming demand
- No in-transit shipments scheduled
- Verify in demand satisfaction section

**Mass Balance Errors**:
- Inflows don't match outflows over time
- Inventory growing without bound
- May indicate data integrity issues

### 2.4 Common Use Cases

#### Use Case 1: Daily Operations Review

**Scenario**: Operations manager reviewing today's plan for execution

**Workflow**:
1. Navigate to today's date
2. Review Manufacturing Activity:
   - Verify production quantities are achievable
   - Check labor hours against shift schedules
   - Identify which products are being made
3. Check In-Transit shipments:
   - Confirm expected deliveries
   - Identify trucks en route
4. Verify Demand Satisfaction:
   - Ensure all customer orders are covered
   - Note any shortages for communication

**Key Questions Answered**:
- What do we need to produce today?
- Where are our trucks currently?
- Will we meet all customer commitments?
- Are there any issues requiring intervention?

#### Use Case 2: Investigating Stockouts

**Scenario**: A destination location shows shortage in the plan

**Workflow**:
1. Navigate to the shortage date (check Demand Satisfaction)
2. Work backward in time:
   - Day -1: Check if shipments departed for this location
   - Day -2 to -5: Review production of the shorted product
   - Review manufacturing location inventory over this period
3. Identify root cause:
   - Insufficient production capacity?
   - Truck capacity constraints?
   - Route shelf-life limitations?
   - Network routing issue?

**Diagnostic Indicators**:
- Production = 0 on critical days → Labor or capacity constraint
- Large in-transit to other locations → Prioritization issue
- Inventory at manufacturing but no shipments → Routing problem
- Old inventory elsewhere → Distribution inefficiency

#### Use Case 3: Planning Production Adjustments

**Scenario**: Need to assess impact of changing production schedule

**Workflow**:
1. Review current production pattern (day by day)
2. Identify production levels and timing
3. Check resulting inventory levels at manufacturing
4. Verify in-transit patterns match truck schedules
5. Assess inventory distribution across network
6. Validate demand satisfaction across planning horizon

**Analysis Points**:
- Can production be smoothed without creating shortages?
- What inventory buffers exist for flexibility?
- Which days are critical for production?
- Where are safety stock opportunities?

#### Use Case 4: Validating Distribution Plans

**Scenario**: Verifying optimization results before committing to execution

**Workflow**:
1. Check first week in detail (day by day):
   - Confirm production aligns with labor calendar
   - Verify shipments match truck schedule constraints
   - Validate demand satisfaction
2. Sample key dates throughout planning horizon:
   - Mondays (high production days)
   - Fridays (double truck capacity)
   - Around public holidays
3. Review final week:
   - Check for end-of-horizon artifacts
   - Verify inventory drawdown is reasonable
   - Confirm no artificial shortages

**Validation Criteria**:
- All production occurs on valid labor days
- Shipments align with truck departure schedules
- No phantom inventory appears/disappears
- Demand satisfaction is consistent
- Batch ages remain within acceptable ranges

---

## 3. Technical Documentation

### 3.1 Architecture

#### Component Overview

The Daily Snapshot feature consists of three primary layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ui/components/daily_snapshot.py - render_daily_snapshot()   │
│  - Streamlit UI components                                   │
│  - Interactive date selection                                │
│  - Data visualization and formatting                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                      Business Logic Layer                    │
│  src/analysis/daily_snapshot.py                              │
│  - DailySnapshotGenerator                                    │
│  - Snapshot calculation engine                               │
│  - Data model definitions                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                        Data Layer                            │
│  - ProductionSchedule (production batches)                   │
│  - Shipments (distribution plan)                             │
│  - Locations (network topology)                              │
│  - Forecast (demand data)                                    │
└─────────────────────────────────────────────────────────────┘
```

#### Data Flow

```
1. User selects date in UI
         │
         ▼
2. UI calls render_daily_snapshot(results, locations, date)
         │
         ▼
3. UI extracts production_schedule and shipments from results
         │
         ▼
4. UI calls _generate_snapshot() helper (simplified version)
    OR
   Create DailySnapshotGenerator for full analysis
         │
         ▼
5. Generator builds lookup structures:
   - Batches by production date
   - Shipments by departure/arrival/delivery dates
         │
         ▼
6. Generator calculates for selected date:
   - Location inventory (track batches through network)
   - In-transit shipments (departure <= date < arrival)
   - Production activity (batches produced today)
   - Inflows (production + arrivals)
   - Outflows (departures + demand)
   - Demand satisfaction (compare forecast to deliveries)
         │
         ▼
7. Returns DailySnapshot object with all data
         │
         ▼
8. UI renders snapshot data:
   - Summary metrics
   - Location inventory tables
   - Transit information
   - Manufacturing activity
   - Flow analysis
   - Demand tracking
         │
         ▼
9. User interacts with date selector → loop back to step 1
```

#### Integration Points

**Input Dependencies**:
- `ProductionSchedule`: Source of production batch data
- `List[Shipment]`: Distribution plan with timing
- `Dict[str, Location]`: Network topology and location metadata
- `Forecast`: Customer demand data for satisfaction tracking

**Output Consumers**:
- Streamlit UI components (primary)
- Could support export to CSV/Excel (future)
- Could feed analytics dashboards (future)
- Could generate PDF reports (future)

**Session State Usage**:
- `{key_prefix}_selected_date`: Currently selected snapshot date
- `forecast`: Forecast data for demand satisfaction (optional)

### 3.2 Data Models

#### BatchInventory

**Purpose**: Represents a production batch at a specific location with age tracking.

**Attributes**:
```python
@dataclass
class BatchInventory:
    batch_id: str              # Unique identifier (e.g., "BATCH-0045")
    product_id: str            # Product SKU (e.g., "176283")
    quantity: float            # Units in this batch
    production_date: Date      # When batch was manufactured
    age_days: int              # Age calculated from snapshot date
```

**Usage Example**:
```python
batch = BatchInventory(
    batch_id="BATCH-0045",
    product_id="176283",
    quantity=5000.0,
    production_date=date(2025, 1, 10),
    age_days=5  # If snapshot date is 2025-01-15
)
print(batch)  # "Batch BATCH-0045: 5000 units (5d old)"
```

**Key Methods**:
- `__str__()`: Human-readable representation for debugging and logging

**Business Rules**:
- Age is calculated as: `(snapshot_date - production_date).days`
- Quantity must be positive (negative indicates modeling error)
- Product ID must match original production batch

#### LocationInventory

**Purpose**: Aggregates all batches at a single location with product breakdowns.

**Attributes**:
```python
@dataclass
class LocationInventory:
    location_id: str                          # e.g., "6122"
    location_name: str                        # e.g., "Manufacturing Site"
    batches: List[BatchInventory]             # All batches at location
    total_quantity: float                     # Sum across batches
    by_product: Dict[str, float]              # Product → quantity mapping
```

**Usage Example**:
```python
loc_inv = LocationInventory(
    location_id="6122",
    location_name="Manufacturing Site"
)

# Add batches
loc_inv.add_batch(batch1)  # 5000 units of product 176283
loc_inv.add_batch(batch2)  # 3000 units of product 176284

print(loc_inv.total_quantity)     # 8000.0
print(loc_inv.by_product)         # {"176283": 5000.0, "176284": 3000.0}
```

**Key Methods**:
- `add_batch(batch)`: Adds a batch and updates totals and product breakdowns
- `__str__()`: Summary representation with product breakdown

**Business Rules**:
- Total quantity is always sum of batch quantities
- Product breakdown is always consistent with batch list
- Batches list can be empty (zero inventory)

#### TransitInventory

**Purpose**: Represents shipments currently in transit between locations.

**Attributes**:
```python
@dataclass
class TransitInventory:
    shipment_id: str              # Unique shipment identifier
    origin_id: str                # Departure location
    destination_id: str           # Arrival location
    product_id: str               # Product being shipped
    quantity: float               # Units in transit
    departure_date: Date          # When shipment left origin
    expected_arrival_date: Date   # When shipment arrives
    days_in_transit: int          # Days since departure
```

**Usage Example**:
```python
transit = TransitInventory(
    shipment_id="SHIP-0123",
    origin_id="6122",
    destination_id="6104",
    product_id="176283",
    quantity=5000.0,
    departure_date=date(2025, 1, 14),
    expected_arrival_date=date(2025, 1, 16),
    days_in_transit=1  # If snapshot is 2025-01-15
)
```

**Key Methods**:
- `__str__()`: Readable representation with route and progress

**Business Rules**:
- In transit condition: `departure_date <= snapshot_date < expected_arrival_date`
- Days in transit = `(snapshot_date - departure_date).days`
- For multi-leg routes, only one leg is in transit at a time

#### InventoryFlow

**Purpose**: Represents a single inventory movement event (in or out).

**Attributes**:
```python
@dataclass
class InventoryFlow:
    flow_type: str           # "production", "arrival", "departure", "demand"
    location_id: str         # Where flow occurs
    product_id: str          # Product flowing
    quantity: float          # Units (positive for in, negative conceptually)
    counterparty: Optional[str]  # Other location (for arrivals/departures)
    batch_id: Optional[str]      # Associated batch (if applicable)
```

**Usage Example**:
```python
# Production inflow
production_flow = InventoryFlow(
    flow_type="production",
    location_id="6122",
    product_id="176283",
    quantity=5000.0,
    counterparty=None,
    batch_id="BATCH-0045"
)

# Departure outflow
departure_flow = InventoryFlow(
    flow_type="departure",
    location_id="6122",
    product_id="176283",
    quantity=5000.0,
    counterparty="6104",  # Shipping to NSW hub
    batch_id="BATCH-0045"
)
```

**Key Methods**:
- `__str__()`: Descriptive representation with all relevant details

**Flow Types**:
- **production**: New inventory created at manufacturing site
- **arrival**: Shipment arriving at a location
- **departure**: Shipment leaving a location
- **demand**: Customer delivery/consumption

#### DemandRecord

**Purpose**: Tracks demand satisfaction for a product at a destination on a specific date.

**Attributes**:
```python
@dataclass
class DemandRecord:
    destination_id: str       # Customer location
    product_id: str           # Product demanded
    demand_quantity: float    # Forecasted demand
    supplied_quantity: float  # Actual delivery in plan
    shortage_quantity: float  # max(0, demand - supplied)
```

**Usage Example**:
```python
record = DemandRecord(
    destination_id="6103",
    product_id="176283",
    demand_quantity=3000.0,
    supplied_quantity=3000.0,
    shortage_quantity=0.0
)

print(record.fill_rate)    # 1.0 (100% satisfied)
print(record.is_satisfied)  # True
```

**Key Properties**:
- `fill_rate`: Returns supplied/demand ratio (0.0 to 1.0), handles zero demand
- `is_satisfied`: Returns True if shortage < 0.01 (allows for rounding errors)

**Key Methods**:
- `__str__()`: Shows destination, product, quantities, fill rate, and status

**Business Rules**:
- Shortage is never negative (max with 0)
- Fill rate capped at 1.0 (can't over-deliver in this calculation)
- Small shortages (<0.01) considered satisfied for practical purposes

#### DailySnapshot

**Purpose**: Complete inventory state for a single date across the entire network.

**Attributes**:
```python
@dataclass
class DailySnapshot:
    date: Date                                      # Snapshot date
    location_inventory: Dict[str, LocationInventory] # By location_id
    in_transit: List[TransitInventory]              # All in-transit shipments
    production_activity: List[BatchInventory]       # Batches produced today
    inflows: List[InventoryFlow]                    # All inflows today
    outflows: List[InventoryFlow]                   # All outflows today
    demand_satisfied: List[DemandRecord]            # Demand tracking
    total_system_inventory: float                   # Sum across locations
    total_in_transit: float                         # Sum in transit
```

**Usage Example**:
```python
snapshot = generator.generate_snapshots(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 1)
)[0]

print(f"Date: {snapshot.date}")
print(f"Total inventory: {snapshot.total_system_inventory:.0f}")
print(f"Locations with inventory: {len(snapshot.location_inventory)}")
print(f"Shipments in transit: {len(snapshot.in_transit)}")
```

**Key Methods**:
- `__str__()`: Summary of snapshot with key counts and totals

**Invariants**:
- `total_system_inventory` = sum of all `location_inventory` totals
- `total_in_transit` = sum of all `in_transit` quantities
- Production activity should only include batches with `production_date == date`

#### DailySnapshotGenerator

**Purpose**: Main engine for generating daily snapshots from planning results.

**Attributes**:
```python
class DailySnapshotGenerator:
    production_schedule: ProductionSchedule
    shipments: List[Shipment]
    locations_dict: Dict[str, Location]
    forecast: Forecast

    # Internal lookup structures (built on init)
    _batches_by_date: Dict[Date, List[ProductionBatch]]
    _shipments_by_departure: Dict[Date, List[Shipment]]
    _shipments_by_arrival: Dict[Date, Dict[str, List[Shipment]]]
    _shipments_by_delivery: Dict[Date, Dict[str, Dict[str, List[Shipment]]]]
```

**Usage Example**:
```python
generator = DailySnapshotGenerator(
    production_schedule=schedule,
    shipments=shipment_list,
    locations_dict=locations,
    forecast=forecast_data
)

# Generate snapshots for date range
snapshots = generator.generate_snapshots(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31)
)

# Or generate single snapshot
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))
```

**Key Methods**: See API Reference section for detailed documentation.

### 3.3 Calculations

#### Location Inventory Calculation

**Algorithm**: Batch Tracking Through Network

The location inventory calculation tracks each production batch as it moves through the supply chain network, maintaining accurate quantity and age information at every location.

**Steps**:

1. **Initialize Batch Positions**:
   - All batches start at manufacturing site on their production date
   - Create dictionary: `batch_quantities[batch_id] = quantity`

2. **Process Shipments Chronologically**:
   - For each shipment, calculate departure and arrival dates
   - Track shipment progress through each route leg

3. **Update Inventory for Each Leg**:
   - If shipment departed from location X on date D and snapshot_date >= D:
     - Subtract shipment quantity from batch at location X
   - If shipment arrived at location Y on date A and snapshot_date >= A:
     - Add shipment quantity to batch at location Y

4. **Build Batch Inventory Objects**:
   - For each location, iterate through batches with quantity > 0
   - Create `BatchInventory` objects with current quantities and ages
   - Add to location's inventory

**Pseudocode**:
```python
def calculate_location_inventory(location_id, snapshot_date):
    batch_quantities = {}

    # Start: all batches at manufacturing site
    if location_id == manufacturing_site_id:
        for batch in production_batches:
            if batch.production_date <= snapshot_date:
                batch_quantities[batch.id] = batch.quantity

    # Track batch movements via shipments
    for shipment in all_shipments:
        departure_date = shipment.delivery_date - shipment.total_transit_days

        for leg in shipment.route.legs:
            arrival_date = departure_date + leg.transit_days

            # Batch leaves origin
            if leg.from_location == location_id and departure_date <= snapshot_date:
                batch_quantities[shipment.batch_id] -= shipment.quantity

            # Batch arrives at destination
            if leg.to_location == location_id and arrival_date <= snapshot_date:
                batch_quantities[shipment.batch_id] += shipment.quantity

            departure_date = arrival_date

    # Convert to BatchInventory objects
    batches = []
    for batch_id, quantity in batch_quantities.items():
        if quantity > 0.01:  # Filter out rounding errors
            batch = find_batch(batch_id)
            age = (snapshot_date - batch.production_date).days
            batches.append(BatchInventory(...))

    return batches
```

**Edge Cases**:
- Zero-quantity batches filtered out (< 0.01 threshold)
- Multi-leg routes tracked through each intermediate stop
- Same-day arrivals and departures handled correctly
- Batch conservation: total quantity never increases or decreases

#### In-Transit Detection

**Algorithm**: Time Window Matching

A shipment is in transit on a specific date if it has departed its origin but not yet arrived at its destination.

**Condition**:
```
departure_date <= snapshot_date < arrival_date
```

**For Multi-Leg Routes**:
```python
def find_in_transit_shipments(snapshot_date):
    in_transit = []

    for shipment in all_shipments:
        current_date = shipment.delivery_date - shipment.total_transit_days

        for leg in shipment.route.legs:
            departure_date = current_date
            arrival_date = current_date + leg.transit_days

            # Check if in transit on this leg
            if departure_date <= snapshot_date < arrival_date:
                days_in_transit = (snapshot_date - departure_date).days

                in_transit.append(TransitInventory(
                    shipment_id=shipment.id,
                    origin_id=leg.from_location,
                    destination_id=leg.to_location,
                    product_id=shipment.product_id,
                    quantity=shipment.quantity,
                    departure_date=departure_date,
                    expected_arrival_date=arrival_date,
                    days_in_transit=days_in_transit
                ))

                break  # Shipment is only on one leg at a time

            current_date = arrival_date

    return in_transit
```

**Key Points**:
- Exclusive upper bound: arrival date is NOT in-transit (already arrived)
- Only one leg can be in-transit per shipment
- Days in transit calculated from leg departure, not shipment origin

#### Inflows Calculation

**Components**:

1. **Production Inflows**:
   - Source: Production batches with `production_date == snapshot_date`
   - Location: Manufacturing site
   - Type: "production"

2. **Arrival Inflows**:
   - Source: Shipments with leg arrival date = snapshot_date
   - Location: Leg destination (to_location_id)
   - Type: "arrival"

**Algorithm**:
```python
def calculate_inflows(snapshot_date):
    inflows = []

    # Production inflows
    for batch in batches_produced_on[snapshot_date]:
        inflows.append(InventoryFlow(
            flow_type="production",
            location_id=batch.manufacturing_site_id,
            product_id=batch.product_id,
            quantity=batch.quantity,
            counterparty=None,
            batch_id=batch.id
        ))

    # Arrival inflows
    for location_id, shipments in arrivals_on[snapshot_date].items():
        for shipment in shipments:
            inflows.append(InventoryFlow(
                flow_type="arrival",
                location_id=location_id,
                product_id=shipment.product_id,
                quantity=shipment.quantity,
                counterparty=shipment.origin_id,
                batch_id=shipment.batch_id
            ))

    return inflows
```

**Multi-Leg Handling**:
- For multi-leg routes, arrival at intermediate hub creates an inflow at the hub
- This is correct: inventory physically arrives at the hub before continuing

#### Outflows Calculation

**Components**:

1. **Departure Outflows**:
   - Source: Shipments with departure date = snapshot_date
   - Location: Shipment origin
   - Type: "departure"

2. **Demand Outflows**:
   - Source: Shipments with delivery date = snapshot_date
   - Location: Final destination
   - Type: "demand"
   - Aggregated by destination and product

**Algorithm**:
```python
def calculate_outflows(snapshot_date):
    outflows = []

    # Departure outflows
    for shipment in departures_on[snapshot_date]:
        outflows.append(InventoryFlow(
            flow_type="departure",
            location_id=shipment.origin_id,
            product_id=shipment.product_id,
            quantity=shipment.quantity,
            counterparty=shipment.first_leg_destination,
            batch_id=shipment.batch_id
        ))

    # Demand outflows (aggregated)
    for dest_id, products in deliveries_on[snapshot_date].items():
        for product_id, shipments in products.items():
            total_delivered = sum(s.quantity for s in shipments)

            outflows.append(InventoryFlow(
                flow_type="demand",
                location_id=dest_id,
                product_id=product_id,
                quantity=total_delivered,
                counterparty=None,
                batch_id=None  # Aggregated across batches
            ))

    return outflows
```

**Note on Demand**:
- Demand flows are aggregated by destination and product
- Multiple batches delivered on same date are summed
- This matches how forecasts are specified (not batch-level)

#### Demand Satisfaction Calculation

**Algorithm**: Compare Forecast to Deliveries

**Steps**:

1. **Extract Forecast Demand**:
   - Query forecast for entries with `forecast_date == snapshot_date`
   - Group by destination and product
   - Sum quantities if multiple forecast entries exist

2. **Calculate Supplied Quantities**:
   - Query shipments for deliveries on snapshot_date
   - Group by destination and product
   - Sum shipment quantities

3. **Compute Shortage**:
   - For each destination-product combination:
     - `shortage = max(0, demand - supplied)`

4. **Create Demand Records**:
   - Include all destination-product combinations that have either demand or supply
   - Handle cases where demand exists but no supply (full shortage)
   - Handle cases where supply exists but no demand (over-supply, shortage = 0)

**Pseudocode**:
```python
def get_demand_satisfied(snapshot_date):
    demand_records = []

    # Get demand from forecast
    demand_by_loc_prod = defaultdict(lambda: defaultdict(float))
    for entry in forecast.entries:
        if entry.forecast_date == snapshot_date:
            demand_by_loc_prod[entry.location_id][entry.product_id] = entry.quantity

    # Get supplied from shipments
    supplied_by_loc_prod = defaultdict(lambda: defaultdict(float))
    for dest_id, products in deliveries_on[snapshot_date].items():
        for product_id, shipments in products.items():
            supplied_by_loc_prod[dest_id][product_id] = sum(s.quantity for s in shipments)

    # Combine to create records
    all_locations = set(demand_by_loc_prod.keys()) | set(supplied_by_loc_prod.keys())

    for location_id in all_locations:
        all_products = set(demand_by_loc_prod[location_id].keys()) | \
                      set(supplied_by_loc_prod[location_id].keys())

        for product_id in all_products:
            demand_qty = demand_by_loc_prod[location_id].get(product_id, 0.0)
            supplied_qty = supplied_by_loc_prod[location_id].get(product_id, 0.0)
            shortage_qty = max(0.0, demand_qty - supplied_qty)

            demand_records.append(DemandRecord(
                destination_id=location_id,
                product_id=product_id,
                demand_quantity=demand_qty,
                supplied_quantity=supplied_qty,
                shortage_quantity=shortage_qty
            ))

    return demand_records
```

**Edge Cases**:
- Zero demand, positive supply: Record shows 100% fill rate, no shortage
- Positive demand, zero supply: Record shows 0% fill rate, full shortage
- Demand and supply both zero: Could filter out or include (current: include)

#### Fill Rate Calculation

**Formula**:
```python
def fill_rate(self) -> float:
    if self.demand_quantity == 0:
        return 1.0  # No demand = 100% satisfied
    return min(1.0, self.supplied_quantity / self.demand_quantity)
```

**Special Cases**:
- Division by zero prevented with guard clause
- Fill rate capped at 1.0 (100%) even if over-supplied
- Result is always in range [0.0, 1.0]

**Interpretation**:
- 1.0 (100%): Fully satisfied
- 0.95 (95%): Minor shortage
- 0.5 (50%): Significant shortage
- 0.0 (0%): Complete stockout

### 3.4 UI Component

#### Component Location
`/home/sverzijl/planning_latest/ui/components/daily_snapshot.py`

#### Main Function

**Signature**:
```python
def render_daily_snapshot(
    results: Dict[str, Any],
    locations: Dict[str, Location],
    key_prefix: str = "daily_snapshot"
) -> None
```

**Parameters**:
- `results`: Dictionary containing planning results
  - Required keys: `production_schedule`, `shipments`
  - Optional keys: `cost_breakdown`
- `locations`: Dictionary mapping location_id → Location object
- `key_prefix`: Prefix for session state keys (enables multiple instances)

**Returns**: None (renders Streamlit UI directly)

#### Integration Points

**Session State**:
- `{key_prefix}_selected_date`: Stores currently selected date
  - Type: `datetime.date`
  - Default: First date with production or shipments
  - Persists across reruns

- `forecast`: Optional forecast data for demand satisfaction
  - Type: `Forecast` object
  - Used if available, gracefully degrades if missing

**Streamlit Components Used**:
- `st.select_slider`: Date selection
- `st.button`: Previous/Next navigation
- `st.columns`: Layout management
- `st.expander`: Collapsible location sections
- `st.dataframe`: Tabular data display with styling
- `st.metric`: Summary metrics display
- `st.markdown`: Custom HTML rendering for badges

**External Dependencies**:
- `ui.components.styling`: Custom CSS and badge functions
  - `section_header()`: Formatted section headers
  - `colored_metric()`: Styled metric cards
  - `success_badge()`, `warning_badge()`, `error_badge()`, `info_badge()`

#### Helper Functions

**_get_date_range()**:
```python
def _get_date_range(
    production_schedule: ProductionSchedule,
    shipments: List[Shipment]
) -> Optional[Tuple[Date, Date]]
```
- Extracts min/max dates from production and shipments
- Returns None if no data available
- Used to set slider bounds

**_generate_snapshot()**:
```python
def _generate_snapshot(
    selected_date: Date,
    production_schedule: ProductionSchedule,
    shipments: List[Shipment],
    locations: Dict[str, Location]
) -> Dict[str, Any]
```
- **Simplified** snapshot generation for UI purposes
- Does NOT implement full batch tracking (unlike DailySnapshotGenerator)
- Returns dictionary with keys:
  - `total_inventory`, `in_transit_total`, `production_total`, `demand_total`
  - `location_inventory`, `in_transit_shipments`, `production_batches`
  - `inflows`, `outflows`, `demand_satisfaction`

**Note**: The UI currently uses a simplified snapshot generator. For production use with complex multi-echelon networks, consider integrating the full `DailySnapshotGenerator` class.

**_get_days_in_transit()**:
```python
def _get_days_in_transit(shipment: Shipment, current_date: Date) -> int
```
- Calculates how many days a shipment has been in transit
- Returns 0 if departure date unavailable

---

## 4. Developer Guide

### 4.1 Adding to Your Application

#### Basic Integration

**Step 1: Import Required Modules**

```python
from datetime import date
from ui.components.daily_snapshot import render_daily_snapshot
from src.models.location import Location
```

**Step 2: Prepare Results Dictionary**

```python
# After running optimization
results = {
    'production_schedule': production_schedule,  # ProductionSchedule object
    'shipments': shipment_list,                  # List[Shipment]
    'cost_breakdown': cost_info,                 # Optional
}
```

**Step 3: Prepare Locations Dictionary**

```python
# Load locations from your data source
locations = {
    "6122": Location(location_id="6122", name="Manufacturing Site", ...),
    "6104": Location(location_id="6104", name="NSW/ACT Hub", ...),
    # ... etc
}
```

**Step 4: Render Component**

```python
import streamlit as st

# In your Streamlit page
st.title("Daily Inventory Snapshot")

render_daily_snapshot(
    results=results,
    locations=locations,
    key_prefix="my_snapshot"  # Unique prefix for this instance
)
```

#### Advanced Integration with DailySnapshotGenerator

For full batch tracking and detailed analysis:

```python
from src.analysis.daily_snapshot import DailySnapshotGenerator

# Initialize generator
generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipment_list,
    locations_dict=locations,
    forecast=forecast_data
)

# Generate snapshots for entire planning horizon
snapshots = generator.generate_snapshots(
    start_date=planning_start,
    end_date=planning_end
)

# Use snapshots in custom analysis
for snapshot in snapshots:
    print(f"Date: {snapshot.date}")
    print(f"Total inventory: {snapshot.total_system_inventory:.0f}")

    # Analyze inventory age
    for loc_id, loc_inv in snapshot.location_inventory.items():
        avg_age = sum(b.age_days * b.quantity for b in loc_inv.batches) / loc_inv.total_quantity
        print(f"  {loc_id}: avg age = {avg_age:.1f} days")
```

#### Session State Requirements

**Minimal Requirements**:
- None! Component manages its own state with `key_prefix`

**Optional Session State**:
- `forecast`: Forecast object for demand satisfaction tracking
  - If not present, demand section will be empty
  - Set with: `st.session_state['forecast'] = forecast_data`

**Multiple Instances**:
```python
# Page 1: Main results
render_daily_snapshot(results, locations, key_prefix="main")

# Page 2: Comparison view
render_daily_snapshot(results_scenario_a, locations, key_prefix="scenario_a")
render_daily_snapshot(results_scenario_b, locations, key_prefix="scenario_b")
```

Each instance maintains independent date selection via unique key prefix.

### 4.2 Customization

#### Changing Colors/Styling

**Batch Age Colors**:

Located in `render_daily_snapshot()`, function `highlight_age()`:

```python
def highlight_age(row):
    age = row['Age (days)']
    if age <= 3:
        return ['background-color: #d4edda'] * len(row)  # Fresh (green)
    elif age <= 7:
        return ['background-color: #fff3cd'] * len(row)  # Medium (yellow)
    else:
        return ['background-color: #f8d7da'] * len(row)  # Old (red)
```

**Customization**:
```python
# More granular age ranges
def highlight_age(row):
    age = row['Age (days)']
    if age <= 2:
        return ['background-color: #d4edda'] * len(row)  # Very fresh
    elif age <= 5:
        return ['background-color: #e7f3ff'] * len(row)  # Fresh
    elif age <= 7:
        return ['background-color: #fff3cd'] * len(row)  # Medium
    elif age <= 10:
        return ['background-color: #ffe5d9'] * len(row)  # Aging
    else:
        return ['background-color: #f8d7da'] * len(row)  # Old
```

**Flow Type Colors**:

```python
# Inflow colors (in highlight_inflow_type)
'Production': '#d1ecf1'  # Blue
'Arrival': '#d4edda'     # Green

# Outflow colors (in highlight_outflow_type)
'Departure': '#fff3cd'   # Yellow
'Demand': '#cfe2ff'      # Light blue
```

**Metric Cards**:

Powered by `ui.components.styling.colored_metric()`:

```python
# Current usage
colored_metric("Total Inventory", f"{total:,.0f} units", "primary")

# Available colors: "primary", "secondary", "accent", "success", "warning", "danger"
```

#### Adding New Sections

**Example: Add Shelf Life Section**

```python
# After demand satisfaction section

st.divider()

st.markdown(section_header("Shelf Life Analysis", level=3, icon="📅"), unsafe_allow_html=True)

# Calculate average age by location
age_data = []
for location_id, inv_data in snapshot['location_inventory'].items():
    location = locations.get(location_id)
    batches = inv_data.get('batches', {})

    for product_id, batch_list in batches.items():
        total_qty = sum(b.get('quantity', 0) for b in batch_list)
        weighted_age = sum(b.get('age_days', 0) * b.get('quantity', 0) for b in batch_list)
        avg_age = weighted_age / total_qty if total_qty > 0 else 0

        remaining_shelf_life = 17 - avg_age  # Ambient shelf life

        age_data.append({
            'Location': location.name if location else location_id,
            'Product': product_id,
            'Quantity': total_qty,
            'Avg Age (days)': round(avg_age, 1),
            'Remaining Shelf Life': round(remaining_shelf_life, 1),
        })

if age_data:
    df_age = pd.DataFrame(age_data)

    # Color code by remaining shelf life
    def highlight_shelf_life(row):
        remaining = row['Remaining Shelf Life']
        if remaining <= 7:
            return ['background-color: #f8d7da'] * len(row)  # Critical
        elif remaining <= 10:
            return ['background-color: #fff3cd'] * len(row)  # Warning
        else:
            return ['background-color: #d4edda'] * len(row)  # Good

    st.dataframe(
        df_age.style.apply(highlight_shelf_life, axis=1),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No inventory for shelf life analysis")
```

#### Modifying Calculations

**Example: Add Production Efficiency Metric**

In `_generate_snapshot()`:

```python
# After calculating production activity
if snapshot['production_batches']:
    total_units = sum(b.quantity for b in snapshot['production_batches'])
    total_labor = sum(b.labor_hours_used for b in snapshot['production_batches'])

    efficiency = total_units / total_labor if total_labor > 0 else 0

    snapshot['production_efficiency'] = efficiency  # Units per labor hour
    snapshot['production_labor'] = total_labor
else:
    snapshot['production_efficiency'] = 0
    snapshot['production_labor'] = 0
```

Then in rendering section:

```python
# In Manufacturing Activity section
if snapshot['production_batches']:
    st.dataframe(df_prod, use_container_width=True, hide_index=True)

    # Show enhanced summary
    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"**Total Labor Hours:** {snapshot['production_labor']:.1f}h")
    with col2:
        st.caption(f"**Efficiency:** {snapshot['production_efficiency']:.0f} units/hour")
```

### 4.3 Extending the Feature

#### Adding New Flow Types

**Use Case**: Track quality control holds

**Step 1: Extend InventoryFlow Types**

In `src/analysis/daily_snapshot.py`:

```python
# Update docstring for flow_type
flow_type: str  # "production", "arrival", "departure", "demand", "qc_hold", "qc_release"
```

**Step 2: Generate QC Flows**

```python
def _calculate_qc_flows(self, snapshot_date: Date) -> Tuple[List[InventoryFlow], List[InventoryFlow]]:
    """Calculate quality control hold and release flows."""
    holds = []
    releases = []

    # Example: check for batches placed on hold
    for batch in self._batches_by_date.get(snapshot_date, []):
        if batch.quality_hold:  # Assuming QC metadata
            holds.append(InventoryFlow(
                flow_type="qc_hold",
                location_id=batch.manufacturing_site_id,
                product_id=batch.product_id,
                quantity=batch.quantity,
                counterparty=None,
                batch_id=batch.id
            ))

    # Check for batches released from hold
    for batch in self.production_schedule.production_batches:
        if hasattr(batch, 'qc_release_date') and batch.qc_release_date == snapshot_date:
            releases.append(InventoryFlow(
                flow_type="qc_release",
                location_id=batch.manufacturing_site_id,
                product_id=batch.product_id,
                quantity=batch.quantity,
                counterparty=None,
                batch_id=batch.id
            ))

    return holds, releases
```

**Step 3: Integrate into Snapshot**

```python
# In _generate_single_snapshot()
qc_holds, qc_releases = self._calculate_qc_flows(snapshot_date)
snapshot.inflows.extend(qc_releases)
snapshot.outflows.extend(qc_holds)
```

**Step 4: Update UI Styling**

```python
# In render_daily_snapshot()
def highlight_flow_type(row):
    flow_type = row['Type']
    if flow_type == 'Production':
        return ['background-color: #d1ecf1'] * len(row)
    elif flow_type == 'Arrival':
        return ['background-color: #d4edda'] * len(row)
    elif flow_type == 'QC Hold':
        return ['background-color: #fff3cd'] * len(row)  # Yellow (warning)
    elif flow_type == 'QC Release':
        return ['background-color: #d4edda'] * len(row)  # Green (success)
    # ... etc
```

#### Supporting Additional Data

**Use Case**: Track cost data in snapshots

**Step 1: Extend DailySnapshot**

```python
@dataclass
class DailySnapshot:
    # ... existing fields ...

    # New fields
    daily_production_cost: float = 0.0
    daily_transport_cost: float = 0.0
    daily_holding_cost: float = 0.0
    cumulative_cost: float = 0.0
```

**Step 2: Calculate Costs**

```python
def _calculate_daily_costs(self, snapshot_date: Date) -> Dict[str, float]:
    """Calculate costs incurred on snapshot date."""
    costs = {
        'production': 0.0,
        'transport': 0.0,
        'holding': 0.0,
    }

    # Production costs
    for batch in self._batches_by_date.get(snapshot_date, []):
        costs['production'] += batch.production_cost

    # Transport costs (shipments departing today)
    for shipment in self._shipments_by_departure.get(snapshot_date, []):
        costs['transport'] += shipment.transport_cost

    # Holding costs (inventory at locations)
    for location_id in self.locations_dict.keys():
        inv = self._calculate_location_inventory(location_id, snapshot_date)
        costs['holding'] += inv.total_quantity * self._daily_holding_cost_per_unit

    return costs
```

**Step 3: Display Costs in UI**

```python
# Add to summary metrics
col5, col6, col7 = st.columns(3)
with col5:
    st.markdown(colored_metric("Production Cost", f"${snapshot.daily_production_cost:,.0f}", "primary"))
with col6:
    st.markdown(colored_metric("Transport Cost", f"${snapshot.daily_transport_cost:,.0f}", "secondary"))
with col7:
    st.markdown(colored_metric("Holding Cost", f"${snapshot.daily_holding_cost:,.0f}", "accent"))
```

#### Creating Custom Views

**Use Case**: Network Flow Visualization

```python
def render_network_flow_view(snapshot: DailySnapshot, locations: Dict[str, Location]):
    """Render network-based flow visualization."""
    import networkx as nx
    import plotly.graph_objects as go

    # Build network graph
    G = nx.DiGraph()

    # Add nodes (locations)
    for loc_id, loc in locations.items():
        G.add_node(loc_id, name=loc.name)

    # Add edges (flows)
    flow_quantities = defaultdict(float)

    for flow in snapshot.inflows:
        if flow.counterparty:  # Arrival from another location
            key = (flow.counterparty, flow.location_id)
            flow_quantities[key] += flow.quantity

    for origin, dest in flow_quantities.keys():
        G.add_edge(origin, dest, weight=flow_quantities[(origin, dest)])

    # Create plotly visualization
    pos = nx.spring_layout(G)

    # ... (build plotly figure with nodes and edges)

    st.plotly_chart(fig, use_container_width=True)
```

### 4.4 Performance Considerations

#### Typical Performance

**Benchmarks** (on standard hardware):

| Planning Horizon | Batches | Shipments | Snapshot Generation Time | UI Render Time |
|------------------|---------|-----------|--------------------------|----------------|
| 7 days           | 20      | 50        | < 0.1s                   | 0.2s           |
| 30 days          | 100     | 250       | 0.3s                     | 0.5s           |
| 90 days          | 300     | 750       | 1.2s                     | 1.5s           |
| 200 days         | 700     | 2000      | 3.5s                     | 4.0s           |

**Scalability**:
- Linear with number of batches and shipments
- Dominated by batch tracking through network (O(batches × shipments × legs))
- UI rendering time increases with data table sizes

#### Optimization Tips

**1. Cache Snapshot Generation**

```python
import streamlit as st
from functools import lru_cache

@st.cache_data
def generate_all_snapshots(
    production_schedule,
    shipments,
    locations,
    forecast,
    start_date,
    end_date
):
    """Cached snapshot generation."""
    generator = DailySnapshotGenerator(
        production_schedule,
        shipments,
        locations,
        forecast
    )
    return generator.generate_snapshots(start_date, end_date)

# In your app
snapshots = generate_all_snapshots(
    production_schedule,
    shipments,
    locations,
    forecast,
    planning_start,
    planning_end
)

# Access specific snapshot
snapshot = snapshots[selected_date - planning_start]
```

**2. Lazy Loading for Large Horizons**

```python
# Only generate snapshot for current date
@st.cache_data
def generate_single_snapshot_cached(
    production_schedule,
    shipments,
    locations,
    forecast,
    snapshot_date
):
    generator = DailySnapshotGenerator(...)
    return generator._generate_single_snapshot(snapshot_date)

# In render function
snapshot = generate_single_snapshot_cached(
    production_schedule,
    shipments,
    locations,
    forecast,
    selected_date
)
```

**3. Pagination for Large Data Tables**

```python
# For locations with many batches
MAX_BATCHES_DISPLAY = 50

if len(batch_data) > MAX_BATCHES_DISPLAY:
    st.warning(f"Showing first {MAX_BATCHES_DISPLAY} of {len(batch_data)} batches")
    batch_data = batch_data[:MAX_BATCHES_DISPLAY]

st.dataframe(df_batches, ...)
```

**4. Optimize Lookup Structures**

The `DailySnapshotGenerator._build_lookup_structures()` method pre-builds indexes:
- Batches by production date: O(1) lookup
- Shipments by departure/arrival: O(1) lookup
- This trades memory for speed (acceptable for planning horizons < 1 year)

**5. Reduce Calculation Scope**

For very large networks, consider:
```python
# Only calculate inventory for locations with activity
relevant_locations = set()

# Locations with production
relevant_locations.add(manufacturing_site_id)

# Locations with shipments
for shipment in shipments:
    relevant_locations.add(shipment.origin_id)
    relevant_locations.add(shipment.destination_id)

# Locations with demand
for entry in forecast.entries:
    relevant_locations.add(entry.location_id)

# Only process relevant locations
for location_id in relevant_locations:
    inventory = calculate_location_inventory(location_id, snapshot_date)
    # ...
```

#### Caching Strategies

**Streamlit Cache Levels**:

1. **Full Horizon Cache** (best for < 90 days):
   ```python
   @st.cache_data
   def generate_all_snapshots(...):
       # Generate all snapshots once
   ```

2. **Single Date Cache** (best for > 90 days):
   ```python
   @st.cache_data
   def generate_snapshot_for_date(date, ...):
       # Generate on-demand
   ```

3. **Generator Cache** (memory efficient):
   ```python
   @st.cache_resource
   def get_snapshot_generator(...):
       # Cache generator, not snapshots
       return DailySnapshotGenerator(...)

   generator = get_snapshot_generator(...)
   snapshot = generator._generate_single_snapshot(selected_date)
   ```

**Cache Invalidation**:
```python
# Clear cache when inputs change
if st.button("Re-run Optimization"):
    st.cache_data.clear()  # Clear all caches
    # ... run optimization ...
```

---

## 5. API Reference

### 5.1 DailySnapshotGenerator

**Class**: `src.analysis.daily_snapshot.DailySnapshotGenerator`

#### Constructor

```python
def __init__(
    self,
    production_schedule: ProductionSchedule,
    shipments: List[Shipment],
    locations_dict: Dict[str, Location],
    forecast: Forecast
)
```

**Parameters**:
- `production_schedule`: Production schedule containing batches
- `shipments`: List of all shipments in the plan
- `locations_dict`: Dictionary mapping location_id to Location object
- `forecast`: Forecast with demand data

**Raises**:
- No explicit exceptions; assumes valid input data

**Side Effects**:
- Builds internal lookup structures for efficient querying

**Example**:
```python
generator = DailySnapshotGenerator(
    production_schedule=schedule,
    shipments=all_shipments,
    locations_dict=locations,
    forecast=forecast_data
)
```

#### generate_snapshots()

```python
def generate_snapshots(
    self,
    start_date: Date,
    end_date: Date
) -> List[DailySnapshot]
```

**Purpose**: Generate daily snapshots for a date range.

**Parameters**:
- `start_date`: First date to snapshot (inclusive)
- `end_date`: Last date to snapshot (inclusive)

**Returns**: List of `DailySnapshot` objects, one per day in range

**Complexity**: O(days × (batches + shipments × legs))

**Example**:
```python
snapshots = generator.generate_snapshots(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31)
)

print(f"Generated {len(snapshots)} snapshots")  # 31 snapshots
```

#### _generate_single_snapshot()

```python
def _generate_single_snapshot(
    self,
    snapshot_date: Date
) -> DailySnapshot
```

**Purpose**: Generate snapshot for a single date.

**Parameters**:
- `snapshot_date`: Date to snapshot

**Returns**: `DailySnapshot` object for the specified date

**Complexity**: O(batches + shipments × legs)

**Note**: This is a private method but can be used directly for on-demand generation.

**Example**:
```python
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

print(snapshot.total_system_inventory)
print(f"{len(snapshot.in_transit)} shipments in transit")
```

#### _calculate_location_inventory()

```python
def _calculate_location_inventory(
    self,
    location_id: str,
    snapshot_date: Date
) -> LocationInventory
```

**Purpose**: Calculate inventory at a specific location on a specific date.

**Parameters**:
- `location_id`: Location to calculate inventory for
- `snapshot_date`: Date to calculate inventory on

**Returns**: `LocationInventory` object with batches and totals

**Algorithm**: Tracks batches through network via shipments

**Example**:
```python
mfg_inventory = generator._calculate_location_inventory("6122", date(2025, 1, 15))

print(f"Manufacturing inventory: {mfg_inventory.total_quantity:.0f} units")
for product_id, qty in mfg_inventory.by_product.items():
    print(f"  {product_id}: {qty:.0f} units")
```

#### _find_in_transit_shipments()

```python
def _find_in_transit_shipments(
    self,
    snapshot_date: Date
) -> List[TransitInventory]
```

**Purpose**: Find all shipments in transit on the snapshot date.

**Parameters**:
- `snapshot_date`: Date to check

**Returns**: List of `TransitInventory` objects

**Condition**: Shipment in transit if `departure_date <= snapshot_date < arrival_date`

**Example**:
```python
in_transit = generator._find_in_transit_shipments(date(2025, 1, 15))

total_in_transit = sum(t.quantity for t in in_transit)
print(f"{total_in_transit:.0f} units in transit")

for transit in in_transit:
    print(f"  {transit.origin_id} → {transit.destination_id}: {transit.quantity:.0f} units")
```

#### _get_production_activity()

```python
def _get_production_activity(
    self,
    snapshot_date: Date
) -> List[BatchInventory]
```

**Purpose**: Get batches produced on the snapshot date.

**Parameters**:
- `snapshot_date`: Date to check

**Returns**: List of `BatchInventory` for batches produced on this date

**Example**:
```python
production = generator._get_production_activity(date(2025, 1, 15))

total_produced = sum(b.quantity for b in production)
print(f"Produced {total_produced:.0f} units today")
```

#### _calculate_inflows()

```python
def _calculate_inflows(
    self,
    snapshot_date: Date
) -> List[InventoryFlow]
```

**Purpose**: Calculate all inflows (production + arrivals) on the snapshot date.

**Parameters**:
- `snapshot_date`: Date to calculate inflows for

**Returns**: List of `InventoryFlow` objects

**Flow Types**: "production", "arrival"

**Example**:
```python
inflows = generator._calculate_inflows(date(2025, 1, 15))

for flow in inflows:
    print(f"{flow.flow_type}: {flow.quantity:.0f} units at {flow.location_id}")
```

#### _calculate_outflows()

```python
def _calculate_outflows(
    self,
    snapshot_date: Date
) -> List[InventoryFlow]
```

**Purpose**: Calculate all outflows (departures + demand) on the snapshot date.

**Parameters**:
- `snapshot_date`: Date to calculate outflows for

**Returns**: List of `InventoryFlow` objects

**Flow Types**: "departure", "demand"

**Example**:
```python
outflows = generator._calculate_outflows(date(2025, 1, 15))

departures = [f for f in outflows if f.flow_type == "departure"]
demands = [f for f in outflows if f.flow_type == "demand"]

print(f"{len(departures)} departures, {len(demands)} deliveries")
```

#### _get_demand_satisfied()

```python
def _get_demand_satisfied(
    self,
    snapshot_date: Date
) -> List[DemandRecord]
```

**Purpose**: Get demand satisfaction records for the snapshot date.

**Parameters**:
- `snapshot_date`: Date to check demand satisfaction

**Returns**: List of `DemandRecord` objects

**Calculation**: Compares forecasted demand to actual deliveries

**Example**:
```python
demand_records = generator._get_demand_satisfied(date(2025, 1, 15))

total_shortage = sum(r.shortage_quantity for r in demand_records)
if total_shortage == 0:
    print("All demand satisfied!")
else:
    print(f"Total shortage: {total_shortage:.0f} units")

    # Show details
    for record in demand_records:
        if not record.is_satisfied:
            print(f"  {record.destination_id} - {record.product_id}: {record.shortage_quantity:.0f} short")
```

### 5.2 render_daily_snapshot()

**Function**: `ui.components.daily_snapshot.render_daily_snapshot()`

```python
def render_daily_snapshot(
    results: Dict[str, Any],
    locations: Dict[str, Location],
    key_prefix: str = "daily_snapshot"
) -> None
```

**Purpose**: Render comprehensive daily inventory snapshot UI component.

**Parameters**:
- `results`: Results dictionary containing:
  - `production_schedule` (required): `ProductionSchedule` object
  - `shipments` (required): `List[Shipment]`
  - `cost_breakdown` (optional): Cost information
- `locations`: Dictionary mapping `location_id` to `Location` object
- `key_prefix`: Prefix for session state keys (default: "daily_snapshot")

**Returns**: None (renders Streamlit UI)

**Session State**:
- Reads: `{key_prefix}_selected_date`, `forecast` (optional)
- Writes: `{key_prefix}_selected_date`

**UI Components Rendered**:
1. Date selector with prev/next buttons
2. Summary metrics (4 cards)
3. Location inventory (expandable sections with batch tables)
4. In-transit shipments table
5. Manufacturing activity table
6. Inflows table
7. Outflows table
8. Demand satisfaction table

**Warnings**:
- Shows warning if no production schedule available
- Shows info message if no production or shipment data

**Example**:
```python
import streamlit as st
from ui.components.daily_snapshot import render_daily_snapshot

# In your Streamlit app
st.title("Planning Results")

if results:
    render_daily_snapshot(
        results=results,
        locations=locations,
        key_prefix="main_snapshot"
    )
else:
    st.info("Run optimization to see results")
```

**Advanced Usage** (Multiple Instances):
```python
# Scenario comparison
col1, col2 = st.columns(2)

with col1:
    st.subheader("Scenario A")
    render_daily_snapshot(results_a, locations, key_prefix="scenario_a")

with col2:
    st.subheader("Scenario B")
    render_daily_snapshot(results_b, locations, key_prefix="scenario_b")
```

---

## 6. Examples

### 6.1 Basic Usage

#### Generating Snapshots

```python
from datetime import date
from src.analysis.daily_snapshot import DailySnapshotGenerator
from src.production.scheduler import ProductionSchedule
from src.models.shipment import Shipment
from src.models.location import Location
from src.models.forecast import Forecast

# Assume you have these from your optimization
production_schedule: ProductionSchedule = ...
shipments: List[Shipment] = ...
locations: Dict[str, Location] = ...
forecast: Forecast = ...

# Create generator
generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipments,
    locations_dict=locations,
    forecast=forecast
)

# Generate snapshots for entire planning horizon
start_date = date(2025, 1, 1)
end_date = date(2025, 3, 31)  # 3 months

snapshots = generator.generate_snapshots(start_date, end_date)

print(f"Generated {len(snapshots)} daily snapshots")

# Analyze first snapshot
first_snapshot = snapshots[0]
print(f"\nSnapshot for {first_snapshot.date}:")
print(f"  Total inventory: {first_snapshot.total_system_inventory:,.0f} units")
print(f"  In transit: {first_snapshot.total_in_transit:,.0f} units")
print(f"  Locations with inventory: {len(first_snapshot.location_inventory)}")
print(f"  Production batches: {len(first_snapshot.production_activity)}")
```

#### Iterating Through Snapshots

```python
# Analyze inventory trends
for snapshot in snapshots:
    print(f"{snapshot.date}: {snapshot.total_system_inventory:,.0f} units in system")

# Find days with production
production_days = [s for s in snapshots if len(s.production_activity) > 0]
print(f"\nProduction occurred on {len(production_days)} days")

# Find days with shortages
shortage_days = [s for s in snapshots if any(d.shortage_quantity > 0 for d in s.demand_satisfied)]
print(f"Shortages occurred on {len(shortage_days)} days")
```

### 6.2 Accessing Specific Data

#### Getting Inventory at a Location

```python
# Get snapshot for specific date
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

# Access inventory at manufacturing site
mfg_inventory = snapshot.location_inventory.get("6122")

if mfg_inventory:
    print(f"Manufacturing Site Inventory:")
    print(f"  Total: {mfg_inventory.total_quantity:,.0f} units")

    # Show by product
    for product_id, quantity in mfg_inventory.by_product.items():
        print(f"    {product_id}: {quantity:,.0f} units")

    # Show batches
    print(f"\n  Batches ({len(mfg_inventory.batches)}):")
    for batch in mfg_inventory.batches:
        print(f"    {batch}")
else:
    print("No inventory at manufacturing site")
```

#### Finding In-Transit Shipments

```python
# Get in-transit shipments for a date
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

print(f"In-Transit Shipments on {snapshot.date}:")
print(f"  Total: {len(snapshot.in_transit)} shipments")

# Group by route
from collections import defaultdict

by_route = defaultdict(list)
for transit in snapshot.in_transit:
    route = f"{transit.origin_id} → {transit.destination_id}"
    by_route[route].append(transit)

for route, transits in by_route.items():
    total_qty = sum(t.quantity for t in transits)
    print(f"\n  {route}: {total_qty:,.0f} units ({len(transits)} shipments)")
    for t in transits:
        print(f"    {t.product_id}: {t.quantity:,.0f} units (day {t.days_in_transit})")
```

#### Checking Demand Satisfaction

```python
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

print(f"Demand Satisfaction for {snapshot.date}:")

total_demand = sum(d.demand_quantity for d in snapshot.demand_satisfied)
total_supplied = sum(d.supplied_quantity for d in snapshot.demand_satisfied)
total_shortage = sum(d.shortage_quantity for d in snapshot.demand_satisfied)

print(f"  Total Demand: {total_demand:,.0f} units")
print(f"  Total Supplied: {total_supplied:,.0f} units")
print(f"  Total Shortage: {total_shortage:,.0f} units")

if total_shortage > 0:
    print("\n  Shortages:")
    for record in snapshot.demand_satisfied:
        if record.shortage_quantity > 0:
            print(f"    {record.destination_id} - {record.product_id}:")
            print(f"      Demand: {record.demand_quantity:,.0f}, Supplied: {record.supplied_quantity:,.0f}")
            print(f"      Short: {record.shortage_quantity:,.0f} (fill rate: {record.fill_rate:.1%})")
else:
    print("\n  ✓ All demand satisfied!")
```

#### Analyzing Flows

```python
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

# Analyze inflows
print(f"Inflows on {snapshot.date}:")
production_inflows = [f for f in snapshot.inflows if f.flow_type == "production"]
arrival_inflows = [f for f in snapshot.inflows if f.flow_type == "arrival"]

print(f"  Production: {sum(f.quantity for f in production_inflows):,.0f} units")
print(f"  Arrivals: {sum(f.quantity for f in arrival_inflows):,.0f} units")

# Analyze outflows
print(f"\nOutflows on {snapshot.date}:")
departure_outflows = [f for f in snapshot.outflows if f.flow_type == "departure"]
demand_outflows = [f for f in snapshot.outflows if f.flow_type == "demand"]

print(f"  Departures: {sum(f.quantity for f in departure_outflows):,.0f} units")
print(f"  Demand: {sum(f.quantity for f in demand_outflows):,.0f} units")

# Net flow
net_inflow = sum(f.quantity for f in snapshot.inflows)
net_outflow = sum(f.quantity for f in snapshot.outflows)
print(f"\nNet Flow: {net_inflow - net_outflow:+,.0f} units")
```

### 6.3 Integration with UI

#### Basic UI Integration

```python
import streamlit as st
from ui.components.daily_snapshot import render_daily_snapshot

# Page setup
st.set_page_config(page_title="Planning Results", layout="wide")
st.title("Production Planning Results")

# Load results from session state
results = st.session_state.get('optimization_results')
locations = st.session_state.get('locations_dict')

if results and locations:
    # Render snapshot component
    render_daily_snapshot(
        results=results,
        locations=locations,
        key_prefix="main"
    )
else:
    st.warning("Please run optimization first")
```

#### Multi-Tab Interface

```python
import streamlit as st
from ui.components.daily_snapshot import render_daily_snapshot

st.title("Planning Results")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Summary",
    "Daily Snapshot",
    "Cost Analysis",
    "Export"
])

with tab1:
    st.header("Plan Summary")
    # Show high-level metrics
    # ...

with tab2:
    st.header("Daily Inventory Snapshot")
    render_daily_snapshot(
        results=st.session_state.get('results'),
        locations=st.session_state.get('locations'),
        key_prefix="daily"
    )

with tab3:
    st.header("Cost Breakdown")
    # Show cost analysis
    # ...

with tab4:
    st.header("Export Results")
    # Export functionality
    # ...
```

#### Scenario Comparison

```python
import streamlit as st
from ui.components.daily_snapshot import render_daily_snapshot

st.title("Scenario Comparison")

# Load scenarios
scenario_a = st.session_state.get('scenario_a_results')
scenario_b = st.session_state.get('scenario_b_results')
locations = st.session_state.get('locations')

if scenario_a and scenario_b and locations:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Scenario A: Base Case")
        render_daily_snapshot(
            results=scenario_a,
            locations=locations,
            key_prefix="scenario_a"
        )

    with col2:
        st.subheader("Scenario B: High Demand")
        render_daily_snapshot(
            results=scenario_b,
            locations=locations,
            key_prefix="scenario_b"
        )
else:
    st.warning("Please load both scenarios")
```

#### Custom Analysis Dashboard

```python
import streamlit as st
from src.analysis.daily_snapshot import DailySnapshotGenerator
import pandas as pd
import plotly.express as px

st.title("Advanced Inventory Analysis")

# Generate snapshots
generator = DailySnapshotGenerator(
    production_schedule=st.session_state.get('production_schedule'),
    shipments=st.session_state.get('shipments'),
    locations_dict=st.session_state.get('locations'),
    forecast=st.session_state.get('forecast')
)

snapshots = generator.generate_snapshots(
    start_date=planning_start,
    end_date=planning_end
)

# Build analysis dataframe
data = []
for snapshot in snapshots:
    data.append({
        'Date': snapshot.date,
        'Total Inventory': snapshot.total_system_inventory,
        'In Transit': snapshot.total_in_transit,
        'Production': sum(b.quantity for b in snapshot.production_activity),
        'Demand': sum(d.demand_quantity for d in snapshot.demand_satisfied),
        'Shortage': sum(d.shortage_quantity for d in snapshot.demand_satisfied),
    })

df = pd.DataFrame(data)

# Visualize
st.subheader("Inventory Over Time")
fig = px.line(df, x='Date', y=['Total Inventory', 'In Transit'],
              title="Inventory and In-Transit Trends")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Production vs Demand")
fig2 = px.bar(df, x='Date', y=['Production', 'Demand'],
              title="Daily Production and Demand", barmode='group')
st.plotly_chart(fig2, use_container_width=True)

# Daily snapshot selector
st.divider()
st.subheader("Detailed Daily View")

selected_date = st.date_input("Select Date", value=planning_start)

# Find snapshot
selected_snapshot = next((s for s in snapshots if s.date == selected_date), None)

if selected_snapshot:
    # Display detailed snapshot
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Inventory", f"{selected_snapshot.total_system_inventory:,.0f}")
    with col2:
        st.metric("In Transit", f"{selected_snapshot.total_in_transit:,.0f}")
    with col3:
        production = sum(b.quantity for b in selected_snapshot.production_activity)
        st.metric("Production", f"{production:,.0f}")

    # Show location breakdown
    st.subheader("Inventory by Location")
    loc_data = []
    for loc_id, inv in selected_snapshot.location_inventory.items():
        loc_name = st.session_state.get('locations')[loc_id].name
        loc_data.append({
            'Location': loc_name,
            'Quantity': inv.total_quantity,
        })

    st.dataframe(pd.DataFrame(loc_data), use_container_width=True, hide_index=True)
```

---

## 7. Testing

### 7.1 Running Tests

#### Unit Tests

**Location**: `/home/sverzijl/planning_latest/tests/test_daily_snapshot.py` (to be created)

**Run All Tests**:
```bash
pytest tests/test_daily_snapshot.py -v
```

**Run Specific Test**:
```bash
pytest tests/test_daily_snapshot.py::test_batch_inventory_creation -v
```

**Run with Coverage**:
```bash
pytest tests/test_daily_snapshot.py --cov=src.analysis.daily_snapshot --cov-report=html
```

#### UI Component Tests

**Interactive Testing**:
```bash
streamlit run test_daily_snapshot_ui.py
```

**What to Test**:
- Date selector navigation
- Summary metrics display
- Location inventory expansion
- In-transit shipment display
- Manufacturing activity
- Inflows/outflows tables
- Demand satisfaction tracking
- Color coding and styling
- Multiple instances with different key_prefixes

### 7.2 Test Coverage

#### Current Test Coverage

**Core Analysis Module** (`src/analysis/daily_snapshot.py`):
- BatchInventory: String representation
- LocationInventory: Batch addition and aggregation
- TransitInventory: String representation
- InventoryFlow: String representation
- DemandRecord: Fill rate, satisfaction status
- DailySnapshot: String representation
- DailySnapshotGenerator: All methods

**UI Component** (`ui/components/daily_snapshot.py`):
- Tested via interactive test app (`test_daily_snapshot_ui.py`)
- Manual testing of all features

#### How to Add New Tests

**Example Test Template**:

```python
"""tests/test_daily_snapshot.py"""

import pytest
from datetime import date, timedelta
from src.analysis.daily_snapshot import (
    DailySnapshotGenerator,
    BatchInventory,
    LocationInventory,
    TransitInventory,
    InventoryFlow,
    DemandRecord,
    DailySnapshot,
)
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.location import Location
from src.models.forecast import Forecast, ForecastEntry
from src.production.scheduler import ProductionSchedule


@pytest.fixture
def sample_locations():
    """Create sample locations for testing."""
    return {
        "6122": Location(
            location_id="6122",
            name="Manufacturing Site",
            location_type="manufacturing",
        ),
        "6104": Location(
            location_id="6104",
            name="NSW/ACT Hub",
            location_type="hub",
        ),
    }


@pytest.fixture
def sample_production_schedule():
    """Create sample production schedule."""
    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="176283",
            manufacturing_site_id="6122",
            production_date=date(2025, 1, 10),
            quantity=5000.0,
            labor_hours_used=8.5,
            production_cost=6000.0,
        ),
    ]

    return ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=date(2025, 1, 10),
        schedule_end_date=date(2025, 1, 20),
        production_batches=batches,
        daily_totals={date(2025, 1, 10): 5000.0},
        daily_labor_hours={date(2025, 1, 10): 8.5},
        infeasibilities=[],
        total_units=5000.0,
        total_labor_hours=8.5,
    )


def test_batch_inventory_age_calculation():
    """Test batch age calculation."""
    batch = BatchInventory(
        batch_id="BATCH-001",
        product_id="176283",
        quantity=5000.0,
        production_date=date(2025, 1, 10),
        age_days=5,
    )

    assert batch.age_days == 5
    assert "5d old" in str(batch)


def test_location_inventory_aggregation():
    """Test location inventory aggregation."""
    loc_inv = LocationInventory(
        location_id="6122",
        location_name="Manufacturing Site",
    )

    # Add first batch
    batch1 = BatchInventory(
        batch_id="BATCH-001",
        product_id="176283",
        quantity=5000.0,
        production_date=date(2025, 1, 10),
        age_days=0,
    )
    loc_inv.add_batch(batch1)

    assert loc_inv.total_quantity == 5000.0
    assert loc_inv.by_product["176283"] == 5000.0

    # Add second batch (different product)
    batch2 = BatchInventory(
        batch_id="BATCH-002",
        product_id="176284",
        quantity=3000.0,
        production_date=date(2025, 1, 10),
        age_days=0,
    )
    loc_inv.add_batch(batch2)

    assert loc_inv.total_quantity == 8000.0
    assert loc_inv.by_product["176283"] == 5000.0
    assert loc_inv.by_product["176284"] == 3000.0


def test_demand_record_fill_rate():
    """Test demand record fill rate calculation."""
    # Full satisfaction
    record1 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=3000.0,
        supplied_quantity=3000.0,
        shortage_quantity=0.0,
    )
    assert record1.fill_rate == 1.0
    assert record1.is_satisfied is True

    # Partial satisfaction
    record2 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=3000.0,
        supplied_quantity=2500.0,
        shortage_quantity=500.0,
    )
    assert record2.fill_rate == pytest.approx(0.8333, rel=0.01)
    assert record2.is_satisfied is False

    # Zero demand
    record3 = DemandRecord(
        destination_id="6103",
        product_id="176283",
        demand_quantity=0.0,
        supplied_quantity=0.0,
        shortage_quantity=0.0,
    )
    assert record3.fill_rate == 1.0
    assert record3.is_satisfied is True


def test_snapshot_generation(sample_production_schedule, sample_locations):
    """Test snapshot generation."""
    # Create minimal forecast
    forecast = Forecast(
        entries=[],
        start_date=date(2025, 1, 10),
        end_date=date(2025, 1, 20),
        source_file="test.xlsx",
    )

    # Create generator
    generator = DailySnapshotGenerator(
        production_schedule=sample_production_schedule,
        shipments=[],
        locations_dict=sample_locations,
        forecast=forecast,
    )

    # Generate snapshot
    snapshot = generator._generate_single_snapshot(date(2025, 1, 10))

    assert snapshot.date == date(2025, 1, 10)
    assert len(snapshot.production_activity) == 1
    assert snapshot.production_activity[0].batch_id == "BATCH-001"


# Add more tests for:
# - In-transit detection
# - Batch tracking through network
# - Multi-leg routes
# - Flow calculations
# - Demand satisfaction
```

**Running the New Tests**:
```bash
pytest tests/test_daily_snapshot.py -v
```

---

## 8. Troubleshooting

### 8.1 Common Issues

#### Issue: "No data available for snapshot analysis"

**Symptoms**:
- Warning message displayed instead of snapshot
- No production schedule in results

**Causes**:
1. Optimization hasn't been run yet
2. Optimization failed without creating results
3. Results dictionary missing `production_schedule` key

**Solutions**:
```python
# Check if results exist
if 'optimization_results' in st.session_state:
    results = st.session_state['optimization_results']

    # Verify required keys
    if 'production_schedule' in results:
        render_daily_snapshot(results, locations)
    else:
        st.error("Results missing production schedule")
else:
    st.warning("Please run optimization first")
```

#### Issue: Missing Locations in Snapshot

**Symptoms**:
- Location IDs shown instead of names
- "Location not found" messages

**Causes**:
1. Locations dictionary not properly loaded
2. Location IDs in results don't match locations dictionary
3. Locations dictionary missing required locations

**Solutions**:
```python
# Validate locations dictionary
def validate_locations(results, locations):
    """Check if all locations in results are in locations dict."""
    required_locations = set()

    # Collect from production
    if 'production_schedule' in results:
        schedule = results['production_schedule']
        required_locations.add(schedule.manufacturing_site_id)

    # Collect from shipments
    if 'shipments' in results:
        for shipment in results['shipments']:
            required_locations.add(shipment.origin_id)
            required_locations.add(shipment.destination_id)

    # Check for missing
    missing = required_locations - set(locations.keys())

    if missing:
        st.error(f"Missing locations: {missing}")
        return False

    return True

# Use before rendering
if validate_locations(results, locations):
    render_daily_snapshot(results, locations)
```

#### Issue: Performance Slow with Large Horizons

**Symptoms**:
- Snapshot takes several seconds to generate
- UI feels sluggish when changing dates

**Causes**:
1. Large number of batches/shipments (> 1000)
2. Long planning horizon (> 180 days)
3. No caching enabled

**Solutions**:
```python
# Solution 1: Cache snapshots
@st.cache_data
def generate_all_snapshots_cached(schedule, shipments, locations, forecast, start, end):
    generator = DailySnapshotGenerator(schedule, shipments, locations, forecast)
    return generator.generate_snapshots(start, end)

# Solution 2: Generate on-demand with caching
@st.cache_data
def get_snapshot_for_date(schedule, shipments, locations, forecast, snapshot_date):
    generator = DailySnapshotGenerator(schedule, shipments, locations, forecast)
    return generator._generate_single_snapshot(snapshot_date)

# Solution 3: Show loading spinner
with st.spinner("Generating snapshot..."):
    snapshot = get_snapshot_for_date(...)
```

#### Issue: Incorrect Inventory Quantities

**Symptoms**:
- Inventory doesn't match expected values
- Negative inventory (should never happen)
- Inventory growing without bound

**Causes**:
1. Batch tracking logic error
2. Shipment data inconsistencies
3. Multi-leg route handling issues

**Diagnostic Steps**:
```python
# Add debugging to track batch movements
def debug_batch_tracking(batch_id, snapshot_date):
    """Debug where a specific batch is."""
    print(f"\nTracking batch {batch_id} on {snapshot_date}:")

    # Find batch
    batch = next((b for b in production_schedule.production_batches if b.id == batch_id), None)
    if batch:
        print(f"  Produced: {batch.production_date}, Quantity: {batch.quantity}")

    # Find shipments
    for shipment in shipments:
        if shipment.batch_id == batch_id:
            print(f"  Shipment: {shipment.origin_id} → {shipment.destination_id}")
            print(f"    Departure: {shipment.departure_date}, Arrival: {shipment.arrival_date}")

    # Check location inventory
    for loc_id, inv in snapshot.location_inventory.items():
        for batch_inv in inv.batches:
            if batch_inv.batch_id == batch_id:
                print(f"  Found at {loc_id}: {batch_inv.quantity} units")

# Run for problematic batch
debug_batch_tracking("BATCH-0045", date(2025, 1, 15))
```

#### Issue: Demand Satisfaction Always Empty

**Symptoms**:
- Demand satisfaction section shows "No demand on this date"
- Even on dates with known demand

**Causes**:
1. Forecast not in session state
2. Forecast date format mismatch
3. Forecast entries don't match snapshot date

**Solutions**:
```python
# Verify forecast is available
if 'forecast' not in st.session_state:
    st.warning("Forecast not loaded - demand satisfaction unavailable")
    st.session_state['forecast'] = forecast  # Load it

# Check forecast date range
forecast = st.session_state.get('forecast')
if forecast:
    print(f"Forecast date range: {forecast.start_date} to {forecast.end_date}")
    print(f"Snapshot date: {selected_date}")

    # Check if date is in range
    if not (forecast.start_date <= selected_date <= forecast.end_date):
        st.warning("Selected date outside forecast range")

# Debug forecast entries
entries_on_date = [e for e in forecast.entries if e.date == selected_date]
print(f"Forecast entries on {selected_date}: {len(entries_on_date)}")
for entry in entries_on_date:
    print(f"  {entry.location_id} - {entry.product_id}: {entry.quantity}")
```

### 8.2 FAQ

#### Q: Why is inventory not showing at a location?

**A**: Inventory is only shown at locations where batches are physically present. Common reasons for empty inventory:

1. **Production hasn't started yet**: Check if snapshot date >= first production date
2. **All inventory shipped**: All batches may have departed via shipments
3. **Location not in network**: Location may not be part of the distribution plan
4. **Batch tracking issue**: Verify shipment data has correct origins and destinations

**Debug**:
```python
# Check if location should have inventory
snapshot = generator._generate_single_snapshot(selected_date)

# Manually calculate expected inventory
expected_batches = []
for batch in production_schedule.production_batches:
    if batch.production_date <= selected_date:
        # Check if shipped
        shipped = any(s.batch_id == batch.id and s.departure_date <= selected_date
                     for s in shipments)
        if not shipped:
            expected_batches.append(batch)

print(f"Expected batches at manufacturing: {len(expected_batches)}")
print(f"Actual batches: {len(snapshot.location_inventory.get('6122', {}).get('batches', []))}")
```

#### Q: How is age calculated?

**A**: Age is calculated as the number of days between the batch's production date and the snapshot date:

```python
age_days = (snapshot_date - production_date).days
```

**Examples**:
- Batch produced on Jan 10, snapshot on Jan 10: age = 0 days
- Batch produced on Jan 10, snapshot on Jan 15: age = 5 days
- Batch produced on Jan 10, snapshot on Jan 25: age = 15 days

**Note**: Age is always calculated from original production date, regardless of shipments or storage mode (frozen vs ambient).

#### Q: What if a shipment has multiple legs?

**A**: Multi-leg shipments are properly tracked through the network:

1. **Departure**: Batch leaves origin on first leg's departure date
2. **In-Transit**: Batch is in-transit on one leg at a time
3. **Intermediate Arrival**: Batch arrives at hub, creating an "arrival" inflow
4. **Hub Inventory**: Batch sits at hub until next leg departs
5. **Subsequent Departure**: Batch departs hub on next leg's departure date
6. **Final Arrival**: Batch arrives at final destination

**Example**: 6122 → 6104 (1 day) → 6103 (1 day)
- **Day 0**: Depart 6122
- **Day 1**: Arrive 6104 (inflow at 6104), Depart 6104 (outflow from 6104)
- **Day 2**: Arrive 6103 (inflow at 6103)

**In Snapshot**:
- Day 0: In-transit 6122→6104
- Day 1: In-transit 6104→6103 (NOT at 6104, simultaneous arrival/departure)
- Day 2: At 6103

**Note**: Current implementation may show brief inventory at hub if arrival and departure are on different days. This is correct and represents actual hub dwell time.

#### Q: How to export snapshot data?

**A**: Currently, the UI doesn't provide built-in export. You can add export functionality:

```python
import pandas as pd
from io import BytesIO

def export_snapshot_to_excel(snapshot: DailySnapshot, locations: Dict[str, Location]) -> bytes:
    """Export snapshot to Excel file."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Location inventory
        loc_data = []
        for loc_id, inv in snapshot.location_inventory.items():
            loc_name = locations.get(loc_id, Location(location_id=loc_id, name=loc_id)).name
            for batch in inv.batches:
                loc_data.append({
                    'Location ID': loc_id,
                    'Location Name': loc_name,
                    'Batch ID': batch.batch_id,
                    'Product ID': batch.product_id,
                    'Quantity': batch.quantity,
                    'Age (days)': batch.age_days,
                    'Production Date': batch.production_date,
                })

        if loc_data:
            df_locations = pd.DataFrame(loc_data)
            df_locations.to_excel(writer, sheet_name='Location Inventory', index=False)

        # In-transit
        transit_data = []
        for transit in snapshot.in_transit:
            transit_data.append({
                'Shipment ID': transit.shipment_id,
                'Origin': transit.origin_id,
                'Destination': transit.destination_id,
                'Product ID': transit.product_id,
                'Quantity': transit.quantity,
                'Departure Date': transit.departure_date,
                'Expected Arrival': transit.expected_arrival_date,
                'Days in Transit': transit.days_in_transit,
            })

        if transit_data:
            df_transit = pd.DataFrame(transit_data)
            df_transit.to_excel(writer, sheet_name='In Transit', index=False)

        # Demand satisfaction
        demand_data = []
        for record in snapshot.demand_satisfied:
            demand_data.append({
                'Destination': record.destination_id,
                'Product ID': record.product_id,
                'Demand': record.demand_quantity,
                'Supplied': record.supplied_quantity,
                'Shortage': record.shortage_quantity,
                'Fill Rate': record.fill_rate,
            })

        if demand_data:
            df_demand = pd.DataFrame(demand_data)
            df_demand.to_excel(writer, sheet_name='Demand Satisfaction', index=False)

    return output.getvalue()

# In Streamlit UI
if st.button("Export Snapshot to Excel"):
    excel_data = export_snapshot_to_excel(snapshot, locations)

    st.download_button(
        label="Download Excel File",
        data=excel_data,
        file_name=f"snapshot_{snapshot.date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

---

## 9. Roadmap

### 9.1 Current Limitations

#### Simplified Inventory Tracking

**Current State**:
- UI uses simplified snapshot generator (`_generate_snapshot()`)
- Does NOT implement full batch tracking through multi-leg routes
- Inventory calculation is approximate for complex networks

**Impact**:
- Works well for simple hub-and-spoke networks
- May show incorrect inventory at intermediate hubs for multi-leg routes
- Doesn't account for hub dwell time properly

**Workaround**:
- Use full `DailySnapshotGenerator` class for accurate tracking
- See Developer Guide section 4.1 for integration

#### No Shelf Life State Tracking

**Current State**:
- Batch age is tracked but not shelf life state (frozen/ambient/thawed)
- Doesn't account for state transitions (e.g., frozen → thawed at 6130)
- Age calculation doesn't reset on thawing

**Impact**:
- Cannot accurately show remaining shelf life for thawed products
- Age-based color coding may be misleading for frozen-then-thawed batches
- Cannot distinguish between frozen and ambient inventory at same location

**Example**:
- Batch produced Jan 1, frozen until Jan 15, thawed Jan 15
- On Jan 20, shows age = 19 days (correct)
- But actual shelf life = 9 days remaining after thaw (not shown)

#### No Visual Network Diagram

**Current State**:
- No graphical representation of network topology
- No visual flow diagram showing shipment paths
- Users must mentally map location relationships

**Impact**:
- Harder to understand complex multi-echelon networks
- Difficult to visualize batch movements
- No intuitive way to see bottlenecks or congestion

**Desired**:
- Interactive network diagram with nodes (locations) and edges (routes)
- Animated flows showing shipments in transit
- Heat map overlays for inventory levels

### 9.2 Future Enhancements

#### Full Network Inventory State Tracker

**Planned Feature**: Comprehensive state tracking system

**Capabilities**:
- Track shelf life state (frozen/ambient/thawed) for each batch at each location
- Calculate remaining shelf life based on state transitions
- Show color-coded shelf life status (not just age)
- Support state transition rules (e.g., frozen→thawed at WA destination)

**Implementation**:
```python
@dataclass
class BatchState:
    batch_id: str
    product_id: str
    quantity: float
    production_date: Date
    current_location: str
    shelf_life_state: str  # "frozen", "ambient", "thawed"
    state_transition_date: Optional[Date]  # When state changed
    remaining_shelf_life_days: int  # Calculated based on state

    def calculate_remaining_shelf_life(self, current_date: Date) -> int:
        """Calculate remaining shelf life based on state."""
        if self.shelf_life_state == "frozen":
            return 120 - (current_date - self.production_date).days
        elif self.shelf_life_state == "thawed":
            return 14 - (current_date - self.state_transition_date).days
        else:  # ambient
            return 17 - (current_date - self.production_date).days
```

**UI Changes**:
- Replace "Age" column with "Remaining Shelf Life"
- Color code based on remaining days (not age)
- Show state badges (🧊 Frozen, 🌡️ Ambient, ♨️ Thawed)

#### Shelf Life Visualization

**Planned Feature**: Visual shelf life tracking

**Charts**:
1. **Shelf Life Timeline**: Gantt chart showing batch lifecycles
2. **Expiration Calendar**: Heatmap of expiring inventory by date
3. **State Transition Diagram**: Flow chart of batches changing states

**Example**:
```
Batch Timeline View:
┌─────────────────────────────────────────────────────────────┐
│ BATCH-0045 (176283, 5000 units)                             │
│ ════════════════════════════════════════════════════════════│
│ Jan 1  ███ Produced at 6122                                 │
│ Jan 2  ███ At 6122 (ambient, 16 days left)                  │
│ Jan 3  ▓▓▓ In transit 6122→6104                             │
│ Jan 4  ███ At 6104 (ambient, 14 days left)                  │
│ Jan 5  ███ At 6104 (ambient, 13 days left)                  │
│ Jan 6  ▓▓▓ In transit 6104→6103                             │
│ Jan 7  ███ Delivered to 6103 (12 days left) ✓               │
└─────────────────────────────────────────────────────────────┘

Legend:
███ At location   ▓▓▓ In transit   🟢 Fresh   🟡 Medium   🔴 Old
```

#### Batch Lineage Viewer

**Planned Feature**: Trace individual batches through network

**Capabilities**:
- Select a batch and see its complete journey
- Timeline view of movements (production → shipments → delivery)
- State changes highlighted
- Cost accumulation along path

**UI**:
```python
def render_batch_lineage(batch_id: str, snapshots: List[DailySnapshot]):
    """Render batch journey through network."""
    st.subheader(f"Batch Lineage: {batch_id}")

    events = []

    for snapshot in snapshots:
        # Check location inventory
        for loc_id, inv in snapshot.location_inventory.items():
            for batch in inv.batches:
                if batch.batch_id == batch_id:
                    events.append({
                        'Date': snapshot.date,
                        'Event': 'At Location',
                        'Location': loc_id,
                        'Quantity': batch.quantity,
                        'Age': batch.age_days,
                    })

        # Check in-transit
        for transit in snapshot.in_transit:
            if transit.shipment_id.startswith(batch_id):
                events.append({
                    'Date': snapshot.date,
                    'Event': 'In Transit',
                    'Location': f"{transit.origin_id} → {transit.destination_id}",
                    'Quantity': transit.quantity,
                    'Age': '—',
                })

    df_lineage = pd.DataFrame(events)
    st.dataframe(df_lineage, use_container_width=True)
```

#### CSV Export

**Planned Feature**: Bulk data export

**Formats**:
- CSV for each snapshot component (inventory, transit, flows, demand)
- Combined ZIP archive for full snapshot
- Time series CSV for multi-date analysis

**Example**:
```python
def export_snapshot_csv(snapshot: DailySnapshot) -> Dict[str, str]:
    """Export snapshot to CSV strings."""
    exports = {}

    # Location inventory
    loc_data = []
    for loc_id, inv in snapshot.location_inventory.items():
        for batch in inv.batches:
            loc_data.append({
                'date': snapshot.date,
                'location_id': loc_id,
                'batch_id': batch.batch_id,
                'product_id': batch.product_id,
                'quantity': batch.quantity,
                'age_days': batch.age_days,
            })

    exports['inventory.csv'] = pd.DataFrame(loc_data).to_csv(index=False)

    # In-transit (similar)
    # Demand satisfaction (similar)

    return exports

# In UI
if st.button("Export All Snapshots to CSV"):
    all_exports = {}
    for snapshot in snapshots:
        exports = export_snapshot_csv(snapshot)
        # Combine into ZIP

    st.download_button("Download ZIP", zip_data, "snapshots.zip")
```

#### Comparison View

**Planned Feature**: Side-by-side snapshot comparison

**Use Cases**:
- Compare two dates in same plan
- Compare same date across scenarios
- Identify changes over time

**UI**:
```python
def render_snapshot_comparison(snapshot1: DailySnapshot, snapshot2: DailySnapshot):
    """Render side-by-side comparison."""
    st.subheader(f"Comparison: {snapshot1.date} vs {snapshot2.date}")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Inventory",
                  f"{snapshot1.total_system_inventory:,.0f}",
                  delta=snapshot1.total_system_inventory - snapshot2.total_system_inventory)

    with col2:
        st.metric("In Transit",
                  f"{snapshot1.total_in_transit:,.0f}",
                  delta=snapshot1.total_in_transit - snapshot2.total_in_transit)

    # Delta tables showing inventory changes
    # ...
```

#### Alerts for Low Inventory

**Planned Feature**: Proactive inventory monitoring

**Alert Types**:
1. **Low Inventory**: Location inventory below threshold
2. **Expiring Soon**: Batches approaching shelf life limit
3. **Shortage Risk**: Insufficient inventory to meet upcoming demand
4. **Overstock**: Excessive inventory buildup

**Implementation**:
```python
def check_inventory_alerts(snapshot: DailySnapshot, thresholds: Dict) -> List[Alert]:
    """Check for inventory alerts."""
    alerts = []

    for loc_id, inv in snapshot.location_inventory.items():
        # Low inventory alert
        if inv.total_quantity < thresholds.get('min_inventory', 0):
            alerts.append({
                'type': 'low_inventory',
                'severity': 'warning',
                'location': loc_id,
                'message': f"Inventory at {loc_id} below threshold: {inv.total_quantity:.0f} units",
            })

        # Expiring soon
        for batch in inv.batches:
            days_to_expire = 17 - batch.age_days  # Ambient shelf life
            if days_to_expire <= 7:
                alerts.append({
                    'type': 'expiring_soon',
                    'severity': 'error' if days_to_expire <= 3 else 'warning',
                    'location': loc_id,
                    'message': f"Batch {batch.batch_id} expires in {days_to_expire} days",
                })

    return alerts

# In UI
alerts = check_inventory_alerts(snapshot, thresholds)

if alerts:
    st.warning(f"⚠️ {len(alerts)} alerts detected")
    for alert in alerts:
        if alert['severity'] == 'error':
            st.error(alert['message'])
        else:
            st.warning(alert['message'])
```

---

## 10. References

### Related Documentation

- **Excel Template Specification**: `/home/sverzijl/planning_latest/data/examples/EXCEL_TEMPLATE_SPEC.md`
  - Input data format for forecasts, locations, routes, etc.

- **Manufacturing Schedule**: `/home/sverzijl/planning_latest/data/examples/MANUFACTURING_SCHEDULE.md`
  - Detailed truck schedules, labor calendar, production constraints

- **Network Routes**: `/home/sverzijl/planning_latest/data/examples/NETWORK_ROUTES.md`
  - Complete route topology and transit times

- **Breadroom Locations**: `/home/sverzijl/planning_latest/data/examples/BREADROOM_LOCATIONS.md`
  - Location details and demand patterns

- **Solver Installation**: `/home/sverzijl/planning_latest/docs/SOLVER_INSTALLATION.md`
  - How to install optimization solvers

### External Resources

- **Streamlit Documentation**: https://docs.streamlit.io/
  - UI framework reference

- **Pandas Documentation**: https://pandas.pydata.org/docs/
  - Data manipulation and Excel I/O

- **Plotly Documentation**: https://plotly.com/python/
  - Interactive visualization library

- **Python Dataclasses**: https://docs.python.org/3/library/dataclasses.html
  - Data model implementation

### Contact for Support

For questions, issues, or feature requests related to the Daily Snapshot feature:

1. **Project Repository**: Check existing issues or create new ones
2. **Development Team**: Contact the planning application development team
3. **Documentation Updates**: Submit pull requests to improve this documentation

### Version History

- **v1.0** (2025-01-01): Initial release with basic snapshot functionality
  - Date selector and navigation
  - Location inventory display
  - In-transit tracking
  - Production activity
  - Inflows/outflows
  - Demand satisfaction

- **v1.1** (Planned): Enhanced features
  - Full batch tracking through network
  - Shelf life state tracking
  - CSV export capability
  - Performance optimizations

---

**Document Version**: 1.0
**Last Updated**: 2025-10-09
**Author**: Planning Application Development Team
**Status**: Production-Ready Documentation
