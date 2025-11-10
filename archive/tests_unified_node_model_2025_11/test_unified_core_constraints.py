"""Test UnifiedNodeModel with core constraints (Phase 5)."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products


def test_unified_model_builds_with_constraints():
    """Test that UnifiedNodeModel builds with core constraints."""

    # Load legacy data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Find manufacturing site
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

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site,
        locations,
        routes,
        truck_schedules_list,
        forecast
    )

    # Create UnifiedNodeModel - 1 week for fast testing
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)

    print("\n" + "=" * 80)
    print("TESTING UNIFIED MODEL WITH CORE CONSTRAINTS")
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
        allow_shortages=True,  # Allow shortages for initial testing
        enforce_shelf_life=True,
    )

    # Build model
    pyomo_model = model.build_model()

    # Assertions
    assert pyomo_model is not None, "Model should build"
    assert hasattr(pyomo_model, 'inventory_balance_con'), "Should have inventory balance constraint"
    assert hasattr(pyomo_model, 'demand_satisfaction_con'), "Should have demand satisfaction constraint"
    assert hasattr(pyomo_model, 'production_capacity_con'), "Should have production capacity constraint"
    assert hasattr(pyomo_model, 'obj'), "Should have objective function"

    # Check constraint counts
    num_constraints = pyomo_model.nconstraints()
    num_variables = pyomo_model.nvariables()

    print(f"\n✅ MODEL WITH CONSTRAINTS BUILT:")
    print(f"   Variables: {num_variables:,}")
    print(f"   Constraints: {num_constraints:,}")
    print(f"   Inventory balance: Unified equation for all nodes")
    print(f"   Demand satisfaction: Cohort-based allocation")
    print(f"   Production capacity: Per manufacturing node")
    print(f"   Objective: Minimize total cost")
    print("=" * 80)

    assert num_constraints > 0, "Should have constraints"
    assert num_variables > 0, "Should have variables"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
