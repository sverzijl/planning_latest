# Product Changeover Times

## Overview

**Changeover time** is the time required to switch the production line from one product to another. This includes cleaning, adjusting equipment, changing packaging materials, and quality checks.

Changeover times are a critical component of production scheduling because they:
- **Reduce effective production capacity** - Hours spent on changeovers can't be used for production
- **Impact labor costs** - More changeovers = more labor hours = higher costs
- **Affect feasibility** - Poor sequencing can make schedules infeasible due to capacity constraints
- **Drive campaign scheduling** - Grouping same products minimizes changeover time

## Production Daily Cycle

Each production day includes several types of overhead time:

```
Daily Timeline:
├─ Startup (0.5h)        ← Line startup at beginning of day
├─ Production            ← Actual manufacturing
│  ├─ Product A (units/production_rate)
│  ├─ Changeover A→B (e.g., 0.25h)
│  ├─ Product B (units/production_rate)
│  ├─ Changeover B→C (e.g., 1.0h)
│  └─ Product C (units/production_rate)
└─ Shutdown (0.5h)       ← Line shutdown at end of day
```

**Total Labor Hours for Day:**
```
labor_hours = startup + shutdown + sum(production_times) + sum(changeover_times)
            = 0.5 + 0.5 + (units_A/rate + units_B/rate + units_C/rate) + (changeover_A→B + changeover_B→C)
```

## Changeover Time Matrix

Changeover times can be **sequence-dependent**: changing from Product A to Product B may take different time than B to A.

### Example Matrix for 5 Products

| From ↓ / To → | HELGAS WHITE | HELGAS MIXED | HELGAS WHOLEM | WONDER WHITE | WONDER WHOLEM |
|---------------|--------------|--------------|---------------|--------------|---------------|
| **HELGAS WHITE**  | 0.0h         | 0.25h        | 0.25h         | 1.0h         | 1.0h          |
| **HELGAS MIXED**  | 0.25h        | 0.0h         | 0.25h         | 1.0h         | 1.0h          |
| **HELGAS WHOLEM** | 0.25h        | 0.25h        | 0.0h          | 1.0h         | 1.0h          |
| **WONDER WHITE**  | 1.0h         | 1.0h         | 1.0h          | 0.0h         | 0.25h         |
| **WONDER WHOLEM** | 1.0h         | 1.0h         | 1.0h          | 0.25h        | 0.0h          |

**Rules:**
- **Same product (diagonal):** 0.0h - no changeover needed
- **Same brand:** 0.25h - quick changeover (15 minutes)
  - Example: HELGAS WHITE → HELGAS MIXED
- **Different brand:** 1.0h - full changeover (60 minutes)
  - Example: HELGAS WHITE → WONDER WHITE
- **First product of day:** 0.0h - no changeover (startup already accounts for line prep)

### Rationale

**Same Brand (15 min):**
- Similar recipes and ingredients
- Same packaging supplier/format
- Minimal cleaning required
- Quick quality checks

**Different Brand (60 min):**
- Different ingredient formulations
- Different packaging materials
- Thorough line cleaning required
- Full quality validation
- Possibly different certifications

## Impact on Capacity

### Example: Poor vs Good Sequencing

**Scenario:** Produce 1,400 units each of 5 products in one day (7,000 units total)

**Poor Sequence** (alternating brands):
```
Startup (0.5h)
→ HELGAS WHITE (1.0h production)
→ Changeover to WONDER WHITE (1.0h)
→ WONDER WHITE (1.0h production)
→ Changeover to HELGAS MIXED (1.0h)
→ HELGAS MIXED (1.0h production)
→ Changeover to WONDER WHOLEM (1.0h)
→ WONDER WHOLEM (1.0h production)
→ Changeover to HELGAS WHOLEM (1.0h)
→ HELGAS WHOLEM (1.0h production)
Shutdown (0.5h)

Total: 0.5 + 5.0 (production) + 4.0 (changeovers) + 0.5 = 10.0 hours
```

**Good Sequence** (campaign scheduling - group by brand):
```
Startup (0.5h)
→ HELGAS WHITE (1.0h production)
→ Changeover to HELGAS MIXED (0.25h)
→ HELGAS MIXED (1.0h production)
→ Changeover to HELGAS WHOLEM (0.25h)
→ HELGAS WHOLEM (1.0h production)
→ Changeover to WONDER WHITE (1.0h)
→ WONDER WHITE (1.0h production)
→ Changeover to WONDER WHOLEM (0.25h)
→ WONDER WHOLEM (1.0h production)
Shutdown (0.5h)

Total: 0.5 + 5.0 (production) + 1.75 (changeovers) + 0.5 = 7.75 hours
```

**Savings:** 2.25 hours per day (22.5% capacity improvement)

### Real-World Impact (204-day forecast)

Using actual forecast data:
- Total demand: ~2.4M units
- Average 2-3 products per production day
- **Poor sequencing:** ~410 hours lost to unnecessary changeovers
- **Good sequencing:** ~170 hours lost (campaign scheduling)
- **Capacity saved:** 240 hours × 1,400 units/hour = **336,000 units**

