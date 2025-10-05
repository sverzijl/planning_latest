"""Unit tests for data validator."""

import pytest
from datetime import datetime, date, timedelta, time
from src.validation import DataValidator, ValidationIssue, ValidationSeverity
from src.models import (
    Forecast, ForecastEntry, Location, LocationType, StorageMode,
    Route, LaborCalendar, LaborDay, TruckSchedule, DepartureType, DayOfWeek,
    CostStructure, ManufacturingSite, Product
)


@pytest.fixture
def sample_forecast():
    """Create sample forecast data."""
    entries = []
    start_date = date(2025, 1, 1)

    # Normal demand
    for i in range(30):
        entries.append(ForecastEntry(
            location_id="6104",
            product_id="PROD1",
            forecast_date=start_date + timedelta(days=i),
            quantity=1000
        ))

    return Forecast(name="Test Forecast", entries=entries)


@pytest.fixture
def sample_locations():
    """Create sample location data."""
    return [
        Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.AMBIENT,
            capacity=100000
        ),
        Location(
            id="6104",
            name="NSW Hub",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.AMBIENT,
            capacity=50000
        ),
        Location(
            id="6125",
            name="VIC Hub",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.AMBIENT,
            capacity=50000
        ),
    ]


@pytest.fixture
def sample_routes(sample_locations):
    """Create sample route data."""
    return [
        Route(
            id="R1",
            origin_id="6122",
            destination_id="6104",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1,
            cost=0.10
        ),
        Route(
            id="R2",
            origin_id="6122",
            destination_id="6125",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1,
            cost=0.10
        ),
    ]


@pytest.fixture
def sample_labor_calendar():
    """Create sample labor calendar."""
    days = []
    start_date = date(2025, 1, 1)

    for i in range(60):
        current_date = start_date + timedelta(days=i)
        is_weekend = current_date.weekday() >= 5

        days.append(LaborDay(
            date=current_date,
            fixed_hours=0 if is_weekend else 12,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=50.0,
            is_fixed_day=not is_weekend,
            minimum_hours=4.0 if is_weekend else 0.0
        ))

    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def sample_truck_schedules():
    """Create sample truck schedules."""
    return [
        TruckSchedule(
            id="T1",
            truck_name="Morning to VIC",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            capacity=14080.0,
            pallet_capacity=44,
            units_per_pallet=320,
            units_per_case=10,
            day_of_week=DayOfWeek.MONDAY
        ),
        TruckSchedule(
            id="T2",
            truck_name="Afternoon to NSW",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id="6104",
            capacity=14080.0,
            pallet_capacity=44,
            units_per_pallet=320,
            units_per_case=10,
            day_of_week=DayOfWeek.MONDAY
        ),
    ]


@pytest.fixture
def sample_cost_structure():
    """Create sample cost structure."""
    return CostStructure(
        production_cost_per_unit=0.50,
        storage_cost_ambient_per_unit_day=0.01,
        waste_cost_multiplier=2.0
    )


@pytest.fixture
def sample_manufacturing_site(sample_labor_calendar):
    """Create sample manufacturing site."""
    return ManufacturingSite(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.AMBIENT,
        capacity=100000,
        production_rate=1400.0,
        labor_calendar=sample_labor_calendar,
        changeover_time_hours=0.5
    )


