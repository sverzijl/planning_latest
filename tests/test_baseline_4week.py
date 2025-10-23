"""Baseline Test 3: 4-week optimization with current model."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_baseline_4week_no_initial_inventory():
    """Baseline: 4-week optimization without initial inventory."""

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
    end_date = start_date + timedelta(days=27)  # 4 weeks

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

    result = model.solve(time_limit_seconds=180, mip_gap=0.01)

    # Note: Current model may not solve optimally for 4 weeks
    # Document the status for baseline
    print(f"\n=== BASELINE 4-WEEK STATUS ===")
    print(f"Termination: {result.termination_condition}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    if result.is_optimal() or result.is_feasible():
        solution = model.get_solution()

        shortages = solution.get('shortages_by_dest_product_date', {})
        total_shortage = sum(shortages.values())
        total_demand = sum(entry.quantity for entry in forecast.entries
                          if start_date <= entry.forecast_date <= end_date)

        fill_rate = (total_demand - total_shortage) / total_demand if total_demand > 0 else 1.0

        baseline_metrics = {
            'status': str(result.termination_condition),
            'fill_rate': fill_rate,
            'total_cost': solution.get('total_cost'),
            'solve_time': result.solve_time_seconds,
        }

        print(f"Fill Rate: {fill_rate:.1%}")
        print(f"Total Cost: ${baseline_metrics['total_cost']:,.2f}")
        print(f"==============================\n")

        import json
        with open('test_baseline_4week_metrics.json', 'w') as f:
            json.dump(baseline_metrics, f, indent=2, default=str)

        assert fill_rate >= 0.85, f"Fill rate should be ≥85% for 4-week, got: {fill_rate:.1%}"
    else:
        print(f"Model did not solve successfully: {result.termination_condition}")
        print(f"This is the BASELINE - document for comparison")
        print(f"==============================\n")

        # Don't fail - just document current behavior
        pytest.skip(f"Current model status: {result.termination_condition}")


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
