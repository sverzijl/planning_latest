"""Integration tests for holding cost implementation.

End-to-end tests that verify holding costs work correctly in a complete
optimization run, including:
- Holding cost > 0 in solution
- Holding cost appears in cost breakdown
- Daily snapshot respects planning horizon
- Inventory minimized on last day
- Total cost = labor + production + transport + holding + waste
"""

import pytest
from datetime import date, timedelta

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results


@pytest.mark.integration
class TestHoldingCostIntegration:
    """Integration tests for complete holding cost flow."""

    @pytest.fixture
    def test_network(self):
        """Create a test network with manufacturing, hub, and demand nodes."""
        # Manufacturing node
        manufacturing = UnifiedNode(
            id="MFG",
            name="Manufacturing Site",
            capabilities=NodeCapabilities(
                can_manufacture=True,
                has_demand=False,
                can_store=True,
                requires_trucks=False,
                production_rate_per_hour=200.0,
                storage_capacity=20000.0,
                storage_mode=StorageMode.AMBIENT,
            )
        )

        # Hub node
        hub = UnifiedNode(
            id="HUB",
            name="Distribution Hub",
            capabilities=NodeCapabilities(
                can_manufacture=False,
                has_demand=False,
                can_store=True,
                requires_trucks=False,
                storage_capacity=10000.0,
                storage_mode=StorageMode.AMBIENT,
            )
        )

        # Demand node
        demand_node = UnifiedNode(
            id="DEST",
            name="Destination",
            capabilities=NodeCapabilities(
                can_manufacture=False,
                has_demand=True,
                can_store=True,
                requires_trucks=False,
                storage_capacity=5000.0,
                storage_mode=StorageMode.AMBIENT,
            )
        )

        # Routes
        route1 = UnifiedRoute(
            id="R1",
            origin_node_id="MFG",
            destination_node_id="HUB",
            transport_mode=TransportMode.AMBIENT,
            transit_days=1.0,
            cost_per_unit=0.3,
        )

        route2 = UnifiedRoute(
            id="R2",
            origin_node_id="HUB",
            destination_node_id="DEST",
            transport_mode=TransportMode.AMBIENT,
            transit_days=1.0,
            cost_per_unit=0.2,
        )

        return {
            'nodes': [manufacturing, hub, demand_node],
            'routes': [route1, route2],
        }

    @pytest.fixture
    def test_forecast(self):
        """Create forecast with demand at end of week."""
        entries = [
            ForecastEntry(
                location_id="DEST",
                product_id="P1",
                forecast_date=date(2025, 10, 7),
                quantity=1000.0,
            ),
        ]
        return Forecast(name="1-Week Forecast", entries=entries)

    @pytest.fixture
    def test_labor_calendar(self):
        """Create 7-day labor calendar."""
        labor_days = [
            LaborDay(
                date=date(2025, 10, 1) + timedelta(days=i),
                is_fixed_day=True,
                fixed_hours=12.0,
                overtime_hours=2.0,
                regular_rate=25.0,
                overtime_rate=37.5,
            )
            for i in range(7)
        ]
        return LaborCalendar(labor_days=labor_days)

    @pytest.fixture
    def test_cost_structure(self):
        """Create cost structure with meaningful holding costs."""
        return CostStructure(
            production_cost_per_unit=2.0,
            transport_cost_per_unit_km=0.01,
            labor_regular_rate_per_hour=25.0,
            labor_overtime_rate_per_hour=37.5,
            storage_cost_frozen_per_unit_day=0.10,  # $0.10/unit/day frozen
            storage_cost_ambient_per_unit_day=0.05,  # $0.05/unit/day ambient
            shortage_penalty_per_unit=200.0,
        )

    @pytest.mark.solver_required
    def test_full_optimization_with_holding_costs(
        self,
        test_network,
        test_forecast,
        test_labor_calendar,
        test_cost_structure
    ):
        """Test complete optimization run with holding costs.

        Verifies:
        1. Holding cost > 0 in solution
        2. Holding cost in cost breakdown
        3. Inventory minimized on last day
        4. Total cost = sum of components
        """
        # Create model
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=test_network['nodes'],
            routes=test_network['routes'],
            forecast=test_forecast,
        products=products,
            labor_calendar=test_labor_calendar,
            cost_structure=test_cost_structure,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        # Solve
        result = model.solve(time_limit_seconds=30)

        # Verify solve succeeded
        assert result.status in ['OPTIMAL', 'FEASIBLE']

        # Get solution
        solution = model.get_solution()
        assert solution is not None

        # 1. Verify holding cost > 0
        total_holding_cost = solution.get('total_holding_cost', 0.0)
        assert total_holding_cost > 0, "Holding cost should be positive with inventory storage"

        # 2. Verify holding cost in cost breakdown
        adapted_results = adapt_optimization_results(model, {}, None)
        assert adapted_results is not None

        cost_breakdown = adapted_results['cost_breakdown']
        assert cost_breakdown.holding is not None
        assert cost_breakdown.holding.total_cost == total_holding_cost

        # 3. Verify inventory minimized on last day
        cohort_inventory = solution.get('cohort_inventory', {})
        last_day = date(2025, 10, 7)

        # Calculate total inventory on last day
        last_day_inventory = sum(
            qty for (node, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
            if curr_date == last_day
        )

        # Calculate total production
        production_by_date_product = solution.get('production_by_date_product', {})
        total_production = sum(production_by_date_product.values())

        # Inventory on last day should be minimal (< 1% of total production)
        # This validates that holding costs incentivize minimizing end-of-horizon inventory
        assert last_day_inventory < 0.01 * total_production, \
            f"Last day inventory ({last_day_inventory}) should be < 1% of production ({total_production})"

        # 4. Verify total cost = sum of components
        expected_total = (
            solution.get('total_labor_cost', 0.0) +
            solution.get('total_production_cost', 0.0) +
            solution.get('total_transport_cost', 0.0) +
            solution.get('total_holding_cost', 0.0) +
            solution.get('total_shortage_cost', 0.0)
        )

        actual_total = solution.get('total_cost', 0.0)

        # Allow small tolerance for floating-point arithmetic
        assert abs(actual_total - expected_total) < 0.01, \
            f"Total cost ({actual_total}) should equal sum of components ({expected_total})"

    @pytest.mark.solver_required
    def test_daily_snapshot_respects_planning_horizon(
        self,
        test_network,
        test_forecast,
        test_labor_calendar,
        test_cost_structure
    ):
        """Test that daily snapshot date range is capped at planning horizon."""
        # Create and solve model
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=test_network['nodes'],
            routes=test_network['routes'],
            forecast=test_forecast,
        products=products,
            labor_calendar=test_labor_calendar,
            cost_structure=test_cost_structure,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.status in ['OPTIMAL', 'FEASIBLE']

        # Adapt results
        adapted_results = adapt_optimization_results(model, {}, None)

        production_schedule = adapted_results['production_schedule']
        shipments = adapted_results['shipments']

        # Test date range capping
        from ui.components.daily_snapshot import _get_date_range

        date_range = _get_date_range(production_schedule, shipments)

        assert date_range is not None
        min_date, max_date = date_range

        # Dates should be within planning horizon
        assert min_date >= date(2025, 10, 1), "Min date should be >= planning start"
        assert max_date <= date(2025, 10, 7), "Max date should be <= planning end"

    @pytest.mark.solver_required
    def test_holding_cost_breakdown_proportions(
        self,
        test_network,
        test_forecast,
        test_labor_calendar,
        test_cost_structure
    ):
        """Test that holding cost proportion is reasonable in total cost."""
        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=test_network['nodes'],
            routes=test_network['routes'],
            forecast=test_forecast,
        products=products,
            labor_calendar=test_labor_calendar,
            cost_structure=test_cost_structure,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.status in ['OPTIMAL', 'FEASIBLE']

        adapted_results = adapt_optimization_results(model, {}, None)
        cost_breakdown = adapted_results['cost_breakdown']

        # Get cost proportions
        proportions = cost_breakdown.get_cost_proportions()

        # Verify holding is in proportions
        assert 'holding' in proportions

        # Verify proportions sum to 1.0
        total_proportion = sum(proportions.values())
        assert abs(total_proportion - 1.0) < 0.0001

        # Holding cost should be a small but non-zero proportion
        # (typically 1-10% of total cost for weekly planning)
        assert 0.0 < proportions['holding'] < 0.2, \
            f"Holding proportion ({proportions['holding']}) should be 0-20% of total"

    def test_zero_holding_costs_no_impact(
        self,
        test_network,
        test_forecast,
        test_labor_calendar,
    ):
        """Test that zero holding costs don't affect optimization."""
        # Cost structure with zero holding costs
        zero_holding_costs = CostStructure(
            production_cost_per_unit=2.0,
            transport_cost_per_unit_km=0.01,
            labor_regular_rate_per_hour=25.0,
            labor_overtime_rate_per_hour=37.5,
            storage_cost_frozen_per_unit_day=0.0,  # Zero
            storage_cost_ambient_per_unit_day=0.0,  # Zero
            shortage_penalty_per_unit=200.0,
        )

        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=test_network['nodes'],
            routes=test_network['routes'],
            forecast=test_forecast,
        products=products,
            labor_calendar=test_labor_calendar,
            cost_structure=zero_holding_costs,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        # Build model (don't need to solve for this test)
        pyomo_model = model.build_model()

        # Model should build successfully even with zero holding costs
        assert pyomo_model is not None

    @pytest.mark.solver_required
    def test_holding_cost_with_initial_inventory(
        self,
        test_network,
        test_forecast,
        test_labor_calendar,
        test_cost_structure
    ):
        """Test that holding costs apply to initial inventory."""
        # Create initial inventory at manufacturing site
        initial_inventory = {
            ('MFG', 'P1'): 500.0,
        }

        # Create products for model (extract unique product IDs from forecast)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = UnifiedNodeModel(
            nodes=test_network['nodes'],
            routes=test_network['routes'],
            forecast=test_forecast,
        products=products,
            labor_calendar=test_labor_calendar,
            cost_structure=test_cost_structure,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
            initial_inventory=initial_inventory,
            inventory_snapshot_date=date(2025, 10, 1),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        result = model.solve(time_limit_seconds=30)
        assert result.status in ['OPTIMAL', 'FEASIBLE']

        solution = model.get_solution()

        # Holding cost should account for initial inventory
        total_holding_cost = solution.get('total_holding_cost', 0.0)
        assert total_holding_cost > 0, "Holding cost should include initial inventory"

        # Verify initial inventory appears in cohort_inventory
        cohort_inventory = solution.get('cohort_inventory', {})

        # Find initial inventory cohorts (production date before planning start)
        init_prod_date = date(2025, 9, 30)  # One day before start
        initial_inv_cohorts = [
            (node, prod, prod_date, curr_date, state)
            for (node, prod, prod_date, curr_date, state) in cohort_inventory.keys()
            if prod_date == init_prod_date
        ]

        assert len(initial_inv_cohorts) > 0, "Initial inventory should appear in cohort inventory"