class TestCompletenessChecks:
    """Test completeness validation."""

    def test_no_forecast_critical(self):
        """Test that missing forecast is detected as critical."""
        validator = DataValidator(forecast=None)
        issues = validator.validate_all()

        forecast_issues = [i for i in issues if i.id == "COMPL_001"]
        assert len(forecast_issues) == 1
        assert forecast_issues[0].severity == ValidationSeverity.CRITICAL
        assert "forecast" in forecast_issues[0].title.lower()

    def test_empty_forecast_critical(self):
        """Test that empty forecast is detected as critical."""
        forecast = Forecast(name="Empty Forecast", entries=[])
        validator = DataValidator(forecast=forecast)
        issues = validator.validate_all()

        forecast_issues = [i for i in issues if i.id == "COMPL_001"]
        assert len(forecast_issues) == 1

    def test_no_locations_critical(self, sample_forecast):
        """Test that missing locations is critical."""
        validator = DataValidator(forecast=sample_forecast, locations=None)
        issues = validator.validate_all()

        location_issues = [i for i in issues if i.id == "COMPL_002"]
        assert len(location_issues) == 1
        assert location_issues[0].severity == ValidationSeverity.CRITICAL

    def test_no_routes_critical(self, sample_forecast, sample_locations):
        """Test that missing routes is critical."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=None
        )
        issues = validator.validate_all()

        route_issues = [i for i in issues if i.id == "COMPL_003"]
        assert len(route_issues) == 1
        assert route_issues[0].severity == ValidationSeverity.CRITICAL

    def test_no_labor_calendar_critical(self, sample_forecast, sample_locations, sample_routes):
        """Test that missing labor calendar is critical."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=None
        )
        issues = validator.validate_all()

        labor_issues = [i for i in issues if i.id == "COMPL_004"]
        assert len(labor_issues) == 1
        assert labor_issues[0].severity == ValidationSeverity.CRITICAL

    def test_no_manufacturing_location_critical(self, sample_forecast):
        """Test that missing manufacturing location is critical."""
        # Create locations without manufacturing type
        locations = [
            Location(
                id="6104",
                name="Hub",
                type=LocationType.STORAGE,
                storage_mode=StorageMode.AMBIENT
            )
        ]

        validator = DataValidator(
            forecast=sample_forecast,
            locations=locations,
            manufacturing_site=None
        )
        issues = validator.validate_all()

        mfg_issues = [i for i in issues if i.id == "COMPL_007"]
        assert len(mfg_issues) == 1
        assert mfg_issues[0].severity == ValidationSeverity.CRITICAL

    def test_all_data_present_passes(
        self,
        sample_forecast,
        sample_locations,
        sample_routes,
        sample_labor_calendar,
        sample_truck_schedules,
        sample_cost_structure,
        sample_manufacturing_site
    ):
        """Test that having all data doesn't trigger completeness issues."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar,
            truck_schedules=sample_truck_schedules,
            cost_structure=sample_cost_structure,
            manufacturing_site=sample_manufacturing_site
        )
        issues = validator.validate_all()

        # Should have no completeness issues
        completeness_issues = [i for i in issues if i.category == "Completeness"]
        assert len(completeness_issues) == 0


class TestConsistencyChecks:
    """Test consistency validation."""

    def test_forecast_invalid_location(self, sample_locations, sample_routes):
        """Test detection of forecast referencing invalid location."""
        # Create forecast with invalid location
        entries = [
            ForecastEntry(
                location_id="INVALID_LOC",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1),
                quantity=1000
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes
        )
        issues = validator.validate_all()

        invalid_loc_issues = [i for i in issues if i.id == "CONS_001"]
        assert len(invalid_loc_issues) == 1
        assert invalid_loc_issues[0].severity == ValidationSeverity.ERROR

    def test_route_invalid_origin(self, sample_forecast, sample_locations):
        """Test detection of route with invalid origin."""
        routes = [
            Route(
                id="R3",
                transport_mode=StorageMode.AMBIENT,
                origin_id="INVALID_ORIGIN",
                destination_id="6104",
                transit_time_days=1,
                cost=0.10
            )
        ]

        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=routes
        )
        issues = validator.validate_all()

        invalid_origin_issues = [i for i in issues if i.id == "CONS_002"]
        assert len(invalid_origin_issues) == 1

    def test_route_invalid_destination(self, sample_forecast, sample_locations):
        """Test detection of route with invalid destination."""
        routes = [
            Route(
                id="R4",
                transport_mode=StorageMode.AMBIENT,
                origin_id="6122",
                destination_id="INVALID_DEST",
                transit_time_days=1,
                cost=0.10
            )
        ]

        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=routes
        )
        issues = validator.validate_all()

        invalid_dest_issues = [i for i in issues if i.id == "CONS_003"]
        assert len(invalid_dest_issues) == 1

    def test_truck_schedule_invalid_destination(self, sample_forecast, sample_locations, sample_routes):
        """Test detection of truck schedule with invalid destination."""
        truck_schedules = [
            TruckSchedule(
                id="TEST1",
                truck_name="Test Truck",
                departure_type=DepartureType.MORNING,
                departure_time=time(8, 0),
                destination_id="INVALID_DEST",
                capacity=14080.0,
                day_of_week=DayOfWeek.MONDAY
            )
        ]

        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            truck_schedules=truck_schedules
        )
        issues = validator.validate_all()

        invalid_truck_issues = [i for i in issues if i.id == "CONS_004"]
        assert len(invalid_truck_issues) == 1
        assert invalid_truck_issues[0].severity == ValidationSeverity.WARNING


class TestProductionCapacityChecks:
    """Test production capacity validation."""

    def test_demand_exceeds_absolute_capacity(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of demand exceeding absolute capacity."""
        # Create extremely high demand
        entries = []
        start_date = date(2025, 1, 1)

        for i in range(30):
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=start_date + timedelta(days=i),
                quantity=100000  # Way over capacity
            ))

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        capacity_issues = [i for i in issues if i.id == "CAP_001"]
        assert len(capacity_issues) == 1
        assert capacity_issues[0].severity == ValidationSeverity.CRITICAL

    def test_demand_requires_weekend_work(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of demand requiring weekend production."""
        # Create demand that needs weekends but not impossible
        # 5 weekdays × 19,600 = 98,000 capacity
        # Create demand of 110,000 to require weekends
        entries = []
        start_date = date(2025, 1, 6)  # Monday

        for i in range(7):  # One week
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=start_date + timedelta(days=i),
                quantity=16000  # 112,000 total > 98,000
            ))

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        weekend_issues = [i for i in issues if i.id == "CAP_002"]
        assert len(weekend_issues) == 1
        assert weekend_issues[0].severity == ValidationSeverity.ERROR

    def test_demand_requires_overtime(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of demand requiring overtime."""
        # Create demand that needs overtime but no weekends
        # Regular capacity: 5 days × 16,800 = 84,000
        # Create demand of 90,000
        entries = []
        start_date = date(2025, 1, 6)  # Monday

        for i in range(5):  # Weekdays only
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=start_date + timedelta(days=i),
                quantity=18000  # 90,000 total
            ))

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        overtime_issues = [i for i in issues if i.id == "CAP_003"]
        assert len(overtime_issues) == 1
        assert overtime_issues[0].severity == ValidationSeverity.WARNING

    def test_capacity_sufficient_info(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test that sufficient capacity generates info message."""
        # Create low demand well within capacity
        entries = []
        start_date = date(2025, 1, 6)  # Monday

        for i in range(5):
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=start_date + timedelta(days=i),
                quantity=10000  # 50,000 total, well under 84,000
            ))

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        capacity_ok_issues = [i for i in issues if i.id == "CAP_004"]
        assert len(capacity_ok_issues) == 1
        assert capacity_ok_issues[0].severity == ValidationSeverity.INFO

    def test_daily_demand_exceeds_capacity(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of single day exceeding capacity."""
        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 6),
                quantity=25000  # Exceeds 19,600 daily max
            )
        ]

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        daily_issues = [i for i in issues if i.id == "CAP_005"]
        assert len(daily_issues) == 1
        assert daily_issues[0].severity == ValidationSeverity.CRITICAL


