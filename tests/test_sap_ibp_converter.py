"""Tests for SAP IBP converter."""

import pytest
from pathlib import Path
from datetime import date

from src.parsers import SapIbpConverter


class TestSapIbpConverter:
    """Tests for SapIbpConverter class."""

    @pytest.fixture
    def sap_ibp_file(self):
        """Path to actual SAP IBP file for testing."""
        return Path("data/examples/Gfree Forecast.xlsm")

    def test_detect_sap_ibp_format_true(self, sap_ibp_file):
        """Test detecting SAP IBP format returns True for SAP IBP file."""
        assert SapIbpConverter.detect_sap_ibp_format(sap_ibp_file) is True

    def test_detect_sap_ibp_format_false(self):
        """Test detecting SAP IBP format returns False for non-SAP IBP file."""
        # Network_Config.xlsx is not SAP IBP format
        network_file = Path("data/examples/Network_Config.xlsx")
        assert SapIbpConverter.detect_sap_ibp_format(network_file) is False

    def test_init_with_valid_file(self, sap_ibp_file):
        """Test initializing converter with valid file."""
        converter = SapIbpConverter(sap_ibp_file)
        assert converter.file_path == sap_ibp_file

    def test_init_with_missing_file(self):
        """Test that initializing with non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            SapIbpConverter("nonexistent.xlsx")

    def test_init_with_invalid_extension(self):
        """Test that initializing with non-Excel file raises error."""
        with pytest.raises(ValueError, match="must be .xlsm or .xlsx"):
            SapIbpConverter("file.txt")

    def test_find_data_sheet(self, sap_ibp_file):
        """Test finding data sheet in SAP IBP file."""
        converter = SapIbpConverter(sap_ibp_file)
        sheet_name = converter.find_data_sheet()

        # Should find "G610 RET" or similar
        assert "G610" in sheet_name or "RET" in sheet_name

    def test_read_sap_ibp_data(self, sap_ibp_file):
        """Test reading SAP IBP data from file."""
        converter = SapIbpConverter(sap_ibp_file)
        df_raw = converter.read_sap_ibp_data()

        # Should have data
        assert len(df_raw) > 0
        assert len(df_raw.columns) > 0

        # Should have rows (metadata + data)
        # Expected: ~50 rows (5 header rows + 45 data rows)
        assert len(df_raw) >= 40

    def test_parse_date_column_dd_mm_yyyy(self, sap_ibp_file):
        """Test parsing date from DD.MM.YYYY format."""
        converter = SapIbpConverter(sap_ibp_file)

        # SAP IBP uses DD.MM.YYYY format
        dt = converter.parse_date_column("02.06.2025")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.day == 2

    def test_parse_date_column_iso_format(self, sap_ibp_file):
        """Test parsing date from ISO format."""
        converter = SapIbpConverter(sap_ibp_file)

        dt = converter.parse_date_column("2025-06-02")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.day == 2

    def test_parse_date_column_invalid(self, sap_ibp_file):
        """Test that invalid date returns None."""
        converter = SapIbpConverter(sap_ibp_file)

        assert converter.parse_date_column("invalid") is None
        assert converter.parse_date_column("") is None
        assert converter.parse_date_column("abc.def.ghij") is None

    def test_convert_to_long_format(self, sap_ibp_file):
        """Test converting SAP IBP wide format to long format."""
        converter = SapIbpConverter(sap_ibp_file)
        df_raw = converter.read_sap_ibp_data()
        df_forecast = converter.convert_to_long_format(df_raw)

        # Should have expected columns
        assert list(df_forecast.columns) == ["location_id", "product_id", "date", "quantity"]

        # Should have data (9 locations × 5 products × 204 days = 9180)
        assert len(df_forecast) > 9000
        assert len(df_forecast) <= 10000  # Allow for some variation

        # Check data types
        assert df_forecast["location_id"].dtype == object  # string
        assert df_forecast["product_id"].dtype == object  # string
        # date column should be date objects
        assert all(isinstance(d, date) for d in df_forecast["date"].head())
        assert df_forecast["quantity"].dtype in ["float64", "int64"]

        # Check no missing values
        assert df_forecast["location_id"].notna().all()
        assert df_forecast["product_id"].notna().all()
        assert df_forecast["date"].notna().all()
        assert df_forecast["quantity"].notna().all()

    def test_convert_full(self, sap_ibp_file):
        """Test full conversion process."""
        converter = SapIbpConverter(sap_ibp_file)
        df_forecast = converter.convert()

        # Should return DataFrame with forecast data
        assert len(df_forecast) > 0
        assert list(df_forecast.columns) == ["location_id", "product_id", "date", "quantity"]

        # Check expected data characteristics
        unique_locations = df_forecast["location_id"].nunique()
        unique_products = df_forecast["product_id"].nunique()

        # Expected: 9 locations, 5 products
        assert unique_locations == 9
        assert unique_products == 5

    def test_convert_locations(self, sap_ibp_file):
        """Test that all expected locations are present."""
        converter = SapIbpConverter(sap_ibp_file)
        df_forecast = converter.convert()

        locations = set(df_forecast["location_id"].unique())

        # Expected locations from SAP_IBP_FORMAT.md
        expected_locations = {"6103", "6104", "6105", "6110", "6120", "6123", "6125", "6130", "6134"}

        assert locations == expected_locations

    def test_convert_products(self, sap_ibp_file):
        """Test that all expected products are present."""
        converter = SapIbpConverter(sap_ibp_file)
        df_forecast = converter.convert()

        products = set(df_forecast["product_id"].unique())

        # Expected products from SAP_IBP_FORMAT.md
        expected_products = {"168846", "168847", "168848", "179649", "179650"}

        assert products == expected_products

    def test_convert_date_range(self, sap_ibp_file):
        """Test that date range is correct."""
        converter = SapIbpConverter(sap_ibp_file)
        df_forecast = converter.convert()

        min_date = df_forecast["date"].min()
        max_date = df_forecast["date"].max()

        # Expected: June 2 - December 22, 2025
        assert min_date == date(2025, 6, 2)
        assert max_date == date(2025, 12, 22)

        # Calculate number of days
        days = (max_date - min_date).days + 1
        assert days == 204

    def test_convert_and_save(self, sap_ibp_file, tmp_path):
        """Test converting and saving to file."""
        converter = SapIbpConverter(sap_ibp_file)

        output_file = tmp_path / "converted.xlsx"
        converter.convert_and_save(output_file)

        # Check file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0

        # Verify can read back
        import pandas as pd
        df_read = pd.read_excel(output_file, sheet_name="Forecast", engine="openpyxl")
        assert len(df_read) > 0
        assert list(df_read.columns) == ["location_id", "product_id", "date", "quantity"]
