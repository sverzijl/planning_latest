"""Tests for integrated production-distribution optimization model.

Tests the integrated model that combines production scheduling with routing decisions.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.optimization.base_model import OptimizationResult
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route


@pytest.fixture
def simple_network_locations():
    """Create simple network locations for testing."""
    manufacturing = Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
    )

    hub = Location(
        id="6125",
        name="VIC Hub",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.AMBIENT,
    )

    dest1 = Location(
        id="6103",
        name="Breadroom 1",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    dest2 = Location(
        id="6105",
        name="Breadroom 2",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )

    return [manufacturing, hub, dest1, dest2]


@pytest.fixture
def simple_network_routes():
    """Create simple network routes for testing."""
    return [
        # Manufacturing to hub
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6125",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10,
        ),
        # Hub to destinations
        Route(
            id="R2",
            origin_id="6125",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.15,
        ),
        Route(
            id="R3",
            origin_id="6125",
            destination_id="6105",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.12,
        ),
        # Direct routes (optional alternatives)
        Route(
            id="R4",
            origin_id="6122",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=2.0,
            cost=0.30,
        ),
    ]


@pytest.fixture
def simple_forecast_disaggregated():
    """Create a simple forecast with location-specific demand."""
    start = date(2025, 1, 15)
    entries = [
        # Product A to Dest 1
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=start, quantity=500),
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=start + timedelta(days=1), quantity=500),

        # Product A to Dest 2
        ForecastEntry(location_id="6105", product_id="PROD_A", forecast_date=start, quantity=300),
        ForecastEntry(location_id="6105", product_id="PROD_A", forecast_date=start + timedelta(days=1), quantity=300),

        # Product B to Dest 1
        ForecastEntry(location_id="6103", product_id="PROD_B", forecast_date=start, quantity=400),
        ForecastEntry(location_id="6103", product_id="PROD_B", forecast_date=start + timedelta(days=1), quantity=400),
    ]
    return Forecast(name="Disaggregated Test Forecast", entries=entries)


@pytest.fixture
def simple_labor_calendar():
    """Create labor calendar with coverage for extended planning horizon."""
    days = []
    # Start earlier to account for transit time buffer (planning horizon extension)
    start = date(2025, 1, 12)  # Start 3 days earlier
    # Cover more days to handle any horizon extensions
    for i in range(10):  # 10 days of coverage
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
    return ManufacturingSite(
        id="6122",
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


class TestIntegratedModelInit:
    """Tests for IntegratedProductionDistributionModel initialization."""

    def test_init_extracts_data(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test model initialization extracts data correctly."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        # Planning horizon is extended backward to accommodate transit times
        # With 2-day max transit, start date should be 2 days before first forecast date
        assert model.start_date <= date(2025, 1, 15)  # May start earlier due to transit
        assert model.end_date == date(2025, 1, 16)
        assert len(model.production_dates) >= 2  # May have more days due to planning horizon extension
        assert len(model.products) == 2
        assert "PROD_A" in model.products
        assert "PROD_B" in model.products

    def test_disaggregated_demand(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that demand is disaggregated by location."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        # Check specific demand entries
        start = date(2025, 1, 15)
        assert model.demand[("6103", "PROD_A", start)] == 500
        assert model.demand[("6105", "PROD_A", start)] == 300
        assert model.demand[("6103", "PROD_B", start)] == 400

        # Check total demand by product
        assert model.total_demand_by_product["PROD_A"] == pytest.approx(1600.0)  # 500+500+300+300
        assert model.total_demand_by_product["PROD_B"] == pytest.approx(800.0)   # 400+400

    def test_route_enumeration(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that routes are enumerated correctly."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
            max_routes_per_destination=3,
        )

        # Should enumerate routes to 6103 and 6105 (destinations in forecast)
        assert len(model.destinations) == 2
        assert "6103" in model.destinations
        assert "6105" in model.destinations

        # Should have enumerated some routes
        assert len(model.enumerated_routes) > 0

        # Check route mappings exist
        assert len(model.route_destination) > 0
        assert len(model.route_cost) > 0
        assert len(model.route_transit_days) > 0

    def test_routes_to_destination_mapping(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test routes_to_destination mapping."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        # Should have routes to both destinations
        assert "6103" in model.routes_to_destination
        assert "6105" in model.routes_to_destination

        # Each destination should have at least one route
        assert len(model.routes_to_destination["6103"]) > 0
        assert len(model.routes_to_destination["6105"]) > 0


class TestIntegratedModelBuild:
    """Tests for building the integrated model."""

    def test_build_model_creates_variables(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that build_model creates expected variables."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        pyomo_model = model.build_model()

        # Check production variables exist
        assert hasattr(pyomo_model, 'production')
        assert hasattr(pyomo_model, 'labor_hours')

        # Check new shipment variables exist
        assert hasattr(pyomo_model, 'shipment')

    def test_build_model_creates_constraints(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that build_model creates expected constraints."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        pyomo_model = model.build_model()

        # Check production constraints exist
        assert hasattr(pyomo_model, 'labor_hours_con')
        assert hasattr(pyomo_model, 'max_hours_con')
        assert hasattr(pyomo_model, 'max_capacity_con')

        # Check new routing constraints exist
        assert hasattr(pyomo_model, 'demand_satisfaction_con')
        assert hasattr(pyomo_model, 'flow_conservation_con')

    def test_build_model_creates_objective(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that build_model creates objective function."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        pyomo_model = model.build_model()

        # Check objective exists
        assert hasattr(pyomo_model, 'obj')

    def test_get_model_statistics(
        self,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test getting model statistics."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
        )

        # Before build
        stats_before = model.get_model_statistics()
        assert stats_before['built'] is False
        assert stats_before['num_variables'] == 0

        # After build
        model.model = model.build_model()
        stats_after = model.get_model_statistics()
        assert stats_after['built'] is True
        assert stats_after['num_variables'] > 0
        assert stats_after['num_constraints'] > 0


class TestIntegratedModelSolve:
    """Tests for solving integrated model.

    These tests mock the solver to avoid requiring actual solver installation.
    """

    def test_solve_returns_result(
        self,
        mock_solver_config,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that solve returns OptimizationResult."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
            solver_config=mock_solver_config,
        )

        result = model.solve()

        assert isinstance(result, OptimizationResult)
        assert result.success is True

    def test_extract_solution_includes_shipments(
        self,
        mock_solver_config,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test solution extraction includes shipment data."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
            solver_config=mock_solver_config,
        )

        result = model.solve()
        solution = model.get_solution()

        assert solution is not None
        assert 'production_by_date_product' in solution
        assert 'production_batches' in solution  # New list format for UI
        assert 'shipments_by_route_product_date' in solution
        assert 'total_transport_cost' in solution
        assert 'total_cost' in solution

        # Verify production_batches structure
        assert isinstance(solution['production_batches'], list)
        if solution['production_batches']:
            batch = solution['production_batches'][0]
            assert 'date' in batch
            assert 'product' in batch
            assert 'quantity' in batch

    def test_get_shipment_plan(
        self,
        mock_solver_config,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test converting solution to shipment plan."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
            solver_config=mock_solver_config,
        )

        result = model.solve()
        shipments = model.get_shipment_plan()

        assert shipments is not None
        assert len(shipments) > 0
        # Each shipment should have required fields
        for shipment in shipments:
            assert shipment.id is not None
            assert shipment.product_id is not None
            assert shipment.quantity > 0
            assert shipment.origin_id == "6122"  # Manufacturing site
            assert shipment.destination_id in ["6103", "6105"]

    def test_print_solution_summary_no_errors(
        self,
        mock_solver_config,
        simple_forecast_disaggregated,
        simple_labor_calendar,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes,
        capsys
    ):
        """Test that print_solution_summary executes without errors."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast_disaggregated,
            labor_calendar=simple_labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=simple_network_locations,
            routes=simple_network_routes,
            solver_config=mock_solver_config,
        )

        result = model.solve()

        # Should not raise errors
        model.print_solution_summary()

        # Verify some output was produced
        captured = capsys.readouterr()
        assert len(captured.out) > 0
        assert "Integrated Production-Distribution Solution" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
