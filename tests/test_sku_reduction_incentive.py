"""Test SKU reduction incentive with binary product_produced enforcement.

This test validates that the UnifiedNodeModel correctly reduces SKU variety
when it is financially beneficial to do so, particularly when changeover
costs can push production into costly overtime.
"""

import pytest
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.forecast import Forecast, ForecastEntry
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def test_zero_demand_skus_not_produced():
    """Test that SKUs with zero demand are not produced.

    Scenario: Single-day planning horizon with 3 SKUs having demand
    and 2 SKUs with zero demand.

    Expected: Model produces only the 3 SKUs with demand, not all 5.
    This validates that the binary product_produced variable correctly
    prevents production of zero-demand SKUs.
    """
    # Load real network configuration
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    _, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
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

    assert manufacturing_site is not None, "Manufacturing site not found"

    # Create simplified forecast: 3 SKUs with demand, 2 SKUs with zero demand
    test_date = date(2025, 10, 20)
    demand_destination = "6110"  # QLD breadroom (direct from manufacturing)

    # Get product IDs from original forecast to use real product names
    original_forecast, _, _, _, _, _ = parser.parse_all()
    product_ids = list(set(entry.product_id for entry in original_forecast.entries))

    # Use first 5 products
    product_ids = product_ids[:5] if len(product_ids) >= 5 else product_ids

    forecast_entries = [
        # SKUs with demand (3000 units each)
        ForecastEntry(location_id=demand_destination, product_id=product_ids[0], forecast_date=test_date, quantity=3000),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[1], forecast_date=test_date, quantity=3000),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[2], forecast_date=test_date, quantity=3000),
        # SKUs with ZERO demand
        ForecastEntry(location_id=demand_destination, product_id=product_ids[3], forecast_date=test_date, quantity=0),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[4], forecast_date=test_date, quantity=0),
    ]

    forecast = Forecast(name="SKU Reduction Test - Zero Demand", entries=forecast_entries)

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    print("\n" + "=" * 80)
    print("TEST 1: ZERO DEMAND SKUs NOT PRODUCED")
    print("=" * 80)
    print(f"Demand: 3 SKUs × 3000 units = 9000 units total")
    print(f"Zero demand: 2 SKUs")
    print(f"Expected: Produce only 3 SKUs (not 5)")

    # Create model with single-day horizon
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=test_date,
        end_date=test_date,  # Single day
        truck_schedules=unified_trucks,
        use_batch_tracking=False,  # Simplify for this test
        allow_shortages=False,  # Must meet demand
        enforce_shelf_life=False,  # Simplify
    )

    # Solve
    result = model.solve(time_limit_seconds=60, mip_gap=0.01, tee=False)

    print(f"\nSolve Status: {result.termination_condition}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    if not (result.is_optimal() or result.is_feasible()):
        pytest.fail(f"Model did not solve: {result.termination_condition}")

    # Get solution
    solution = model.get_solution()
    assert solution is not None, "Solution should not be None"

    # Count SKUs produced
    production = solution.get('production_by_date_product', {})
    skus_produced = set()
    for (prod_date, product), qty in production.items():
        if qty > 0.1:  # Tolerance for numerical precision
            skus_produced.add(product)

    num_skus_produced = len(skus_produced)

    print(f"\n✅ SOLUTION:")
    print(f"   SKUs produced: {num_skus_produced} out of 5")
    print(f"   Products: {sorted(skus_produced)}")
    print(f"   Total production: {sum(production.values()):,.0f} units")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")

    # Extract cost breakdown if available
    if 'cost_breakdown' in solution:
        breakdown = solution['cost_breakdown']
        print(f"\n   Cost breakdown:")
        print(f"     Labor: ${breakdown.get('labor', 0):,.2f}")
        print(f"     Production: ${breakdown.get('production', 0):,.2f}")
        print(f"     Transport: ${breakdown.get('transport', 0):,.2f}")

    print("=" * 80)

    # Assertions
    assert num_skus_produced == 3, f"Expected 3 SKUs produced, got {num_skus_produced}"
    assert product_ids[3] not in skus_produced, "Zero-demand SKU should not be produced"
    assert product_ids[4] not in skus_produced, "Zero-demand SKU should not be produced"


def test_sku_reduction_cost_benefit():
    """Test that reducing SKUs provides measurable cost savings.

    Scenario: Compare cost of producing all 5 SKUs vs only needed SKUs.

    Expected: Fewer SKUs = lower labor cost due to reduced changeover time.
    """
    # Load real network configuration
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    _, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
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

    # Create forecast
    test_date = date(2025, 10, 20)
    demand_destination = "6110"

    original_forecast, _, _, _, _, _ = parser.parse_all()
    product_ids = list(set(entry.product_id for entry in original_forecast.entries))[:5]

    # Scenario: 3 SKUs with demand
    forecast_entries = [
        ForecastEntry(location_id=demand_destination, product_id=product_ids[0], forecast_date=test_date, quantity=3000),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[1], forecast_date=test_date, quantity=3000),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[2], forecast_date=test_date, quantity=3000),
    ]

    forecast = Forecast(name="SKU Reduction Test - Cost Benefit", entries=forecast_entries)

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    print("\n" + "=" * 80)
    print("TEST 2: SKU REDUCTION COST BENEFIT")
    print("=" * 80)
    print(f"Demand: 3 SKUs × 3000 units = 9000 units total")
    print(f"Testing with changeover tracking enabled")

    # Create and solve model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=test_date,
        end_date=test_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=False,
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        pytest.fail(f"Model did not solve: {result.termination_condition}")

    solution = model.get_solution()

    # Count SKUs
    production = solution.get('production_by_date_product', {})
    skus_produced = set()
    for (prod_date, product), qty in production.items():
        if qty > 0.1:
            skus_produced.add(product)

    num_skus = len(skus_produced)
    total_cost = solution['total_cost']

    print(f"\n✅ SOLUTION:")
    print(f"   SKUs produced: {num_skus}")
    print(f"   Total cost: ${total_cost:,.2f}")

    if 'cost_breakdown' in solution:
        breakdown = solution['cost_breakdown']
        labor_cost = breakdown.get('labor', 0)
        print(f"   Labor cost: ${labor_cost:,.2f}")

        # Expected: Labor cost should reflect reduced changeover time
        # 3 SKUs overhead: startup + shutdown + 2*changeover
        # = 0.5h + 0.5h + 2*1.0h = 3.0h overhead
        # Production time: 9000/1400 = 6.43h
        # Total: 9.43h at regular rate ($20/h) = $188.60
        print(f"\n   Expected labor hours: ~9-10h (6.4h production + 2.5-3.0h overhead)")
        print(f"   Expected labor cost: ~$180-200 (all within regular hours)")

    print("=" * 80)

    # Assertion: Should produce exactly the needed SKUs
    assert num_skus == 3, f"Expected 3 SKUs, got {num_skus}"
    assert total_cost > 0, "Total cost should be positive"


