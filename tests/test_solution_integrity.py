"""
Solution Integrity Validation - Catch Result Issues Before UI

Comprehensive validation of optimization solution to catch issues like:
- Dates outside planning horizon
- Negative values
- Missing required data
- Inconsistent totals
- Invalid assignments
"""

import pytest
from datetime import date


def validate_production_batches(solution, planning_start, planning_end):
    """Validate production batch data integrity."""
    issues = []

    for batch in solution.production_batches:
        # Check date in range
        if batch.date < planning_start:
            issues.append(f"Production BEFORE planning start: {batch.date} < {planning_start}")

        if batch.date > planning_end:
            issues.append(f"Production AFTER planning end: {batch.date} > {planning_end}")

        # Check quantity positive
        if batch.quantity < 0:
            issues.append(f"Negative production quantity: {batch.quantity}")

        # Check quantity not absurdly large
        if batch.quantity > 1000000:
            issues.append(f"Suspiciously large batch: {batch.quantity:,.0f}")

    return issues


def validate_shipments(solution, planning_start, planning_end):
    """Validate shipment data integrity."""
    issues = []

    for ship in solution.shipments:
        # Check departure date
        if ship.departure_date < planning_start:
            issues.append(f"Shipment departs BEFORE planning: {ship.departure_date}")

        if ship.departure_date > planning_end:
            issues.append(f"Shipment departs AFTER planning: {ship.departure_date}")

        # Check delivery date (if present)
        if hasattr(ship, 'delivery_date') and ship.delivery_date:
            # Delivery can be after planning end (in-transit at end)
            if ship.delivery_date < ship.departure_date:
                issues.append(f"Delivery before departure: {ship.delivery_date} < {ship.departure_date}")

        # Check quantity
        if ship.quantity < 0:
            issues.append(f"Negative shipment: {ship.quantity}")

        if ship.quantity > 100000:
            issues.append(f"Suspiciously large shipment: {ship.quantity:,.0f}")

    return issues


def validate_inventory_state(solution, planning_start, planning_end):
    """Validate inventory state data."""
    issues = []

    if not hasattr(solution, 'inventory_state') or not solution.inventory_state:
        # OK if not present (aggregate model)
        return issues

    for date, state_dict in solution.inventory_state.items():
        # Check date in range
        if date < planning_start:
            issues.append(f"Inventory date BEFORE planning: {date}")

        if date > planning_end:
            issues.append(f"Inventory date AFTER planning: {date}")

        # Check for negative inventory
        for node_id, inv_by_prod in state_dict.items():
            for prod_id, inv in inv_by_prod.items():
                if inv.quantity < 0:
                    issues.append(f"Negative inventory: {node_id}/{prod_id}/{date}: {inv.quantity}")

    return issues


def validate_cost_totals(solution):
    """Validate cost breakdown adds up correctly."""
    issues = []

    # Extract individual costs
    production_cost = solution.costs.production.total if hasattr(solution.costs, 'production') else 0
    labor_cost = solution.costs.labor.total if hasattr(solution.costs, 'labor') else 0
    transport_cost = solution.costs.transport.total if hasattr(solution.costs, 'transport') else 0
    holding_cost = solution.costs.holding.total if hasattr(solution.costs, 'holding') else 0
    waste_cost = solution.costs.waste.total if hasattr(solution.costs, 'waste') else 0

    # Sum components
    sum_of_parts = production_cost + labor_cost + transport_cost + holding_cost + waste_cost

    # Should approximately equal total (allowing for rounding and other costs)
    if hasattr(solution, 'objective_value'):
        total = solution.objective_value

        # Allow 10% variance for residual costs
        if abs(sum_of_parts - total) > total * 0.10:
            issues.append(
                f"Cost breakdown doesn't sum to total: "
                f"${sum_of_parts:,.2f} vs ${total:,.2f} "
                f"(diff: ${abs(sum_of_parts - total):,.2f})"
            )

    # Check for negative costs
    if production_cost < 0:
        issues.append(f"Negative production cost: ${production_cost:,.2f}")

    if labor_cost < 0:
        issues.append(f"Negative labor cost: ${labor_cost:,.2f}")

    return issues


def test_4week_solution_integrity():
    """Validate 4-week solution has no integrity issues."""
    from src.parsers.multi_file_parser import MultiFileParser
    from src.optimization.sliding_window_model import SlidingWindowModel
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
    from tests.conftest import create_test_products
    from datetime import timedelta

    # Load data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

    from src.parsers.inventory_parser import InventoryParser
    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory = inv_parser.parse()

    planning_start = inventory.snapshot_date
    planning_end = planning_start + timedelta(weeks=4)

    # Build and solve
    from src.models.location import LocationType
    mfg = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(mfg, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks, mfg.id)

    products = create_test_products(
        sorted(set(e.product_id for e in forecast.entries
                  if planning_start <= e.forecast_date <= planning_end))
    )

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_cal,
        cost_structure=costs,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=unified_trucks,
        initial_inventory=inventory.to_optimization_dict(),
        inventory_snapshot_date=inventory.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.02)
    solution = model.get_solution()

    # Validate
    all_issues = []

    all_issues.extend(validate_production_batches(solution, planning_start, planning_end))
    all_issues.extend(validate_shipments(solution, planning_start, planning_end))
    all_issues.extend(validate_inventory_state(solution, planning_start, planning_end))
    all_issues.extend(validate_cost_totals(solution))

    if all_issues:
        pytest.fail(
            f"Found {len(all_issues)} solution integrity issues:\n" +
            "\n".join(all_issues[:20])
        )

    print(f"✅ Solution integrity validated: {len(solution.production_batches)} batches, {len(solution.shipments)} shipments")


