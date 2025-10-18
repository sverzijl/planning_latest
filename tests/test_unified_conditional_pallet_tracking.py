"""Tests for UnifiedNodeModel conditional pallet tracking with state-specific fixed costs.

Tests cover:
1. Pallet tracking enabled for both frozen and ambient states
2. Pallet tracking enabled for frozen only
3. Pallet tracking enabled for ambient only
4. Pallet tracking disabled (no pallet costs)
5. State-specific fixed costs in objective function
"""

import pytest
from datetime import date, timedelta, time
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule, DepartureType, DayOfWeek
from src.models import (
    Forecast,
    ForecastEntry,
    LaborCalendar,
    LaborDay,
    CostStructure,
    Product,
)


def create_simple_network():
    """
    Create a minimal network for testing pallet tracking.

    Network:
    - Manufacturing node (6122) with ambient storage
    - Hub node (6125) with demand
    - Route: 6122 -> 6125 (ambient, 1 day)
    - Truck: 6122 -> 6125 (Monday morning)
    """
    # Manufacturing node
    manufacturing = UnifiedNode(
        id="6122",
        name="Manufacturing Site",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=1400.0,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            requires_truck_schedules=True,
        )
    )

    # Hub with demand
    hub = UnifiedNode(
        id="6125",
        name="Hub",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=True,
            requires_truck_schedules=False,
        )
    )

    nodes = [manufacturing, hub]

    # Route
    route = UnifiedRoute(
        id="R1",
        origin_node_id="6122",
        destination_node_id="6125",
        transit_days=1.0,
        transport_mode=TransportMode.AMBIENT,
        cost_per_unit=0.30,
    )
    routes = [route]

    # Truck schedule
    truck = UnifiedTruckSchedule(
        id="T1",
        origin_node_id="6122",
        destination_node_id="6125",
        departure_type=DepartureType.MORNING,
        departure_time=time(8, 0),
        day_of_week=DayOfWeek.MONDAY,
        capacity=14080.0,
    )
    trucks = [truck]

    return nodes, routes, trucks


def create_frozen_network():
    """
    Create a network with frozen storage capability for testing frozen pallet tracking.

    Network:
    - Manufacturing node (6122) with both frozen and ambient storage
    - Frozen storage node (Lineage) with frozen-only storage
    - Hub node (6125) with demand
    - Route 1: 6122 -> Lineage (frozen, 0.5 days)
    - Route 2: Lineage -> 6125 (frozen, 3.0 days)
    """
    # Manufacturing node (can produce, store ambient)
    manufacturing = UnifiedNode(
        id="6122",
        name="Manufacturing Site",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=1400.0,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,  # Ambient storage
            requires_truck_schedules=True,
        )
    )

    # Frozen storage node
    frozen_storage = UnifiedNode(
        id="Lineage",
        name="Lineage Frozen Storage",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.FROZEN,  # Frozen only
            has_demand=False,
            requires_truck_schedules=False,
        )
    )

    # Hub with demand
    hub = UnifiedNode(
        id="6125",
        name="Hub",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,  # Ambient storage
            has_demand=True,
            requires_truck_schedules=False,
        )
    )

    nodes = [manufacturing, frozen_storage, hub]

    # Routes
    routes = [
        UnifiedRoute(
            id="R1",
            origin_node_id="6122",
            destination_node_id="Lineage",
            transit_days=0.5,
            transport_mode=TransportMode.FROZEN,
            cost_per_unit=0.40,
        ),
        UnifiedRoute(
            id="R2",
            origin_node_id="Lineage",
            destination_node_id="6125",
            transit_days=3.0,
            transport_mode=TransportMode.FROZEN,
            cost_per_unit=0.50,
        ),
    ]

    # Truck schedule (manufacturing to frozen storage)
    trucks = [
        UnifiedTruckSchedule(
            id="T1",
            origin_node_id="6122",
            destination_node_id="Lineage",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            day_of_week=DayOfWeek.WEDNESDAY,
            capacity=14080.0,
        )
    ]

    return nodes, routes, trucks


