"""Regression tests for backward compatibility with alias resolution."""

import pytest
from pathlib import Path
from datetime import date
import pandas as pd

from src.parsers.excel_parser import ExcelParser
from src.parsers.sap_ibp_parser import SapIbpParser
from src.parsers.multi_file_parser import MultiFileParser


@pytest.fixture
def legacy_forecast_file(tmp_path):
    """Create a legacy forecast file (no aliases, standard product names)."""
    file_path = tmp_path / "legacy_forecast.xlsx"

    forecast_data = {
        'location_id': ['6122', '6122'],
        'product_id': ['BREAD_WHITE', 'BREAD_MULTIGRAIN'],
        'date': [date(2025, 1, 1), date(2025, 1, 1)],
        'quantity': [100.0, 200.0],
    }
    forecast_df = pd.DataFrame(forecast_data)

    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

    return file_path


@pytest.fixture
def legacy_network_file(tmp_path):
    """Create a legacy network config file (no Alias sheet)."""
    file_path = tmp_path / "legacy_network.xlsx"

    locations_data = {
        'id': ['6122', '6104'],
        'name': ['Manufacturing', 'Hub NSW'],
        'type': ['manufacturing', 'storage'],
        'storage_mode': ['ambient', 'ambient'],
        'production_rate': [1400.0, None],
    }
    locations_df = pd.DataFrame(locations_data)

    routes_data = {
        'id': ['R1'],
        'origin_id': ['6122'],
        'destination_id': ['6104'],
        'transport_mode': ['ambient'],
        'transit_time_days': [1.0],
    }
    routes_df = pd.DataFrame(routes_data)

    labor_data = {
        'date': [date(2025, 1, 1)],
        'fixed_hours': [12.0],
        'regular_rate': [20.0],
        'overtime_rate': [30.0],
    }
    labor_df = pd.DataFrame(labor_data)

    trucks_data = {
        'id': ['T1'],
        'truck_name': ['Morning NSW'],
        'departure_type': ['morning'],
        'departure_time': ['08:00:00'],
        'destination_id': ['6104'],
        'capacity': [14080.0],
    }
    trucks_df = pd.DataFrame(trucks_data)

    costs_data = {
        'cost_type': ['production_cost_per_unit', 'shortage_penalty_per_unit'],
        'value': [0.5, 10.0],
    }
    costs_df = pd.DataFrame(costs_data)

    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        locations_df.to_excel(writer, sheet_name='Locations', index=False)
        routes_df.to_excel(writer, sheet_name='Routes', index=False)
        labor_df.to_excel(writer, sheet_name='LaborCalendar', index=False)
        trucks_df.to_excel(writer, sheet_name='TruckSchedules', index=False)
        costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

    return file_path


class TestExcelParserBackwardCompatibility:
    """Tests for ExcelParser backward compatibility."""

    def test_parse_forecast_without_resolver_parameter(self, legacy_forecast_file):
        """Test that ExcelParser works without product_alias_resolver parameter."""
        # Create parser without resolver (original behavior)
        parser = ExcelParser(legacy_forecast_file)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check that parsing works
        assert len(forecast.entries) == 2

        # Product IDs should be preserved as-is
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids
        assert 'BREAD_MULTIGRAIN' in product_ids

    def test_parse_forecast_with_none_resolver(self, legacy_forecast_file):
        """Test that ExcelParser works with product_alias_resolver=None."""
        # Create parser with explicit None resolver
        parser = ExcelParser(legacy_forecast_file, product_alias_resolver=None)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Should behave same as without parameter
        assert len(forecast.entries) == 2
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids

    def test_all_parser_methods_work_without_resolver(self, legacy_network_file):
        """Test that all parser methods work without resolver."""
        # Create parser without resolver
        parser = ExcelParser(legacy_network_file)

        # All methods should work
        locations = parser.parse_locations()
        assert len(locations) == 2

        routes = parser.parse_routes()
        assert len(routes) == 1

        labor = parser.parse_labor_calendar()
        assert len(labor.days) == 1

        trucks = parser.parse_truck_schedules()
        assert len(trucks) == 1

        costs = parser.parse_cost_structure()
        assert costs.production_cost_per_unit == 0.5


