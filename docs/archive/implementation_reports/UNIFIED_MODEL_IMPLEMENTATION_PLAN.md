# Unified Node Model - Implementation Plan

## Status: Ready to Begin Implementation

**Decision:** Proceeding with Option A - Full Unified Model refactor with test-driven development.

---

## Phase 1: BASELINE TESTS (COMPLETED)

**Objective:** Capture current model behavior as regression reference

**Tests Created:**
- ✅ `tests/test_baseline_1week.py` - 1-week optimization
- ✅ `tests/test_baseline_2week.py` - 2-week optimization
- ✅ `tests/test_baseline_4week.py` - 4-week optimization
- ✅ `tests/test_baseline_weekend_trucks.py` - Truck schedule enforcement
- ✅ `tests/test_baseline_state_transitions.py` - Freeze/thaw logic
- ✅ `tests/test_baseline_initial_inventory.py` - With initial inventory

**Next Step:** Run all baseline tests to capture metrics
```bash
venv/bin/python -m pytest tests/test_baseline_*.py -v --tb=short
```

**Baseline metrics will be saved to:**
- `test_baseline_*_metrics.json` files for comparison

---

## Phase 2: UNIFIED DATA MODELS

**Files to Create:**

### 2.1 Core Models
**File:** `src/models/unified_node.py`
```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StorageMode(str, Enum):
    FROZEN = "frozen"
    AMBIENT = "ambient"
    BOTH = "both"


class NodeCapabilities(BaseModel):
    """Capabilities that a node can have."""
    can_manufacture: bool = Field(False, description="Can produce product")
    production_rate_per_hour: Optional[float] = Field(None, description="Units/hour if manufacturing")

    can_store: bool = Field(True, description="Can hold inventory")
    storage_mode: StorageMode = Field(StorageMode.AMBIENT, description="Storage temperature capability")
    storage_capacity: Optional[float] = Field(None, description="Max units (None=unlimited)")

    has_demand: bool = Field(False, description="Is a demand destination")

    # Truck constraints (if True, outbound shipments must use scheduled trucks)
    requires_truck_schedules: bool = Field(False, description="Outbound needs truck schedules")


class UnifiedNode(BaseModel):
    """Unified node - replaces Location/ManufacturingSite/Storage types."""
    id: str = Field(..., description="Node ID")
    name: str = Field(..., description="Node name")
    capabilities: NodeCapabilities = Field(..., description="Node capabilities")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def can_produce(self) -> bool:
        return self.capabilities.can_manufacture

    def has_demand_capability(self) -> bool:
        return self.capabilities.has_demand

    def supports_frozen_storage(self) -> bool:
        return self.capabilities.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]

    def supports_ambient_storage(self) -> bool:
        return self.capabilities.storage_mode in [StorageMode.AMBIENT, StorageMode.BOTH]

    def can_freeze_thaw(self) -> bool:
        return self.capabilities.storage_mode == StorageMode.BOTH
```

### 2.2 Unified Route
**File:** `src/models/unified_route.py`
```python
from enum import Enum
from pydantic import BaseModel, Field


class TransportMode(str, Enum):
    FROZEN = "frozen"
    AMBIENT = "ambient"


class UnifiedRoute(BaseModel):
    """Route connecting two nodes."""
    id: str
    origin_node_id: str
    destination_node_id: str
    transit_days: float = Field(..., description="Transit time (0=instant, 0.5=half day, 1.0=one day)")
    transport_mode: TransportMode = Field(TransportMode.AMBIENT)
    cost_per_unit: float = Field(0.0, description="Cost per unit shipped")
```

### 2.3 Generalized Truck Schedule
**File:** `src/models/unified_truck_schedule.py`
```python
from enum import Enum
from typing import Optional, List
from datetime import time, date as Date
from pydantic import BaseModel, Field


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class DepartureType(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"


class UnifiedTruckSchedule(BaseModel):
    """Generalized truck schedule - works for ANY route."""
    id: str
    origin_node_id: str  # NEW: Can be 6122, 6125, 6104, etc.
    destination_node_id: str
    departure_type: DepartureType
    departure_time: time
    day_of_week: Optional[DayOfWeek] = None  # None = runs every day
    capacity: float
    cost_fixed: float = 0.0
    cost_per_unit: float = 0.0
    intermediate_stops: List[str] = Field(default_factory=list)
    pallet_capacity: int = 44

    def applies_on_date(self, check_date: Date) -> bool:
        """Check if truck runs on given date."""
        if not self.day_of_week:
            return True

        day_map = {
            DayOfWeek.MONDAY: 0, DayOfWeek.TUESDAY: 1,
            DayOfWeek.WEDNESDAY: 2, DayOfWeek.THURSDAY: 3,
            DayOfWeek.FRIDAY: 4, DayOfWeek.SATURDAY: 5,
            DayOfWeek.SUNDAY: 6,
        }
        return check_date.weekday() == day_map[self.day_of_week]
```

