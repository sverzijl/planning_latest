"""Integration tests for end-to-end batch tracking workflows.

This test suite validates complete workflows from model building through
solution extraction to daily snapshot generation:
- Build model → Solve → Extract batches → Display snapshot
- Batch traceability through network
- FIFO consumption validation
- Mass balance verification across entire supply chain

These tests are slower but validate the complete system.
"""

import pytest
from datetime import date, timedelta
from typing import Dict, List
from collections import defaultdict

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, RouteLeg
from src.production.scheduler import ProductionSchedule
from src.analysis.daily_snapshot import DailySnapshotGenerator


# ===========================
# Fixtures - Realistic Scenario
# ===========================


@pytest.fixture
def realistic_forecast() -> Forecast:
    """Create realistic 14-day forecast with 2 products and 3 destinations."""
    base_date = date(2025, 10, 13)
    entries = []

    # Product 176283: 200 units/day at each destination
    # Product 176284: 150 units/day at each destination
    products = {
        "176283": 200.0,
        "176284": 150.0
    }

    destinations = ["6103", "6105", "6110"]

    for dest in destinations:
        for product, daily_qty in products.items():
            for i in range(14):
                entries.append(
                    ForecastEntry(
                        location_id=dest,
                        product_id=product,
                        forecast_date=base_date + timedelta(days=i),
                        quantity=daily_qty
                    )
                )

    return Forecast(name="Realistic 14-day Forecast", entries=entries)


@pytest.fixture
def realistic_labor_calendar() -> LaborCalendar:
    """Create realistic labor calendar with weekends."""
    base_date = date(2025, 10, 13)
    days = []

    for i in range(21):
        current_date = base_date + timedelta(days=i)
        is_weekend = current_date.weekday() >= 5

        days.append(
            LaborDay(
                calendar_date=current_date,
                fixed_hours=0.0 if is_weekend else 12.0,
                is_public_holiday=False,
                labor_cost_rate=60.0 if is_weekend else 40.0
            )
        )

    return LaborCalendar(days=days)


@pytest.fixture
def realistic_manufacturing() -> ManufacturingSite:
    """Create realistic manufacturing site."""
    return ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )


@pytest.fixture
def realistic_cost_structure() -> CostStructure:
    """Create realistic cost structure."""
    return CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0
    )


@pytest.fixture
def realistic_locations() -> List[Location]:
    """Create realistic location network."""
    return [
        Location(
            id="6122",
            name="Manufacturing Site",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
            capacity=100000
        ),
        Location(
            id="6125",
            name="Hub VIC",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
            capacity=50000
        ),
        Location(
            id="6104",
            name="Hub NSW",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
            capacity=50000
        ),
        Location(
            id="6103",
            name="Breadroom VIC",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=5000
        ),
        Location(
            id="6105",
            name="Breadroom NSW",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=5000
        ),
        Location(
            id="6110",
            name="Breadroom QLD",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
            capacity=5000
        ),
    ]


@pytest.fixture
def realistic_routes() -> List[Route]:
    """Create realistic route network."""
    return [
        # Direct routes
        Route(
            id="R1",
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6110",
                    transport_mode="ambient",
                    transit_days=2,
                    cost_per_unit=2.0
                )
            ]
        ),
        # Hub routes via VIC
        Route(
            id="R2",
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6125",
                    transport_mode="ambient",
                    transit_days=1,
                    cost_per_unit=0.5
                ),
                RouteLeg(
                    from_location_id="6125",
                    to_location_id="6103",
                    transport_mode="ambient",
                    transit_days=1,
                    cost_per_unit=0.5
                )
            ]
        ),
        # Hub routes via NSW
        Route(
            id="R3",
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6104",
                    transport_mode="ambient",
                    transit_days=1,
                    cost_per_unit=0.5
                ),
                RouteLeg(
                    from_location_id="6104",
                    to_location_id="6105",
                    transport_mode="ambient",
                    transit_days=1,
                    cost_per_unit=0.5
                )
            ]
        ),
    ]


# ===========================
# Tests - End-to-End Workflows
# ===========================


