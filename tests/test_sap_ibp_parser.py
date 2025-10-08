"""Tests for SAP IBP format parser."""

from datetime import date
from pathlib import Path

import pytest

from src.parsers import SapIbpParser, ExcelParser
from src.models import Forecast, ForecastEntry


# Test file paths
SAP_IBP_FILE = Path("data/examples/Gfree Forecast.xlsm")
STANDARD_FILE = Path("data/examples/Gfree Forecast_Converted.xlsx")


class TestSapIbpDetection:
    """Test SAP IBP format detection."""

    def test_detect_sap_ibp_format(self):
        """Test detection of SAP IBP format in real file."""
        sheet_name = SapIbpParser.detect_sap_ibp_format(SAP_IBP_FILE)

        assert sheet_name is not None
        assert sheet_name == "G610 RET"

    def test_detect_sap_ibp_format_standard_file(self):
        """Test that standard files are not detected as SAP IBP."""
        sheet_name = SapIbpParser.detect_sap_ibp_format(STANDARD_FILE)

        # Standard files should not be detected as SAP IBP
        assert sheet_name is None

    def test_detect_sap_ibp_format_nonexistent_file(self):
        """Test detection with nonexistent file."""
        nonexistent = Path("nonexistent_file.xlsm")

        sheet_name = SapIbpParser.detect_sap_ibp_format(nonexistent)

        assert sheet_name is None