class TestMultiFileParserBackwardCompatibility:
    """Tests for MultiFileParser backward compatibility."""

    def test_parse_without_network_file(self, legacy_forecast_file):
        """Test MultiFileParser with only forecast file (no network file)."""
        # Create parser with only forecast file
        parser = MultiFileParser(forecast_file=legacy_forecast_file)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Should work normally
        assert len(forecast.entries) == 2
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids

    def test_parse_without_alias_sheet(self, legacy_forecast_file, legacy_network_file):
        """Test MultiFileParser with network file that has no Alias sheet."""
        # Create parser
        parser = MultiFileParser(
            forecast_file=legacy_forecast_file,
            network_file=legacy_network_file
        )

        # Resolver should be None OR exist but be empty (no mappings)
        # The implementation catches the exception when Alias sheet is missing
        if parser._product_alias_resolver is not None:
            # If resolver exists, it should have no mappings
            assert parser._product_alias_resolver.get_mapping_count() == 0
        # else: resolver is None, which is also acceptable

        # Parse all data
        forecast, locations, routes, labor, trucks, costs = parser.parse_all()

        # All parsing should work
        assert len(forecast.entries) == 2
        assert len(locations) == 2
        assert len(routes) == 1
        assert len(labor.days) == 1
        assert len(trucks) == 1

        # Product IDs should be preserved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids
        assert 'BREAD_MULTIGRAIN' in product_ids

    def test_parse_only_network_file(self, legacy_network_file):
        """Test MultiFileParser with only network file (no forecast)."""
        # Create parser with only network file
        parser = MultiFileParser(network_file=legacy_network_file)

        # Parse network data
        locations = parser.parse_locations()
        routes = parser.parse_routes()

        # Should work normally
        assert len(locations) == 2
        assert len(routes) == 1

    def test_validate_consistency_still_works(self, legacy_forecast_file, legacy_network_file):
        """Test that validate_consistency method still works without aliases."""
        # Create parser
        parser = MultiFileParser(
            forecast_file=legacy_forecast_file,
            network_file=legacy_network_file
        )

        # Parse data
        forecast = parser.parse_forecast()
        locations = parser.parse_locations()
        routes = parser.parse_routes()

        # Validate consistency
        validation = parser.validate_consistency(forecast, locations, routes)

        # Should work normally
        assert isinstance(validation, dict)
        assert 'missing_locations' in validation
        assert 'warnings' in validation


class TestSapIbpParserBackwardCompatibility:
    """Tests for SapIbpParser backward compatibility."""

    def test_parse_sap_ibp_without_resolver(self, tmp_path):
        """Test SapIbpParser without product_alias_resolver parameter."""
        file_path = tmp_path / "sap_ibp.xlsx"

        # Create SAP IBP format data
        rows = [
            # Metadata rows
            ['SAP IBP Export', None, None, None, None, None, None, None, None, None, None],
            ['Filters: None', None, None, None, None, None, None, None, None, None, None],
            ['Generated: 2025-01-01', None, None, None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None, None, None],
            # Header row
            [None, None, None, None, None, 'Product Desc', 'Product ID', 'Location ID', 'Location Name', 'Key Figure', '01.01.2025'],
            # Data row
            [None, None, None, None, None, 'Bread', 'BREAD_001', '6104', 'Hub NSW', 'Demand', 100],
        ]

        df = pd.DataFrame(rows)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='G610 RET', index=False, header=False)

        # Parse without resolver
        forecast = SapIbpParser.parse_sap_ibp_forecast(
            file_path,
            'G610 RET'
            # No product_alias_resolver parameter
        )

        # Should work normally
        assert len(forecast.entries) == 1
        assert forecast.entries[0].product_id == 'BREAD_001'

    def test_detect_sap_ibp_format_still_works(self, tmp_path):
        """Test that SAP IBP auto-detection still works."""
        file_path = tmp_path / "sap_ibp.xlsx"

        # Create SAP IBP format data
        rows = [
            ['SAP IBP Export', None, None, None, None, None, None, None, None, None, None],
            ['Filters: None', None, None, None, None, None, None, None, None, None, None],
            ['Generated: 2025-01-01', None, None, None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None, None, None],
            [None, None, None, None, None, 'Product Desc', 'Product ID', 'Location ID', 'Location Name', 'Key Figure', '01.01.2025'],
            [None, None, None, None, None, 'Bread', 'BREAD_001', '6104', 'Hub NSW', 'Demand', 100],
        ]

        df = pd.DataFrame(rows)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='G610 RET', index=False, header=False)

        # Auto-detect should still work
        sheet_name = SapIbpParser.detect_sap_ibp_format(file_path)
        assert sheet_name == 'G610 RET'


