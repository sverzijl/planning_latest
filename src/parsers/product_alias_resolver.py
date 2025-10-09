"""Product alias resolver for mapping equivalent product codes."""

from pathlib import Path
from typing import Dict, Optional, Set
import pandas as pd


class ProductAliasResolver:
    """Resolves product code aliases to canonical product IDs.

    The Network_Config.xlsx file contains an "Alias" tab with product codes
    that are equivalent (e.g., different SAP material codes for the same product).

    Format of Alias tab (with headers):
    - Column headers: Alias1, Alias2, Alias3, Alias4, ...
    - Alias1 (column 0): Product name (used as canonical ID)
    - Alias2+ (columns 1+): Equivalent product codes

    Example:
        | Alias1                        | Alias2 | Alias3 | Alias4 |
        |-------------------------------|--------|--------|--------|
        | HELGAS GFREE MIXED GRAIN 500G | 168847 | 176283 | 184222 |
        | HELGAS GFREE TRAD WHITE 470G  | 168846 | 176299 | 184226 |

    The resolver maps all codes (168847, 176283, 184222) to the canonical
    product ID "HELGAS GFREE MIXED GRAIN 500G".

    Note:
        The parser is position-based and works with or without explicit column headers.
        Legacy files without headers are still supported for backwards compatibility.
    """

    def __init__(self, network_config_file: Path | str, sheet_name: str = "Alias"):
        """Initialize product alias resolver.

        Args:
            network_config_file: Path to Network_Config.xlsx file
            sheet_name: Name of the alias sheet (default: "Alias")

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If Alias sheet is missing or malformed
        """
        self.file_path = Path(network_config_file)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {network_config_file}")

        self.sheet_name = sheet_name
        self._alias_map: Dict[str, str] = {}
        self._canonical_products: Set[str] = set()
        self._parse_aliases()

    def _parse_aliases(self):
        """Parse the Alias sheet and build the mapping."""
        try:
            # Read the Alias sheet
            df = pd.read_excel(
                self.file_path,
                sheet_name=self.sheet_name,
                engine="openpyxl"
            )

            if df.empty:
                # No aliases defined - that's okay
                return

            # Validate header format (informational only - not enforced for backwards compatibility)
            if len(df.columns) > 0:
                # Check if headers follow the expected Alias1, Alias2, ... pattern
                expected_headers = [f"Alias{i+1}" for i in range(len(df.columns))]
                actual_headers = [str(col) for col in df.columns]

                # Only warn if headers look wrong (but still allow parsing)
                if actual_headers != expected_headers and not all(col.startswith('Unnamed:') for col in actual_headers):
                    import warnings
                    warnings.warn(
                        f"Alias sheet header format has changed. "
                        f"Expected: {expected_headers[:3]}... "
                        f"Found: {actual_headers[:3]}... "
                        f"Parsing will proceed using position-based column access. "
                        f"Consider updating headers to: Alias1, Alias2, Alias3, etc."
                    )

            # Iterate through rows
            for _, row in df.iterrows():
                # First column is the canonical product name/ID
                canonical_id = str(row.iloc[0]).strip()
                self._canonical_products.add(canonical_id)

                # Map the canonical ID to itself
                self._alias_map[canonical_id] = canonical_id

                # Remaining columns are aliases
                for col_idx in range(1, len(row)):
                    alias_code = row.iloc[col_idx]

                    # Skip NaN or empty values
                    if pd.isna(alias_code):
                        continue

                    alias_code = str(alias_code).strip()
                    if not alias_code:
                        continue

                    # Map this alias to the canonical ID
                    self._alias_map[alias_code] = canonical_id

        except Exception as e:
            # If Alias sheet doesn't exist, that's okay - no aliases defined
            if "Worksheet" in str(e) or "sheet" in str(e).lower():
                return
            raise ValueError(f"Error parsing Alias sheet: {e}")

    def resolve_product_id(self, product_code: str) -> str:
        """Resolve a product code to its canonical ID.

        Args:
            product_code: Product code to resolve (e.g., "176283")

        Returns:
            Canonical product ID. If no mapping exists, returns the input code.

        Example:
            >>> resolver.resolve_product_id("176283")
            "HELGAS GFREE MIXED GRAIN 500G"
            >>> resolver.resolve_product_id("999999")  # No mapping
            "999999"
        """
        product_code_str = str(product_code).strip()
        return self._alias_map.get(product_code_str, product_code_str)

    def is_mapped(self, product_code: str) -> bool:
        """Check if a product code has an alias mapping.

        Args:
            product_code: Product code to check

        Returns:
            True if the code has a mapping, False otherwise
        """
        return str(product_code).strip() in self._alias_map

    def get_canonical_products(self) -> Set[str]:
        """Get set of all canonical product IDs.

        Returns:
            Set of canonical product IDs
        """
        return self._canonical_products.copy()

    def get_all_aliases(self, canonical_id: str) -> Set[str]:
        """Get all aliases for a canonical product ID.

        Args:
            canonical_id: Canonical product ID

        Returns:
            Set of all product codes that map to this canonical ID
        """
        aliases = set()
        for code, canon in self._alias_map.items():
            if canon == canonical_id:
                aliases.add(code)
        return aliases

    def get_mapping_count(self) -> int:
        """Get total number of product code mappings.

        Returns:
            Number of product codes in the alias map
        """
        return len(self._alias_map)

    def __str__(self) -> str:
        """String representation."""
        return f"ProductAliasResolver({len(self._canonical_products)} products, {len(self._alias_map)} codes)"