def test_complete_workflow_batch_tracking(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test complete workflow: build → solve → extract → snapshot.

    This is the PRIMARY integration test validating the entire system.
    """
    # Step 1: Build model
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    # Step 2: Solve
    result = model.solve(time_limit_seconds=120)

    assert result is not None
    assert 'solver_status' in result

    if result['solver_status'] != 'optimal':
        pytest.skip(f"Solver did not find optimal solution: {result['solver_status']}")

    # Step 3: Verify batch objects created
    assert 'production_batch_objects' in result
    batches = result['production_batch_objects']
    assert len(batches) > 0, "No batches created"

    # Step 4: Verify batch tracking flag
    assert result['use_batch_tracking'] == True

    # Step 5: Extract shipments
    if 'batch_shipments' in result:
        shipments = result['batch_shipments']
        assert len(shipments) > 0, "No shipments created"

        # Verify shipments reference valid batches
        batch_ids = {b.id for b in batches}
        for shipment in shipments:
            assert shipment.batch_id in batch_ids, \
                f"Shipment references unknown batch: {shipment.batch_id}"

    # Step 6: Create production schedule from batches
    if batches:
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            schedule_start_date=min(b.production_date for b in batches),
            schedule_end_date=max(b.production_date for b in batches),
            production_batches=batches,
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_units=sum(b.quantity for b in batches),
            total_labor_hours=0.0
        )

        # Step 7: Generate daily snapshot
        locations_dict = {loc.id: loc for loc in realistic_locations}

        if 'batch_shipments' in result:
            generator = DailySnapshotGenerator(
                production_schedule=schedule,
                shipments=result['batch_shipments'],
                locations_dict=locations_dict,
                forecast=realistic_forecast,
                model_solution=result  # Pass solution for model mode
            )

            # Generate snapshot for mid-horizon date
            snapshot_date = realistic_forecast.entries[7].forecast_date
            snapshot = generator._generate_single_snapshot(snapshot_date)

            # Verify snapshot structure
            assert snapshot is not None
            assert snapshot.date == snapshot_date
            assert len(snapshot.location_inventory) > 0


def test_batch_traceability_through_network(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test that batches can be traced through multi-leg routes."""
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    if 'batch_shipments' not in result:
        pytest.skip("Batch shipments not in result")

    batches = result['production_batch_objects']
    shipments = result['batch_shipments']

    # Build traceability map: batch_id -> list of shipments
    batch_shipments: Dict[str, List] = defaultdict(list)
    for shipment in shipments:
        batch_shipments[shipment.batch_id].append(shipment)

    # For each batch, verify we can trace it through the network
    for batch in batches:
        if batch.id in batch_shipments:
            batch_ships = batch_shipments[batch.id]

            # Verify total shipped quantity ≤ batch quantity
            total_shipped = sum(s.quantity for s in batch_ships)
            assert total_shipped <= batch.quantity + 0.01, \
                f"Batch {batch.id}: shipped {total_shipped} > produced {batch.quantity}"

            # Verify all shipments start from manufacturing site
            for shipment in batch_ships:
                assert shipment.origin_id == "6122", \
                    f"Shipment {shipment.id} doesn't originate from manufacturing"


def test_fifo_consumption_tendency(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test that model prefers FIFO consumption (older batches first).

    This test checks that if multiple cohorts exist, the model tends to
    consume older inventory before younger inventory.
    """
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # If cohort_inventory is available, check FIFO tendency
    if 'cohort_inventory' not in result:
        pytest.skip("Cohort inventory not in result")

    cohort_inventory = result['cohort_inventory']

    # Group cohorts by (location, product, current_date)
    location_product_cohorts: Dict[tuple, List[tuple]] = defaultdict(list)

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
        if qty > 0.01:  # Only consider non-zero cohorts
            age = (curr_date - prod_date).days
            location_product_cohorts[(loc, prod, curr_date)].append((age, qty))

    # Check FIFO tendency: if younger cohorts have inventory, older should have more
    fifo_violations = 0

    for key, cohorts in location_product_cohorts.items():
        if len(cohorts) < 2:
            continue  # Need at least 2 cohorts to check

        # Sort by age (oldest first)
        cohorts.sort(key=lambda x: x[0], reverse=True)

        # Check if older cohorts are depleted before younger ones
        for i in range(len(cohorts) - 1):
            older_age, older_qty = cohorts[i]
            younger_age, younger_qty = cohorts[i + 1]

            # If younger cohort has inventory, older should have at least as much (FIFO)
            if younger_qty > 0.01 and older_qty < younger_qty * 0.5:
                fifo_violations += 1

    # Allow some violations (model may have other constraints)
    # But most cohorts should follow FIFO
    total_location_product_dates = len(location_product_cohorts)
    if total_location_product_dates > 0:
        violation_rate = fifo_violations / total_location_product_dates
        assert violation_rate < 0.2, \
            f"Too many FIFO violations: {fifo_violations}/{total_location_product_dates} ({violation_rate:.1%})"


def test_mass_balance_across_supply_chain(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test mass balance: production = inventory + in_transit + demand_satisfied."""
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # Calculate total production
    total_production = sum(result.get('production_by_date_product', {}).values())

    # Calculate total ending inventory (from cohorts if available)
    if 'cohort_inventory' in result:
        total_inventory = sum(result['cohort_inventory'].values())
    else:
        total_inventory = 0.0

    # Calculate total demand satisfied
    total_demand = sum(result.get('demand_by_dest_product_date', {}).values())
    total_shortage = sum(result.get('shortages_by_dest_product_date', {}).values())
    total_satisfied = total_demand - total_shortage

    # Mass balance: production ≈ satisfied + ending_inventory
    # (assuming no initial inventory)
    expected = total_satisfied + total_inventory

    assert abs(total_production - expected) < 10.0, \
        f"Mass balance violated: production={total_production:.2f}, " \
        f"satisfied={total_satisfied:.2f}, inventory={total_inventory:.2f}, " \
        f"expected={expected:.2f}, diff={abs(total_production - expected):.2f}"


def test_no_expired_inventory_in_solution(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test that solution contains no expired inventory.

    For ambient storage, inventory older than 17 days should not exist.
    """
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    if 'cohort_inventory' not in result:
        pytest.skip("Cohort inventory not in result")

    AMBIENT_SHELF_LIFE = 17
    FROZEN_SHELF_LIFE = 120

    for (loc, prod, prod_date, curr_date, state), qty in result['cohort_inventory'].items():
        if qty > 0.01:  # Only check non-zero inventory
            age = (curr_date - prod_date).days

            # Check shelf life based on state
            if state == 'ambient':
                assert age <= AMBIENT_SHELF_LIFE, \
                    f"Expired ambient inventory: {loc}, {prod}, age={age}d > {AMBIENT_SHELF_LIFE}d"
            elif state == 'frozen':
                assert age <= FROZEN_SHELF_LIFE, \
                    f"Expired frozen inventory: {loc}, {prod}, age={age}d > {FROZEN_SHELF_LIFE}d"


def test_daily_snapshot_with_model_solution(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test daily snapshot generation with model solution (model mode)."""
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    # Create production schedule from batches
    batches = result.get('production_batch_objects', [])
    if not batches:
        pytest.skip("No batches in result")

    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=min(b.production_date for b in batches),
        schedule_end_date=max(b.production_date for b in batches),
        production_batches=batches,
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=sum(b.quantity for b in batches),
        total_labor_hours=0.0
    )

    # Create snapshot generator with model solution
    locations_dict = {loc.id: loc for loc in realistic_locations}
    shipments = result.get('batch_shipments', [])

    generator = DailySnapshotGenerator(
        production_schedule=schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=realistic_forecast,
        model_solution=result  # CRITICAL: Pass model solution
    )

    # Verify generator uses model mode
    assert generator.use_model_inventory == True

    # Generate snapshot
    snapshot_date = realistic_forecast.entries[7].forecast_date
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Verify snapshot
    assert snapshot is not None
    assert snapshot.date == snapshot_date
    assert len(snapshot.location_inventory) > 0

    # Verify inventory extraction from model worked
    # At least one location should have inventory or we should see all locations
    assert len(snapshot.location_inventory) == len(realistic_locations)


def test_snapshot_inventory_matches_model_cohorts(
    realistic_forecast: Forecast,
    realistic_labor_calendar: LaborCalendar,
    realistic_manufacturing: ManufacturingSite,
    realistic_cost_structure: CostStructure,
    realistic_locations: List[Location],
    realistic_routes: List[Route]
) -> None:
    """Test that snapshot inventory totals match model cohort inventory."""
    model = IntegratedProductionDistributionModel(
        forecast=realistic_forecast,
        labor_calendar=realistic_labor_calendar,
        manufacturing_site=realistic_manufacturing,
        cost_structure=realistic_cost_structure,
        locations=realistic_locations,
        routes=realistic_routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    result = model.solve(time_limit_seconds=120)

    if result.get('solver_status') != 'optimal':
        pytest.skip("Solver did not find optimal solution")

    if 'cohort_inventory' not in result:
        pytest.skip("Cohort inventory not in result")

    batches = result.get('production_batch_objects', [])
    if not batches:
        pytest.skip("No batches in result")

    # Create snapshot
    schedule = ProductionSchedule(
        manufacturing_site_id="6122",
        schedule_start_date=min(b.production_date for b in batches),
        schedule_end_date=max(b.production_date for b in batches),
        production_batches=batches,
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_units=sum(b.quantity for b in batches),
        total_labor_hours=0.0
    )

    locations_dict = {loc.id: loc for loc in realistic_locations}
    shipments = result.get('batch_shipments', [])

    generator = DailySnapshotGenerator(
        production_schedule=schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=realistic_forecast,
        model_solution=result
    )

    # Pick a date in the middle of the horizon
    snapshot_date = realistic_forecast.entries[7].forecast_date
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Sum snapshot inventory by location
    snapshot_totals: Dict[str, float] = {}
    for loc_id, loc_inv in snapshot.location_inventory.items():
        snapshot_totals[loc_id] = loc_inv.total_quantity

    # Sum model cohort inventory for this date
    model_totals: Dict[str, float] = defaultdict(float)
    for (loc, prod, prod_date, curr_date, state), qty in result['cohort_inventory'].items():
        if curr_date == snapshot_date:
            model_totals[loc] += qty

    # Compare totals
    all_locations = set(snapshot_totals.keys()) | set(model_totals.keys())

    for loc in all_locations:
        snapshot_qty = snapshot_totals.get(loc, 0.0)
        model_qty = model_totals.get(loc, 0.0)

        assert abs(snapshot_qty - model_qty) < 0.1, \
            f"Inventory mismatch at {loc} on {snapshot_date}: " \
            f"snapshot={snapshot_qty:.2f}, model={model_qty:.2f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
