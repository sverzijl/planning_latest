"""Product changeover time management for production scheduling.

This module handles sequence-dependent changeover times between different
products on the manufacturing line.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional


@dataclass
class ProductChangeoverTime:
    """
    Represents a changeover time between two products.

    Attributes:
        from_product_id: Product being changed from
        to_product_id: Product being changed to
        changeover_hours: Time required for changeover in hours
    """
    from_product_id: str
    to_product_id: str
    changeover_hours: float

    def __str__(self) -> str:
        return f"{self.from_product_id} → {self.to_product_id}: {self.changeover_hours}h"


class ProductChangeoverMatrix:
    """
    Manages changeover times between products.

    Changeover times can be sequence-dependent (A→B may differ from B→A).
    The matrix supports:
    - Explicit changeover times for specific product pairs
    - Default changeover time for unspecified pairs
    - Zero changeover time when product doesn't change

    Example:
        >>> matrix = ProductChangeoverMatrix(default_changeover_hours=1.0)
        >>> matrix.add_changeover("PROD_A", "PROD_B", 0.5)
        >>> matrix.add_changeover("PROD_B", "PROD_A", 1.5)  # Different return time
        >>> matrix.get_changeover_time("PROD_A", "PROD_B")  # Returns 0.5
        >>> matrix.get_changeover_time("PROD_A", "PROD_A")  # Returns 0.0 (same product)
        >>> matrix.get_changeover_time("PROD_A", "PROD_C")  # Returns 1.0 (default)
    """

    def __init__(self, default_changeover_hours: float = 1.0):
        """
        Initialize changeover matrix.

        Args:
            default_changeover_hours: Default time for unspecified product pairs
        """
        self.default_changeover_hours = default_changeover_hours
        self.matrix: Dict[Tuple[str, str], float] = {}

    def add_changeover(
        self,
        from_product_id: str,
        to_product_id: str,
        changeover_hours: float
    ) -> None:
        """
        Add or update a changeover time between two products.

        Args:
            from_product_id: Product being changed from
            to_product_id: Product being changed to
            changeover_hours: Time required for changeover

        Raises:
            ValueError: If changeover_hours is negative
        """
        if changeover_hours < 0:
            raise ValueError(f"Changeover hours must be non-negative, got {changeover_hours}")

        key = (from_product_id, to_product_id)
        self.matrix[key] = changeover_hours

    def get_changeover_time(
        self,
        from_product_id: Optional[str],
        to_product_id: str
    ) -> float:
        """
        Get changeover time between two products.

        Args:
            from_product_id: Product being changed from (None if first product of day)
            to_product_id: Product being changed to

        Returns:
            Changeover time in hours:
            - 0.0 if from_product_id is None (first product of day)
            - 0.0 if from_product_id == to_product_id (same product)
            - Specified time if pair exists in matrix
            - Default time otherwise
        """
        # First product of the day - no changeover
        if from_product_id is None:
            return 0.0

        # Same product - no changeover needed
        if from_product_id == to_product_id:
            return 0.0

        # Look up in matrix, or use default
        key = (from_product_id, to_product_id)
        return self.matrix.get(key, self.default_changeover_hours)

    def has_changeover(
        self,
        from_product_id: str,
        to_product_id: str
    ) -> bool:
        """
        Check if a specific changeover time is defined.

        Args:
            from_product_id: Product being changed from
            to_product_id: Product being changed to

        Returns:
            True if changeover time is explicitly defined
        """
        key = (from_product_id, to_product_id)
        return key in self.matrix

    def get_all_changeovers(self) -> list[ProductChangeoverTime]:
        """
        Get all defined changeover times.

        Returns:
            List of ProductChangeoverTime objects
        """
        return [
            ProductChangeoverTime(from_prod, to_prod, hours)
            for (from_prod, to_prod), hours in self.matrix.items()
        ]

    def __str__(self) -> str:
        """String representation."""
        return (
            f"ProductChangeoverMatrix: {len(self.matrix)} defined changeovers, "
            f"default={self.default_changeover_hours}h"
        )

    def __repr__(self) -> str:
        """Developer representation."""
        return f"ProductChangeoverMatrix(default={self.default_changeover_hours}h, entries={len(self.matrix)})"


def create_simple_changeover_matrix(
    product_ids: list[str],
    same_brand_hours: float = 0.25,
    different_brand_hours: float = 1.0,
    default_hours: float = 1.0
) -> ProductChangeoverMatrix:
    """
    Create a simple changeover matrix based on brand similarity.

    This is a convenience function for creating a basic changeover matrix
    where changeover time depends on whether products share a brand prefix.

    Brand is determined by the first word in the product ID:
    - "HELGAS WHITE" and "HELGAS MIXED" share brand "HELGAS"
    - "WONDER WHITE" and "HELGAS WHITE" have different brands

    Args:
        product_ids: List of product IDs
        same_brand_hours: Changeover time for products with same brand
        different_brand_hours: Changeover time for products with different brands
        default_hours: Default changeover time for the matrix

    Returns:
        Populated ProductChangeoverMatrix

    Example:
        >>> products = ["HELGAS WHITE", "HELGAS MIXED", "WONDER WHITE"]
        >>> matrix = create_simple_changeover_matrix(products)
        >>> matrix.get_changeover_time("HELGAS WHITE", "HELGAS MIXED")  # 0.25h (same brand)
        >>> matrix.get_changeover_time("HELGAS WHITE", "WONDER WHITE")  # 1.0h (different brand)
    """
    matrix = ProductChangeoverMatrix(default_changeover_hours=default_hours)

    # Extract brand from product ID (first word)
    def get_brand(product_id: str) -> str:
        return product_id.split()[0] if ' ' in product_id else product_id

    # Create all pairwise changeovers
    for from_product in product_ids:
        for to_product in product_ids:
            if from_product == to_product:
                continue  # Skip same product (handled automatically as 0.0)

            from_brand = get_brand(from_product)
            to_brand = get_brand(to_product)

            if from_brand == to_brand:
                changeover_time = same_brand_hours
            else:
                changeover_time = different_brand_hours

            matrix.add_changeover(from_product, to_product, changeover_time)

    return matrix
