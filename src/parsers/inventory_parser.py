"""Inventory parser for SAP stock export files."""

from datetime import date as Date, datetime
from pathlib import Path
from typing import Optional, List, Tuple
import warnings

import pandas as pd

from ..models.inventory import InventorySnapshot, InventoryEntry
from .product_alias_resolver import ProductAliasResolver


class InventoryParser:
    """Parser for SAP inventory export files.

    Expected file format:
    - Sheet: First sheet (usually named "Sheet1")
    - Columns:
        - Material: Product code (may need alias resolution)
        - Plant: Location ID (e.g., 6122, 6130)
        - Storage Location: 4000 = at plant, 4070 = at Lineage, 5000 = ignore
        - Base Unit of Measure: CAS (cases, 10 units each) or EA (each, 1 unit)
        - Unrestricted: Quantity in the unit specified by Base Unit of Measure

    The parser:
    1. Reads the inventory data
    2. Skips entries with Storage Location 5000
    3. Converts quantities to units based on Base Unit of Measure (CAS: ×10, EA: ×1)
    4. Aggregates quantities by Material + Plant + Storage Location
    5. Handles negative quantities (sets to 0 with warning)
    6. Optionally resolves product aliases
    """

    # Unit conversion factors
    UNIT_CONVERSION = {
        'CAS': 10.0,  # Cases: 10 units per case
        'EA': 1.0,    # Each: already in units
    }

    def __init__(
        self,
        file_path: Path | str,
        product_alias_resolver: Optional[ProductAliasResolver] = None,
        snapshot_date: Optional[Date] = None,
    ):
        """Initialize inventory parser.

        Args:
            file_path: Path to inventory Excel file
            product_alias_resolver: Optional alias resolver for product codes
            snapshot_date: Date of inventory snapshot (default: today)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.product_alias_resolver = product_alias_resolver
        self.snapshot_date = snapshot_date or Date.today()

    def parse(self, sheet_name: str | int = 0) -> InventorySnapshot:
        """Parse inventory file and return InventorySnapshot.

        Args:
            sheet_name: Sheet name or index (default: 0 for first sheet)

        Returns:
            InventorySnapshot with aggregated inventory entries

        Raises:
            ValueError: If required columns are missing or data is malformed
        """
        # Read Excel file
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"Material", "Plant", "Unrestricted", "Base Unit of Measure"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Check for Storage Location column (optional)
        has_storage_location = "Storage Location" in df.columns

        # Parse inventory entries
        raw_entries = []
        negative_count = 0
        unmapped_products = set()
        skipped_5000 = 0
        unknown_units = set()

        for _, row in df.iterrows():
            # Extract data
            material = str(row["Material"]).strip()
            plant = str(int(row["Plant"])) if pd.notna(row["Plant"]) else None
            quantity_raw = float(row["Unrestricted"]) if pd.notna(row["Unrestricted"]) else 0.0
            base_unit = str(row["Base Unit of Measure"]).strip().upper() if pd.notna(row["Base Unit of Measure"]) else None
            storage_location = None
            if has_storage_location and pd.notna(row.get("Storage Location")):
                storage_location = str(int(row["Storage Location"]))

            # Skip if no plant
            if plant is None:
                continue

            # Skip Storage Location 5000
            if storage_location == "5000":
                skipped_5000 += 1
                continue

            # Convert to units based on Base Unit of Measure
            if base_unit not in self.UNIT_CONVERSION:
                unknown_units.add(base_unit)
                quantity_units = quantity_raw  # Default to 1:1 if unknown
            else:
                quantity_units = quantity_raw * self.UNIT_CONVERSION[base_unit]

            # Handle negative quantities
            if quantity_units < 0:
                negative_count += 1
                quantity_units = 0.0

            # Skip zero quantities
            if quantity_units == 0:
                continue

            # Resolve product alias if resolver provided
            product_id = material
            if self.product_alias_resolver:
                resolved_id = self.product_alias_resolver.resolve_product_id(material)
                if resolved_id != material:
                    product_id = resolved_id
                elif not self.product_alias_resolver.is_mapped(material):
                    unmapped_products.add(material)

            raw_entries.append({
                "location_id": plant,
                "product_id": product_id,
                "quantity": quantity_units,
                "storage_location": storage_location,
            })

        # Aggregate by (location_id, product_id, storage_location)
        aggregated = self._aggregate_entries(raw_entries)

        # Create InventoryEntry objects
        entries = []
        for agg in aggregated:
            entry = InventoryEntry(
                location_id=agg["location_id"],
                product_id=agg["product_id"],
                quantity=agg["quantity"],
                storage_location=agg["storage_location"],
            )
            entries.append(entry)

        # Warnings
        if negative_count > 0:
            warnings.warn(
                f"Found {negative_count} negative quantity values. These were set to 0.",
                UserWarning
            )

        if skipped_5000 > 0:
            warnings.warn(
                f"Skipped {skipped_5000} entries with Storage Location 5000 (excluded from inventory).",
                UserWarning
            )

        if unknown_units:
            warnings.warn(
                f"Found {len(unknown_units)} unknown unit types (using 1:1 conversion): {sorted(list(unknown_units))}",
                UserWarning
            )

        if unmapped_products:
            warnings.warn(
                f"Found {len(unmapped_products)} unmapped product codes: {sorted(list(unmapped_products)[:5])}{'...' if len(unmapped_products) > 5 else ''}",
                UserWarning
            )

        # Create snapshot
        snapshot = InventorySnapshot(
            snapshot_date=self.snapshot_date,
            entries=entries,
            source_file=self.file_path.name,
        )

        return snapshot

    def _aggregate_entries(self, raw_entries: List[dict]) -> List[dict]:
        """Aggregate raw entries by (location_id, product_id, storage_location).

        Args:
            raw_entries: List of raw entry dictionaries

        Returns:
            List of aggregated entry dictionaries
        """
        # Group by key
        aggregated_dict = {}

        for entry in raw_entries:
            key = (
                entry["location_id"],
                entry["product_id"],
                entry["storage_location"],
            )

            if key in aggregated_dict:
                aggregated_dict[key]["quantity"] += entry["quantity"]
            else:
                aggregated_dict[key] = entry.copy()

        return list(aggregated_dict.values())
