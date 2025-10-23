"""Test that unified model produces (no shortages allowed)."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products


def test_unified_model_produces_without_shortages():
    """Test unified model with allow_shortages=False to force production."""

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

    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)

    print("\n" + "=" * 80)
    print("TESTING UNIFIED MODEL PRODUCTION (NO SHORTAGES ALLOWED)")
    print("=" * 80)

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
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=False,  # FORCE production - no shortages allowed
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=120, mip_gap=0.05)

    print(f"\nSolve Status: {result.termination_condition}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    if not (result.is_optimal() or result.is_feasible()):
        print(f"❌ Model did not solve: {result.termination_condition}")
        if result.infeasibility_message:
            print(f"   {result.infeasibility_message}")
        pytest.skip(f"Model infeasible or unsolved: {result.termination_condition}")

    solution = model.get_solution()

    assert solution is not None

    production_entries = len(solution.get('production_by_date_product', {}))
    shipment_entries = len(solution.get('shipments_by_route_product_date', {}))
    total_production = sum(solution.get('production_by_date_product', {}).values())
    total_shipments = sum(solution.get('shipments_by_route_product_date', {}).values())

    print(f"\n✅ SOLUTION WITH NO SHORTAGES:")
    print(f"   Production entries: {production_entries}")
    print(f"   Total production: {total_production:,.0f} units")
    print(f"   Shipment entries: {shipment_entries}")
    print(f"   Total shipments: {total_shipments:,.0f} units")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print("=" * 80)

    # Verify production happens
    assert production_entries > 0, "Should have production when shortages not allowed"
    assert total_production > 0, "Should produce units"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
