"""
Integration tests for validated data architecture.

Tests that the validation layer correctly loads data and the model
produces expected results with validated data.
"""

import pytest
from pathlib import Path
from datetime import timedelta
import time

from src.validation.data_coordinator import load_validated_data, ValidationError


@pytest.fixture
def data_files():
    """Paths to test data files."""
    base_path = Path("data/examples")
    return {
        'forecast': base_path / "Gluten Free Forecast - Latest.xlsm",
        'network': base_path / "Network_Config.xlsx",
        'inventory': base_path / "inventory_latest.XLSX"
    }


def test_data_coordinator_loads_successfully(data_files):
    """Test that data coordinator loads and validates data successfully."""

    # Load and validate data
    validated_data = load_validated_data(
        forecast_file=data_files['forecast'],
        network_file=data_files['network'],
        inventory_file=data_files['inventory'],
        planning_weeks=4
    )

    # Verify data structure
    assert validated_data is not None
    assert len(validated_data.products) > 0, "Should have products"
    assert len(validated_data.nodes) > 0, "Should have nodes"
    assert len(validated_data.demand_entries) > 0, "Should have demand"

    # Verify dates
    assert validated_data.planning_start_date < validated_data.planning_end_date
    horizon_days = (validated_data.planning_end_date - validated_data.planning_start_date).days
    assert 20 <= horizon_days <= 35, f"4-week horizon should be 28-35 days, got {horizon_days}"

    # Verify inventory
    assert len(validated_data.inventory_entries) > 0, "Should have inventory"

    # Verify product ID consistency (THE KEY FIX!)
    demand_products = {e.product_id for e in validated_data.demand_entries}
    inventory_products = {e.product_id for e in validated_data.inventory_entries}
    registered_products = {p.id for p in validated_data.products}

    # All demand products should be in registered products
    assert demand_products <= registered_products, \
        f"Demand has unregistered products: {demand_products - registered_products}"

    # All inventory products should be in registered products
    assert inventory_products <= registered_products, \
        f"Inventory has unregistered products: {inventory_products - registered_products}"

    # Should have some products with both demand and inventory
    common_products = demand_products & inventory_products
    assert len(common_products) > 0, \
        "Should have products with both demand and inventory (product ID resolution working)"

    print(f"\n✓ Validation successful:")
    print(f"  Products: {len(validated_data.products)}")
    print(f"  Nodes: {len(validated_data.nodes)}")
    print(f"  Demand entries: {len(validated_data.demand_entries)}")
    print(f"  Inventory entries: {len(validated_data.inventory_entries)}")
    print(f"  Products with demand & inventory: {len(common_products)}")


def test_sliding_window_with_validated_data(data_files):
    """Test sliding window model with validated data - should produce > 0."""

    from src.optimization.sliding_window_model import SlidingWindowModel
    from src.models.product import Product

    print("\n" + "="*80)
    print("TEST: SLIDING WINDOW MODEL WITH VALIDATED DATA")
    print("="*80)

    # Load and validate data
    print("\n1. Loading and validating data...")
    validated_data = load_validated_data(
        forecast_file=data_files['forecast'],
        network_file=data_files['network'],
        inventory_file=data_files['inventory'],
        planning_weeks=4
    )

    print(f"✓ Data validated successfully")
    print(validated_data.summary())

    # Convert to model format
    print("\n2. Creating model...")

    # Convert ValidatedPlanningData products to Product objects
    products_dict = {}
    for prod in validated_data.products:
        products_dict[prod.id] = Product(
            id=prod.id,
            sku=prod.sku or prod.id,
            name=prod.name,
            units_per_mix=415  # Default
        )

    # Create forecast from validated demand (needed before conversion)
    from src.models.forecast import Forecast, ForecastEntry
    forecast_entries = [
        ForecastEntry(
            location_id=entry.node_id,
            product_id=entry.product_id,
            forecast_date=entry.demand_date,
            quantity=entry.quantity
        )
        for entry in validated_data.demand_entries
    ]
    forecast = Forecast(name="Validated Forecast", entries=forecast_entries)

    # Load network components using MultiFileParser (handles all format conversions)
    # This is the exact pattern from the working test - reuse proven infrastructure
    print("   Loading network components via MultiFileParser...")
    from src.parsers.multi_file_parser import MultiFileParser

    parser = MultiFileParser(
        forecast_file=data_files['forecast'],
        network_file=data_files['network'],
        inventory_file=data_files['inventory']
    )

    # Parse all components
    _, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manufacturing_site = manufacturing_locations[0]

    # Convert to unified format (exact pattern from working test)
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes_legacy)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Build model
    model_start = time.time()

    model = SlidingWindowModel(
        nodes=nodes,  # Pass as list, model will convert to dict internally
        routes=unified_routes,  # Use converted unified routes
        forecast=forecast,
        products=products_dict,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=validated_data.planning_start_date,
        end_date=validated_data.planning_end_date,
        truck_schedules=unified_truck_schedules,  # Use converted unified truck schedules
        initial_inventory=validated_data.get_inventory_dict(),  # VALIDATED!
        inventory_snapshot_date=validated_data.inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    model_build_time = time.time() - model_start
    print(f"✓ Model built in {model_build_time:.2f}s")

    # Solve
    print("\n3. Solving model...")
    solve_start = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.02,
        use_aggressive_heuristics=False,
        tee=False
    )

    solve_time = time.time() - solve_start

    print(f"\n✓ SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s")
    print(f"   Objective: ${result.objective_value:,.2f}")

    # Get the actual solution (not just solver result!)
    solution = model.get_solution()
    assert solution is not None, "Solution should not be None"

    # Extract metrics from OptimizationSolution
    total_production = solution.total_production
    total_shortage = solution.total_shortage_units
    demand_in_horizon = sum(entry.quantity for entry in validated_data.demand_entries)
    fill_rate = ((demand_in_horizon - total_shortage) / demand_in_horizon * 100) if demand_in_horizon > 0 else 0

    print(f"\n4. SOLUTION QUALITY:")
    print(f"   Total demand: {demand_in_horizon:,.0f} units")
    print(f"   Total production: {total_production:,.0f} units")
    print(f"   Total shortage: {total_shortage:,.0f} units")
    print(f"   Fill rate: {fill_rate:.1f}%")
    print(f"   Initial inventory: {sum(e.quantity for e in validated_data.inventory_entries):,.0f} units")

    # CRITICAL ASSERTIONS - These verify the bug is fixed!
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected optimal/feasible solution, got {result.termination_condition}"

    assert total_production > 0, \
        f"ZERO PRODUCTION BUG STILL PRESENT! Production should be > 0, got {total_production}"

    assert fill_rate >= 50, \
        f"Fill rate too low: {fill_rate:.1f}% (expected >= 50%)"

    print(f"\n" + "="*80)
    print("✓ TEST PASSED: Production > 0, zero production bug FIXED!")
    print("="*80)