class TestShelfLifeChecks:
    """Test shelf life validation."""

    def test_long_transit_route_warning(self, sample_forecast, sample_locations):
        """Test detection of routes with long transit times."""
        routes = [
            Route(
                id="R5",
                transport_mode=StorageMode.AMBIENT,
                origin_id="6122",
                destination_id="6104",
                transit_time_days=15,  # Exceeds 10-day threshold
                cost=0.10
            )
        ]

        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=routes
        )
        issues = validator.validate_all()

        shelf_life_issues = [i for i in issues if i.id == "SHELF_001"]
        assert len(shelf_life_issues) == 1
        assert shelf_life_issues[0].severity == ValidationSeverity.WARNING

    def test_destination_needs_frozen_transport(self, sample_locations):
        """Test detection of destinations needing frozen transport."""
        # Create forecast for destination with very long transit
        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1),
                quantity=1000
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        # Create route that leaves insufficient shelf life
        # Transit 12 days, leaves 17-12=5 days, which is < 7 day minimum
        routes = [
            Route(
                id="R6",
                transport_mode=StorageMode.AMBIENT,
                origin_id="6122",
                destination_id="6104",
                transit_time_days=12,
                cost=0.10
            )
        ]

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=routes
        )
        issues = validator.validate_all()

        frozen_needed_issues = [i for i in issues if i.id == "SHELF_002"]
        assert len(frozen_needed_issues) == 1
        assert frozen_needed_issues[0].severity == ValidationSeverity.ERROR


