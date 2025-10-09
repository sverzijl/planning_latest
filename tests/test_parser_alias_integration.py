"""Integration tests for parser alias resolution."""

import pytest
from pathlib import Path
from datetime import date
import pandas as pd
import warnings

from src.parsers.excel_parser import ExcelParser
from src.parsers.sap_ibp_parser import SapIbpParser
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.product_alias_resolver import ProductAliasResolver


@pytest.fixture
def network_config_with_aliases(tmp_path):
    """Create a network config file with Alias sheet."""
    file_path = tmp_path / "network_config.xlsx"

    # Create Alias sheet
    alias_data = {
        'Alias1': ['BREAD_WHITE', 'BREAD_MULTIGRAIN', 'BREAD_SEEDED'],
        'Alias2': ['168846', '168847', '168848'],
        'Alias3': ['176299', '176283', '176284'],
        'Alias4': ['184226', '184222', None],
    }
    alias_df = pd.DataFrame(alias_data)

    # Create minimal Locations sheet
    locations_data = {
        'id': ['6122', '6104'],
        'name': ['Manufacturing', 'Hub NSW'],
        'type': ['manufacturing', 'storage'],
        'storage_mode': ['ambient', 'ambient'],
        'production_rate': [1400.0, None],
    }
    locations_df = pd.DataFrame(locations_data)

    # Create minimal Routes sheet
    routes_data = {
        'id': ['R1'],
        'origin_id': ['6122'],
        'destination_id': ['6104'],
        'transport_mode': ['ambient'],
        'transit_time_days': [1.0],
    }
    routes_df = pd.DataFrame(routes_data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        alias_df.to_excel(writer, sheet_name='Alias', index=False)
        locations_df.to_excel(writer, sheet_name='Locations', index=False)
        routes_df.to_excel(writer, sheet_name='Routes', index=False)

    return file_path


@pytest.fixture
def forecast_with_aliases(tmp_path):
    """Create a forecast file using alias codes (not canonical Alias1)."""
    file_path = tmp_path / "forecast_aliases.xlsx"

    # Create forecast data using alias codes
    forecast_data = {
        'location_id': ['6104', '6104', '6104'],
        'product_id': ['168846', '176283', '184222'],  # Using Alias2 and Alias3 codes
        'date': [date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1)],
        'quantity': [100.0, 200.0, 150.0],
    }
    forecast_df = pd.DataFrame(forecast_data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

    return file_path


@pytest.fixture
def forecast_with_unmapped_codes(tmp_path):
    """Create a forecast file with unmapped product codes."""
    file_path = tmp_path / "forecast_unmapped.xlsx"

    # Create forecast data with unmapped codes
    forecast_data = {
        'location_id': ['6104', '6104'],
        'product_id': ['168846', 'UNKNOWN_999'],  # One mapped, one unmapped
        'date': [date(2025, 1, 1), date(2025, 1, 1)],
        'quantity': [100.0, 50.0],
    }
    forecast_df = pd.DataFrame(forecast_data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

    return file_path


@pytest.fixture
def sap_ibp_forecast_with_aliases(tmp_path):
    """Create a SAP IBP forecast file with material codes."""
    file_path = tmp_path / "sap_ibp_aliases.xlsx"

    # Create SAP IBP format (wide format with dates as columns)
    # Rows 0-3: Metadata
    # Row 4: Headers
    # Row 5+: Data
    rows = [
        # Metadata rows
        ['SAP IBP Export', None, None, None, None, None, None, None, None, None, None],
        ['Filters: None', None, None, None, None, None, None, None, None, None, None],
        ['Generated: 2025-01-01', None, None, None, None, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None, None],
        # Header row
        [None, None, None, None, None, 'Product Desc', 'Product ID', 'Location ID', 'Location Name', 'Key Figure', '01.01.2025', '02.01.2025'],
        # Data rows - using alias codes
        [None, None, None, None, None, 'White Bread', '168846', '6104', 'Hub NSW', 'Demand', 100, 110],
        [None, None, None, None, None, 'Multigrain Bread', '176283', '6104', 'Hub NSW', 'Demand', 200, 220],
    ]

    df = pd.DataFrame(rows)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='G610 RET', index=False, header=False)

    return file_path


@pytest.fixture
def network_config_no_aliases(tmp_path):
    """Create a network config file WITHOUT Alias sheet."""
    file_path = tmp_path / "network_no_aliases.xlsx"

    # Create minimal Locations sheet (no Alias sheet)
    locations_data = {
        'id': ['6122'],
        'name': ['Manufacturing'],
        'type': ['manufacturing'],
        'storage_mode': ['ambient'],
        'production_rate': [1400.0],
    }
    locations_df = pd.DataFrame(locations_data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        locations_df.to_excel(writer, sheet_name='Locations', index=False)

    return file_path


class TestExcelParserWithResolver:
    """Tests for ExcelParser with ProductAliasResolver."""

    def test_parse_forecast_with_resolver_mapped_codes(self, forecast_with_aliases, network_config_with_aliases):
        """Test parsing forecast with resolver resolves mapped codes."""
        # Create resolver
        resolver = ProductAliasResolver(network_config_with_aliases)

        # Create parser with resolver
        parser = ExcelParser(forecast_with_aliases, product_alias_resolver=resolver)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check that product IDs are resolved to canonical Alias1
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids  # 168846 -> BREAD_WHITE
        assert 'BREAD_MULTIGRAIN' in product_ids  # 176283 -> BREAD_MULTIGRAIN, 184222 -> BREAD_MULTIGRAIN

        # Original codes should NOT be present
        assert '168846' not in product_ids
        assert '176283' not in product_ids
        assert '184222' not in product_ids

    def test_parse_forecast_with_resolver_unmapped_codes(self, forecast_with_unmapped_codes, network_config_with_aliases):
        """Test parsing forecast with unmapped codes passes through with warning."""
        # Create resolver
        resolver = ProductAliasResolver(network_config_with_aliases)

        # Create parser with resolver
        parser = ExcelParser(forecast_with_unmapped_codes, product_alias_resolver=resolver)

        # Parse forecast - should warn about unmapped products
        with pytest.warns(UserWarning, match="unmapped product codes"):
            forecast = parser.parse_forecast()

        # Check results
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids  # Mapped
        assert 'UNKNOWN_999' in product_ids  # Unmapped, passed through

    def test_parse_forecast_without_resolver(self, forecast_with_aliases):
        """Test parsing forecast without resolver (backward compatibility)."""
        # Create parser without resolver
        parser = ExcelParser(forecast_with_aliases)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check that product IDs are NOT resolved (original codes preserved)
        product_ids = {entry.product_id for entry in forecast.entries}
        assert '168846' in product_ids
        assert '176283' in product_ids
        assert '184222' in product_ids

        # Canonical names should NOT be present
        assert 'BREAD_WHITE' not in product_ids
        assert 'BREAD_MULTIGRAIN' not in product_ids

    def test_parse_forecast_quantities_preserved(self, forecast_with_aliases, network_config_with_aliases):
        """Test that quantities are preserved after alias resolution."""
        # Create resolver
        resolver = ProductAliasResolver(network_config_with_aliases)

        # Create parser with resolver
        parser = ExcelParser(forecast_with_aliases, product_alias_resolver=resolver)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check quantities are preserved
        assert len(forecast.entries) == 3

        # Map product to quantity
        # 168846 -> BREAD_WHITE: 100.0
        # 176283 -> BREAD_MULTIGRAIN: 200.0
        # 184222 -> BREAD_MULTIGRAIN: 150.0
        quantities = {}
        for entry in forecast.entries:
            if entry.product_id not in quantities:
                quantities[entry.product_id] = 0.0
            quantities[entry.product_id] += entry.quantity

        assert quantities['BREAD_WHITE'] == 100.0
        assert quantities['BREAD_MULTIGRAIN'] == 350.0  # 200 + 150


class TestSapIbpParserWithResolver:
    """Tests for SapIbpParser with ProductAliasResolver."""

    def test_parse_sap_ibp_with_resolver(self, sap_ibp_forecast_with_aliases, network_config_with_aliases):
        """Test parsing SAP IBP forecast with alias resolution."""
        # Create resolver
        resolver = ProductAliasResolver(network_config_with_aliases)

        # Parse SAP IBP forecast with resolver
        forecast = SapIbpParser.parse_sap_ibp_forecast(
            sap_ibp_forecast_with_aliases,
            'G610 RET',
            product_alias_resolver=resolver
        )

        # Check that product IDs are resolved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids
        assert 'BREAD_MULTIGRAIN' in product_ids

        # Original codes should NOT be present
        assert '168846' not in product_ids
        assert '176283' not in product_ids

    def test_parse_sap_ibp_without_resolver(self, sap_ibp_forecast_with_aliases):
        """Test parsing SAP IBP forecast without resolver."""
        # Parse SAP IBP forecast without resolver
        forecast = SapIbpParser.parse_sap_ibp_forecast(
            sap_ibp_forecast_with_aliases,
            'G610 RET',
            product_alias_resolver=None
        )

        # Check that product IDs are NOT resolved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert '168846' in product_ids
        assert '176283' in product_ids

    def test_sap_ibp_auto_detect_with_resolver(self, sap_ibp_forecast_with_aliases, network_config_with_aliases):
        """Test SAP IBP auto-detection with alias resolution through ExcelParser."""
        # Create resolver
        resolver = ProductAliasResolver(network_config_with_aliases)

        # Create ExcelParser with resolver
        parser = ExcelParser(sap_ibp_forecast_with_aliases, product_alias_resolver=resolver)

        # Parse forecast (should auto-detect SAP IBP format)
        forecast = parser.parse_forecast()

        # Check that product IDs are resolved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids
        assert 'BREAD_MULTIGRAIN' in product_ids


class TestMultiFileParserWithAliases:
    """Tests for MultiFileParser with automatic alias resolution."""

    def test_auto_load_alias_sheet(self, forecast_with_aliases, network_config_with_aliases):
        """Test that MultiFileParser auto-loads Alias sheet from network file."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=forecast_with_aliases,
            network_file=network_config_with_aliases
        )

        # Check that resolver was loaded
        assert parser._product_alias_resolver is not None
        assert parser._product_alias_resolver.get_mapping_count() > 0

    def test_parse_forecast_with_auto_resolution(self, forecast_with_aliases, network_config_with_aliases):
        """Test that forecast parsing applies automatic alias resolution."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=forecast_with_aliases,
            network_file=network_config_with_aliases
        )

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check that product IDs are resolved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE' in product_ids
        assert 'BREAD_MULTIGRAIN' in product_ids

    def test_without_network_file_no_resolution(self, forecast_with_aliases):
        """Test that without network file, no alias resolution occurs."""
        # Create multi-file parser without network file
        parser = MultiFileParser(forecast_file=forecast_with_aliases)

        # Parse forecast
        forecast = parser.parse_forecast()

        # Check that product IDs are NOT resolved
        product_ids = {entry.product_id for entry in forecast.entries}
        assert '168846' in product_ids
        assert '176283' in product_ids

    def test_with_network_file_no_alias_sheet(self, forecast_with_aliases, network_config_no_aliases):
        """Test graceful handling when network file has no Alias sheet."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=forecast_with_aliases,
            network_file=network_config_no_aliases
        )

        # Resolver should be None OR exist but be empty (no mappings)
        # The implementation catches the exception when Alias sheet is missing
        if parser._product_alias_resolver is not None:
            # If resolver exists, it should have no mappings
            assert parser._product_alias_resolver.get_mapping_count() == 0
        # else: resolver is None, which is also acceptable

        # Parse forecast - should work without errors
        forecast = parser.parse_forecast()

        # Check that product IDs are NOT resolved (no aliases available)
        product_ids = {entry.product_id for entry in forecast.entries}
        assert '168846' in product_ids
        assert '176283' in product_ids

    def test_parse_locations_unaffected(self, forecast_with_aliases, network_config_with_aliases):
        """Test that parsing locations is unaffected by alias resolver."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=forecast_with_aliases,
            network_file=network_config_with_aliases
        )

        # Parse locations
        locations = parser.parse_locations()

        # Should work normally
        assert len(locations) == 2
        assert locations[0].id == '6122'


