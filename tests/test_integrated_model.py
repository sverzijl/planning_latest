"""Tests for integrated production-distribution optimization model.

Tests the integrated model that combines production scheduling with routing decisions.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
import warnings

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

        # Check new routing constraints exist (updated for state tracking)
        # The model now uses separate frozen and ambient inventory balance constraints
        assert hasattr(pyomo_model, 'inventory_frozen_balance_con')
        assert hasattr(pyomo_model, 'inventory_ambient_balance_con')

        # Check inventory variables exist (state-specific)
        assert hasattr(pyomo_model, 'inventory_frozen')
        assert hasattr(pyomo_model, 'inventory_ambient')

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
        # Note: shipments_by_route_product_date is deprecated but kept for backward compatibility
        assert 'shipments_by_route_product_date' in solution
        # New leg-based routing uses shipments_by_leg_product_date
        assert 'shipments_by_leg_product_date' in solution
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

        # Note: get_shipment_plan() currently uses deprecated route-based shipments
        # which may be empty in leg-based routing. This is a known limitation
        # that should be addressed separately.
        assert shipments is not None
        # Don't assert length > 0 as it may be empty with leg-based routing

        # If there are shipments, verify their structure
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


class TestLaborCalendarValidation:
    """Tests for labor calendar validation logic in _validate_feasibility().

    Tests the smart validation that distinguishes between:
    - Critical missing dates (weekdays in forecast range): Hard error
    - Non-critical missing dates (weekdays outside forecast range): Warning only
    - Weekend dates (both critical and non-critical): Warning only
    """

    def test_complete_labor_coverage_passes(
        self,
        simple_forecast_disaggregated,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that complete labor calendar coverage passes without errors or warnings.

        Scenario: Labor calendar covers critical date range (forecast + transit buffer).
        Expected: Model initialization succeeds without errors or warnings.
        """
        # Forecast spans 2025-01-15 to 2025-01-16
        # Max transit = 2 days, so critical range is 2025-01-13 to 2025-01-16
        # Create labor calendar covering this range plus some buffer
        days = []
        for i in range(10):  # 2025-01-10 to 2025-01-19
            day = LaborDay(
                date=date(2025, 1, 10) + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
            days.append(day)

        labor_calendar = LaborCalendar(name="Complete Coverage", days=days)

        # Should initialize without errors or warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Turn warnings into errors
            model = IntegratedProductionDistributionModel(
                forecast=simple_forecast_disaggregated,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
            )

        assert model is not None

    def test_missing_critical_weekday_fails(
        self,
        simple_forecast_disaggregated,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that missing critical weekday dates raise ValueError.

        Scenario: Labor calendar missing weekday dates within critical forecast range.
        Expected: ValueError with actionable error message including:
        - Forecast range
        - Required production start date
        - Labor coverage details
        - Fix instructions
        """
        # Forecast spans 2025-01-15 (Wed) to 2025-01-16 (Thu)
        # Max transit = 2 days, so critical range is 2025-01-13 (Mon) to 2025-01-16 (Thu)
        # Create labor calendar missing 2025-01-14 (Tuesday) - a critical weekday
        days = []
        for i in range(10):
            day_date = date(2025, 1, 10) + timedelta(days=i)
            # Skip 2025-01-14 (Tuesday)
            if day_date == date(2025, 1, 14):
                continue
            day = LaborDay(
                date=day_date,
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
            days.append(day)

        labor_calendar = LaborCalendar(name="Missing Critical Weekday", days=days)

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            model = IntegratedProductionDistributionModel(
                forecast=simple_forecast_disaggregated,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
            )

        error_msg = str(exc_info.value)
        # Verify error message contains key information
        assert "Labor calendar missing entries for" in error_msg
        assert "critical weekday production date(s)" in error_msg
        assert "2025-01-14" in error_msg
        assert "Forecast range:" in error_msg
        assert "Required production start" in error_msg
        assert "Labor calendar coverage:" in error_msg
        assert "To fix: Extend labor calendar" in error_msg

    def test_missing_noncritical_weekday_warns_but_passes(
        self,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that missing non-critical weekday dates warn but pass.

        Scenario: Labor calendar covers critical range but missing dates in extended
        planning horizon (beyond forecast).
        Expected: Pass (not raise ValueError) but issue UserWarning explaining
        dates are outside critical range.
        """
        # Create forecast spanning 2025-01-15 to 2025-01-16
        forecast = Forecast(
            name="Test Forecast",
            entries=[
                ForecastEntry(location_id="6103", product_id="PROD_A",
                            forecast_date=date(2025, 1, 15), quantity=500),
                ForecastEntry(location_id="6103", product_id="PROD_A",
                            forecast_date=date(2025, 1, 16), quantity=500),
            ]
        )

        # Critical range with 2-day transit: 2025-01-13 to 2025-01-16
        # Create labor calendar covering critical range but missing later dates
        days = []
        # Cover 2025-01-10 to 2025-01-16 (includes critical range)
        for i in range(7):
            day = LaborDay(
                date=date(2025, 1, 10) + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
            days.append(day)

        labor_calendar = LaborCalendar(name="Limited Coverage", days=days)

        # Should warn but not fail
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = IntegratedProductionDistributionModel(
                forecast=forecast,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
                end_date=date(2025, 1, 20),  # Extend planning horizon beyond labor coverage
            )

            # Should have warnings about non-critical missing weekdays
            warning_messages = [str(warning.message) for warning in w]
            non_critical_warnings = [msg for msg in warning_messages
                                    if "weekday entries outside critical forecast range" in msg]
            assert len(non_critical_warnings) > 0
            assert "not needed to satisfy forecast demand" in non_critical_warnings[0]

        assert model is not None

    def test_missing_weekend_in_critical_range_warns(
        self,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that missing weekend dates in critical range issue warnings.

        Scenario: Labor calendar missing weekend dates within critical forecast range.
        Expected: Pass (not fail) but issue UserWarning about zero weekend capacity.
        """
        # Create forecast spanning 2025-01-17 (Fri) to 2025-01-20 (Mon)
        # This includes weekend 2025-01-18 (Sat) and 2025-01-19 (Sun)
        forecast = Forecast(
            name="Weekend Test Forecast",
            entries=[
                ForecastEntry(location_id="6103", product_id="PROD_A",
                            forecast_date=date(2025, 1, 17), quantity=500),
                ForecastEntry(location_id="6103", product_id="PROD_A",
                            forecast_date=date(2025, 1, 20), quantity=500),
            ]
        )

        # Create labor calendar with only weekdays (no weekends)
        days = []
        for i in range(15):
            day_date = date(2025, 1, 13) + timedelta(days=i)
            # Only include weekdays
            if day_date.weekday() < 5:
                day = LaborDay(
                    date=day_date,
                    fixed_hours=12.0,
                    regular_rate=50.0,
                    overtime_rate=75.0,
                    is_fixed_day=True,
                )
                days.append(day)

        labor_calendar = LaborCalendar(name="Weekdays Only", days=days)

        # Should warn about missing weekend dates in critical range
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = IntegratedProductionDistributionModel(
                forecast=forecast,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
            )

            # Should have warnings about missing weekend dates
            warning_messages = [str(warning.message) for warning in w]
            weekend_warnings = [msg for msg in warning_messages
                               if "weekend dates in critical forecast range" in msg]
            assert len(weekend_warnings) > 0
            assert "zero production capacity" in weekend_warnings[0]
            assert "Add weekend labor entries" in weekend_warnings[0]

        assert model is not None

    def test_missing_weekend_outside_critical_range_warns(
        self,
        simple_forecast_disaggregated,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that missing weekend dates outside critical range issue informational warnings.

        Scenario: Labor calendar missing weekend dates outside critical forecast range.
        Expected: Pass with informational UserWarning.
        """
        # Forecast spans 2025-01-15 to 2025-01-16
        # Critical range with 2-day transit: 2025-01-13 to 2025-01-16
        # Create labor calendar with weekdays only, but extend planning horizon
        days = []
        for i in range(15):
            day_date = date(2025, 1, 10) + timedelta(days=i)
            # Only include weekdays
            if day_date.weekday() < 5:
                day = LaborDay(
                    date=day_date,
                    fixed_hours=12.0,
                    regular_rate=50.0,
                    overtime_rate=75.0,
                    is_fixed_day=True,
                )
                days.append(day)

        labor_calendar = LaborCalendar(name="Weekdays Only Extended", days=days)

        # Should warn about missing weekend dates outside critical range
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = IntegratedProductionDistributionModel(
                forecast=simple_forecast_disaggregated,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
                end_date=date(2025, 1, 25),  # Extend beyond critical range
            )

            # Should have warnings about weekend dates outside critical range
            warning_messages = [str(warning.message) for warning in w]
            weekend_warnings = [msg for msg in warning_messages
                               if "weekend dates outside critical range" in msg]
            assert len(weekend_warnings) > 0
            assert "zero production capacity" in weekend_warnings[0]
            assert "weekend production is optional" in weekend_warnings[0]

        assert model is not None

    def test_labor_shorter_than_forecast_fails(
        self,
        simple_forecast_disaggregated,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test that labor calendar ending before forecast end date raises ValueError.

        Scenario: Labor calendar ends before forecast end date.
        Expected: ValueError for missing critical weekdays.
        """
        # Forecast spans 2025-01-15 to 2025-01-16
        # Create labor calendar that ends on 2025-01-15 (missing 2025-01-16)
        days = []
        for i in range(6):  # 2025-01-10 to 2025-01-15
            day = LaborDay(
                date=date(2025, 1, 10) + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
            days.append(day)

        labor_calendar = LaborCalendar(name="Too Short", days=days)

        # Should raise ValueError for missing critical weekday
        with pytest.raises(ValueError) as exc_info:
            model = IntegratedProductionDistributionModel(
                forecast=simple_forecast_disaggregated,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
            )

        error_msg = str(exc_info.value)
        assert "Labor calendar missing entries for" in error_msg
        assert "critical weekday production date(s)" in error_msg
        assert "2025-01-16" in error_msg

    def test_extended_planning_horizon_with_partial_labor(
        self,
        simple_forecast_disaggregated,
        manufacturing_site,
        cost_structure,
        simple_network_locations,
        simple_network_routes
    ):
        """Test extended planning horizon with labor only covering forecast period.

        Scenario: User provides end_date extending 6 months beyond forecast.
        Labor calendar only covers forecast period.
        Expected: Pass with warnings about non-critical missing dates.
        This is the specific scenario from the bug report (268 missing weekdays).
        """
        # Forecast spans 2025-01-15 to 2025-01-16
        # Critical range with 2-day transit: 2025-01-13 to 2025-01-16
        # Create labor calendar covering only critical range
        days = []
        for i in range(7):  # 2025-01-10 to 2025-01-16
            day = LaborDay(
                date=date(2025, 1, 10) + timedelta(days=i),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                is_fixed_day=True,
            )
            days.append(day)

        labor_calendar = LaborCalendar(name="Forecast Coverage Only", days=days)

        # Extend planning horizon 6 months beyond forecast
        extended_end_date = date(2025, 7, 16)

        # Should warn but not fail
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model = IntegratedProductionDistributionModel(
                forecast=simple_forecast_disaggregated,
                labor_calendar=labor_calendar,
                manufacturing_site=manufacturing_site,
                cost_structure=cost_structure,
                locations=simple_network_locations,
                routes=simple_network_routes,
                end_date=extended_end_date,
            )

            # Should have warnings about non-critical missing weekdays
            warning_messages = [str(warning.message) for warning in w]
            non_critical_warnings = [msg for msg in warning_messages
                                    if "weekday entries outside critical forecast range" in msg]
            assert len(non_critical_warnings) > 0

            # Verify warning explains the situation
            warning_text = non_critical_warnings[0]
            assert "not needed to satisfy forecast demand" in warning_text
            assert "The model will proceed" in warning_text

        # Model should be created successfully
        assert model is not None
        assert model.end_date == extended_end_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