class TestExistingTestFixturesStillWork:
    """Tests to ensure existing test fixtures and patterns still work."""

    def test_simple_forecast_parsing_unchanged(self, legacy_forecast_file):
        """Test that simple forecast parsing behavior is unchanged."""
        parser = ExcelParser(legacy_forecast_file)
        forecast = parser.parse_forecast()

        # Original behavior preserved
        assert forecast.name.startswith("Forecast from")
        assert all(hasattr(entry, 'location_id') for entry in forecast.entries)
        assert all(hasattr(entry, 'product_id') for entry in forecast.entries)
        assert all(hasattr(entry, 'forecast_date') for entry in forecast.entries)
        assert all(hasattr(entry, 'quantity') for entry in forecast.entries)

    def test_parser_initialization_validation_unchanged(self):
        """Test that parser initialization validation is unchanged."""
        # Should raise FileNotFoundError for non-existent file
        # (file existence is checked before extension validation)
        with pytest.raises(FileNotFoundError):
            ExcelParser("nonexistent.xlsx")

        # Should raise ValueError for wrong extension (if file exists)
        # Note: We can't easily test this without creating a file with wrong extension
        # But the validation order is: file exists -> extension check
        # So FileNotFoundError takes precedence

    def test_multi_file_parser_initialization_validation_unchanged(self):
        """Test that MultiFileParser initialization validation is unchanged."""
        # Should raise ValueError if both files are None
        with pytest.raises(ValueError, match="At least one of"):
            MultiFileParser()

        # Should raise FileNotFoundError for non-existent files
        with pytest.raises(FileNotFoundError):
            MultiFileParser(forecast_file="nonexistent.xlsx")


class TestNoRegressionInExistingFunctionality:
    """Tests to ensure no regression in existing functionality."""

    def test_forecast_entry_attributes_preserved(self, legacy_forecast_file):
        """Test that ForecastEntry attributes are preserved."""
        parser = ExcelParser(legacy_forecast_file)
        forecast = parser.parse_forecast()

        entry = forecast.entries[0]
        assert hasattr(entry, 'location_id')
        assert hasattr(entry, 'product_id')
        assert hasattr(entry, 'forecast_date')
        assert hasattr(entry, 'quantity')
        assert hasattr(entry, 'confidence')

        # Types should be correct
        assert isinstance(entry.location_id, str)
        assert isinstance(entry.product_id, str)
        assert isinstance(entry.forecast_date, date)
        assert isinstance(entry.quantity, float)

    def test_location_parsing_unchanged(self, legacy_network_file):
        """Test that location parsing behavior is unchanged."""
        parser = ExcelParser(legacy_network_file)
        locations = parser.parse_locations()

        assert len(locations) == 2
        loc = locations[0]
        assert hasattr(loc, 'id')
        assert hasattr(loc, 'name')
        assert hasattr(loc, 'type')
        assert hasattr(loc, 'storage_mode')

    def test_route_parsing_unchanged(self, legacy_network_file):
        """Test that route parsing behavior is unchanged."""
        parser = ExcelParser(legacy_network_file)
        routes = parser.parse_routes()

        assert len(routes) == 1
        route = routes[0]
        assert hasattr(route, 'id')
        assert hasattr(route, 'origin_id')
        assert hasattr(route, 'destination_id')
        assert hasattr(route, 'transport_mode')
        assert hasattr(route, 'transit_time_days')

    def test_labor_calendar_parsing_unchanged(self, legacy_network_file):
        """Test that labor calendar parsing behavior is unchanged."""
        parser = ExcelParser(legacy_network_file)
        labor = parser.parse_labor_calendar()

        assert hasattr(labor, 'name')
        assert hasattr(labor, 'days')
        assert len(labor.days) == 1

        day = labor.days[0]
        assert hasattr(day, 'date')
        assert hasattr(day, 'fixed_hours')
        assert hasattr(day, 'regular_rate')
        assert hasattr(day, 'overtime_rate')

    def test_truck_schedules_parsing_unchanged(self, legacy_network_file):
        """Test that truck schedules parsing behavior is unchanged."""
        parser = ExcelParser(legacy_network_file)
        trucks = parser.parse_truck_schedules()

        assert len(trucks) == 1
        truck = trucks[0]
        assert hasattr(truck, 'id')
        assert hasattr(truck, 'truck_name')
        assert hasattr(truck, 'departure_type')
        assert hasattr(truck, 'departure_time')
        assert hasattr(truck, 'capacity')

    def test_cost_structure_parsing_unchanged(self, legacy_network_file):
        """Test that cost structure parsing behavior is unchanged."""
        parser = ExcelParser(legacy_network_file)
        costs = parser.parse_cost_structure()

        assert hasattr(costs, 'production_cost_per_unit')
        assert hasattr(costs, 'setup_cost')
        assert hasattr(costs, 'default_regular_rate')
        assert costs.production_cost_per_unit == 0.5
        assert costs.shortage_penalty_per_unit == 10.0