class TestDateRangeChecks:
    """Test date range validation."""

    def test_forecast_in_past_warning(self, sample_locations, sample_routes):
        """Test detection of old forecast data."""
        # Create forecast starting 30 days ago
        old_date = date.today() - timedelta(days=30)
        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=old_date,
                quantity=1000
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes
        )
        issues = validator.validate_all()

        past_issues = [i for i in issues if i.id == "DATE_001"]
        assert len(past_issues) == 1
        assert past_issues[0].severity == ValidationSeverity.WARNING

    def test_labor_calendar_gap_error(self, sample_locations, sample_routes):
        """Test detection of labor calendar not covering forecast."""
        # Forecast in future
        future_start = date(2025, 6, 1)
        entries = []
        for i in range(30):
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=future_start + timedelta(days=i),
                quantity=1000
            ))
        forecast = Forecast(name="Test", entries=entries)

        # Labor calendar only covers January
        labor_days = []
        for i in range(31):
            labor_days.append(LaborDay(
                date=date(2025, 1, 1) + timedelta(days=i),
                fixed_hours=12,
                regular_rate=25.0,
                overtime_rate=37.5,
                non_fixed_rate=50.0
            ))
        labor_calendar = LaborCalendar(name="Test Calendar", days=labor_days)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=labor_calendar
        )
        issues = validator.validate_all()

        calendar_gap_issues = [i for i in issues if i.id == "DATE_002"]
        assert len(calendar_gap_issues) == 1
        assert calendar_gap_issues[0].severity == ValidationSeverity.ERROR

    def test_short_planning_horizon_warning(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of very short planning horizon."""
        # Create forecast for only 3 days
        entries = []
        for i in range(3):
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1) + timedelta(days=i),
                quantity=1000
            ))
        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        short_horizon_issues = [i for i in issues if i.id == "DATE_003"]
        assert len(short_horizon_issues) == 1
        assert short_horizon_issues[0].severity == ValidationSeverity.WARNING


class TestDataQualityChecks:
    """Test data quality validation."""

    def test_outlier_detection(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of outlier values."""
        entries = []
        # Normal values
        for i in range(20):
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1) + timedelta(days=i),
                quantity=1000
            ))

        # Add outlier
        entries.append(ForecastEntry(
            location_id="6104",
            product_id="PROD1",
            forecast_date=date(2025, 1, 21),
            quantity=50000  # Way higher than normal
        ))

        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        outlier_issues = [i for i in issues if i.id == "QUAL_001"]
        assert len(outlier_issues) == 1
        assert outlier_issues[0].severity == ValidationSeverity.WARNING

    def test_zero_quantity_warning(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of zero quantities."""
        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1),
                quantity=0
            ),
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 2),
                quantity=-100  # Negative
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        zero_qty_issues = [i for i in issues if i.id == "QUAL_002"]
        assert len(zero_qty_issues) == 1
        assert zero_qty_issues[0].severity == ValidationSeverity.WARNING

    def test_non_case_quantity_info(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of non-case quantities."""
        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=date(2025, 1, 1),
                quantity=1005  # Not multiple of 10
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        non_case_issues = [i for i in issues if i.id == "QUAL_003"]
        assert len(non_case_issues) == 1
        assert non_case_issues[0].severity == ValidationSeverity.INFO


class TestBusinessRuleChecks:
    """Test business rule validation."""

    def test_unreachable_destination_critical(self, sample_locations, sample_labor_calendar):
        """Test detection of unreachable destinations."""
        # Create forecast for location not in routes
        entries = [
            ForecastEntry(
                location_id="6999",  # Not reachable
                product_id="PROD1",
                forecast_date=date(2025, 1, 1),
                quantity=1000
            )
        ]
        forecast = Forecast(name="Test", entries=entries)

        # Add the destination to locations but not routes
        locations = sample_locations + [
            Location(
                id="6999",
                name="Unreachable",
                type=LocationType.BREADROOM,
                storage_mode=StorageMode.AMBIENT
            )
        ]

        # Routes don't include 6999
        routes = [
            Route(
                id="R7",
                transport_mode=StorageMode.AMBIENT,
                origin_id="6122",
                destination_id="6104",
                transit_time_days=1,
                cost=0.10
            )
        ]

        validator = DataValidator(
            forecast=forecast,
            locations=locations,
            routes=routes,
            labor_calendar=sample_labor_calendar
        )
        issues = validator.validate_all()

        unreachable_issues = [i for i in issues if i.id == "RULE_003"]
        assert len(unreachable_issues) == 1
        assert unreachable_issues[0].severity == ValidationSeverity.CRITICAL


class TestValidatorMethods:
    """Test validator helper methods."""

    def test_get_summary_stats(self, sample_forecast, sample_locations, sample_routes, sample_labor_calendar):
        """Test summary statistics generation."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar
        )
        validator.validate_all()

        stats = validator.get_summary_stats()

        assert 'total_issues' in stats
        assert 'by_severity' in stats
        assert 'by_category' in stats
        assert isinstance(stats['total_issues'], int)

    def test_has_critical_issues(self, sample_forecast, sample_locations):
        """Test critical issue detection."""
        # No routes - should trigger critical
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=None
        )
        validator.validate_all()

        assert validator.has_critical_issues() is True

    def test_has_no_critical_issues(
        self,
        sample_forecast,
        sample_locations,
        sample_routes,
        sample_labor_calendar,
        sample_truck_schedules,
        sample_cost_structure,
        sample_manufacturing_site
    ):
        """Test when no critical issues exist."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar,
            truck_schedules=sample_truck_schedules,
            cost_structure=sample_cost_structure,
            manufacturing_site=sample_manufacturing_site
        )
        validator.validate_all()

        # Should have no critical issues with complete valid data
        assert validator.has_critical_issues() is False

    def test_is_planning_feasible(
        self,
        sample_forecast,
        sample_locations,
        sample_routes,
        sample_labor_calendar,
        sample_truck_schedules,
        sample_cost_structure,
        sample_manufacturing_site
    ):
        """Test planning feasibility check."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar,
            truck_schedules=sample_truck_schedules,
            cost_structure=sample_cost_structure,
            manufacturing_site=sample_manufacturing_site
        )
        validator.validate_all()

        # With valid complete data, planning should be feasible
        assert validator.is_planning_feasible() is True


class TestTransportCapacityChecks:
    """Test transport capacity validation."""

    def test_no_truck_schedules_warning(self, sample_forecast, sample_locations, sample_routes):
        """Test warning when no truck schedules defined."""
        validator = DataValidator(
            forecast=sample_forecast,
            locations=sample_locations,
            routes=sample_routes,
            truck_schedules=None
        )
        issues = validator.validate_all()

        no_trucks_issues = [i for i in issues if i.id == "TRANS_001"]
        assert len(no_trucks_issues) == 1
        assert no_trucks_issues[0].severity == ValidationSeverity.WARNING

    def test_demand_exceeds_truck_capacity(self, sample_locations, sample_routes, sample_labor_calendar):
        """Test detection of demand exceeding truck capacity."""
        # Create high demand over 4 weeks
        # 2 trucks/week × 14,080 capacity × 4 weeks = 112,640 capacity
        # Create demand of 150,000
        entries = []
        start_date = date(2025, 1, 6)  # Monday

        for i in range(28):  # 4 weeks
            entries.append(ForecastEntry(
                location_id="6104",
                product_id="PROD1",
                forecast_date=start_date + timedelta(days=i),
                quantity=5400  # ~151,000 total
            ))

        forecast = Forecast(name="Test", entries=entries)

        # 2 trucks per week
        truck_schedules = [
            TruckSchedule(
                id="TRUCK1",
                truck_name="Truck1",
                departure_type=DepartureType.MORNING,
                departure_time=time(8, 0),
                destination_id="6104",
                capacity=14080.0,
                day_of_week=DayOfWeek.MONDAY
            ),
            TruckSchedule(
                id="TRUCK2",
                truck_name="Truck2",
                departure_type=DepartureType.AFTERNOON,
                departure_time=time(14, 0),
                destination_id="6104",
                capacity=14080.0,
                day_of_week=DayOfWeek.MONDAY
            ),
        ]

        validator = DataValidator(
            forecast=forecast,
            locations=sample_locations,
            routes=sample_routes,
            labor_calendar=sample_labor_calendar,
            truck_schedules=truck_schedules
        )
        issues = validator.validate_all()

        truck_capacity_issues = [i for i in issues if i.id == "TRANS_002"]
        assert len(truck_capacity_issues) == 1
        assert truck_capacity_issues[0].severity == ValidationSeverity.ERROR