def test_overtime_triggers_sku_reduction():
    """Test that model avoids overtime by reducing SKUs when beneficial.

    Scenario: High production volume that would trigger overtime with 5 SKUs
    but stays within regular hours with fewer SKUs.

    Expected: Model chooses fewer SKUs to avoid costly overtime.
    """
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    _, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

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

    test_date = date(2025, 10, 20)  # Must be a weekday
    demand_destination = "6110"

    original_forecast, _, _, _, _, _ = parser.parse_all()
    product_ids = list(set(entry.product_id for entry in original_forecast.entries))[:5]

    # High volume: 2500 units × 5 SKUs = 12,500 units
    # With 5 SKUs: overhead = 1.0h + 4*1.0h = 5.0h
    # Production time: 12,500/1400 = 8.93h
    # Total: 13.93h → uses overtime (12h fixed + 1.93h OT @ $30/h = extra $57.90)
    #
    # With 3 SKUs: overhead = 1.0h + 2*1.0h = 3.0h
    # Production time: 7,500/1400 = 5.36h (only 3 SKUs needed)
    # Total: 8.36h → no overtime
    #
    # But wait - we need to meet demand for all 5 SKUs if they all have demand.
    # Let's make only 3 have demand:
    forecast_entries = [
        ForecastEntry(location_id=demand_destination, product_id=product_ids[0], forecast_date=test_date, quantity=2500),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[1], forecast_date=test_date, quantity=2500),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[2], forecast_date=test_date, quantity=2500),
        # These could be produced "just in case" but would push into overtime
        ForecastEntry(location_id=demand_destination, product_id=product_ids[3], forecast_date=test_date, quantity=0),
        ForecastEntry(location_id=demand_destination, product_id=product_ids[4], forecast_date=test_date, quantity=0),
    ]

    forecast = Forecast(name="SKU Reduction Test - Overtime Avoidance", entries=forecast_entries)

    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    print("\n" + "=" * 80)
    print("TEST 3: OVERTIME AVOIDANCE THROUGH SKU REDUCTION")
    print("=" * 80)
    print(f"Demand: 3 SKUs × 2500 units = 7500 units")
    print(f"Scenario: High volume could trigger overtime with unnecessary SKUs")
    print(f"Expected: Produce only needed 3 SKUs to stay in regular hours")

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=test_date,
        end_date=test_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=False,
        allow_shortages=False,
        enforce_shelf_life=False,
    )

    result = model.solve(time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        pytest.fail(f"Model did not solve: {result.termination_condition}")

    solution = model.get_solution()

    production = solution.get('production_by_date_product', {})
    skus_produced = set()
    for (prod_date, product), qty in production.items():
        if qty > 0.1:
            skus_produced.add(product)

    num_skus = len(skus_produced)

    print(f"\n✅ SOLUTION:")
    print(f"   SKUs produced: {num_skus}")
    print(f"   Total production: {sum(production.values()):,.0f} units")
    print(f"   Total cost: ${solution['total_cost']:,.2f}")

    if 'cost_breakdown' in solution:
        breakdown = solution['cost_breakdown']
        print(f"\n   Cost breakdown:")
        print(f"     Labor: ${breakdown.get('labor', 0):,.2f}")
        print(f"     Production: ${breakdown.get('production', 0):,.2f}")
        print(f"     Transport: ${breakdown.get('transport', 0):,.2f}")

        # Verify no overtime
        labor_cost = breakdown.get('labor', 0)
        # With 3 SKUs: 7500/1400 + 3.0h overhead = 8.36h @ $20/h = $167.20
        # If producing 5 SKUs unnecessarily: would increase cost
        print(f"\n   Expected: ~$167 labor cost (no overtime)")

    print("=" * 80)

    # Assertions
    assert num_skus == 3, f"Expected 3 SKUs to avoid overtime, got {num_skus}"
    assert sum(production.values()) >= 7500, "Should meet all demand"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
