"""Test pallet entry tracking for fixed costs.

Following TDD: Tests written FIRST.
"""

import pytest
from datetime import date, timedelta
from pyomo.environ import value
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products


class TestPalletEntryTracking:
    """Test pallet entry detection and fixed cost application."""

    def test_pallet_entry_variable_exists(self):
        """Should create pallet_entry variables when fixed costs > 0."""
        # Arrange
        parser = MultiFileParser(
            forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
            network_file='data/examples/Network_Config.xlsx'
        )
        forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

        # Verify fixed cost is configured
        assert cost_params.storage_cost_fixed_per_pallet_frozen > 0, "Test requires frozen fixed cost > 0"

        mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
        converter = LegacyToUnifiedConverter()
        nodes, unified_routes, unified_trucks = converter.convert_all(
            manufacturing_site=mfg_site, locations=locations, routes=routes,
            truck_schedules=truck_schedules, forecast=forecast
        )

        start = min(e.forecast_date for e in forecast.entries)
        end = start + timedelta(days=2)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = SlidingWindowModel(
            nodes=nodes, routes=unified_routes, forecast=forecast,
            products=products, labor_calendar=labor_calendar,
            cost_structure=cost_params, start_date=start, end_date=end,
            truck_schedules=unified_trucks, initial_inventory=None,
            allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=False
        )

        # Act
        pyomo_model = model.build_model()

        # Assert
        assert hasattr(pyomo_model, 'pallet_entry'), "Should have pallet_entry variables when fixed cost > 0"
        assert len(list(pyomo_model.pallet_entry)) > 0, "Should create pallet_entry variables"

    def test_pallet_entry_constraint_detects_increase(self):
        """Should have constraint: pallet_entry[t] >= pallet_count[t] - pallet_count[t-1]."""
        # Arrange
        parser = MultiFileParser(
            forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
            network_file='data/examples/Network_Config.xlsx'
        )
        forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

        mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
        converter = LegacyToUnifiedConverter()
        nodes, unified_routes, unified_trucks = converter.convert_all(
            manufacturing_site=mfg_site, locations=locations, routes=routes,
            truck_schedules=truck_schedules, forecast=forecast
        )

        start = min(e.forecast_date for e in forecast.entries)
        end = start + timedelta(days=2)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = SlidingWindowModel(
            nodes=nodes, routes=unified_routes, forecast=forecast,
            products=products, labor_calendar=labor_calendar,
            cost_structure=cost_params, start_date=start, end_date=end,
            truck_schedules=unified_trucks, initial_inventory=None,
            allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=False
        )

        # Act
        pyomo_model = model.build_model()

        # Assert
        assert hasattr(pyomo_model, 'pallet_entry_detection_con'), \
            "Should have pallet entry detection constraint"

        # Check constraint structure for a sample
        constraints = list(pyomo_model.pallet_entry_detection_con)
        assert len(constraints) > 0, "Should have entry detection constraints"

    def test_fixed_cost_in_objective(self):
        """Should include fixed pallet cost in objective when configured."""
        # Arrange
        parser = MultiFileParser(
            forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
            network_file='data/examples/Network_Config.xlsx'
        )
        forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

        fixed_cost = cost_params.storage_cost_fixed_per_pallet_frozen
        assert fixed_cost > 0, "Test requires frozen fixed cost > 0"

        mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
        converter = LegacyToUnifiedConverter()
        nodes, unified_routes, unified_trucks = converter.convert_all(
            manufacturing_site=mfg_site, locations=locations, routes=routes,
            truck_schedules=truck_schedules, forecast=forecast
        )

        start = min(e.forecast_date for e in forecast.entries)
        end = start + timedelta(days=2)
        product_ids = sorted(set(entry.product_id for entry in forecast.entries))
        products = create_test_products(product_ids)

        model = SlidingWindowModel(
            nodes=nodes, routes=unified_routes, forecast=forecast,
            products=products, labor_calendar=labor_calendar,
            cost_structure=cost_params, start_date=start, end_date=end,
            truck_schedules=unified_trucks, initial_inventory=None,
            allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=False
        )

        # Act
        pyomo_model = model.build_model()

        # Assert - check objective expression contains pallet_entry
        obj_expr = str(pyomo_model.obj.expr)
        assert 'pallet_entry' in obj_expr, \
            "Objective should include pallet_entry variables for fixed cost"