**Integration Test After This Phase:**
```bash
venv/bin/python -m pytest tests/test_unified_models.py -v
# Validates: Models can be created, validated, converted from legacy
```

---

## Phase 3: CONVERSION LAYER

**File:** `src/optimization/legacy_to_unified_converter.py`

**Purpose:** Convert existing data to unified format for backward compatibility

```python
from typing import List, Tuple, Dict
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule


class LegacyToUnifiedConverter:
    """Convert legacy data structures to unified node model."""

    def convert_nodes(
        self,
        manufacturing_site,
        locations: List,
        forecast
    ) -> List[UnifiedNode]:
        """Convert manufacturing site + locations to unified nodes."""

        nodes = []
        demand_locations = {e.location_id for e in forecast.entries}

        # Manufacturing site becomes node with manufacturing capability
        nodes.append(UnifiedNode(
            id=manufacturing_site.id,
            name=manufacturing_site.name,
            capabilities=NodeCapabilities(
                can_manufacture=True,
                production_rate_per_hour=manufacturing_site.production_rate,
                can_store=True,
                storage_mode=StorageMode.AMBIENT,  # 6122 produces ambient
                requires_truck_schedules=True,  # Manufacturing uses scheduled trucks
            ),
            latitude=manufacturing_site.latitude,
            longitude=manufacturing_site.longitude,
        ))

        # Other locations become nodes based on their properties
        for loc in locations:
            nodes.append(UnifiedNode(
                id=loc.id,
                name=loc.name,
                capabilities=NodeCapabilities(
                    can_manufacture=False,
                    can_store=True,
                    storage_mode=loc.storage_mode,
                    has_demand=(loc.id in demand_locations),
                    requires_truck_schedules=False,  # Hubs don't require trucks (for now)
                ),
                latitude=loc.latitude,
                longitude=loc.longitude,
            ))

        return nodes

    def convert_routes(self, routes: List) -> List[UnifiedRoute]:
        """Convert legacy routes to unified format."""
        unified_routes = []

        for route in routes:
            unified_routes.append(UnifiedRoute(
                id=route.id,
                origin_node_id=route.origin_id,
                destination_node_id=route.destination_id,
                transit_days=route.transit_time_days,
                transport_mode=TransportMode.FROZEN if route.transport_mode == 'frozen' else TransportMode.AMBIENT,
                cost_per_unit=route.cost_per_unit if hasattr(route, 'cost_per_unit') else 0.0,
            ))

        return unified_routes

    def convert_truck_schedules(
        self,
        truck_schedules,
        manufacturing_site_id: str
    ) -> List[UnifiedTruckSchedule]:
        """Convert legacy truck schedules (adds origin_node_id)."""
        unified_trucks = []

        for truck in truck_schedules.schedules:
            # Current truck schedules are all from manufacturing
            # In unified model, we explicitly set origin_node_id
            unified_trucks.append(UnifiedTruckSchedule(
                id=truck.id,
                origin_node_id=manufacturing_site_id,  # Explicit origin
                destination_node_id=truck.destination_id,
                departure_type=truck.departure_type,
                departure_time=truck.departure_time,
                day_of_week=truck.day_of_week,
                capacity=truck.capacity,
                cost_fixed=truck.cost_fixed,
                cost_per_unit=truck.cost_per_unit,
                intermediate_stops=truck.intermediate_stops,
                pallet_capacity=truck.pallet_capacity,
            ))

        return unified_trucks
```

**Integration Test:**
```bash
venv/bin/python -m pytest tests/test_legacy_conversion.py -v
# Validates: All legacy data converts correctly to unified format
```

---

## Phase 4: UNIFIED MODEL SKELETON

**File:** `src/optimization/unified_node_model.py`

