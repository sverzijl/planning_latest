"""Tests for Excel parser."""

import pytest
from pathlib import Path
from datetime import date

from src.parsers import ExcelParser


class TestExcelParser:
    """Tests for ExcelParser class."""

    def test_parser_initialization_with_nonexistent_file(self):
        """Test that parser raises error for non-existent file."""
        with pytest.raises(FileNotFoundError):
            ExcelParser("nonexistent_file.xlsm")

    def test_parser_initialization_with_wrong_extension(self, tmp_path):
        """Test that parser raises error for wrong file extension."""
        # Create a temporary file with wrong extension
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(ValueError, match="must be .xlsm or .xlsx"):
            ExcelParser(test_file)

    # TODO: Add tests with actual Excel files
    # These will require sample Excel files in data/examples/
    # def test_parse_forecast(self):
    #     """Test parsing forecast data."""
    #     pass
    #
    # def test_parse_locations(self):
    #     """Test parsing location data."""
    #     pass
    #
    # def test_parse_routes(self):
    #     """Test parsing route data."""
    #     pass
