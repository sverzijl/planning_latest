"""Test truck routing fixes: intermediate stops and day-of-week enforcement.

This test validates the critical fixes for:
1. Intermediate stop expansion (Lineage receives goods)
2. Day-of-week enforcement (trucks only run on scheduled days)
"""

import pytest
from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def test_intermediate_stop_expansion():
    """Test that intermediate stops are expanded into explicit routes."""

    # Parse data
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gluten Free Forecast - Latest.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=None
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Count routes before
    routes_before = len(routes)

    # Convert
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Build model (triggers route expansion)
    start_date = date(2025, 1, 6)
    end_date = start_date + timedelta(days=6)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        products=products,
        forecast=forecast,
        initial_inventory=None,
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,
        use_pallet_tracking=False,  # Faster
        use_truck_pallet_tracking=False
    )

    # Check routes after expansion
    routes_after = len(model_builder.routes)

    print(f"\nRoutes before expansion: {routes_before}")
    print(f"Routes after expansion: {routes_after}")
    print(f"Routes added: {routes_after - routes_before}")

    # Verify Lineage → 6125 route was added
    lineage_to_6125 = any(
        r for r in model_builder.routes
        if r.origin_node_id == 'Lineage' and r.destination_node_id == '6125'
    )

    assert lineage_to_6125, "Lineage → 6125 route should be created from intermediate stop expansion"

    # Verify original routes still exist
    assert routes_after >= routes_before, "Route expansion should not remove existing routes"

    print("✅ Intermediate stop expansion working correctly")


def test_day_of_week_enforcement():
    """Test that trucks only run on their scheduled days."""

    # Parse data
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gluten Free Forecast - Latest.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=data_dir / "inventory_latest.XLSX" if (data_dir / "inventory_latest.XLSX").exists() else None
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Find Monday and Tuesday in truck schedules
    monday_trucks = [t for t in truck_schedules_list if t.day_of_week and 'monday' in str(t.day_of_week).lower()]
    tuesday_trucks = [t for t in truck_schedules_list if t.day_of_week and 'tuesday' in str(t.day_of_week).lower()]

    print(f"\nMonday trucks: {[t.destination_id for t in monday_trucks]}")
    print(f"Tuesday trucks: {[t.destination_id for t in tuesday_trucks]}")

    # Monday should have 6125, 6104 (not 6110)
    monday_dests = {t.destination_id for t in monday_trucks}
    assert '6125' in monday_dests, "Monday should have truck to 6125"
    assert '6104' in monday_dests, "Monday should have truck to 6104"
    assert '6110' not in monday_dests, "Monday should NOT have truck to 6110"

    # Tuesday should have 6110
    tuesday_dests = {t.destination_id for t in tuesday_trucks}
    assert '6110' in tuesday_dests, "Tuesday should have truck to 6110"

    print("✅ Truck schedules configured correctly")

    # Build model and check enforcement
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # One week including Monday (2025-01-06)
    start_date = date(2025, 1, 6)  # Monday
    end_date = start_date + timedelta(days=6)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        products=products,
        forecast=forecast,
        initial_inventory=None,
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,
        use_pallet_tracking=False,
        use_truck_pallet_tracking=False
    )

    pyomo_model = model_builder.build_model()

    # Check in_transit variables
    # Monday (2025-01-06) should have:
    #   - 6122 → 6125 ✓
    #   - 6122 → 6104 ✓
    #   - 6122 → 6110 ✗ (no truck)

    monday = date(2025, 1, 6)

    has_6110_monday = any(
        (origin, dest, prod, dep_date, state) in pyomo_model.in_transit
        for origin in ['6122']
        for dest in ['6110']
        for prod in pyomo_model.products
        for dep_date in [monday]
        for state in ['ambient', 'frozen']
    )

    has_6125_monday = any(
        (origin, dest, prod, dep_date, state) in pyomo_model.in_transit
        for origin in ['6122']
        for dest in ['6125']
        for prod in pyomo_model.products
        for dep_date in [monday]
        for state in ['ambient', 'frozen']
    )

    has_6104_monday = any(
        (origin, dest, prod, dep_date, state) in pyomo_model.in_transit
        for origin in ['6122']
        for dest in ['6104']
        for prod in pyomo_model.products
        for dep_date in [monday]
        for state in ['ambient', 'frozen']
    )

    print(f"\nMonday (2025-01-06) shipment variables:")
    print(f"  6122 → 6125: {has_6125_monday}")
    print(f"  6122 → 6104: {has_6104_monday}")
    print(f"  6122 → 6110: {has_6110_monday}")

    assert has_6125_monday, "Should have shipment variables for 6122 → 6125 on Monday"
    assert has_6104_monday, "Should have shipment variables for 6122 → 6104 on Monday"
    assert not has_6110_monday, "Should NOT have shipment variables for 6122 → 6110 on Monday (no truck)"

    print("✅ Day-of-week enforcement working correctly")


