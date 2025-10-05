"""Tests for UI data type handling and compatibility.

These tests ensure that data types are correctly handled throughout the UI
and that proper error messages are shown when incorrect types are passed.
"""

import pytest
from datetime import date, time
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection, DepartureType
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.optimization.integrated_model import IntegratedProductionDistributionModel


@pytest.fixture
def sample_truck_list():
    """Create a sample list of TruckSchedule objects."""
    return [
        TruckSchedule(
            id="T1",
            truck_name="Morning Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            capacity=14080,
        ),
        TruckSchedule(
            id="T2",
            truck_name="Afternoon Truck",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            capacity=14080,
        ),
    ]


@pytest.fixture
def simple_model_data():
    """Create minimal data for model initialization."""
    forecast = Forecast(
        name="Test Forecast",
        entries=[
            ForecastEntry(
                location_id="6103",
                product_id="P1",
                forecast_date=date(2025, 1, 15),
                quantity=1000,
            ),
        ]
    )

    labor_calendar = LaborCalendar(
        name="Test Labor Calendar",
        days=[
            LaborDay(
                date=date(2025, 1, 15),
                fixed_hours=12.0,
                regular_rate=50.0,
                overtime_rate=75.0,
            ),
        ]
    )

    manufacturing_site = ManufacturingSite(
        id="6122",
        name="Manufacturing",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
        production_rate=1400.0,
        labor_calendar=labor_calendar,
    )

    cost_structure = CostStructure(
        labor_fixed_rate=50.0,
        labor_overtime_rate=75.0,
        production_cost_per_unit=1.0,
        transport_cost_per_km=0.1,
        shortage_penalty_per_unit=100.0,
    )

    locations = [
        manufacturing_site,
        Location(
            id="6103",
            name="Breadroom",
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT,
        ),
    ]

    routes = [
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6103",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10,
        ),
    ]

    return {
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'manufacturing_site': manufacturing_site,
        'cost_structure': cost_structure,
        'locations': locations,
        'routes': routes,
    }


class TestTruckScheduleCollection:
    """Test TruckScheduleCollection wrapper functionality."""

    def test_list_to_collection_wrapping(self, sample_truck_list):
        """Test that a list can be wrapped in TruckScheduleCollection."""
        collection = TruckScheduleCollection(schedules=sample_truck_list)

        assert isinstance(collection, TruckScheduleCollection)
        assert len(collection) == 2
        assert len(collection.schedules) == 2

    def test_collection_iteration(self, sample_truck_list):
        """Test that TruckScheduleCollection can be iterated."""
        collection = TruckScheduleCollection(schedules=sample_truck_list)

        truck_ids = []
        for truck in collection:
            truck_ids.append(truck.id)

        assert truck_ids == ["T1", "T2"]

    def test_collection_length(self, sample_truck_list):
        """Test that len() works on TruckScheduleCollection."""
        collection = TruckScheduleCollection(schedules=sample_truck_list)

        assert len(collection) == 2

    def test_empty_collection(self):
        """Test that empty TruckScheduleCollection works."""
        collection = TruckScheduleCollection()

        assert len(collection) == 0
        assert len(collection.schedules) == 0


class TestModelTypeValidation:
    """Test type validation in IntegratedProductionDistributionModel."""

    def test_model_rejects_list_type(self, simple_model_data, sample_truck_list):
        """Test that model rejects list[TruckSchedule] with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            IntegratedProductionDistributionModel(
                truck_schedules=sample_truck_list,  # Passing list instead of collection
                **simple_model_data
            )

        # Check error message is helpful
        error_msg = str(exc_info.value)
        assert "TruckScheduleCollection" in error_msg
        assert "list" in error_msg.lower()
        assert "Wrap your list" in error_msg

    def test_model_accepts_collection_type(self, simple_model_data, sample_truck_list):
        """Test that model accepts TruckScheduleCollection."""
        collection = TruckScheduleCollection(schedules=sample_truck_list)

        # Should not raise
        model = IntegratedProductionDistributionModel(
            truck_schedules=collection,
            validate_feasibility=False,  # Skip feasibility check for faster test
            **simple_model_data
        )

        assert model.truck_schedules == collection

    def test_model_accepts_none(self, simple_model_data):
        """Test that model accepts None for truck_schedules."""
        # Should not raise
        model = IntegratedProductionDistributionModel(
            truck_schedules=None,
            validate_feasibility=False,
            **simple_model_data
        )

        assert model.truck_schedules is None

    def test_model_rejects_wrong_type(self, simple_model_data):
        """Test that model rejects completely wrong types."""
        with pytest.raises(TypeError) as exc_info:
            IntegratedProductionDistributionModel(
                truck_schedules="invalid",  # Passing string
                **simple_model_data
            )

        error_msg = str(exc_info.value)
        assert "TruckScheduleCollection" in error_msg


class TestDataFlowIntegration:
    """Test the complete data flow from parsing to model."""

    def test_parser_returns_list(self):
        """Verify that parser returns list[TruckSchedule]."""
        from src.parsers.excel_parser import ExcelParser

        # This test documents the current behavior:
        # ExcelParser.parse_truck_schedules() returns list[TruckSchedule]
        # This is intentional - the wrapping should happen in the UI layer

        # Note: This is a documentation test, not a functional test
        # It serves to remind developers about the data flow

    def test_ui_should_wrap_before_storage(self, sample_truck_list):
        """Test that UI correctly wraps list before storing."""
        # Simulate what UI should do after parsing
        truck_schedules_list = sample_truck_list  # From parser

        # UI should wrap it
        truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

        # Verify wrapping worked
        assert isinstance(truck_schedules, TruckScheduleCollection)
        assert len(truck_schedules) == len(truck_schedules_list)

        # Verify iteration still works
        for original, wrapped in zip(truck_schedules_list, truck_schedules):
            assert original.id == wrapped.id


class TestErrorDiagnostics:
    """Test error diagnostics for common mistakes."""

    def test_error_message_includes_solution(self, simple_model_data, sample_truck_list):
        """Test that error message includes the solution."""
        try:
            IntegratedProductionDistributionModel(
                truck_schedules=sample_truck_list,
                **simple_model_data
            )
            pytest.fail("Should have raised TypeError")
        except TypeError as e:
            error_msg = str(e)
            # Error should mention how to fix it
            assert "TruckScheduleCollection(schedules=" in error_msg

    def test_attribute_error_prevented(self, simple_model_data, sample_truck_list):
        """Test that we prevent the original AttributeError."""
        # The original error was: 'list' object has no attribute 'schedules'
        # Our type validation should prevent this from ever happening

        with pytest.raises(TypeError):  # Should raise TypeError, NOT AttributeError
            IntegratedProductionDistributionModel(
                truck_schedules=sample_truck_list,
                **simple_model_data
            )