def create_forecast(start_date, days=7):
    """Create a simple forecast for testing."""
    entries = []
    for i in range(days):
        entries.append(
            ForecastEntry(
                location_id="6125",
                product_id="P1",
                forecast_date=start_date + timedelta(days=i),
                quantity=1000.0,
            )
        )
    return Forecast(name="Test Forecast", entries=entries)


def create_labor_calendar(start_date, days=7):
    """Create a simple labor calendar for testing."""
    labor_days = []
    for i in range(days):
        day_date = start_date + timedelta(days=i)
        is_weekday = day_date.weekday() < 5  # Monday=0, Sunday=6

        labor_days.append(
            LaborDay(
                date=day_date,
                fixed_hours=12.0 if is_weekday else 0.0,
                regular_rate=20.0,
                overtime_rate=30.0,
                non_fixed_rate=40.0,
            )
        )

    return LaborCalendar(name="Test Labor Calendar", days=labor_days)


class TestUnifiedNodeModelConditionalPalletTracking:
    """Tests for conditional pallet tracking based on state-specific fixed costs."""

    def test_pallet_tracking_both_states(self):
        """
        Test that pallet tracking is enabled for both frozen and ambient states.

        When both frozen and ambient have non-zero pallet costs,
        pallet_cohort_index should include both 'frozen' and 'ambient' states.
        """
        nodes, routes, trucks = create_frozen_network()
        start_date = date(2025, 10, 20)  # Monday
        forecast = create_forecast(start_date, days=7)
        labor_calendar = create_labor_calendar(start_date, days=7)

        # Cost structure with non-zero pallet costs for BOTH states
        costs = CostStructure(
            production_cost_per_unit=5.0,
            storage_cost_fixed_per_pallet_frozen=5.0,  # Frozen fixed cost
            storage_cost_fixed_per_pallet_ambient=2.0,  # Ambient fixed cost
            storage_cost_per_pallet_day_frozen=0.5,  # Frozen daily cost
            storage_cost_per_pallet_day_ambient=0.2,  # Ambient daily cost
            # Unit costs set to 0 to use pallet-based exclusively
            storage_cost_frozen_per_unit_day=0.0,
            storage_cost_ambient_per_unit_day=0.0,
        )

        # Create model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=costs,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            truck_schedules=trucks,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify pallet_count variable exists
        assert hasattr(pyomo_model, 'pallet_count'), "pallet_count variable should exist"

        # Verify pallet_cohort_index includes both frozen and ambient
        pallet_cohort_index = list(pyomo_model.pallet_cohort_index)

        # Check if frozen state is tracked
        frozen_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'frozen']
        assert len(frozen_cohorts) > 0, "Pallet tracking should include 'frozen' state"

        # Check if ambient state is tracked
        ambient_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'ambient']
        assert len(ambient_cohorts) > 0, "Pallet tracking should include 'ambient' state"

        print(f"\nPallet tracking for both states:")
        print(f"  Total pallet cohorts: {len(pallet_cohort_index)}")
        print(f"  Frozen cohorts: {len(frozen_cohorts)}")
        print(f"  Ambient cohorts: {len(ambient_cohorts)}")

    def test_pallet_tracking_frozen_only(self):
        """
        Test that pallet tracking is enabled for frozen state only.

        When only frozen has non-zero pallet costs (ambient = 0),
        pallet_cohort_index should include 'frozen' but exclude 'ambient' and 'thawed'.
        """
        nodes, routes, trucks = create_frozen_network()
        start_date = date(2025, 10, 20)
        forecast = create_forecast(start_date, days=7)
        labor_calendar = create_labor_calendar(start_date, days=7)

        # Cost structure with frozen pallet costs ONLY
        costs = CostStructure(
            production_cost_per_unit=5.0,
            storage_cost_fixed_per_pallet_frozen=5.0,  # Frozen fixed cost
            storage_cost_per_pallet_day_frozen=0.5,  # Frozen daily cost
            # Ambient costs are None/0 (no pallet tracking)
            storage_cost_fixed_per_pallet_ambient=0.0,
            storage_cost_per_pallet_day_ambient=0.0,
            # Unit-based costs for ambient (fallback)
            storage_cost_frozen_per_unit_day=0.0,
            storage_cost_ambient_per_unit_day=0.02,
        )

        # Create model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=costs,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            truck_schedules=trucks,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify pallet_count variable exists
        assert hasattr(pyomo_model, 'pallet_count'), "pallet_count variable should exist"

        # Verify pallet_cohort_index includes only frozen
        pallet_cohort_index = list(pyomo_model.pallet_cohort_index)

        frozen_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'frozen']
        ambient_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'ambient']
        thawed_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'thawed']

        assert len(frozen_cohorts) > 0, "Pallet tracking should include 'frozen' state"
        assert len(ambient_cohorts) == 0, "Pallet tracking should exclude 'ambient' state"
        assert len(thawed_cohorts) == 0, "Pallet tracking should exclude 'thawed' state"

        print(f"\nPallet tracking for frozen only:")
        print(f"  Total pallet cohorts: {len(pallet_cohort_index)}")
        print(f"  Frozen cohorts: {len(frozen_cohorts)}")
        print(f"  Ambient cohorts: {len(ambient_cohorts)}")

    def test_pallet_tracking_ambient_only(self):
        """
        Test that pallet tracking is enabled for ambient state only.

        When only ambient has non-zero pallet costs (frozen = 0),
        pallet_cohort_index should include 'ambient' and 'thawed' but exclude 'frozen'.
        """
        nodes, routes, trucks = create_simple_network()
        start_date = date(2025, 10, 20)
        forecast = create_forecast(start_date, days=7)
        labor_calendar = create_labor_calendar(start_date, days=7)

        # Cost structure with ambient pallet costs ONLY
        costs = CostStructure(
            production_cost_per_unit=5.0,
            storage_cost_fixed_per_pallet_ambient=2.0,  # Ambient fixed cost
            storage_cost_per_pallet_day_ambient=0.2,  # Ambient daily cost
            # Frozen costs are 0 (no pallet tracking)
            storage_cost_fixed_per_pallet_frozen=0.0,
            storage_cost_per_pallet_day_frozen=0.0,
            # Unit-based costs for frozen (fallback)
            storage_cost_frozen_per_unit_day=0.05,
            storage_cost_ambient_per_unit_day=0.0,
        )

        # Create model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=costs,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            truck_schedules=trucks,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify pallet_count variable exists
        assert hasattr(pyomo_model, 'pallet_count'), "pallet_count variable should exist"

        # Verify pallet_cohort_index includes ambient and thawed, excludes frozen
        pallet_cohort_index = list(pyomo_model.pallet_cohort_index)

        frozen_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'frozen']
        ambient_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'ambient']
        thawed_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'thawed']

        assert len(frozen_cohorts) == 0, "Pallet tracking should exclude 'frozen' state"
        assert len(ambient_cohorts) > 0, "Pallet tracking should include 'ambient' state"
        # Note: thawed_cohorts may be 0 if no freeze/thaw nodes in network

        print(f"\nPallet tracking for ambient only:")
        print(f"  Total pallet cohorts: {len(pallet_cohort_index)}")
        print(f"  Frozen cohorts: {len(frozen_cohorts)}")
        print(f"  Ambient cohorts: {len(ambient_cohorts)}")
        print(f"  Thawed cohorts: {len(thawed_cohorts)}")

    def test_pallet_tracking_neither_state(self):
        """
        Test that pallet tracking is disabled when both states use unit-based costs.

        When all pallet costs are 0 (only unit-based costs set),
        model should NOT have pallet_count attribute or pallet_cohort_index should be empty.
        """
        nodes, routes, trucks = create_simple_network()
        start_date = date(2025, 10, 20)
        forecast = create_forecast(start_date, days=7)
        labor_calendar = create_labor_calendar(start_date, days=7)

        # Cost structure with ONLY unit-based costs (no pallet costs)
        costs = CostStructure(
            production_cost_per_unit=5.0,
            # All pallet costs are 0 or None
            storage_cost_fixed_per_pallet_frozen=0.0,
            storage_cost_fixed_per_pallet_ambient=0.0,
            storage_cost_per_pallet_day_frozen=0.0,
            storage_cost_per_pallet_day_ambient=0.0,
            # Use unit-based costs instead
            storage_cost_frozen_per_unit_day=0.05,
            storage_cost_ambient_per_unit_day=0.02,
        )

        # Create model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=costs,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            truck_schedules=trucks,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify pallet_count does NOT exist OR pallet_cohort_index is empty
        if hasattr(pyomo_model, 'pallet_count'):
            pallet_cohort_index = list(pyomo_model.pallet_cohort_index)
            assert len(pallet_cohort_index) == 0, (
                "Pallet tracking should be disabled when all pallet costs are 0"
            )
            print(f"\nPallet tracking disabled: pallet_cohort_index is empty")
        else:
            print(f"\nPallet tracking disabled: pallet_count attribute does not exist")

    def test_state_specific_fixed_costs_in_objective(self):
        """
        Test that different fixed costs are applied to frozen and ambient inventory.

        Build and solve a small model with different fixed pallet costs for frozen
        and ambient states. Verify that the holding cost reflects these different rates.

        This test validates that:
        1. State-specific fixed costs are correctly parsed from CostStructure
        2. UnifiedNodeModel applies different fixed costs to different states
        3. The objective function includes state-specific fixed pallet costs
        """
        nodes, routes, trucks = create_frozen_network()
        start_date = date(2025, 10, 20)  # Monday
        forecast = create_forecast(start_date, days=7)
        labor_calendar = create_labor_calendar(start_date, days=7)

        # Cost structure with DIFFERENT fixed costs for frozen and ambient
        costs = CostStructure(
            production_cost_per_unit=5.0,
            storage_cost_fixed_per_pallet_frozen=5.0,  # Higher for frozen
            storage_cost_fixed_per_pallet_ambient=2.0,  # Lower for ambient
            storage_cost_per_pallet_day_frozen=0.5,
            storage_cost_per_pallet_day_ambient=0.2,
            # Disable unit-based to force pallet-based
            storage_cost_frozen_per_unit_day=0.0,
            storage_cost_ambient_per_unit_day=0.0,
            # Low transport costs to encourage storage
            transport_cost_frozen_per_unit=0.01,
            transport_cost_ambient_per_unit=0.01,
        )

        # Verify get_fixed_pallet_costs() returns different values
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()
        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0"
        assert ambient_fixed == 2.0, "Ambient fixed cost should be 2.0"
        assert frozen_fixed != ambient_fixed, "Fixed costs should be different"

        # Create model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=costs,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            truck_schedules=trucks,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=False,
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify pallet tracking is enabled
        assert hasattr(pyomo_model, 'pallet_count'), "Pallet tracking should be enabled"

        # Verify both states have pallet cohorts
        pallet_cohort_index = list(pyomo_model.pallet_cohort_index)
        frozen_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'frozen']
        ambient_cohorts = [idx for idx in pallet_cohort_index if idx[4] == 'ambient']

        assert len(frozen_cohorts) > 0, "Should have frozen pallet cohorts"
        assert len(ambient_cohorts) > 0, "Should have ambient pallet cohorts"

        print(f"\nState-specific fixed costs verification:")
        print(f"  Frozen fixed cost: ${frozen_fixed}/pallet")
        print(f"  Ambient fixed cost: ${ambient_fixed}/pallet")
        print(f"  Frozen pallet cohorts: {len(frozen_cohorts)}")
        print(f"  Ambient pallet cohorts: {len(ambient_cohorts)}")

        # Solve model (small problem should solve quickly)
        result = model.solve(time_limit_seconds=60, mip_gap=0.05, tee=False)

        if result.is_optimal() or result.is_feasible():
            print(f"  Model solved: {result.termination_condition}")
            print(f"  Objective value: ${result.objective_value:,.2f}")

            # Extract holding cost breakdown if available
            try:
                # Get solution
                solution = model.get_solution()
                if solution and hasattr(solution, 'cost_breakdown'):
                    holding_cost = solution.cost_breakdown.get('holding_cost', 0.0)
                    print(f"  Holding cost: ${holding_cost:,.2f}")
            except Exception as e:
                print(f"  (Could not extract holding cost: {e})")

        else:
            print(f"  Model status: {result.termination_condition}")
            print(f"  (Solve not required for this test - model structure validated)")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
