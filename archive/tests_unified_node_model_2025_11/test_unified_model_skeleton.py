"""Test UnifiedNodeModel skeleton (Phase 4)."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products


def test_unified_model_builds():
    """Test that UnifiedNodeModel skeleton builds without errors."""

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

    # Create UnifiedNodeModel
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=6)  # 1 week for fast testing

    print("\n" + "=" * 80)
    print("TESTING UNIFIED MODEL SKELETON")
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
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Build Pyomo model
    pyomo_model = model.build_model()

    # Assertions: Model structure
    assert pyomo_model is not None, "Model should be built"
    assert hasattr(pyomo_model, 'nodes'), "Model should have nodes set"
    assert hasattr(pyomo_model, 'products'), "Model should have products set"
    assert hasattr(pyomo_model, 'dates'), "Model should have dates set"
    assert hasattr(pyomo_model, 'routes'), "Model should have routes set"

    # Assertions: Variables exist
    assert hasattr(pyomo_model, 'production'), "Model should have production variables"
    assert hasattr(pyomo_model, 'inventory_cohort'), "Model should have inventory cohort variables"
    assert hasattr(pyomo_model, 'shipment_cohort'), "Model should have shipment cohort variables"

    if model.truck_schedules:
        assert hasattr(pyomo_model, 'truck_used'), "Model should have truck_used variables"
        assert hasattr(pyomo_model, 'truck_load'), "Model should have truck_load variables"

    # Assertions: Cohort indices created
    assert len(model.cohort_index_set) > 0, "Should have cohort indices"
    assert len(model.shipment_cohort_index_set) > 0, "Should have shipment cohort indices"
    assert len(model.demand_cohort_index_set) > 0, "Should have demand cohort indices"

    # Verify no duplicate 6122/6122_Storage issue
    node_ids = list(pyomo_model.nodes)
    assert '6122' in node_ids, "Real manufacturing node should exist"
    assert '6122_Storage' not in node_ids, "Virtual 6122_Storage should NOT exist in unified model"

    # Verify routes only from real nodes (no virtual nodes)
    for (origin, dest) in pyomo_model.routes:
        assert origin in node_ids, f"Route origin {origin} should be a real node"
        assert dest in node_ids, f"Route destination {dest} should be a real node"
        assert origin != '6122_Storage', "No routes from virtual 6122_Storage"

    print("\n✅ PHASE 4 VALIDATION:")
    print(f"   Model builds successfully")
    print(f"   Nodes: {len(pyomo_model.nodes)} (no virtual locations)")
    print(f"   Routes: {len(pyomo_model.routes)}")
    print(f"   Cohorts: {len(model.cohort_index_set):,}")
    print(f"   Shipment cohorts: {len(model.shipment_cohort_index_set):,}")
    print(f"   Demand cohorts: {len(model.demand_cohort_index_set):,}")
    print(f"   Variables created, ready for constraints (Phase 5)")
    print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
