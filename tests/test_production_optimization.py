"""Tests for production optimization model.

Tests the simple production planning optimization model.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.optimization.production_model import ProductionOptimizationModel
from src.optimization.base_model import OptimizationResult
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure


@pytest.fixture
def simple_forecast():
    """Create a simple 3-day forecast with 2 products."""
    start = date(2025, 1, 15)
    entries = [
        # Product A: 1000 units/day for 3 days = 3000 total
        ForecastEntry(location_id="LOC1", product_id="PROD_A", forecast_date=start, quantity=500),
        ForecastEntry(location_id="LOC2", product_id="PROD_A", forecast_date=start, quantity=500),
        ForecastEntry(location_id="LOC1", product_id="PROD_A", forecast_date=start + timedelta(days=1), quantity=500),
        ForecastEntry(location_id="LOC2", product_id="PROD_A", forecast_date=start + timedelta(days=1), quantity=500),
        ForecastEntry(location_id="LOC1", product_id="PROD_A", forecast_date=start + timedelta(days=2), quantity=500),
        ForecastEntry(location_id="LOC2", product_id="PROD_A", forecast_date=start + timedelta(days=2), quantity=500),

        # Product B: 800 units/day for 3 days = 2400 total
        ForecastEntry(location_id="LOC1", product_id="PROD_B", forecast_date=start, quantity=400),
        ForecastEntry(location_id="LOC2", product_id="PROD_B", forecast_date=start, quantity=400),
        ForecastEntry(location_id="LOC1", product_id="PROD_B", forecast_date=start + timedelta(days=1), quantity=400),
        ForecastEntry(location_id="LOC2", product_id="PROD_B", forecast_date=start + timedelta(days=1), quantity=400),
        ForecastEntry(location_id="LOC1", product_id="PROD_B", forecast_date=start + timedelta(days=2), quantity=400),
        ForecastEntry(location_id="LOC2", product_id="PROD_B", forecast_date=start + timedelta(days=2), quantity=400),
    ]
    return Forecast(name="Simple Test Forecast", entries=entries)


@pytest.fixture
def simple_labor_calendar():
    """Create labor calendar with 3 fixed days."""
    days = []
    start = date(2025, 1, 15)
    for i in range(3):
        day = LaborDay(
            date=start + timedelta(days=i),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0,
            is_fixed_day=True,
        )
        days.append(day)

    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def manufacturing_site():
    """Create manufacturing site."""
    from src.models.location import LocationType, StorageMode

    return ManufacturingSite(
        id="MFG1",
        name="Test Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
        production_rate=1400.0,
    )


@pytest.fixture
def cost_structure():
    """Create cost structure."""
    return CostStructure(
        production_cost_per_unit=0.80,
        transport_cost_per_unit_km=0.01,
        waste_cost_multiplier=1.5,
        shortage_penalty_per_unit=1.50,
    )


class TestProductionOptimizationModel:
    """Tests for ProductionOptimizationModel class."""

    def test_init_extracts_data(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test model initialization extracts data correctly."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        assert model.start_date == date(2025, 1, 15)
        assert model.end_date == date(2025, 1, 17)
        assert len(model.production_dates) == 3
        assert len(model.products) == 2
        assert "PROD_A" in model.products
        assert "PROD_B" in model.products

    def test_total_demand_by_product(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that total demand is calculated correctly."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        assert model.total_demand_by_product["PROD_A"] == pytest.approx(3000.0)
        assert model.total_demand_by_product["PROD_B"] == pytest.approx(2400.0)

    def test_build_model_creates_variables(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that build_model creates expected variables."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        pyomo_model = model.build_model()

        # Check variables exist
        assert hasattr(pyomo_model, 'production')
        assert hasattr(pyomo_model, 'labor_hours')
        assert hasattr(pyomo_model, 'fixed_hours_used')
        assert hasattr(pyomo_model, 'overtime_hours_used')

    def test_build_model_creates_constraints(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that build_model creates expected constraints."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        pyomo_model = model.build_model()

        # Check constraints exist
        assert hasattr(pyomo_model, 'labor_hours_con')
        assert hasattr(pyomo_model, 'max_hours_con')
        assert hasattr(pyomo_model, 'max_capacity_con')
        # Note: ProductionOptimizationModel uses simple demand satisfaction,
        # not inventory tracking (that's only in IntegratedProductionDistributionModel)

    def test_build_model_creates_objective(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that build_model creates objective function."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        pyomo_model = model.build_model()

        # Check objective exists
        assert hasattr(pyomo_model, 'obj')

    def test_get_model_statistics(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test getting model statistics."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
        )

        # Before build
        stats_before = model.get_model_statistics()
        assert stats_before['built'] is False
        assert stats_before['num_variables'] == 0

        # After build
        model.build_model()
        model.model = model.build_model()
        stats_after = model.get_model_statistics()
        assert stats_after['built'] is True
        assert stats_after['num_variables'] > 0
        assert stats_after['num_constraints'] > 0

    def test_empty_forecast_raises_error(
        self,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that empty forecast raises ValueError."""
        empty_forecast = Forecast(name="Empty", entries=[])

        with pytest.raises(ValueError, match="at least one entry"):
            ProductionOptimizationModel(
                forecast=empty_forecast,
                labor_calendar=simple_labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
            )

    def test_custom_date_range(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test custom start and end dates."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            start_date=date(2025, 1, 16),
            end_date=date(2025, 1, 16),
        )

        assert model.start_date == date(2025, 1, 16)
        assert model.end_date == date(2025, 1, 16)
        assert len(model.production_dates) == 1


class TestProductionOptimizationSolve:
    """Tests for solving production optimization model.

    These tests mock the solver to avoid requiring actual solver installation.
    """

    def test_solve_without_solver_returns_error(
        self,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test solving without solver available returns error result."""
        # Mock solver config to simulate no solver available
        mock_config = Mock()
        mock_config.create_solver.side_effect = RuntimeError("No solver available")

        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            solver_config=mock_config,
        )

        result = model.solve()

        assert result.success is False
        assert "No solver available" in result.infeasibility_message

    def test_solve_returns_result(
        self,
        mock_solver_config,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test that solve returns OptimizationResult."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            solver_config=mock_solver_config,
        )

        result = model.solve()

        assert isinstance(result, OptimizationResult)
        assert result.success is True

    def test_extract_solution_after_solve(
        self,
        mock_solver_config,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test solution extraction after successful solve."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            solver_config=mock_solver_config,
        )

        result = model.solve()
        solution = model.get_solution()

        assert solution is not None
        assert 'production_by_date_product' in solution
        assert 'labor_hours_by_date' in solution
        assert 'total_labor_cost' in solution
        assert 'total_production_cost' in solution

    def test_get_production_schedule(
        self,
        mock_solver_config,
        simple_forecast,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure
    ):
        """Test converting solution to ProductionSchedule."""
        model = ProductionOptimizationModel(
            forecast=simple_forecast,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            solver_config=mock_solver_config,
        )

        result = model.solve()
        schedule = model.get_production_schedule()

        assert schedule is not None
        assert len(schedule.production_batches) > 0
        assert schedule.manufacturing_site_id == "MFG1"
        assert schedule.is_feasible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
