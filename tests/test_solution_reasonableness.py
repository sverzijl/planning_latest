"""
Solution Reasonableness Tests

These tests verify that optimization solutions make business sense,
not just that they're mathematically "optimal".

Purpose: Prevent bugs where model finds technically optimal but
economically nonsensical solutions (e.g., 13% fill rate when capacity exists).

CRITICAL: These tests should fail LOUDLY when solutions are unrealistic,
catching formulation bugs before they reach production.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


def build_and_solve_model(horizon_days):
    """Build and solve model for given horizon.

    Returns:
        tuple: (model_builder, solution, solve_result)
    """
    # Load data
    coordinator = DataCoordinator(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    validated = coordinator.load_and_validate()

    # Build forecast
    forecast_entries = [
        ForecastEntry(
            location_id=entry.node_id,
            product_id=entry.product_id,
            forecast_date=entry.demand_date,
            quantity=entry.quantity
        )
        for entry in validated.demand_entries
    ]
    forecast = Forecast(name="Test Forecast", entries=forecast_entries)

    # Load network
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    _, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes_legacy)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    products_dict = {p.id: p for p in validated.products}

    # Set horizon
    start = validated.planning_start_date
    end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

    # Build model
    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        products=products_dict,
        start_date=start,
        end_date=end,
        truck_schedules=unified_truck_schedules,
        initial_inventory=validated.get_inventory_dict(),
        inventory_snapshot_date=validated.inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
    model = model_builder.model  # Get the solved Pyomo model
    solution = model_builder.extract_solution(model)

    # Get demand and init_inv for this horizon
    total_demand_original = sum(model_builder.demand_original.values())
    total_init_inv_original = sum(model_builder.initial_inventory_original.values())

    return model_builder, solution, result, total_demand_original, total_init_inv_original


class TestSolutionReasonableness:
    """Test suite for solution business logic validation."""

    def test_1week_production_meets_demand(self):
        """1-week solve should produce enough to meet demand (minus initial inventory)."""
        model_builder, solution, result, total_demand, init_inv = build_and_solve_model(7)

        # Check solve succeeded
        assert result.success, f"Solve failed: {result.termination_condition}"

        # Calculate expected production
        expected_production = max(0, total_demand - init_inv)

        # Actual production
        actual_production = solution.total_production

        # Check production is reasonable (within 20% of expected)
        lower_bound = 0.75 * expected_production  # Allow 25% under if shortages acceptable
        upper_bound = 1.2 * expected_production    # Allow 20% over for buffer

        assert lower_bound < actual_production < upper_bound, (
            f"Production unrealistic for 1-week:\n"
            f"  Total demand: {total_demand:,.0f} units\n"
            f"  Initial inventory: {init_inv:,.0f} units\n"
            f"  Expected production: {expected_production:,.0f} units\n"
            f"  Actual production: {actual_production:,.0f} units\n"
            f"  Acceptable range: [{lower_bound:,.0f}, {upper_bound:,.0f}]"
        )

        # Check fill rate
        assert solution.fill_rate > 0.90, (
            f"Fill rate too low: {solution.fill_rate:.1%} (should be >90%)"
        )

    def test_4week_production_meets_demand(self):
        """4-week solve should produce enough to meet demand (minus initial inventory)."""
        model_builder, solution, result, total_demand, init_inv = build_and_solve_model(28)

        # Check solve succeeded
        assert result.success, f"Solve failed: {result.termination_condition}"

        # Calculate expected production
        expected_production = max(0, total_demand - init_inv)

        # Actual production
        actual_production = solution.total_production

        # Check production is reasonable
        lower_bound = 0.75 * expected_production
        upper_bound = 1.2 * expected_production

        assert lower_bound < actual_production < upper_bound, (
            f"Production unrealistic for 4-week:\n"
            f"  Total demand: {total_demand:,.0f} units\n"
            f"  Initial inventory: {init_inv:,.0f} units\n"
            f"  Expected production: {expected_production:,.0f} units\n"
            f"  Actual production: {actual_production:,.0f} units\n"
            f"  Acceptable range: [{lower_bound:,.0f}, {upper_bound:,.0f}]\n"
            f"\n"
            f"  ⚠️  This likely indicates a formulation bug (e.g., inventory double-counting)"
        )

        # Check fill rate
        assert solution.fill_rate > 0.95, (
            f"Fill rate too low: {solution.fill_rate:.1%} (should be >95% for 4-week)"
        )

        # Check production distribution
        producing_days = len([batch for batch in solution.production_batches if batch['quantity'] > 0])
        assert producing_days >= 15, (
            f"Too few production days: {producing_days} (should be >=15 for 4-week horizon)\n"
            f"  This suggests production is blocked by constraints or costs are miscalibrated"
        )

    def test_4week_conservation_of_flow(self):
        """Verify material balance: can't consume more than available."""
        model_builder, solution, result, total_demand, init_inv = build_and_solve_model(28)

        # Calculate supply
        total_production = solution.total_production
        total_supply = init_inv + total_production

        # Calculate usage (consumed + end inventory + shipments in transit at end)
        total_consumed = sum(solution.demand_consumed.values()) if hasattr(solution, 'demand_consumed') else 0
        total_shortage = solution.total_shortage_units

        # From demand equation: consumed + shortage = demand
        # So: consumed = demand - shortage
        consumed_from_demand_eq = total_demand - total_shortage

        # CRITICAL CHECK: Consumed cannot exceed supply
        assert total_consumed <= total_supply * 1.01, (  # 1% tolerance for rounding
            f"CONSERVATION VIOLATION: Consuming more than available!\n"
            f"  Initial inventory: {init_inv:,.0f} units\n"
            f"  Total production: {total_production:,.0f} units\n"
            f"  Total supply: {total_supply:,.0f} units\n"
            f"  Total consumed: {total_consumed:,.0f} units\n"
            f"  PHANTOM SUPPLY: {total_consumed - total_supply:,.0f} units\n"
            f"\n"
            f"  🚨 This indicates initial inventory is being DOUBLE-COUNTED in constraints!"
        )

        # Verify demand equation consistency
        demand_eq_check = abs((total_consumed + total_shortage) - total_demand)
        assert demand_eq_check < 100, (
            f"Demand equation violated: consumed + shortage != demand\n"
            f"  Consumed: {total_consumed:,.0f}\n"
            f"  Shortage: {total_shortage:,.0f}\n"
            f"  Sum: {total_consumed + total_shortage:,.0f}\n"
            f"  Demand: {total_demand:,.0f}\n"
            f"  Error: {demand_eq_check:,.0f} units"
        )

    def test_4week_cost_components_reasonable(self):
        """Verify cost component magnitudes make sense."""
        model_builder, solution, result, total_demand, init_inv = build_and_solve_model(28)

        # Extract cost components
        total_cost = solution.total_cost
        production_cost = solution.total_production_cost
        shortage_units = solution.total_shortage_units

        # Calculate expected shortage cost
        shortage_penalty = model_builder.cost_structure.shortage_penalty_per_unit
        expected_shortage_cost = shortage_units * shortage_penalty

        # If significant shortage exists, shortage cost should dominate
        if shortage_units > 0.1 * total_demand:
            shortage_fraction = expected_shortage_cost / total_cost if total_cost > 0 else 0

            assert shortage_fraction > 0.5, (
                f"Shortage cost should dominate objective when shortages are high:\n"
                f"  Shortage: {shortage_units:,.0f} units ({shortage_units/total_demand:.1%} of demand)\n"
                f"  Expected shortage cost: ${expected_shortage_cost:,.0f}\n"
                f"  Total cost: ${total_cost:,.0f}\n"
                f"  Shortage fraction: {shortage_fraction:.1%}\n"
                f"\n"
                f"  ⚠️  If shortage cost is low despite high shortages, penalty may not be in objective!"
            )

        # Objective should be in realistic range for 4-week
        assert 100_000 < total_cost < 5_000_000, (
            f"Objective value outside expected range: ${total_cost:,.0f}\n"
            f"  Expected: $100k - $5M for 4-week horizon\n"
            f"  This may indicate cost scaling errors"
        )


