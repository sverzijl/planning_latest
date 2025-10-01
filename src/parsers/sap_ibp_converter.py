"""SAP IBP format converter for transforming wide format to long format."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


class SapIbpConverter:
    """
    Converter for SAP Integrated Business Planning (IBP) export files.

    Converts SAP IBP wide format (dates as columns) to application long format
    (date as field) suitable for the ExcelParser.

    SAP IBP Format:
    - Sheet: "G610 RET" (or similar)
    - Rows 1-5: Metadata and headers
    - Row 6+: Data rows
    - Column 7: Product ID
    - Column 8: Location ID
    - Columns 11+: Daily forecast values (dates as headers in DD.MM.YYYY format)

    Output Format:
    - Columns: location_id, product_id, date, quantity
    - Long format: One row per location-product-date combination
    """

    # SAP IBP sheet name indicators
    SAP_IBP_SHEET_INDICATORS = ["G610 RET", "SapIbpChartFeeder", "IBPFormattingSheet"]

    # Column positions (0-indexed after pandas reads)
    PRODUCT_ID_COL = 6  # Column 7 in Excel (0-indexed)
    LOCATION_ID_COL = 7  # Column 8 in Excel
    DATA_START_COL = 10  # Column 11 in Excel (first date column)

    # Row positions
    HEADER_ROW = 4  # Row 5 in Excel (0-indexed, contains column headers)
    DATA_START_ROW = 5  # Row 6 in Excel (first data row)

    def __init__(self, file_path: Path | str):
        """
        Initialize converter with SAP IBP file path.

        Args:
            file_path: Path to SAP IBP Excel file (.xlsm or .xlsx)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not Excel format
        """
        self.file_path = Path(file_path)
        if self.file_path.suffix not in [".xlsm", ".xlsx"]:
            raise ValueError(f"File must be .xlsm or .xlsx: {file_path}")
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    @staticmethod
    def detect_sap_ibp_format(file_path: Path | str) -> bool:
        """
        Detect if a file is in SAP IBP format.

        Args:
            file_path: Path to Excel file

        Returns:
            True if SAP IBP format detected, False otherwise
        """
        try:
            xl_file = pd.ExcelFile(file_path, engine="openpyxl")
            return any(
                indicator in xl_file.sheet_names
                for indicator in SapIbpConverter.SAP_IBP_SHEET_INDICATORS
            )
        except Exception:
            return False

    def find_data_sheet(self) -> str:
        """
        Find the data sheet in SAP IBP file.

        Returns:
            Sheet name containing forecast data

        Raises:
            ValueError: If no data sheet found
        """
        xl_file = pd.ExcelFile(self.file_path, engine="openpyxl")

        # Look for "G610 RET" or similar pattern
        for sheet_name in xl_file.sheet_names:
            if "G610" in sheet_name or "RET" in sheet_name:
                return sheet_name

        # If not found, raise error
        raise ValueError(
            f"No SAP IBP data sheet found. Available sheets: {xl_file.sheet_names}"
        )

    def read_sap_ibp_data(
        self, sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Read SAP IBP data from Excel file.

        Args:
            sheet_name: Name of sheet to read (if None, auto-detect)

        Returns:
            Raw DataFrame from SAP IBP file

        Raises:
            ValueError: If sheet not found or cannot be read
        """
        if sheet_name is None:
            sheet_name = self.find_data_sheet()

        # Read entire sheet
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl",
            header=None,  # Don't use first row as header
        )

        return df

    def parse_date_column(self, date_str: str) -> Optional[datetime]:
        """
        Parse date from SAP IBP column header format.

        SAP IBP uses DD.MM.YYYY format (e.g., "02.06.2025")

        Args:
            date_str: Date string from column header

        Returns:
            Parsed datetime object, or None if parsing fails
        """
        try:
            # Handle various formats
            date_str = str(date_str).strip()

            # Try DD.MM.YYYY format (SAP IBP standard)
            if "." in date_str:
                return datetime.strptime(date_str, "%d.%m.%Y")

            # Try other common formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def convert_to_long_format(
        self, df_raw: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Convert SAP IBP wide format to application long format.

        Args:
            df_raw: Raw DataFrame from SAP IBP file

        Returns:
            DataFrame with columns: location_id, product_id, date, quantity
        """
        # Extract header row to identify date columns
        header_row = df_raw.iloc[self.HEADER_ROW]

        # Extract data rows (skip metadata and header rows)
        df_data = df_raw.iloc[self.DATA_START_ROW:].copy()

        # Rename columns for clarity
        df_data.columns = df_raw.iloc[self.HEADER_ROW]

        # Extract product_id and location_id columns
        product_col_name = df_data.columns[self.PRODUCT_ID_COL]
        location_col_name = df_data.columns[self.LOCATION_ID_COL]

        # Get date columns (starting from DATA_START_COL)
        date_columns = [col for i, col in enumerate(df_data.columns) if i >= self.DATA_START_COL]

        # Filter to only valid date columns
        valid_date_columns = []
        for col in date_columns:
            if self.parse_date_column(col) is not None:
                valid_date_columns.append(col)

        if not valid_date_columns:
            raise ValueError("No valid date columns found in SAP IBP file")

        # Select relevant columns: product_id, location_id, and all date columns
        cols_to_keep = [product_col_name, location_col_name] + valid_date_columns
        df_subset = df_data[cols_to_keep].copy()

        # Remove rows with missing location_id or product_id
        df_subset = df_subset.dropna(subset=[location_col_name, product_col_name])

        # Convert to long format using melt
        df_long = pd.melt(
            df_subset,
            id_vars=[location_col_name, product_col_name],
            value_vars=valid_date_columns,
            var_name="date_str",
            value_name="quantity",
        )

        # Parse dates
        df_long["date"] = df_long["date_str"].apply(self.parse_date_column)

        # Remove rows with invalid dates or missing quantities
        df_long = df_long.dropna(subset=["date", "quantity"])

        # Convert quantity to numeric, coercing errors to NaN
        df_long["quantity"] = pd.to_numeric(df_long["quantity"], errors="coerce")

        # Remove rows with non-numeric quantities
        df_long = df_long.dropna(subset=["quantity"])

        # Rename columns to match expected format
        df_long = df_long.rename(
            columns={
                location_col_name: "location_id",
                product_col_name: "product_id",
            }
        )

        # Select and order final columns
        df_forecast = df_long[["location_id", "product_id", "date", "quantity"]].copy()

        # Convert location_id and product_id to strings
        df_forecast["location_id"] = df_forecast["location_id"].astype(str)
        df_forecast["product_id"] = df_forecast["product_id"].astype(str)

        # Convert date to date (not datetime)
        df_forecast["date"] = df_forecast["date"].dt.date

        # Sort for consistency
        df_forecast = df_forecast.sort_values(
            ["location_id", "product_id", "date"]
        ).reset_index(drop=True)

        return df_forecast

    def convert(
        self, sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Full conversion from SAP IBP to long format.

        Args:
            sheet_name: Name of sheet to read (if None, auto-detect)

        Returns:
            DataFrame with columns: location_id, product_id, date, quantity
        """
        df_raw = self.read_sap_ibp_data(sheet_name)
        df_forecast = self.convert_to_long_format(df_raw)
        return df_forecast

    def convert_and_save(
        self,
        output_path: Path | str,
        sheet_name: Optional[str] = None,
        output_sheet_name: str = "Forecast",
    ) -> None:
        """
        Convert SAP IBP file and save to new Excel file.

        Args:
            output_path: Path for output Excel file
            sheet_name: Name of sheet to read (if None, auto-detect)
            output_sheet_name: Name of output sheet (default: "Forecast")
        """
        df_forecast = self.convert(sheet_name)

        # Save to Excel
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_forecast.to_excel(writer, sheet_name=output_sheet_name, index=False)

        print(f"Converted {len(df_forecast)} forecast entries")
        print(f"Saved to: {output_path}")