**Structure:**
```python
class UnifiedNodeModel(BaseOptimizationModel):
    """Unified node-based optimization model.

    Key simplifications:
    - No virtual locations (no 6122_Storage)
    - Single inventory balance equation for all nodes
    - Generalized truck constraints for any route
    - Clean state transition rules
    """

    def __init__(
        self,
        nodes: List[UnifiedNode],
        routes: List[UnifiedRoute],
        forecast: Forecast,
        labor_calendar: LaborCalendar,
        cost_structure: CostStructure,
        start_date: Date,
        end_date: Date,
        truck_schedules: Optional[List[UnifiedTruckSchedule]] = None,
        initial_inventory: Optional[Dict] = None,
        use_batch_tracking: bool = True,
        allow_shortages: bool = False,
    ):
        # Extract sets
        self.nodes = {n.id: n for n in nodes}
        self.routes = routes
        self.manufacturing_nodes = [n for n in nodes if n.can_produce()]
        self.demand_nodes = [n for n in nodes if n.has_demand_capability()]

        # Build route index
        self.routes_by_origin = defaultdict(list)
        self.routes_by_destination = defaultdict(list)
        for route in routes:
            self.routes_by_origin[route.origin_node_id].append(route)
            self.routes_by_destination[route.destination_node_id].append(route)

        # Truck schedules indexed by origin node
        self.trucks_by_origin = defaultdict(list)
        if truck_schedules:
            for truck in truck_schedules:
                self.trucks_by_origin[truck.origin_node_id].append(truck)

    def build_model(self) -> ConcreteModel:
        """Build unified model."""
        model = ConcreteModel()

        # Sets
        model.nodes = list(self.nodes.keys())
        model.products = list(self.products)
        model.dates = list(self.production_dates)
        model.routes = [(r.origin_node_id, r.destination_node_id) for r in self.routes]

        # Decision variables (simplified - no separate frozen/ambient at model level)
        # State tracking happens in cohorts

        # inventory[node, product, prod_date, curr_date, state]
        model.inventory_cohort = Var(
            model.cohort_index,  # Sparse index
            within=NonNegativeReals
        )

        # production[node, product, date] - only for manufacturing nodes
        model.production = Var(...)

        # shipment[route, product, prod_date, delivery_date, arrival_state]
        model.shipment_cohort = Var(...)

        # truck_load[truck_id, product, delivery_date] - if trucks defined
        if self.truck_schedules:
            model.truck_load = Var(...)

        # Build constraints
        self._add_inventory_balance_constraints(model)
        self._add_production_constraints(model)
        self._add_demand_constraints(model)
        if self.truck_schedules:
            self._add_truck_constraints(model)
        self._add_state_transition_constraints(model)

        return model
```

**Integration Test After This Phase:**
```bash
venv/bin/python -m pytest tests/test_unified_model_builds.py -v
# Validates: Model builds without errors, variables created correctly
```

---

## Phase 5: CORE CONSTRAINTS

**Implement in order:**

### 5.1 Unified Inventory Balance
```python
def _add_inventory_balance_constraints(self, model):
    """Single inventory balance equation for ALL nodes."""

    def inventory_balance_rule(model, node_id, prod, prod_date, curr_date, state):
        """
        Unified balance: works for manufacturing, hubs, storage, destinations

        inventory[t] = inventory[t-1] +
                       production (if node.can_manufacture and prod_date==curr_date) +
                       arrivals_in_this_state +
                       state_transitions_to_this_state -
                       demand (if node.has_demand) -
                       departures_from_this_state -
                       state_transitions_from_this_state
        """
        node = self.nodes[node_id]

        # Previous inventory
        prev_date = self.date_previous.get(curr_date)
        prev_inv = (model.inventory_cohort[node_id, prod, prod_date, prev_date, state]
                   if prev_date else self.initial_inventory.get(...))

        # Production inflow (only if manufacturing node, prod_date==curr_date, correct state)
        production_inflow = 0
        if node.can_produce() and prod_date == curr_date:
            # Production state matches node storage mode
            if state == self._get_production_state(node):
                production_inflow = model.production[node_id, prod, curr_date]

        # Route arrivals in this state
        arrivals = sum(
            model.shipment_cohort[route, prod, prod_date, curr_date, arrival_state]
            for route in self.routes_to_node[node_id]
            if arrival_state == state  # Only count arrivals matching current state
        )

        # State transitions
        transitions_in = self._get_state_transition_inflows(...)
        transitions_out = self._get_state_transition_outflows(...)

        # Demand consumption (only if node has demand capability)
        demand_consumption = 0
        if node.has_demand_capability():
            if (node_id, prod, curr_date) in self.demand:
                demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]

        # Route departures from this state
        departures = sum(
            model.shipment_cohort[route, prod, prod_date, delivery_date, state]
            for route in self.routes_from_node[node_id]
            where departure_date == curr_date
        )

        return model.inventory_cohort[node_id, prod, prod_date, curr_date, state] == (
            prev_inv + production_inflow + arrivals + transitions_in -
            demand_consumption - departures - transitions_out
        )

    model.inventory_balance_con = Constraint(
        model.cohort_index,
        rule=inventory_balance_rule,
        doc="Unified inventory balance for all nodes"
    )
```

