# Campaign Pattern Algorithm Design

**Status:** PENDING EXPERT INPUT
**Assigned To:** production-planner
**Priority:** HIGH
**Last Updated:** 2025-10-19

---

## Objective

Design algorithm to generate production campaign patterns for warmstart initial solution.

---

## Business Context

### Production Constraints
- **Products:** 5 SKUs (PROD_001 through PROD_005)
- **Production Rate:** 1,400 units/hour
- **Daily Capacity:** 16,800 units regular (12h), 19,600 units with overtime (14h)
- **Weekly Capacity:** 84,000 units regular, 98,000 units with overtime
- **Changeover Time:** 1.0 hour per SKU switch
- **Changeover Cost:** Labor hours (0.5h startup + 0.25h shutdown + 1.0h changeover)

### Labor Schedule
- **Monday-Friday:** 12 hours fixed labor (regular rate) + 2 hours overtime (premium rate)
- **Saturday-Sunday:** Overtime only with 4-hour minimum payment (premium rate)
- **Public Holidays:** Same as weekend (4h minimum, premium rate)
- **Cost Structure:**
  - Regular rate: $20/hour
  - Overtime rate: $30/hour
  - Non-fixed rate: $40/hour

### Campaign Objectives
1. **Minimize changeovers** - Reduce setup time and costs
2. **Minimize weekend production** - Avoid high labor costs
3. **Meet demand** - Satisfy forecast requirements
4. **Rotate products** - Ensure all 5 SKUs produced weekly
5. **Smooth production** - Avoid extreme daily variations

---

## Requirements

### Functional Requirements

1. **Weekly Rotation**
   - All 5 products must be produced at least once per week
   - Prevent stale inventory and stockouts

2. **Campaign Grouping**
   - Group 2-3 SKUs per production day
   - Minimize changeover time (max 2 changeovers per day)

3. **Demand Allocation**
   - Distribute weekly demand across production days
   - Account for shelf life constraints (17 days ambient)

4. **Weekday Preference**
   - Prioritize Monday-Friday production
   - Use weekends only when necessary (high demand weeks)

5. **Capacity Respect**
   - Stay within daily production capacity
   - Flag when overtime needed

### Algorithm Requirements

1. **Input Data**
   - Forecast: demand by product, location, date
   - Products: list of SKUs
   - Planning horizon: start_date to end_date
   - Node capabilities: manufacturing nodes

2. **Output Format**
   ```python
   {
       ('production', (node_id, product_id, date)): quantity,
       ('product_produced', (node_id, product_id, date)): 1.0,  # binary
       ('num_products_produced', (node_id, date)): 2,  # integer
       # ... more variables
   }
   ```

3. **Validation**
   - Total production ≥ total demand (with buffer)
   - Capacity constraints satisfied (or flagged)
   - All products produced weekly

---

## Algorithm Design Questions

### Q1: Demand Aggregation Strategy
**Question:** How to aggregate demand for campaign planning?

**Options:**
- A. Weekly total demand (sum all days/locations)
- B. Rolling 7-day demand window
- C. Horizon total demand ÷ number of weeks
- D. Daily demand + safety stock buffer

**Considerations:**
- Shelf life: 17 days (can produce in week N for week N+2 demand)
- Multi-echelon network: Hub vs direct routes
- Demand variance: Some weeks higher than others

**Required Information:**
- Aggregation period (daily/weekly/horizon)
- Safety stock % (e.g., 5% buffer)
- Shelf life incorporation

### Q2: Product Grouping Strategy
**Question:** How to group 5 products into campaigns?

**Options:**
- A. Fixed rotation (Mon: P1+P2, Tue: P3+P4, Wed: P5, repeat)
- B. Demand-weighted (high-demand products on separate days)
- C. SKU similarity (group by product family)
- D. Random rotation with capacity balancing

**Example Fixed Rotation:**
```
Week 1:
  Monday: PROD_001, PROD_002 (2 SKUs, 1 changeover)
  Tuesday: PROD_003, PROD_004 (2 SKUs, 1 changeover)
  Wednesday: PROD_005 (1 SKU, 0 changeovers)
  Thursday: PROD_001, PROD_002 (repeat)
  Friday: PROD_003, PROD_004 (repeat)

Week 2: Same pattern
```

**Required Information:**
- Grouping logic (fixed vs dynamic)
- Priority ordering (demand-based, alphabetic, etc.)
- Rotation frequency (weekly, bi-weekly, etc.)

### Q3: Quantity Allocation Strategy
**Question:** How to allocate weekly demand to production days?

**Options:**
- A. EQUAL: Divide equally across production days
- B. DEMAND_WEIGHTED: Proportional to daily demand
- C. CAPACITY_BALANCED: Smooth to utilize capacity evenly
- D. JUST_IN_TIME: Produce close to demand date

**Example (DEMAND_WEIGHTED):**
```
Product: PROD_001
Weekly demand: 10,000 units
Production days: Monday (40%), Wednesday (60%)

Allocation:
  Monday: 4,000 units (40% of 10,000)
  Wednesday: 6,000 units (60% of 10,000)
```

**Required Information:**
- Allocation method
- Weighting factors (demand, capacity, transit time)
- Buffer/safety stock handling