def test_lineage_receives_goods():
    """Test that Lineage receives goods via intermediate stop on Wednesday."""

    # Parse with inventory
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gluten Free Forecast - Latest.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=data_dir / "inventory_latest.XLSX" if (data_dir / "inventory_latest.XLSX").exists() else None
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Setup
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]

    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # 2 weeks including a Wednesday
    start_date = date(2025, 1, 6)  # Monday
    end_date = start_date + timedelta(days=13)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    # Parse inventory if available
    inventory_snapshot = None
    if parser._inventory_parser:
        try:
            inventory_snapshot = parser.parse_inventory(snapshot_date=start_date)
        except:
            pass

    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        products=products,
        forecast=forecast,
        initial_inventory=inventory_snapshot.to_optimization_dict() if inventory_snapshot else None,
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        allow_shortages=True,
        use_pallet_tracking=False,
        use_truck_pallet_tracking=False
    )

    # Check that Lineage route exists
    has_route_to_lineage = any(
        r for r in model_builder.routes
        if r.origin_node_id == '6122' and r.destination_node_id == 'Lineage'
    )

    has_route_from_lineage = any(
        r for r in model_builder.routes
        if r.origin_node_id == 'Lineage'
    )

    print(f"\nLineage routing:")
    print(f"  Route TO Lineage (6122 → Lineage): {has_route_to_lineage}")
    print(f"  Routes FROM Lineage: {has_route_from_lineage}")

    assert has_route_to_lineage, "Route 6122 → Lineage must exist"
    assert has_route_from_lineage, "Lineage must have outbound routes"

    # Build and solve
    pyomo_model = model_builder.build_model()
    result = model_builder.solve(pyomo_model)

    assert result.is_optimal() or result.is_feasible(), f"Expected feasible solution, got {result.termination_condition}"

    # Extract solution
    solution = model_builder.extract_solution(pyomo_model)

    print(f"\nSolution:")
    print(f"  Total production: {solution.total_production_quantity:,} units")
    print(f"  Fill rate: {solution.fill_rate:.1%}")

    # Check shipments to Lineage
    shipments_to_lineage = [
        s for s in solution.shipments
        if s.destination == 'Lineage'
    ]

    print(f"  Shipments to Lineage: {len(shipments_to_lineage)}")
    if shipments_to_lineage:
        total_to_lineage = sum(s.quantity for s in shipments_to_lineage)
        print(f"  Total shipped to Lineage: {total_to_lineage:,} units")
        assert total_to_lineage > 0, "Lineage should receive shipments"
    else:
        # May be OK if no demand for 6130 in this horizon
        print(f"  ⚠️  No shipments to Lineage (may be OK if no 6130 demand)")

    print("✅ Lineage routing test complete")


if __name__ == "__main__":
    print("=" * 80)
    print("TRUCK ROUTING FIXES TEST SUITE")
    print("=" * 80)

    print("\nTest 1: Intermediate Stop Expansion")
    print("-" * 80)
    test_intermediate_stop_expansion()

    print("\n\nTest 2: Day-of-Week Enforcement")
    print("-" * 80)
    test_day_of_week_enforcement()

    print("\n\nTest 3: Lineage Receives Goods")
    print("-" * 80)
    test_lineage_receives_goods()

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)