def test_validation_catches_product_id_mismatch():
    """Test that validation catches product ID mismatches."""

    from src.validation.planning_data_schema import (
        ValidatedPlanningData,
        ProductID,
        NodeID,
        DemandEntry,
        InventoryEntry
    )
    from datetime import date

    # Create scenario: inventory has product not in products list
    products = [ProductID(id="PROD_A", name="Product A", sku="PROD_A")]
    nodes = [NodeID(id="NODE1", name="Node 1")]

    demand_entries = [
        DemandEntry(
            node_id="NODE1",
            product_id="PROD_A",
            demand_date=date(2025, 11, 3),
            quantity=100.0
        )
    ]

    inventory_entries = [
        InventoryEntry(
            node_id="NODE1",
            product_id="PROD_B",  # NOT in products list!
            state="ambient",
            quantity=50.0
        )
    ]

    # Should raise ValidationError
    with pytest.raises(Exception) as exc_info:
        ValidatedPlanningData(
            products=products,
            nodes=nodes,
            demand_entries=demand_entries,
            inventory_entries=inventory_entries,
            planning_start_date=date(2025, 11, 3),
            planning_end_date=date(2025, 11, 10),
            data_source="test"
        )

    # Verify error message is helpful
    error_msg = str(exc_info.value)
    assert "PROD_B" in error_msg, "Error should mention the problematic product"
    assert "inventory" in error_msg.lower(), "Error should mention inventory"

    print(f"\n✓ Validation correctly caught product ID mismatch:")
    print(f"  Error: {error_msg[:200]}...")


def test_validation_catches_invalid_node_reference():
    """Test that validation catches invalid node references in demand."""

    from src.validation.planning_data_schema import (
        ValidatedPlanningData,
        ProductID,
        NodeID,
        DemandEntry
    )
    from datetime import date

    products = [ProductID(id="PROD_A", name="Product A", sku="PROD_A")]
    nodes = [NodeID(id="NODE1", name="Node 1")]

    # Demand references non-existent node
    demand_entries = [
        DemandEntry(
            node_id="NODE_INVALID",  # Doesn't exist!
            product_id="PROD_A",
            demand_date=date(2025, 11, 3),
            quantity=100.0
        )
    ]

    # Should raise ValidationError
    with pytest.raises(Exception) as exc_info:
        ValidatedPlanningData(
            products=products,
            nodes=nodes,
            demand_entries=demand_entries,
            inventory_entries=[],
            planning_start_date=date(2025, 11, 3),
            planning_end_date=date(2025, 11, 10),
            data_source="test"
        )

    error_msg = str(exc_info.value)
    assert "NODE_INVALID" in error_msg or "unknown node" in error_msg.lower()

    print(f"\n✓ Validation correctly caught invalid node reference")