### Q4: Overtime Decision Strategy
**Question:** When to use overtime vs split across days?

**Options:**
- A. AVOID_OVERTIME: Never use overtime, split to next day
- B. USE_IF_NEEDED: Overtime if demand exceeds regular capacity
- C. AGGRESSIVE_OT: Use overtime to minimize production days
- D. WEEKEND_LAST: Only use weekends if weekdays full

**Scenario:**
```
Daily demand: 18,000 units
Regular capacity: 16,800 units
Options:
  1. Overtime 1,200 units on one day (2 hours OT @ $30/h)
  2. Split across two days (9,000 each, no OT)
```

**Required Information:**
- Overtime threshold (units or %)
- Weekend trigger (when to use Saturday/Sunday)
- Cost tradeoff formula

### Q5: Multi-Week Planning
**Question:** How to handle 4-week planning horizons?

**Options:**
- A. REPEAT_PATTERN: Same weekly pattern for all 4 weeks
- B. ROLLING_PATTERN: Shift pattern each week
- C. WEEK_SPECIFIC: Custom pattern per week based on demand
- D. HYBRID: Fixed pattern + demand adjustments

**Example (REPEAT_PATTERN):**
```
Week 1: Monday (P1,P2), Tuesday (P3,P4), Wednesday (P5), ...
Week 2: Monday (P1,P2), Tuesday (P3,P4), Wednesday (P5), ...
Week 3: Monday (P1,P2), Tuesday (P3,P4), Wednesday (P5), ...
Week 4: Monday (P1,P2), Tuesday (P3,P4), Wednesday (P5), ...
```

**Required Information:**
- Pattern repetition logic
- Demand variation handling
- Public holiday adjustments

---

## Expected Deliverables

### From production-planner:

1. **Algorithm Specification**
   - Pseudocode or flowchart
   - Step-by-step logic
   - Decision rules

2. **Strategy Selections**
   - Answers to Q1-Q5
   - Rationale for choices
   - Tradeoff analysis

3. **Implementation Guidance**
   - Python function signature
   - Input/output examples
   - Edge case handling

4. **Validation Criteria**
   - Success metrics
   - Failure detection
   - Quality thresholds

5. **Example Scenarios**
   - 5 products, 1 week example
   - 5 products, 4 weeks example
   - High demand week (>98k units)

---

## Example Output Format

```python
# Expected warmstart data structure
warmstart_values = {
    # Production quantities (continuous)
    ('production', ('6122', 'PROD_001', date(2025, 10, 20))): 5000.0,
    ('production', ('6122', 'PROD_002', date(2025, 10, 20))): 4500.0,
    ('production', ('6122', 'PROD_003', date(2025, 10, 21))): 6000.0,

    # Binary indicators
    ('product_produced', ('6122', 'PROD_001', date(2025, 10, 20))): 1.0,
    ('product_produced', ('6122', 'PROD_002', date(2025, 10, 20))): 1.0,
    ('product_produced', ('6122', 'PROD_003', date(2025, 10, 21))): 1.0,

    # Changeover counts (integer)
    ('num_products_produced', ('6122', date(2025, 10, 20))): 2,
    ('num_products_produced', ('6122', date(2025, 10, 21))): 1,

    # ... inventory and shipment cohorts (optional)
}
```

---

## Integration Points

### WarmstartGenerator class structure
```python
class WarmstartGenerator:
    """Generate warmstart solutions for UnifiedNodeModel."""

    def __init__(self, model: UnifiedNodeModel):
        self.model = model
        self.nodes = model.nodes
        self.forecast = model.forecast
        self.start_date = model.start_date
        self.end_date = model.end_date

    def generate(self) -> Dict[Tuple, float]:
        """Generate warmstart values.

        Returns:
            Dictionary mapping (variable_name, index_tuple) to value
        """
        warmstart = {}

        # 1. Generate production campaign pattern
        production_plan = self._generate_campaign_pattern()

        # 2. Convert to warmstart format
        warmstart.update(self._production_to_warmstart(production_plan))

        # 3. (Optional) Generate inventory/shipment cohorts
        # warmstart.update(self._generate_inventory_cohorts())

        return warmstart

    def _generate_campaign_pattern(self) -> Dict:
        """Generate production campaign pattern.

        Returns:
            Production plan: {(node_id, product_id, date): quantity}
        """
        # >>> IMPLEMENT ALGORITHM HERE <<<
        pass
```

---

## Dependencies

**Upstream:**
- `cbc_warmstart_mechanism.md` (warmstart data structure)

**Downstream:**
- `integration_design.md` (uses campaign algorithm)

---

## Timeline

- **Request Date:** 2025-10-19
- **Expected Response:** Within 1 iteration (after CBC mechanism design)
- **Dependencies:** CBC warmstart mechanism design
- **Blocking:** Implementation agents

---

## Notes

- Algorithm must be deterministic (same input → same output)
- Should complete in <5 seconds for 4-week horizon
- Must handle edge cases (public holidays, high demand, capacity limits)
- Can use simplified heuristics (not optimal, just feasible)

---

## Status Tracking

- [ ] Expert assigned
- [ ] Questions answered
- [ ] Algorithm specified
- [ ] Pseudocode provided
- [ ] Examples validated
- [ ] Approved for implementation