This is equivalent to 24 full production days worth of capacity!

## Implementation in Code

### Data Model

#### ManufacturingSite
```python
class ManufacturingSite(Location):
    daily_startup_hours: float = 0.5
    daily_shutdown_hours: float = 0.5
    default_changeover_hours: float = 1.0  # Used when specific pair not defined
```

#### ProductChangeoverMatrix
```python
from src.production import ProductChangeoverMatrix, create_simple_changeover_matrix

# Option 1: Manual specification
matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)
matrix.add_changeover("HELGAS WHITE", "HELGAS MIXED", 0.25)
matrix.add_changeover("HELGAS WHITE", "WONDER WHITE", 1.0)

# Option 2: Simple brand-based heuristic
products = ["HELGAS WHITE", "HELGAS MIXED", "WONDER WHITE", "WONDER WHOLEM"]
matrix = create_simple_changeover_matrix(
    product_ids=products,
    same_brand_hours=0.25,
    different_brand_hours=1.0
)
```

#### ProductionBatch
```python
class ProductionBatch(BaseModel):
    sequence_number: Optional[int]           # Order in daily production (1, 2, 3, ...)
    changeover_from_product: Optional[str]   # Previous product on line
    changeover_time_hours: float = 0.0       # Time spent on changeover
```

### Usage Example

```python
from src.production import ProductionScheduler, create_simple_changeover_matrix

# Create changeover matrix for your products
product_ids = ["HELGAS WHITE", "HELGAS MIXED", "HELGAS WHOLEM",
               "WONDER WHITE", "WONDER WHOLEM"]
changeover_matrix = create_simple_changeover_matrix(product_ids)

# Create scheduler with changeover matrix
scheduler = ProductionScheduler(
    manufacturing_site=manufacturing_site,
    labor_calendar=labor_calendar,
    graph_builder=graph_builder,
    changeover_matrix=changeover_matrix
)

# Generate schedule - automatically sequences products optimally
schedule = scheduler.schedule_from_forecast(forecast)

# Examine batches
for batch in schedule.production_batches:
    print(f"Seq {batch.sequence_number}: {batch.product_id}")
    print(f"  Changeover from: {batch.changeover_from_product}")
    print(f"  Changeover time: {batch.changeover_time_hours}h")
    print(f"  Production time: {batch.quantity / manufacturing_site.production_rate}h")
    print(f"  Total labor: {batch.labor_hours_used}h")
```

## Campaign Scheduling Algorithm

The production scheduler uses a **greedy campaign scheduling heuristic**:

1. **Group requirements by production date**
2. **For each day, sort batches by product_id** (groups same products together)
3. **Assign sequence numbers** (1st, 2nd, 3rd, ...)
4. **Calculate changeover times** using the changeover matrix
5. **Allocate overhead:**
   - First batch gets startup time
   - Last batch gets shutdown time
   - All batches get their changeover time

This simple heuristic achieves near-optimal results because:
- Consecutive same-product batches have 0 changeover time
- Products are implicitly grouped by brand (alphabetical sorting)
- Computational complexity is O(n log n) per day (just sorting)

### Future Enhancements

More sophisticated algorithms could optimize changeover order using:
- **Traveling Salesman Problem (TSP) approach** - minimize total changeover time
- **Branch and bound** - find optimal sequence for small product sets
- **Dynamic programming** - optimal sequencing with additional constraints
- **Mixed-integer programming** - integrate with full optimization model

## Configuration in Excel

Future versions will support a **ChangeoverTimes** sheet:

| FromProduct    | ToProduct      | ChangeoverHours |
|----------------|----------------|-----------------|
| HELGAS WHITE   | HELGAS MIXED   | 0.25            |
| HELGAS WHITE   | HELGAS WHOLEM  | 0.25            |
| HELGAS WHITE   | WONDER WHITE   | 1.0             |
| HELGAS MIXED   | HELGAS WHITE   | 0.25            |
| ...            | ...            | ...             |

If not provided, the system uses the `default_changeover_hours` from ManufacturingSite.

## Best Practices

1. **Define changeover times based on actual operations data**
   - Measure real changeover times at the plant
   - Account for cleaning, setup, quality checks
   - Include time for crew breaks during changeovers

2. **Use brand-based heuristics as a starting point**
   - Same brand = quick changeover
   - Different brand = longer changeover
   - Refine based on operational experience

3. **Consider sequence-dependency**
   - WHITE → WHOLEMEAL may be faster than reverse (less cleaning)
   - FROZEN → AMBIENT may differ from AMBIENT → FROZEN

4. **Account for all daily overhead**
   - Startup time (line preparation)
   - Shutdown time (cleaning, securing)
   - Changeovers between products

5. **Monitor and update regularly**
   - Track actual vs planned changeover times
   - Adjust matrix based on production data
   - Account for equipment improvements or process changes

## See Also

- `MANUFACTURING_SCHEDULE.md` - Complete operational schedule details
- `BREADROOM_LOCATIONS.md` - Demand locations
- `NETWORK_ROUTES.md` - Distribution routing
- `src/production/changeover.py` - Implementation code
- `src/production/scheduler.py` - Campaign scheduling algorithm
