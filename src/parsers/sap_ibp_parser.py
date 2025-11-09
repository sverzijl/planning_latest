"""SAP IBP format parser for reading forecast files exported from SAP Integrated Business Planning."""

from datetime import datetime, date
from pathlib import Path
from typing import Optional
import warnings

import pandas as pd
from openpyxl import load_workbook

from ..models import Forecast, ForecastEntry
from .product_alias_resolver import ProductAliasResolver


class SapIbpParser:
    """
    Parser for SAP IBP forecast export files.

    SAP IBP exports typically have:
    - Wide format with dates as columns
    - Metadata rows before data
    - Sheet names like "G610 RET", "IBP", "Demand Planning", etc.
    - Structure:
      - Rows 0-2: Metadata and filters
      - Row 3: Empty
      - Row 4: Headers
      - Row 5+: Data rows
    - Columns:
      - 0-4: Empty (padding)
      - 5: Product Desc
      - 6: Product ID
      - 7: Location ID
      - 8: Location Name
      - 9: Key Figure
      - 10+: Date columns in DD.MM.YYYY format
    """

    # Common SAP IBP sheet name patterns
    SAP_IBP_PATTERNS = [
        "RET",  # Retail
        "IBP",  # Integrated Business Planning
        "Demand Planning",
        "Demand Plan",
        "DP",  # Demand Planning
        "G610",  # Customer-specific codes
    ]

    @staticmethod
    def detect_sap_ibp_format(file_path: Path) -> Optional[str]:
        """
        Auto-detect SAP IBP sheets by searching for common patterns.

        Args:
            file_path: Path to the Excel file

        Returns:
            Sheet name if SAP IBP format detected, None otherwise
        """
        try:
            # Use context manager to ensure file handle is closed (Windows compatibility)
            with pd.ExcelFile(file_path, engine="openpyxl") as xl:
                # Check each sheet for SAP IBP patterns
                for sheet_name in xl.sheet_names:
                    # Skip internal Excel sheets
                    if sheet_name.startswith("_"):
                        continue

                    # Check if sheet name contains any SAP IBP pattern
                    for pattern in SapIbpParser.SAP_IBP_PATTERNS:
                        if pattern in sheet_name:
                            # Verify structure by reading first few rows
                            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=6, engine="openpyxl")

                            # Check if row 4 looks like headers (should have "Product ID", "Location ID", dates)
                            if len(df) > 4:
                                row_4 = df.iloc[4].astype(str)
                                if "Product ID" in row_4.values and "Location ID" in row_4.values:
                                    return sheet_name

                return None
        except Exception:
            return None

    @staticmethod
    def parse_sap_ibp_forecast(
        file_path: Path,
        sheet_name: str,
        product_alias_resolver: Optional[ProductAliasResolver] = None
    ) -> Forecast:
        """
        Parse forecast data from SAP IBP export sheet.

        Transforms wide format (dates as columns) to long format (one row per location-product-date).

        Args:
            file_path: Path to the Excel file
            sheet_name: Name of the sheet containing SAP IBP data
            product_alias_resolver: Optional product alias resolver for mapping product codes to canonical IDs

        Returns:
            Forecast object with entries

        Raises:
            ValueError: If sheet is missing or malformed
        """
        # Read sheet with no header to access raw structure
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine="openpyxl")

        # Validate structure
        if len(df) < 5:
            raise ValueError(f"Sheet '{sheet_name}' has insufficient rows. Expected at least 5 rows (metadata + headers + data).")

        # Extract headers from row 4 (0-indexed = Excel Row 5)
        # Actual structure:
        #   iloc[0-3] (Excel rows 1-4): Metadata/empty
        #   iloc[4] (Excel row 5): Headers (Product Desc, Product ID, Location ID, dates...)
        #   iloc[5+] (Excel rows 6+): Data rows
        headers = df.iloc[4].tolist()

        # Validate required columns exist
        if "Product ID" not in headers or "Location ID" not in headers:
            raise ValueError(f"Sheet '{sheet_name}' is missing required columns 'Product ID' or 'Location ID'.")

        # Find column positions
        product_id_col = headers.index("Product ID")
        location_id_col = headers.index("Location ID")

        # Find first date column (should be after "Key Figure" which is typically at column 9)
        date_start_col = None
        for i, header in enumerate(headers):
            if header and isinstance(header, str):
                try:
                    # Try parsing as date
                    datetime.strptime(header, "%d.%m.%Y")
                    date_start_col = i
                    break
                except (ValueError, TypeError):
                    continue

        if date_start_col is None:
            raise ValueError(f"Sheet '{sheet_name}' has no date columns in DD.MM.YYYY format.")

        # Extract data rows (row 5 onwards = Excel row 6+)
        data_df = df.iloc[5:].copy()

        # Set headers
        data_df.columns = headers

        # Extract date columns
        date_columns = headers[date_start_col:]

        # Parse date column names to actual dates
        date_mapping = {}
        for col in date_columns:
            if col and isinstance(col, str):
                try:
                    parsed_date = datetime.strptime(col, "%d.%m.%Y").date()
                    date_mapping[col] = parsed_date
                except (ValueError, TypeError):
                    # Skip invalid date columns
                    continue

        if not date_mapping:
            raise ValueError(f"Sheet '{sheet_name}' has no valid date columns.")

        # Select relevant columns: Product ID, Location ID, and date columns
        id_columns = ["Product ID", "Location ID"]
        columns_to_keep = id_columns + list(date_mapping.keys())

        # Filter to only existing columns
        existing_columns = [col for col in columns_to_keep if col in data_df.columns]
        df_subset = data_df[existing_columns].copy()

        # Remove rows with NaN in Product ID or Location ID
        df_subset = df_subset.dropna(subset=["Product ID", "Location ID"])

        # Convert Product ID and Location ID to strings
        df_subset["Product ID"] = df_subset["Product ID"].astype(str)
        df_subset["Location ID"] = df_subset["Location ID"].astype(str)

        # Transform from wide to long format using pd.melt
        df_long = pd.melt(
            df_subset,
            id_vars=id_columns,
            value_vars=list(date_mapping.keys()),
            var_name="date_str",
            value_name="quantity"
        )

        # Remove rows with NaN quantities
        df_long = df_long.dropna(subset=["quantity"])

        # Map date strings to date objects
        df_long["date"] = df_long["date_str"].map(date_mapping)

        # Convert quantity to float
        df_long["quantity"] = df_long["quantity"].astype(float)

        # Create ForecastEntry objects
        entries = []
        unmapped_products = set()

        for _, row in df_long.iterrows():
            raw_product_id = row["Product ID"]

            # Resolve product alias if resolver provided
            product_id = raw_product_id
            if product_alias_resolver:
                resolved_id = product_alias_resolver.resolve_product_id(raw_product_id)
                if resolved_id != raw_product_id:
                    product_id = resolved_id
                elif not product_alias_resolver.is_mapped(raw_product_id):
                    unmapped_products.add(raw_product_id)

            entry = ForecastEntry(
                location_id=row["Location ID"],
                product_id=product_id,  # Use resolved ID
                forecast_date=row["date"],
                quantity=row["quantity"],
                confidence=None,
            )
            entries.append(entry)

        # Warn about unmapped products
        if unmapped_products:
            warnings.warn(
                f"SAP IBP forecast contains {len(unmapped_products)} unmapped product codes: "
                f"{sorted(list(unmapped_products)[:5])}{'...' if len(unmapped_products) > 5 else ''}. "
                f"These will be used as-is. Consider adding them to the Alias sheet.",
                UserWarning
            )

        forecast_name = f"SAP IBP Forecast from {Path(file_path).name} (Sheet: {sheet_name})"
        return Forecast(name=forecast_name, entries=entries)