**Integration Test:**
```bash
venv/bin/python -m pytest tests/test_unified_inventory_balance.py -v
# Validates: Inventory balance works, mass balance preserved
```

### 5.2 Production Constraints
```python
def _add_production_constraints(self, model):
    """Production capacity constraints for manufacturing nodes."""

    def production_capacity_rule(model, node_id, date):
        node = self.nodes[node_id]
        if not node.can_produce():
            return Constraint.Skip

        # Get labor hours for this date
        labor_hours = self.labor_hours[date]
        capacity = node.capabilities.production_rate_per_hour * labor_hours

        total_production = sum(model.production[node_id, p, date] for p in model.products)
        return total_production <= capacity

    model.production_capacity_con = Constraint(...)
```

### 5.3 Demand Satisfaction
```python
def _add_demand_constraints(self, model):
    """Demand satisfaction for nodes with demand capability."""

    def demand_satisfaction_rule(model, node_id, prod, date):
        node = self.nodes[node_id]
        if not node.has_demand_capability():
            return Constraint.Skip

        if (node_id, prod, date) not in self.demand:
            return Constraint.Skip

        # Sum cohort allocations + shortage = demand
        cohort_supply = sum(
            model.demand_from_cohort[node_id, prod, prod_date, date]
            for prod_date in valid_prod_dates
        )

        return cohort_supply + model.shortage[node_id, prod, date] == self.demand[(node_id, prod, date)]
```

**Integration Test:**
```bash
venv/bin/python -m pytest tests/test_unified_core_constraints.py -v
# Validates: Production, demand, basic flow works
# Compare: 1-week solution cost/fill_rate with baseline
```

---

## Phase 6: STATE TRANSITIONS

**State Determination Logic:**

```python
def determine_arrival_state(
    self,
    route: UnifiedRoute,
    destination_node: UnifiedNode
) -> str:
    """Determine product state upon arrival at destination.

    Rules:
    - Ambient transport + Ambient node → ambient (no change)
    - Ambient transport + Frozen node → frozen (freeze, reset to 120d)
    - Frozen transport + Frozen node → frozen (no change)
    - Frozen transport + Ambient node → thawed (reset to 14d)
    """
    if route.transport_mode == TransportMode.AMBIENT:
        if destination_node.supports_frozen_storage() and not destination_node.supports_ambient_storage():
            return 'frozen'  # Freeze upon arrival
        else:
            return 'ambient'  # Stays ambient
    else:  # FROZEN transport
        if destination_node.supports_ambient_storage() and not destination_node.supports_frozen_storage():
            return 'thawed'  # Thaw upon arrival (14-day reset)
        else:
            return 'frozen'  # Stays frozen
```

**Constraints:**
```python
def _add_state_transition_constraints(self, model):
    """Automatic state transitions based on storage mode mismatch."""

    # State transitions are IMPLICIT in cohort creation
    # When shipment arrives, arrival_state determines which cohort it flows into
    # No explicit freeze/thaw variables needed - handled by cohort indexing

    # Shelf life enforcement via sparse indexing:
    # - Frozen cohorts: age <= 120 days
    # - Ambient cohorts: age <= 17 days
    # - Thawed cohorts: age_since_thaw <= 14 days (prod_date = thaw_date)
```

**Integration Test:**
```bash
venv/bin/python -m pytest tests/test_unified_state_transitions.py -v
# Validates: 6130 receives frozen → becomes thawed with 14-day shelf life
# Validates: Lineage receives ambient → becomes frozen with 120-day shelf life
```

---

## Phase 7: GENERALIZED TRUCK CONSTRAINTS

**Truck Constraint (Works for ANY Node):**

```python
def _add_truck_constraints(self, model):
    """Generalized truck constraints for any route with truck schedules."""

    # For each route that has truck schedules defined
    for route in self.routes:
        trucks_for_route = [
            t for t in self.truck_schedules
            if t.origin_node_id == route.origin_node_id and
               t.destination_node_id == route.destination_node_id
        ]

        if not trucks_for_route:
            continue  # No truck constraints for this route

        def route_truck_linking_rule(model, prod, delivery_date):
            """Shipment on route = sum of truck loads (if trucks defined)."""

            # Which trucks can deliver on this date?
            departure_date = delivery_date - timedelta(days=route.transit_days)
            applicable_trucks = [
                t for t in trucks_for_route
                if t.applies_on_date(departure_date)
            ]

            shipment_qty = sum(
                model.shipment_cohort[route_key, prod, pd, delivery_date, state]
                for all valid cohorts/states
            )

            truck_load_qty = sum(
                model.truck_load[t.id, prod, delivery_date]
                for t in applicable_trucks
            )

            return shipment_qty == truck_load_qty

        model.add_component(
            f'truck_link_{route.id}',
            Constraint(model.products, model.dates, rule=route_truck_linking_rule)
        )
```

