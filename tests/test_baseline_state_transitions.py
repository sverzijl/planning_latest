"""Baseline Test 5: State transition verification."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_baseline_state_transitions():
    """Baseline: Verify freeze/thaw state transitions in current model."""

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

    # Check for frozen inventory at Lineage (should freeze ambient arrivals)
    cohort_inventory = solution.get('cohort_inventory', {})

    lineage_frozen = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                        if loc == 'Lineage' and state == 'frozen')

    lineage_ambient = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                         if loc == 'Lineage' and state == 'ambient')

    # Check for thawed inventory at 6130 (WA - should thaw frozen arrivals)
    wa_thawed = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                   if loc == '6130' and state == 'thawed')

    wa_frozen = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                   if loc == '6130' and state == 'frozen')

    baseline_metrics = {
        'lineage_frozen': lineage_frozen,
        'lineage_ambient': lineage_ambient,
        'wa_thawed': wa_thawed,
        'wa_frozen': wa_frozen,
    }

    print(f"\n=== BASELINE STATE TRANSITIONS ===")
    print(f"Lineage frozen inventory: {lineage_frozen:,.0f} units")
    print(f"Lineage ambient inventory: {lineage_ambient:,.0f} units")
    print(f"WA (6130) thawed inventory: {wa_thawed:,.0f} units")
    print(f"WA (6130) frozen inventory: {wa_frozen:,.0f} units")
    print(f"==================================\n")

    import json
    with open('test_baseline_state_transitions_metrics.json', 'w') as f:
        json.dump(baseline_metrics, f, indent=2, default=str)

    # Note: May be zero if Lineage/WA routes not used in optimal solution
    # Document for comparison with unified model


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
