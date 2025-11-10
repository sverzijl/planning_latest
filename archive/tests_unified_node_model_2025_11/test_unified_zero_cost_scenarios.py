"""Test unified model solution extraction with zero-cost scenarios.

These tests verify that the model can extract solutions successfully even when
certain cost parameters are set to 0, which can cause solver to leave variables
uninitialized (valid behavior).
"""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products


@pytest.fixture
def base_model_data():
    """Load base model data from example files."""
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
    end_date = start_date + timedelta(days=6)  # 1 week for fast tests

    return {
        'nodes': nodes,
        'routes': unified_routes,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'start_date': start_date,
        'end_date': end_date,
        'truck_schedules': unified_trucks,
    }


def test_zero_transport_costs_solution_extraction(base_model_data):
    """Test that solution extracts successfully when all transport costs = 0.

    This tests the fix for uninitialized variable errors when costs are zero.
    The solver may leave shipment variables uninitialized, which is valid behavior.
    """
    # Set all route costs to 0
    for route in base_model_data['routes']:
        route.cost_per_unit = 0.0

    print("\n" + "=" * 80)
    print("TESTING ZERO TRANSPORT COSTS")
    print("=" * 80)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=base_model_data['nodes'],
        routes=base_model_data['routes'],
        forecast=base_model_data['forecast'],
        products=products,
        labor_calendar=base_model_data['labor_calendar'],
        cost_structure=base_model_data['cost_structure'],
        start_date=base_model_data['start_date'],
        end_date=base_model_data['end_date'],
        truck_schedules=base_model_data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    # Should succeed despite zero costs
    assert result.success, f"Solution extraction should succeed with zero transport costs. Error: {result.infeasibility_message}"
    assert result.is_optimal() or result.is_feasible(), "Should find optimal or feasible solution"

    # Get solution
    solution = model.get_solution()
    assert solution is not None, "Solution should be extracted"
    assert 'total_cost' in solution, "Should have total cost"
    assert 'shipments_by_route_product_date' in solution, "Should have shipments"

    # Transport cost should be 0
    assert solution.get('total_transport_cost', 0) == 0, "Transport cost should be 0"

    print(f"\n✅ ZERO TRANSPORT COSTS TEST PASSED:")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print(f"   Transport cost: ${solution.get('total_transport_cost', 0):,.2f}")
    print(f"   Shipments: {len(solution.get('shipments_by_route_product_date', {}))}")
    print("=" * 80)


def test_zero_storage_costs_solution_extraction(base_model_data):
    """Test solution extraction with zero storage costs.

    When storage costs are 0, inventory variables may be uninitialized.
    """
    # Set all storage costs to 0
    base_model_data['cost_structure'].storage_cost_frozen_per_unit_day = 0.0
    base_model_data['cost_structure'].storage_cost_ambient_per_unit_day = 0.0
    base_model_data['cost_structure'].storage_cost_per_pallet_day_frozen = 0.0
    base_model_data['cost_structure'].storage_cost_per_pallet_day_ambient = 0.0
    base_model_data['cost_structure'].storage_cost_fixed_per_pallet_frozen = 0.0
    base_model_data['cost_structure'].storage_cost_fixed_per_pallet_ambient = 0.0

    print("\n" + "=" * 80)
    print("TESTING ZERO STORAGE COSTS")
    print("=" * 80)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=base_model_data['nodes'],
        routes=base_model_data['routes'],
        forecast=base_model_data['forecast'],
        products=products,
        labor_calendar=base_model_data['labor_calendar'],
        cost_structure=base_model_data['cost_structure'],
        start_date=base_model_data['start_date'],
        end_date=base_model_data['end_date'],
        truck_schedules=base_model_data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    # Should succeed
    assert result.success, f"Solution extraction should succeed with zero storage costs. Error: {result.infeasibility_message}"
    assert result.is_optimal() or result.is_feasible(), "Should find optimal or feasible solution"

    # Get solution
    solution = model.get_solution()
    assert solution is not None, "Solution should be extracted"
    assert 'total_cost' in solution, "Should have total cost"

    # Storage cost should be 0
    assert solution.get('total_holding_cost', 0) == 0, "Holding cost should be 0"

    print(f"\n✅ ZERO STORAGE COSTS TEST PASSED:")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print(f"   Holding cost: ${solution.get('total_holding_cost', 0):,.2f}")
    print(f"   Inventory entries: {len(solution.get('cohort_inventory', {}))}")
    print("=" * 80)


def test_mixed_zero_nonzero_costs(base_model_data):
    """Test extraction when some routes have zero cost and others don't.

    This creates a sparse solution where some variables are initialized
    and others are not.
    """
    # Set 50% of routes to zero cost (every other route)
    for i, route in enumerate(base_model_data['routes']):
        if i % 2 == 0:
            route.cost_per_unit = 0.0
        else:
            route.cost_per_unit = 0.5  # Keep original cost

    print("\n" + "=" * 80)
    print("TESTING MIXED ZERO/NON-ZERO COSTS")
    print("=" * 80)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=base_model_data['nodes'],
        routes=base_model_data['routes'],
        forecast=base_model_data['forecast'],
        products=products,
        labor_calendar=base_model_data['labor_calendar'],
        cost_structure=base_model_data['cost_structure'],
        start_date=base_model_data['start_date'],
        end_date=base_model_data['end_date'],
        truck_schedules=base_model_data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    # Should succeed
    assert result.success, f"Solution extraction should succeed with mixed costs. Error: {result.infeasibility_message}"
    assert result.is_optimal() or result.is_feasible(), "Should find optimal or feasible solution"

    # Get solution
    solution = model.get_solution()
    assert solution is not None, "Solution should be extracted"
    assert 'total_cost' in solution, "Should have total cost"

    print(f"\n✅ MIXED COSTS TEST PASSED:")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print(f"   Transport cost: ${solution.get('total_transport_cost', 0):,.2f}")
    print(f"   Shipments: {len(solution.get('shipments_by_route_product_date', {}))}")
    print("=" * 80)


def test_zero_production_cost(base_model_data):
    """Test extraction when production cost is zero.

    Production variables may be uninitialized when cost is 0.
    """
    # Set production cost to 0
    base_model_data['cost_structure'].production_cost_per_unit = 0.0

    print("\n" + "=" * 80)
    print("TESTING ZERO PRODUCTION COST")
    print("=" * 80)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=base_model_data['nodes'],
        routes=base_model_data['routes'],
        forecast=base_model_data['forecast'],
        products=products,
        labor_calendar=base_model_data['labor_calendar'],
        cost_structure=base_model_data['cost_structure'],
        start_date=base_model_data['start_date'],
        end_date=base_model_data['end_date'],
        truck_schedules=base_model_data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=90, mip_gap=0.05)

    # Should succeed
    assert result.success, f"Solution extraction should succeed with zero production cost. Error: {result.infeasibility_message}"
    assert result.is_optimal() or result.is_feasible(), "Should find optimal or feasible solution"

    # Get solution
    solution = model.get_solution()
    assert solution is not None, "Solution should be extracted"
    assert 'total_cost' in solution, "Should have total cost"
    assert 'production_by_date_product' in solution, "Should have production data"

    # Production cost should be 0
    assert solution.get('total_production_cost', 0) == 0, "Production cost should be 0"

    print(f"\n✅ ZERO PRODUCTION COST TEST PASSED:")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")
    print(f"   Production cost: ${solution.get('total_production_cost', 0):,.2f}")
    print(f"   Production entries: {len(solution.get('production_by_date_product', {}))}")
    print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
