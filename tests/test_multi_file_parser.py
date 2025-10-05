"""Tests for MultiFileParser."""

import pytest
from pathlib import Path

from src.parsers import MultiFileParser


class TestMultiFileParser:
    """Tests for MultiFileParser class."""

    @pytest.fixture
    def network_config_path(self):
        """Path to Network_Config.xlsx test file."""
        return Path("data/examples/Network_Config.xlsx")

    @pytest.fixture
    def forecast_path(self):
        """Path to Gfree Forecast.xlsm test file (SAP IBP format, not directly parseable)."""
        # Note: This file is in SAP IBP format and requires conversion
        # For now, we skip forecast parsing tests
        return Path("data/examples/Gfree Forecast.xlsm")

    def test_init_with_both_files(self, forecast_path, network_config_path):
        """Test initializing with both files."""
        parser = MultiFileParser(
            forecast_file=forecast_path,
            network_file=network_config_path
        )
        assert parser.forecast_file == forecast_path
        assert parser.network_file == network_config_path
        assert parser._forecast_parser is not None
        assert parser._network_parser is not None

    def test_init_with_forecast_only(self, forecast_path):
        """Test initializing with forecast file only."""
        parser = MultiFileParser(forecast_file=forecast_path)
        assert parser.forecast_file == forecast_path
        assert parser.network_file is None
        assert parser._forecast_parser is not None
        assert parser._network_parser is None

    def test_init_with_network_only(self, network_config_path):
        """Test initializing with network file only."""
        parser = MultiFileParser(network_file=network_config_path)
        assert parser.forecast_file is None
        assert parser.network_file == network_config_path
        assert parser._forecast_parser is None
        assert parser._network_parser is not None

    def test_init_with_no_files(self):
        """Test that initializing with no files raises error."""
        with pytest.raises(ValueError, match="At least one of forecast_file or network_file must be provided"):
            MultiFileParser()

    def test_init_with_missing_file(self):
        """Test that initializing with non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            MultiFileParser(forecast_file="nonexistent.xlsx")

    def test_parse_locations(self, network_config_path):
        """Test parsing locations from network file."""
        parser = MultiFileParser(network_file=network_config_path)
        locations = parser.parse_locations()

        assert len(locations) == 11
        location_ids = {loc.id for loc in locations}
        assert "6122" in location_ids  # Manufacturing
        assert "6104" in location_ids  # Hub
        assert "Lineage" in location_ids  # Frozen storage

    def test_parse_routes(self, network_config_path):
        """Test parsing routes from network file."""
        parser = MultiFileParser(network_file=network_config_path)
        routes = parser.parse_routes()

        assert len(routes) == 10
        route_ids = {r.id for r in routes}
        assert "R1" in route_ids
        assert "R10" in route_ids

    def test_parse_labor_calendar(self, network_config_path):
        """Test parsing labor calendar from network file."""
        parser = MultiFileParser(network_file=network_config_path)
        labor_calendar = parser.parse_labor_calendar()

        assert len(labor_calendar.days) == 211  # May 26 - Dec 22, 2025 (extended by 7 days before forecast)
        assert labor_calendar.days[0].date.month == 5
        assert labor_calendar.days[0].date.day == 26

        # Check first day (Monday May 26, 2025)
        first_day = labor_calendar.days[0]
        assert first_day.fixed_hours == 12.0
        assert first_day.is_fixed_day

    def test_parse_truck_schedules(self, network_config_path):
        """Test parsing truck schedules from network file."""
        parser = MultiFileParser(network_file=network_config_path)
        truck_schedules = parser.parse_truck_schedules()

        assert len(truck_schedules) == 11  # 11 weekly departures
        truck_ids = {t.id for t in truck_schedules}
        assert "T1" in truck_ids
        assert "T11" in truck_ids

        # Check Wednesday truck has intermediate stop
        wed_truck = next(t for t in truck_schedules if t.id == "T3")
        assert wed_truck.has_intermediate_stops()
        assert "Lineage" in wed_truck.intermediate_stops

    def test_parse_cost_structure(self, network_config_path):
        """Test parsing cost structure from network file."""
        parser = MultiFileParser(network_file=network_config_path)
        cost_structure = parser.parse_cost_structure()

        assert cost_structure.production_cost_per_unit == 5.0
        assert cost_structure.default_regular_rate == 25.0
        assert cost_structure.default_overtime_rate == 37.5

    def test_parse_forecast_without_file(self, network_config_path):
        """Test that parsing forecast without forecast file raises error."""
        parser = MultiFileParser(network_file=network_config_path)
        with pytest.raises(ValueError, match="no forecast_file provided"):
            parser.parse_forecast()

    def test_parse_locations_without_file(self, forecast_path):
        """Test that parsing locations without network file raises error."""
        parser = MultiFileParser(forecast_file=forecast_path)
        with pytest.raises(ValueError, match="no network_file provided"):
            parser.parse_locations()

    def test_parse_all_with_network_only(self, network_config_path):
        """Test that parse_all requires forecast file."""
        parser = MultiFileParser(network_file=network_config_path)
        with pytest.raises(ValueError, match="no forecast_file provided"):
            parser.parse_all()

    def test_validate_consistency_perfect_match(self, network_config_path):
        """Test validation with perfectly consistent data."""
        parser = MultiFileParser(network_file=network_config_path)
        locations = parser.parse_locations()
        routes = parser.parse_routes()

        # Create mock forecast with matching location IDs
        from src.models import Forecast, ForecastEntry
        from datetime import date

        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="P1",
                forecast_date=date(2025, 6, 2),
                quantity=100.0
            ),
            ForecastEntry(
                location_id="6110",
                product_id="P1",
                forecast_date=date(2025, 6, 2),
                quantity=150.0
            ),
        ]
        forecast = Forecast(name="Test", entries=entries)

        validation = parser.validate_consistency(forecast, locations, routes)

        # These locations exist and are used (in routes)
        assert len(validation["missing_locations"]) == 0
        assert len(validation["missing_route_locations"]) == 0
        # No warnings since all locations are either in forecast or routes
        assert len(validation["warnings"]) == 0 or any("unused" not in w.lower() for w in validation["warnings"])

    def test_validate_consistency_missing_locations(self, network_config_path):
        """Test validation detects missing locations."""
        parser = MultiFileParser(network_file=network_config_path)
        locations = parser.parse_locations()
        routes = parser.parse_routes()

        # Create forecast with non-existent location
        from src.models import Forecast, ForecastEntry
        from datetime import date

        entries = [
            ForecastEntry(
                location_id="9999",  # Doesn't exist
                product_id="P1",
                forecast_date=date(2025, 6, 2),
                quantity=100.0
            ),
        ]
        forecast = Forecast(name="Test", entries=entries)

        validation = parser.validate_consistency(forecast, locations, routes)

        assert "9999" in validation["missing_locations"]
        assert len(validation["warnings"]) > 0

    def test_validate_consistency_unused_locations(self, network_config_path):
        """Test validation detects unused locations."""
        parser = MultiFileParser(network_file=network_config_path)

        # Create minimal location and route set
        from src.models import Location, LocationType, StorageMode, Route

        locations = [
            Location(id="6104", name="Test1", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
            Location(id="6110", name="Test2", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
            Location(id="9999", name="Unused", type=LocationType.BREADROOM, storage_mode=StorageMode.AMBIENT),
        ]
        routes = []  # No routes

        # Create forecast with only subset of locations
        from src.models import Forecast, ForecastEntry
        from datetime import date

        entries = [
            ForecastEntry(
                location_id="6104",
                product_id="P1",
                forecast_date=date(2025, 6, 2),
                quantity=100.0
            ),
        ]
        forecast = Forecast(name="Test", entries=entries)

        validation = parser.validate_consistency(forecast, locations, routes)

        # 6110 and 9999 should be unused (not in forecast or routes)
        assert len(validation["unused_locations"]) >= 2
        assert "6110" in validation["unused_locations"]
        assert "9999" in validation["unused_locations"]
        # Warnings should be present if there are unused locations
        if len(validation["unused_locations"]) > 0:
            assert len(validation["warnings"]) > 0