**Key Benefit:** This works for manufacturing→hub AND hub→spoke trucks!

**Integration Test:**
```bash
venv/bin/python -m pytest tests/test_unified_truck_constraints.py -v
# Validates: Manufacturing trucks constrained to Mon-Fri
# Validates: No weekend outflows from nodes with truck schedules
# Validates: Hub inventory exists on weekends
```

---

## Phase 8: COMPLETE INTEGRATION TESTING

**Run Full Test Suite:**

```bash
# Baseline tests (current model)
venv/bin/python -m pytest tests/test_baseline_*.py -v

# Unified model tests (new model)
venv/bin/python -m pytest tests/test_unified_*.py -v

# Comparison
venv/bin/python compare_baseline_vs_unified.py
```

**Acceptance Criteria:**
- ✅ All unified tests pass
- ✅ Fill rates match or exceed baseline
- ✅ Solve times comparable or better
- ✅ Weekend hub inventory > 0 (fixes current bug)
- ✅ No weekend truck usage (fixes current bug)
- ✅ State transitions work correctly

---

## Phase 9: UI INTEGRATION

**9.1 Add Model Selector:**
```python
# ui/pages/2_Planning.py
model_type = st.selectbox(
    "Model Type",
    options=["Legacy Model (Current)", "Unified Node Model (New)"],
    help="Legacy: Current implementation. Unified: Simplified architecture."
)

if model_type == "Unified Node Model (New)":
    # Use UnifiedNodeModel
    from src.optimization.unified_node_model import UnifiedNodeModel
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(truck_schedules, manufacturing_site.id)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        ...
    )
else:
    # Use existing IntegratedProductionDistributionModel
    model = IntegratedProductionDistributionModel(...)
```

**9.2 Result Adapter:**
- Ensure UnifiedNodeModel.get_solution() returns same format as legacy
- Daily snapshot should work with both models
- No UI changes needed if solution format is compatible

---

## Timeline Estimate

| Phase | Task | Estimated Time |
|-------|------|----------------|
| 1 | Baseline tests | ✅ Complete |
| 2 | Unified data models | 2 hours |
| 3 | Conversion layer | 2 hours |
| 4 | Model skeleton | 2 hours |
| 5 | Core constraints | 4 hours |
| 6 | State transitions | 3 hours |
| 7 | Truck constraints | 3 hours |
| 8 | Integration testing | 2 hours |
| 9 | UI integration | 2 hours |
| **Total** | **~20 hours** | **2.5 days** |

---

## Risk Mitigation

**At Each Phase:**
1. Write integration test FIRST
2. Implement feature
3. Run test - must pass before proceeding
4. If test fails, debug or revert
5. Commit only when tests pass

**Abort Conditions:**
- If any phase takes >2x estimated time → reassess
- If tests show worse performance → investigate before proceeding
- If fill rates drop significantly → root cause analysis required

---

## Success Metrics

**The unified model is successful if:**

1. **Correctness:**
   - All integration tests pass
   - Fill rates ≥ baseline
   - Mass balance preserved

2. **Bug Fixes:**
   - ✅ No weekend shipments from nodes with Mon-Fri trucks
   - ✅ Hub inventory visible on weekends
   - ✅ No 6122/6122_Storage confusion

3. **New Capabilities:**
   - ✅ Can define truck schedules for hub-to-spoke routes
   - ✅ Cleaner state transition logic
   - ✅ Easier to extend

4. **Performance:**
   - Solve times within 2x of baseline (acceptable given added flexibility)
   - 4-week horizon solves optimally (currently fails)

---

## Next Immediate Steps

**User Action Required:**
1. Review this plan - approve to proceed
2. Decide on testing frequency (test after each phase vs. batch testing)

**Development Approach:**
- **Incremental commits** - one per phase with passing tests
- **Branch strategy** - create `feature/unified-node-model` branch?
- **Parallel availability** - legacy model remains in master during development

**First Development Session:**
1. Run baseline tests, capture metrics
2. Create unified data models (Phase 2)
3. Test model creation
4. Commit if tests pass
5. Report progress

Ready to begin implementation?
