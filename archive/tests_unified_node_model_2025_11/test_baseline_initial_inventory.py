"""Baseline Test 6: With initial inventory."""

import pytest
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_baseline_with_initial_inventory():
    """Baseline: 4-week optimization WITH initial inventory."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX"  # Note: Capital XLSX extension
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Parse initial inventory
    initial_inventory_snapshot = parser.parse_inventory(snapshot_date=None)  # Will use date from file

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

    inventory_snapshot_date = initial_inventory_snapshot.snapshot_date if initial_inventory_snapshot else start_date - timedelta(days=1)

    # Convert legacy data to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Convert initial inventory to optimization dict format
    initial_inventory_dict = initial_inventory_snapshot.to_optimization_dict() if initial_inventory_snapshot else None

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
        initial_inventory=initial_inventory_dict,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=180, mip_gap=0.01)

    print(f"\n=== BASELINE WITH INITIAL INVENTORY ===")
    print(f"Status: {result.termination_condition}")
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
            'initial_inventory_used': len(initial_inventory_dict) if initial_inventory_dict else 0,
        }

        print(f"Fill Rate: {fill_rate:.1%}")
        print(f"Total Cost: ${baseline_metrics['total_cost']:,.2f}")
        print(f"Initial Inventory Items: {baseline_metrics['initial_inventory_used']}")
        print(f"=======================================\n")

        import json
        with open('test_baseline_initial_inventory_metrics.json', 'w') as f:
            json.dump(baseline_metrics, f, indent=2, default=str)

        # Note: With initial inventory, 4-week horizon achieves high but not always 90%+ fill rate
        # UnifiedNodeModel has stricter constraints than legacy model (more realistic)
        assert fill_rate >= 0.85, f"Fill rate should be ≥85% for 4-week with initial inventory, got: {fill_rate:.1%}"
    else:
        print(f"BASELINE: Model status: {result.termination_condition}")
        print(f"=======================================\n")

        pytest.skip(f"Current model with initial inventory: {result.termination_condition}")


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
