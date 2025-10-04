"""Tests for UI result adapter utility."""

import pytest
from datetime import date
from ui.utils.result_adapter import (
    _create_production_schedule,
    _create_cost_breakdown,
)
from src.distribution.truck_loader import TruckLoadPlan
from src.costs.cost_breakdown import TotalCostBreakdown, WasteCostBreakdown


# Note: Tests for _create_placeholder_truck_plan removed as it has been
# replaced with _create_truck_plan_from_optimization which requires
# model and shipments as inputs. The new function is tested via integration tests.


class TestCostBreakdown:
    """Test cost breakdown creation from optimization results."""

    def test_create_cost_breakdown_returns_valid_breakdown(self):
        """Test that cost breakdown creates a valid TotalCostBreakdown instance."""
        # Create mock model and solution
        class MockModel:
            manufacturing_site = type('obj', (object,), {'id': '6122'})()
            start_date = date(2025, 1, 1)
            end_date = date(2025, 1, 7)

        solution = {
            'total_labor_cost': 1000.0,
            'total_production_cost': 2000.0,
            'total_transport_cost': 500.0,
            'total_truck_cost': 300.0,
            'total_shortage_cost': 100.0,
            'total_shortage_units': 50.0,
            'total_cost': 3900.0,
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
            'production_by_date_product': {},
        }

        breakdown = _create_cost_breakdown(MockModel(), solution)

        assert isinstance(breakdown, TotalCostBreakdown)
        assert breakdown.total_cost == 3900.0

    def test_waste_breakdown_uses_correct_parameter_names(self):
        """Test that WasteCostBreakdown is created with correct parameter names."""
        class MockModel:
            manufacturing_site = type('obj', (object,), {'id': '6122'})()
            start_date = date(2025, 1, 1)
            end_date = date(2025, 1, 7)

        solution = {
            'total_labor_cost': 0.0,
            'total_production_cost': 0.0,
            'total_transport_cost': 0.0,
            'total_truck_cost': 0.0,
            'total_shortage_cost': 250.0,
            'total_shortage_units': 100.0,
            'total_cost': 250.0,
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
            'production_by_date_product': {},
        }

        breakdown = _create_cost_breakdown(MockModel(), solution)

        # Verify waste breakdown has correct attributes (not shortage_units/shortage_cost)
        waste = breakdown.waste
        assert isinstance(waste, WasteCostBreakdown)
        assert waste.total_cost == 250.0
        assert waste.unmet_demand_units == 100.0  # Correct parameter name
        assert waste.unmet_demand_cost == 250.0   # Correct parameter name
        assert hasattr(waste, 'waste_details')

        # Verify it doesn't have the old incorrect names
        assert not hasattr(waste, 'shortage_units')
        assert not hasattr(waste, 'shortage_cost')

    def test_waste_breakdown_has_all_required_attributes(self):
        """Test that WasteCostBreakdown has all required attributes."""
        class MockModel:
            manufacturing_site = type('obj', (object,), {'id': '6122'})()
            start_date = date(2025, 1, 1)
            end_date = date(2025, 1, 7)

        solution = {
            'total_labor_cost': 0.0,
            'total_production_cost': 0.0,
            'total_transport_cost': 0.0,
            'total_truck_cost': 0.0,
            'total_shortage_cost': 0.0,
            'total_shortage_units': 0.0,
            'total_cost': 0.0,
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
            'production_by_date_product': {},
        }

        breakdown = _create_cost_breakdown(MockModel(), solution)
        waste = breakdown.waste

        # Verify all required attributes exist
        assert hasattr(waste, 'total_cost')
        assert hasattr(waste, 'expired_units')
        assert hasattr(waste, 'expired_cost')
        assert hasattr(waste, 'unmet_demand_units')
        assert hasattr(waste, 'unmet_demand_cost')
        assert hasattr(waste, 'waste_by_location')
        assert hasattr(waste, 'waste_by_product')
        assert hasattr(waste, 'waste_details')

    def test_zero_shortage_creates_valid_waste_breakdown(self):
        """Test that zero shortage still creates valid WasteCostBreakdown."""
        class MockModel:
            manufacturing_site = type('obj', (object,), {'id': '6122'})()
            start_date = date(2025, 1, 1)
            end_date = date(2025, 1, 7)

        solution = {
            'total_labor_cost': 1000.0,
            'total_production_cost': 2000.0,
            'total_transport_cost': 500.0,
            'total_truck_cost': 0.0,
            'total_shortage_cost': 0.0,
            'total_shortage_units': 0.0,
            'total_cost': 3500.0,
            'labor_hours_by_date': {},
            'labor_cost_by_date': {},
            'production_by_date_product': {},
        }

        breakdown = _create_cost_breakdown(MockModel(), solution)

        assert breakdown.waste.total_cost == 0.0
        assert breakdown.waste.unmet_demand_units == 0.0
        assert breakdown.waste.unmet_demand_cost == 0.0
