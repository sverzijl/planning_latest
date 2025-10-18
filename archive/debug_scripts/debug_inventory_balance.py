"""
Debug the inventory balance constraint for specific cohorts.
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure

# Setup minimal case
day_1 = date(2025, 1, 1)
day_6 = date(2025, 1, 6)
day_7 = date(2025, 1, 7)

manufacturing = UnifiedNode(
    id='MFG', name='Manufacturing Site',
    capabilities=NodeCapabilities(
        can_manufacture=True, has_demand=False, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=1400.0,
    ),
)

breadroom = UnifiedNode(
    id='BR1', name='Breadroom 1',
    capabilities=NodeCapabilities(
        can_manufacture=False, has_demand=True, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=None,
    ),
)

route = UnifiedRoute(
    id='MFG-BR1',
    origin_node_id='MFG',
    destination_node_id='BR1',
    transit_days=1.0,
    cost_per_unit=1.0,
    transport_mode=TransportMode.AMBIENT,
)

forecast = Forecast(
    name='Minimal Test',
    entries=[
        ForecastEntry(
            location_id='BR1',
            product_id='PROD1',
            forecast_date=day_7,
            quantity=1000.0
        )
    ]
)

labor_days = []
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    labor_days.append(LaborDay(
        date=curr_date,
        is_fixed_day=True,
        fixed_hours=12.0,
        overtime_hours=2.0,
        minimum_hours=4.0,
        regular_rate=25.0,
        overtime_rate=37.50,
        non_fixed_rate=50.0,
    ))

labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    shortage_penalty_per_unit=10000.0,
)

# Create model
unified_model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom],
    routes=[route],
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=day_1,
    end_date=day_7,
    truck_schedules=None,
    initial_inventory=None,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
)

# Access the internal building method to inspect constraint generation
from pyomo.environ import ConcreteModel

model = ConcreteModel()
model.nodes = list(unified_model.nodes.keys())
model.products = list(unified_model.products)
model.dates = sorted(list(unified_model.production_dates))
model.routes = [(r.origin_node_id, r.destination_node_id) for r in unified_model.routes]

# Build cohort indices
unified_model.cohort_index_set = unified_model._build_cohort_indices(model.dates)
unified_model.shipment_cohort_index_set = unified_model._build_shipment_cohort_indices(model.dates)
unified_model.demand_cohort_index_set = unified_model._build_demand_cohort_indices(model.dates)

print()
print("=" * 80)
print("MANUAL CONSTRAINT GENERATION FOR KEY COHORTS")
print("=" * 80)
print()

# Manually trace the inventory balance rule for critical cohorts
test_cohorts = [
    ('MFG', 'PROD1', day_6, day_6, 'ambient', "MFG day-6 on day-6 (production day)"),
    ('BR1', 'PROD1', day_6, day_7, 'ambient', "BR1 day-6 on day-7 (arrival/demand day)"),
]

for (node_id, prod, prod_date, curr_date, state, description) in test_cohorts:
    print(f"{description}:")
    print(f"  Cohort: {(node_id, prod, prod_date, curr_date, state)}")
    print()

    node = unified_model.nodes[node_id]

    # Previous inventory
    prev_date = unified_model.date_previous.get(curr_date)
    if prev_date is None:
        prev_inv_str = f"0 (first date)"
    else:
        if (node_id, prod, prod_date, prev_date, state) in unified_model.cohort_index_set:
            prev_inv_str = f"inventory_cohort[{node_id}, {prod}, {prod_date}, {prev_date}, {state}]"
        else:
            prev_inv_str = "0 (cohort doesn't exist on prev date)"

    print(f"  Previous inventory: {prev_inv_str}")

    # Production inflow
    if node.can_produce() and prod_date == curr_date:
        production_state = node.get_production_state()
        if state == production_state:
            prod_str = f"production[{node_id}, {prod}, {curr_date}]"
        else:
            prod_str = "0 (wrong state)"
    else:
        prod_str = "0 (not production day or can't produce)"

    print(f"  Production inflow: {prod_str}")

    # Arrivals
    arrivals_list = []
    for r in unified_model.routes_to_node[node_id]:
        arrival_state = unified_model._determine_arrival_state(r, node)
        if arrival_state == state:
            if (r.origin_node_id, r.destination_node_id, prod, prod_date, curr_date, arrival_state) in unified_model.shipment_cohort_index_set:
                arrivals_list.append(f"shipment_cohort[{r.origin_node_id}, {r.destination_node_id}, {prod}, {prod_date}, {curr_date}, {arrival_state}]")

    if arrivals_list:
        print(f"  Arrivals: {' + '.join(arrivals_list)}")
    else:
        print(f"  Arrivals: 0")

    # Departures
    departures_list = []
    for r in unified_model.routes_from_node[node_id]:
        if r.transport_mode == TransportMode.FROZEN:
            departure_state = 'frozen'
        else:
            departure_state = 'ambient'

        if state != departure_state:
            continue

        for delivery_date in model.dates:
            transit_timedelta = timedelta(days=r.transit_days)
            departure_datetime = delivery_date - transit_timedelta

            if isinstance(departure_datetime, date):
                departure_date = departure_datetime
            else:
                departure_date = departure_datetime.date()

            if departure_date == curr_date:
                arrival_state = unified_model._determine_arrival_state(r, unified_model.nodes[r.destination_node_id])
                if (r.origin_node_id, r.destination_node_id, prod, prod_date, delivery_date, arrival_state) in unified_model.shipment_cohort_index_set:
                    departures_list.append(f"shipment_cohort[{r.origin_node_id}, {r.destination_node_id}, {prod}, {prod_date}, {delivery_date}, {arrival_state}]")

    if departures_list:
        print(f"  Departures: {' + '.join(departures_list)}")
    else:
        print(f"  Departures: 0")

    # Demand
    if node.has_demand_capability():
        if (node_id, prod, curr_date) in unified_model.demand:
            if (node_id, prod, prod_date, curr_date) in unified_model.demand_cohort_index_set:
                if state == 'ambient' and node.supports_ambient_storage():
                    demand_str = f"demand_from_cohort[{node_id}, {prod}, {prod_date}, {curr_date}]"
                else:
                    demand_str = "0 (wrong state)"
            else:
                demand_str = "0 (cohort not in demand index)"
        else:
            demand_str = "0 (no demand on this date)"
    else:
        demand_str = "0 (node can't have demand)"

    print(f"  Demand consumption: {demand_str}")
    print()

    print(f"  Balance equation:")
    print(f"    {prev_inv_str} + {prod_str} + Arrivals ==")
    print(f"    inventory_cohort[{node_id}, {prod}, {prod_date}, {curr_date}, {state}] + {demand_str} + Departures")
    print()
    print("-" * 80)
    print()
