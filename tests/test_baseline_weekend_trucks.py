"""Baseline Test 4: Truck schedule enforcement."""

import pytest
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_baseline_weekend_truck_constraints():
    """Baseline: Verify truck schedules are enforced (or not) in current model."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=13)  # 2 weeks (includes 2 weekends)

    # Convert legacy data to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=120, mip_gap=0.02)

    assert result.is_optimal() or result.is_feasible()

    solution = model.get_solution()

    # Check truck usage on weekends
    truck_used_by_date = solution.get('truck_used_by_date', {})

    weekend_violations = []
    for (truck_idx, date_val), used in truck_used_by_date.items():
        if used:
            # Check if truck departed on weekend (delivery_date - transit_time)
            truck = truck_schedules.schedules[truck_idx]
            transit_days = 1  # Simplified - actual transit varies
            departure_date = date_val - timedelta(days=transit_days)

            if departure_date.weekday() in [5, 6]:  # Weekend departure
                if not truck.applies_on_date(departure_date):
                    weekend_violations.append((truck.id, departure_date))

    # Check weekend hub inventory
    cohort_inventory = solution.get('cohort_inventory', {})
    hubs = ['6104', '6125']

    weekend_dates = [d for d in range(start_date.toordinal(), end_date.toordinal() + 1)
                     if date.fromordinal(d).weekday() in [5, 6]]
    weekend_dates = [date.fromordinal(d) for d in weekend_dates]

    weekend_hub_totals = {}
    for weekend_date in weekend_dates:
        for hub_id in hubs:
            total = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                       if loc == hub_id and curr_date == weekend_date)
            if total > 0.01:
                weekend_hub_totals[(hub_id, weekend_date)] = total

    baseline_metrics = {
        'weekend_violations': len(weekend_violations),
        'weekend_hub_inventory_instances': len(weekend_hub_totals),
        'total_weekends': len(weekend_dates),
    }

    print(f"\n=== BASELINE WEEKEND TRUCK CONSTRAINTS ===")
    print(f"Weekend truck violations: {baseline_metrics['weekend_violations']}")
    print(f"Weekend hub inventory instances: {baseline_metrics['weekend_hub_inventory_instances']}/{baseline_metrics['total_weekends'] * len(hubs)}")
    print(f"=========================================\n")

    import json
    with open('test_baseline_weekend_trucks_metrics.json', 'w') as f:
        json.dump(baseline_metrics, f, indent=2, default=str)

    # Document current behavior (may have bugs)
    # After unified model: weekend_violations must be 0, hub_inventory must be > 0


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