class TestHorizonScaling:
    """Test that solutions scale appropriately with horizon length."""

    @pytest.mark.slow
    def test_production_scales_with_demand(self):
        """Longer horizons should produce proportionally more."""
        # Solve 1-week
        _, sol_1w, _, demand_1w, init_inv = build_and_solve_model(7)

        # Solve 4-week
        _, sol_4w, _, demand_4w, _ = build_and_solve_model(28)

        # Production should scale roughly with demand
        production_ratio = sol_4w.total_production / sol_1w.total_production
        demand_ratio = demand_4w / demand_1w

        # Allow ±50% variance (init_inv amortizes differently across horizons)
        assert 0.5 * demand_ratio < production_ratio < 1.5 * demand_ratio, (
            f"Production doesn't scale with demand:\n"
            f"  1-week demand: {demand_1w:,.0f}, production: {sol_1w.total_production:,.0f}\n"
            f"  4-week demand: {demand_4w:,.0f}, production: {sol_4w.total_production:,.0f}\n"
            f"  Demand ratio: {demand_ratio:.2f}×\n"
            f"  Production ratio: {production_ratio:.2f}×\n"
            f"\n"
            f"  ⚠️  This suggests formulation changes behavior across horizons"
        )


if __name__ == "__main__":
    # Allow running individual tests for debugging
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
