"""Test unified model solution extraction."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def test_unified_solution_extraction():
    """Test that solution can be extracted from unified model."""

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
    print("TESTING SOLUTION EXTRACTION")
    print("=" * 80)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    assert result.is_optimal() or result.is_feasible()

    # Get solution
    solution = model.get_solution()

    assert solution is not None, "Solution should be extracted"
    assert isinstance(solution, dict), "Solution should be a dictionary"

    # Check required keys
    assert 'production_by_date_product' in solution
    assert 'cohort_inventory' in solution
    assert 'total_cost' in solution

    # Check solution contents
    print(f"\n✅ SOLUTION EXTRACTED:")
    print(f"   Production entries: {len(solution.get('production_by_date_product', {}))}")
    print(f"   Cohort inventory entries: {len(solution['cohort_inventory'])}")
    print(f"   Shipment entries: {len(solution.get('shipments_by_route_product_date', {}))}")
    print(f"   Shortage entries: {len(solution.get('shortages_by_dest_product_date', {}))}")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print(f"   Production cost: ${solution.get('total_production_cost', 0):,.2f}")
    print(f"   Transport cost: ${solution.get('total_transport_cost', 0):,.2f}")
    print(f"   Shortage cost: ${solution.get('total_shortage_cost', 0):,.2f}")

    # Extract production schedule
    prod_schedule = model.extract_production_schedule()
    assert prod_schedule is not None, "Should extract production schedule"

    # Extract shipments
    shipments = model.extract_shipments()
    assert isinstance(shipments, list), "Should return list of shipments"

    print(f"\n   Production schedule: {len(prod_schedule.production_batches)} batches")
    print(f"   Shipments: {len(shipments)}")
    print("=" * 80)

    # Note: May have zero production if model chooses to use only initial inventory
    # or if demand is very low. This is OK for testing extraction logic.


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