def test_initial_inventory_production_dates():
    """Regression test for Bug #1: Initial inventory batches must have past production dates.

    Bug discovered 2025-11-05: Initial inventory batches were showing production_date = planning_start,
    causing "future production dates" in Daily Inventory Snapshot.

    Root cause: sliding_window_model.py line 3491 used self.start_date instead of estimating past date.
    Fix: Calculate estimated_production_date = snapshot_date - estimated_age.

    NOTE: This test uses test_ui_workflow to avoid inventory alias resolution complexity.
    """
    # Use existing UI workflow test which handles inventory aliases correctly
    from tests.test_integration_ui_workflow import load_test_data
    from datetime import timedelta

    data_files = {
        'forecast': 'data/examples/Gluten Free Forecast - Latest.xlsm',
        'network': 'data/examples/Network_Config.xlsx',
        'inventory': 'data/examples/inventory_latest.XLSX'
    }

    parsed_data = load_test_data(data_files)

    planning_start = parsed_data['inventory_snapshot_date']
    planning_end = planning_start + timedelta(weeks=1)  # Shorter for speed

    from tests.conftest import create_test_products

    products = create_test_products(
        sorted(set(e.product_id for e in parsed_data['forecast'].entries
                  if planning_start <= e.forecast_date <= planning_end))
    )

    from src.optimization.sliding_window_model import SlidingWindowModel

    model = SlidingWindowModel(
        nodes=parsed_data['nodes'],
        routes=parsed_data['unified_routes'],
        forecast=parsed_data['forecast'],
        products=products,
        labor_calendar=parsed_data['labor_calendar'],
        cost_structure=parsed_data['cost_structure'],
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=parsed_data['unified_truck_schedules'],
        initial_inventory=parsed_data['initial_inventory'].to_optimization_dict() if parsed_data['initial_inventory'] else None,
        inventory_snapshot_date=parsed_data['inventory_snapshot_date'],
        allow_shortages=True,
        use_pallet_tracking=False,  # Faster
        product_alias_resolver=parsed_data.get('product_aliases')
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.02)
    solution = model.get_solution()

    # REGRESSION TEST: All initial inventory batches must have production_date < planning_start
    init_batches = [b for b in (solution.fefo_batch_objects or []) if b.id.startswith('INIT')]

    assert len(init_batches) > 0, "Should have initial inventory batches"

    future_count = 0
    for batch in init_batches:
        if batch.production_date >= planning_start:
            future_count += 1
            print(f"❌ REGRESSION: Initial batch {batch.id[:40]} has production_date={batch.production_date} >= planning_start={planning_start}")

    assert future_count == 0, f"Bug #1 regression: {future_count}/{len(init_batches)} initial batches have future production dates"

    print(f"✅ Bug #1 regression test PASSED: All {len(init_batches)} initial inventory batches have past production dates")


def test_weekend_labor_minimum_payment():
    """Regression test for Bug #3: Weekend production must use 0h or ≥4h (minimum payment).

    Bug discovered 2025-11-05: Sunday Oct 26 showed 1.78h labor with 387 units production,
    violating the 4-hour minimum payment rule for weekend labor.

    Root cause: any_production_upper_link_con was too weak (allowed any_production=0 while production>0).
    Fix: Reversed Big-M constraint to: sum(product_produced) <= N * any_production.
    """
    from src.parsers.multi_file_parser import MultiFileParser
    from src.optimization.sliding_window_model import SlidingWindowModel
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
    from tests.conftest import create_test_products
    from datetime import timedelta
    from src.parsers.inventory_parser import InventoryParser
    from src.models.location import LocationType

    # Load data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()
    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory = inv_parser.parse()

    planning_start = inventory.snapshot_date
    planning_end = planning_start + timedelta(weeks=4)

    # Build model
    mfg = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(mfg, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks, mfg.id)
    products = create_test_products(
        sorted(set(e.product_id for e in forecast.entries
                  if planning_start <= e.forecast_date <= planning_end))
    )

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_cal,
        cost_structure=costs,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=unified_trucks,
        initial_inventory=inventory.to_optimization_dict(),
        inventory_snapshot_date=inventory.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.02)
    solution = model.get_solution()

    # REGRESSION TEST: Weekend production must have 0h or ≥4h labor
    production_by_date = {}
    for batch in solution.production_batches:
        production_by_date[batch.date] = production_by_date.get(batch.date, 0) + batch.quantity

    violations = []
    for date, labor_info in (solution.labor_hours_by_date or {}).items():
        day_of_week = date.strftime('%A')

        if day_of_week not in ['Saturday', 'Sunday']:
            continue

        hours = labor_info.paid if hasattr(labor_info, 'paid') else labor_info.used
        production = production_by_date.get(date, 0)

        # Check: If production > 0, hours must be >= 4.0
        if production > 0 and hours < 3.9:
            violations.append((date, day_of_week, hours, production))
            print(f"❌ REGRESSION: {day_of_week} {date}: {hours:.2f}h with {production:.0f} units (< 4h minimum)")

    assert len(violations) == 0, f"Bug #3 regression: {len(violations)} weekend violations (production with <4h labor)"

    print(f"✅ Bug #3 regression test PASSED: No weekend labor minimum violations")


if __name__ == "__main__":
    print("Running solution integrity validation...")
    test_4week_solution_integrity()
    print("✅ Basic validations passed!")

    print("\nRunning Bug #1 regression test...")
    test_initial_inventory_production_dates()

    print("\nRunning Bug #3 regression test...")
    test_weekend_labor_minimum_payment()

    print("\n✅ ALL TESTS PASSED!")
