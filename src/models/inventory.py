"""Inventory data models for initial inventory snapshots."""

from dataclasses import dataclass, field
from datetime import date as Date
from typing import Dict, List, Optional, Tuple


@dataclass
class InventoryEntry:
    """Represents a single inventory record at a location.

    Attributes:
        location_id: Destination location ID (e.g., "6122", "6130")
        product_id: Canonical product ID (after alias resolution)
        quantity: Quantity in units (not cases)
        storage_location: Optional storage location code (e.g., "4000" for plant, "4070" for Lineage)
    """
    location_id: str
    product_id: str
    quantity: float
    storage_location: Optional[str] = None

    def __post_init__(self):
        """Validate inventory entry."""
        if self.quantity < 0:
            raise ValueError(f"Inventory quantity cannot be negative: {self.quantity}")


@dataclass
class InventorySnapshot:
    """Represents an inventory snapshot at a point in time.

    This is used to set initial inventory conditions for the optimization model.

    Attributes:
        snapshot_date: Date of the inventory snapshot
        entries: List of inventory entries
        source_file: Optional name of the source file
    """
    snapshot_date: Date
    entries: List[InventoryEntry] = field(default_factory=list)
    source_file: Optional[str] = None

    def to_optimization_dict(self) -> Dict[Tuple[str, str], float]:
        """Convert inventory to optimization model format.

        Storage location mapping:
        - 4000: At plant (use entry.location_id as-is)
        - 4070: At Lineage frozen storage (map to "Lineage" location)
        - 5000: Excluded (already filtered by parser)

        Returns:
            Dictionary mapping (location_id, product_id) to total quantity in units

        Example:
            {
                ("6122", "176283"): 320.0,  # 32 cases at plant
                ("Lineage", "176283"): 640.0,  # 64 cases at Lineage frozen
            }
        """
        inventory_dict = {}

        # Aggregate quantities by (location_id, product_id)
        for entry in self.entries:
            # Map storage location 4070 to Lineage
            if entry.storage_location == "4070":
                location_id = "Lineage"
            else:
                # 4000 or no storage_location: use original location_id
                location_id = entry.location_id

            key = (location_id, entry.product_id)
            inventory_dict[key] = inventory_dict.get(key, 0.0) + entry.quantity

        return inventory_dict

    def get_total_quantity(self) -> float:
        """Get total inventory quantity across all locations and products."""
        return sum(entry.quantity for entry in self.entries)

    def get_quantity_by_location(self) -> Dict[str, float]:
        """Get total quantity by location.

        Returns:
            Dictionary mapping location_id to total quantity
        """
        location_totals = {}
        for entry in self.entries:
            location_totals[entry.location_id] = (
                location_totals.get(entry.location_id, 0.0) + entry.quantity
            )
        return location_totals

    def get_quantity_by_product(self) -> Dict[str, float]:
        """Get total quantity by product.

        Returns:
            Dictionary mapping product_id to total quantity
        """
        product_totals = {}
        for entry in self.entries:
            product_totals[entry.product_id] = (
                product_totals.get(entry.product_id, 0.0) + entry.quantity
            )
        return product_totals

    def get_quantity_by_storage_location(self) -> Dict[str, float]:
        """Get total quantity by storage location.

        Returns:
            Dictionary mapping storage_location to total quantity
            None key represents entries without storage location
        """
        storage_totals = {}
        for entry in self.entries:
            storage_loc = entry.storage_location if entry.storage_location else "Unknown"
            storage_totals[storage_loc] = (
                storage_totals.get(storage_loc, 0.0) + entry.quantity
            )
        return storage_totals

    def get_entry_count(self) -> int:
        """Get number of inventory entries."""
        return len(self.entries)

    def __str__(self) -> str:
        """String representation."""
        return f"InventorySnapshot(date={self.snapshot_date}, entries={len(self.entries)}, total={self.get_total_quantity():.0f} units)"