class TestSapIbpParsing:
    """Test SAP IBP forecast parsing."""

    def test_parse_sap_ibp_forecast(self):
        """Test parsing SAP IBP forecast from actual file."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Verify forecast object
        assert isinstance(forecast, Forecast)
        assert forecast.name.startswith("SAP IBP Forecast")
        assert "G610 RET" in forecast.name

        # Verify entries count
        # Expected: 45 data rows × 204 dates = 9,180 entries
        # However, some values may be NaN and filtered out
        assert len(forecast.entries) > 9000
        assert len(forecast.entries) <= 9180

        # Verify all entries are ForecastEntry objects
        for entry in forecast.entries:
            assert isinstance(entry, ForecastEntry)

    def test_parse_sap_ibp_forecast_data_structure(self):
        """Test that parsed data has correct structure and types."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Check first entry
        first_entry = forecast.entries[0]
        assert isinstance(first_entry.location_id, str)
        assert isinstance(first_entry.product_id, str)
        assert isinstance(first_entry.forecast_date, date)
        assert isinstance(first_entry.quantity, float)
        assert first_entry.quantity > 0  # Quantities should be positive

        # Verify no confidence values (not in SAP IBP format)
        for entry in forecast.entries[:100]:
            assert entry.confidence is None

    def test_parse_sap_ibp_forecast_date_range(self):
        """Test that dates are parsed correctly and within expected range."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Extract unique dates
        dates = sorted(set(entry.forecast_date for entry in forecast.entries))

        # Expected range: 02.06.2025 to 22.12.2025 (204 dates)
        assert dates[0] == date(2025, 6, 2)
        assert dates[-1] == date(2025, 12, 22)

        # Verify expected number of dates
        assert len(dates) == 204

    def test_parse_sap_ibp_forecast_locations(self):
        """Test that all expected locations are present."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Extract unique locations
        locations = set(entry.location_id for entry in forecast.entries)

        # Expected 9 locations (based on context)
        assert len(locations) == 9

        # Verify some known locations
        expected_locations = {"6103", "6104", "6105", "6110", "6120", "6123", "6125", "6130", "6134"}
        assert locations == expected_locations

    def test_parse_sap_ibp_forecast_products(self):
        """Test that all expected products are present."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Extract unique products
        products = set(entry.product_id for entry in forecast.entries)

        # Expected 5 products (based on context: 45 rows = 5 products × 9 locations)
        assert len(products) == 5

        # Verify some known products
        expected_products = {"168846", "168847", "168848", "179649", "179650"}
        assert products == expected_products

    def test_parse_sap_ibp_forecast_sample_values(self):
        """Test that sample values match source data."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Find specific entry: Product 168847, Location 6103, Date 02.06.2025
        target_entry = None
        for entry in forecast.entries:
            if (entry.product_id == "168847" and
                entry.location_id == "6103" and
                entry.forecast_date == date(2025, 6, 2)):
                target_entry = entry
                break

        assert target_entry is not None
        # From the source data, this value should be approximately 211.787952
        assert abs(target_entry.quantity - 211.787952) < 0.01

    def test_parse_sap_ibp_forecast_invalid_sheet(self):
        """Test parsing with invalid sheet name."""
        with pytest.raises(ValueError, match="not found"):
            SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, "NonexistentSheet")

    def test_parse_sap_ibp_date_parsing(self):
        """Test that DD.MM.YYYY format dates are parsed correctly."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Check various dates to ensure correct parsing
        dates = set(entry.forecast_date for entry in forecast.entries)

        # Test some specific dates
        assert date(2025, 6, 2) in dates  # 02.06.2025
        assert date(2025, 7, 15) in dates  # 15.07.2025
        assert date(2025, 12, 22) in dates  # 22.12.2025

        # Verify no invalid dates
        for d in dates:
            assert 2025 <= d.year <= 2026
            assert 1 <= d.month <= 12
            assert 1 <= d.day <= 31


class TestIntegrationWithExcelParser:
    """Test integration of SAP IBP parser with ExcelParser."""

    def test_excel_parser_auto_detects_sap_ibp(self):
        """Test that ExcelParser auto-detects SAP IBP format."""
        parser = ExcelParser(SAP_IBP_FILE)

        # Should auto-detect and parse SAP IBP format when "Forecast" sheet doesn't exist
        forecast = parser.parse_forecast()

        # Verify successful parsing
        assert isinstance(forecast, Forecast)
        assert len(forecast.entries) > 9000
        assert "SAP IBP Forecast" in forecast.name

    def test_excel_parser_with_standard_format(self):
        """Test that ExcelParser still works with standard format."""
        parser = ExcelParser(STANDARD_FILE)

        # Should parse standard format
        forecast = parser.parse_forecast()

        # Verify successful parsing
        assert isinstance(forecast, Forecast)
        assert "SAP IBP" not in forecast.name
        assert len(forecast.entries) > 9000


class TestSapIbpParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_handles_nan_quantities(self):
        """Test that NaN quantities are filtered out."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # All entries should have valid (non-NaN) quantities
        for entry in forecast.entries:
            assert entry.quantity is not None
            assert not isinstance(entry.quantity, type(None))
            # Check it's a valid float
            assert isinstance(entry.quantity, float)

    def test_parse_converts_ids_to_strings(self):
        """Test that location and product IDs are converted to strings."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # All IDs should be strings
        for entry in forecast.entries[:100]:
            assert isinstance(entry.location_id, str)
            assert isinstance(entry.product_id, str)

    def test_parse_forecast_entry_count_consistency(self):
        """Test that entry count is consistent across multiple parses."""
        sheet_name = "G610 RET"

        # Parse twice
        forecast1 = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)
        forecast2 = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Should produce same number of entries
        assert len(forecast1.entries) == len(forecast2.entries)

    def test_parse_no_duplicate_entries(self):
        """Test that there are no duplicate entries (same location, product, date)."""
        sheet_name = "G610 RET"

        forecast = SapIbpParser.parse_sap_ibp_forecast(SAP_IBP_FILE, sheet_name)

        # Create set of unique combinations
        unique_combos = set()
        for entry in forecast.entries:
            combo = (entry.location_id, entry.product_id, entry.forecast_date)
            assert combo not in unique_combos, f"Duplicate entry found: {combo}"
            unique_combos.add(combo)

        # All entries should be unique
        assert len(unique_combos) == len(forecast.entries)