class TestWarningBehavior:
    """Tests for warning behavior."""

    def test_warning_for_unmapped_products(self, forecast_with_unmapped_codes, network_config_with_aliases):
        """Test that warning is generated for unmapped products."""
        resolver = ProductAliasResolver(network_config_with_aliases)
        parser = ExcelParser(forecast_with_unmapped_codes, product_alias_resolver=resolver)

        # Should warn about unmapped products
        with pytest.warns(UserWarning) as record:
            forecast = parser.parse_forecast()

        # Check warning message
        assert len(record) == 1
        assert 'unmapped product codes' in str(record[0].message)
        assert 'UNKNOWN_999' in str(record[0].message)

    def test_no_warning_for_all_mapped_products(self, network_config_with_aliases, tmp_path):
        """Test that no warning is generated when all products are mapped."""
        # Create a forecast file with all mapped codes
        forecast_file = tmp_path / "forecast_all_mapped.xlsx"
        forecast_data = {
            'location_id': ['6104', '6104'],
            'product_id': ['168846', '176283'],  # All mapped codes
            'date': [date(2025, 1, 1), date(2025, 1, 1)],
            'quantity': [100.0, 200.0],
        }
        forecast_df = pd.DataFrame(forecast_data)

        with pd.ExcelWriter(forecast_file, engine='openpyxl') as writer:
            forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

        resolver = ProductAliasResolver(network_config_with_aliases)
        parser = ExcelParser(forecast_file, product_alias_resolver=resolver)

        # Should NOT warn
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Convert warnings to errors
            forecast = parser.parse_forecast()  # Should not raise

    def test_warning_for_wrong_headers(self, tmp_path):
        """Test that warning is generated for wrong header format."""
        file_path = tmp_path / "wrong_headers.xlsx"

        # Create Alias sheet with wrong headers
        data = {
            'ProductName': ['PRODUCT_A'],
            'Code1': ['CODE_A1'],
        }
        df = pd.DataFrame(data)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Alias', index=False)

        # Should warn about header format
        with pytest.warns(UserWarning, match="header format has changed"):
            resolver = ProductAliasResolver(file_path)
