"""Baseline Test 2: 2-week optimization with current model."""

import pytest
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_baseline_2week_no_initial_inventory():
    """Baseline: 2-week optimization without initial inventory."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

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
    end_date = start_date + timedelta(days=13)  # 2 weeks

    # Convert legacy data to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
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
    assert solution is not None

    # Calculate fill rate
    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())
    total_demand = sum(entry.quantity for entry in forecast.entries
                      if start_date <= entry.forecast_date <= end_date)

    fill_rate = (total_demand - total_shortage) / total_demand if total_demand > 0 else 1.0
    # Note: Short horizons (2-week) have lower fill rates due to transit times and lead times
    # UnifiedNodeModel produces realistic results with tighter constraints
    assert fill_rate >= 0.70, f"Fill rate should be ≥70% for 2-week horizon, got: {fill_rate:.1%}"

    # Capture baseline
    baseline_metrics = {
        'fill_rate': fill_rate,
        'total_cost': solution.get('total_cost'),
        'solve_time': result.solve_time_seconds,
    }

    print(f"\n=== BASELINE 2-WEEK METRICS ===")
    for key, value in baseline_metrics.items():
        print(f"{key}: {value}")
    print(f"================================\n")

    import json
    with open('test_baseline_2week_metrics.json', 'w') as f:
        json.dump(baseline_metrics, f, indent=2, default=str)


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
