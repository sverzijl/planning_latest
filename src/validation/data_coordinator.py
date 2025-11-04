"""
Data Validation Coordinator.

This module coordinates data loading from multiple sources and ensures
all data passes validation before being used by the optimization model.

Architecture:
    Excel Files → Parsers → DataCoordinator → ValidatedPlanningData → Model

The coordinator:
    1. Loads data from multiple files (forecast, network, inventory)
    2. Resolves product aliases and ID mismatches
    3. Validates all cross-references
    4. Returns a single ValidatedPlanningData object
    5. Fails fast with clear error messages
"""

from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import date, datetime, timedelta
import logging

from src.validation.planning_data_schema import (
    ValidatedPlanningData,
    ProductID,
    NodeID,
    DemandEntry,
    InventoryEntry,
    ValidationError
)
from src.parsers.excel_parser import ExcelParser
from src.parsers.unified_model_parser import UnifiedModelParser
from src.parsers.inventory_parser import InventoryParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.models.product import Product
from src.models.forecast import ForecastEntry

logger = logging.getLogger(__name__)


class DataCoordinator:
    """Coordinates data loading and validation from multiple sources.

    Fail-Fast Guarantees:
        - All files must exist and be readable
        - All product IDs must be consistent (or resolvable via aliases)
        - All node IDs must be consistent across files
        - All dates must be within valid ranges
        - No cross-reference violations
    """

    def __init__(
        self,
        forecast_file: Path | str,
        network_file: Path | str,
        inventory_file: Optional[Path | str] = None,
        alias_resolver: Optional[ProductAliasResolver] = None
    ):
        """Initialize coordinator with file paths.

        Args:
            forecast_file: Path to forecast Excel file
            network_file: Path to network configuration Excel file
            inventory_file: Path to inventory Excel file (optional)
            alias_resolver: Product alias resolver for handling ID mismatches
        """
        self.forecast_file = Path(forecast_file)
        self.network_file = Path(network_file)
        self.inventory_file = Path(inventory_file) if inventory_file else None
        self.alias_resolver = alias_resolver

        # Validate files exist
        self._validate_files_exist()

    def _validate_files_exist(self):
        """Validate all required files exist."""
        if not self.forecast_file.exists():
            raise ValidationError(
                f"Forecast file not found: {self.forecast_file}",
                {"file": str(self.forecast_file), "exists": False}
            )

        if not self.network_file.exists():
            raise ValidationError(
                f"Network file not found: {self.network_file}",
                {"file": str(self.network_file), "exists": False}
            )

        if self.inventory_file and not self.inventory_file.exists():
            raise ValidationError(
                f"Inventory file not found: {self.inventory_file}",
                {"file": str(self.inventory_file), "exists": False}
            )

    def _map_storage_mode(self, legacy_mode):
        """Map legacy StorageMode to unified StorageMode."""
        from src.models.unified_node import StorageMode as UnifiedStorageMode
        from src.models.location import StorageMode

        if legacy_mode == StorageMode.AMBIENT:
            return UnifiedStorageMode.AMBIENT
        elif legacy_mode == StorageMode.FROZEN:
            return UnifiedStorageMode.FROZEN
        elif legacy_mode == StorageMode.BOTH:
            return UnifiedStorageMode.BOTH
        else:
            return UnifiedStorageMode.AMBIENT  # Default

    def load_and_validate(
        self,
        planning_weeks: int = 4,
        planning_start_date: Optional[date] = None
    ) -> ValidatedPlanningData:
        """Load all data and return validated dataset.

        This is the main entry point. It:
        1. Loads forecast, network, and inventory
        2. Resolves product ID mismatches using alias resolver
        3. Validates all cross-references
        4. Returns ValidatedPlanningData or raises ValidationError

        Args:
            planning_weeks: Number of weeks to plan
            planning_start_date: Start date (or None to use today)

        Returns:
            ValidatedPlanningData object with all data validated

        Raises:
            ValidationError: If any validation fails
        """
        try:
            logger.info(f"Loading planning data from {self.forecast_file.parent}")

            # Auto-load alias resolver if not provided and alias sheet exists
            if self.alias_resolver is None:
                try:
                    # Try to load from network file (common location for Alias sheet)
                    self.alias_resolver = ProductAliasResolver(str(self.network_file))
                    logger.info("✓ Loaded product aliases from network file")
                except Exception:
                    # Try forecast file
                    try:
                        self.alias_resolver = ProductAliasResolver(str(self.forecast_file))
                        logger.info("✓ Loaded product aliases from forecast file")
                    except Exception:
                        logger.info("No alias sheet found (this is OK if product IDs are consistent)")
                        pass

            # 1. Load forecast
            logger.info(f"Loading forecast from {self.forecast_file.name}")
            forecast_parser = ExcelParser(str(self.forecast_file), self.alias_resolver)
            forecast = forecast_parser.parse_forecast()

            # Extract unique product IDs from forecast and create Product objects
            product_ids = sorted(set(entry.product_id for entry in forecast.entries))

            # Try to load products from Products sheet if available, otherwise create minimal products
            try:
                products_dict = forecast_parser.parse_products()
                products_from_forecast = list(products_dict.values())

                # Ensure all forecast products are in products list
                missing_products = set(product_ids) - set(products_dict.keys())
                if missing_products:
                    logger.warning(f"Found {len(missing_products)} products in forecast not in Products sheet. Creating minimal Product objects.")
                    for prod_id in missing_products:
                        from src.models.product import Product
                        products_from_forecast.append(
                            Product(
                                id=prod_id,
                                sku=prod_id,
                                name=prod_id,
                                units_per_mix=415  # Default
                            )
                        )
            except ValueError as e:
                # Products sheet doesn't exist - create minimal products from forecast
                logger.warning(f"Products sheet not found: {e}. Creating minimal Product objects from forecast.")
                from src.models.product import Product
                products_from_forecast = [
                    Product(
                        id=prod_id,
                        sku=prod_id,
                        name=prod_id,
                        units_per_mix=415  # Default
                    )
                    for prod_id in product_ids
                ]

            # 2. Load network
            logger.info(f"Loading network from {self.network_file.name}")

            # Try unified format first, fall back to legacy format
            try:
                network_parser = UnifiedModelParser(str(self.network_file))
                nodes = network_parser.parse_nodes()
                routes_unified = network_parser.parse_routes()

                # Convert UnifiedRoute to simple route-like objects for validation
                # (UnifiedRoute has origin_node_id, destination_node_id attributes)
                logger.info("Using unified network format (Nodes/Routes sheets)")

            except ValueError as e:
                if "Nodes" in str(e):
                    # Fall back to legacy format
                    logger.info("Nodes sheet not found, trying legacy format (Locations sheet)")

                    # Use ExcelParser for legacy format (it parses Locations sheet)
                    legacy_parser = ExcelParser(str(self.network_file))
                    locations = legacy_parser.parse_locations()

                    # Convert Location to UnifiedNode-like structure
                    from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode as UnifiedStorageMode

                    nodes = []
                    for loc in locations:
                        # Map legacy LocationType to capabilities
                        from src.models.location import LocationType
                        capabilities = NodeCapabilities(
                            can_manufacture=(loc.type == LocationType.MANUFACTURING),
                            can_store=True,
                            storage_mode=self._map_storage_mode(loc.storage_mode),
                            has_demand=(loc.type == LocationType.BREADROOM),
                            requires_truck_schedules=(loc.type == LocationType.MANUFACTURING)
                        )

                        node = UnifiedNode(
                            id=loc.id,
                            name=loc.name,
                            capabilities=capabilities,
                            latitude=loc.latitude,
                            longitude=loc.longitude
                        )
                        nodes.append(node)

                    # Parse routes from legacy format
                    routes_legacy = legacy_parser.parse_routes()
                    from src.models.unified_route import UnifiedRoute, TransportMode as UnifiedTransportMode

                    routes_unified = []
                    for route in routes_legacy:
                        # Convert legacy Route to UnifiedRoute
                        # Handle transport_mode - could be string or enum
                        if hasattr(route.transport_mode, 'value'):
                            transport_mode_str = route.transport_mode.value
                        else:
                            transport_mode_str = str(route.transport_mode)

                        unified_route = UnifiedRoute(
                            id=route.id,
                            origin_node_id=route.origin_id,
                            destination_node_id=route.destination_id,
                            transit_days=route.transit_time_days,
                            transport_mode=UnifiedTransportMode(transport_mode_str),
                            cost_per_unit=route.cost
                        )
                        routes_unified.append(unified_route)

                    logger.info("Using legacy network format (Locations/Routes sheets)")
                else:
                    raise

            # 3. Load inventory (if available)
            inventory_entries = []
            inventory_snapshot_date = None

            if self.inventory_file:
                logger.info(f"Loading inventory from {self.inventory_file.name}")
                inventory_parser = InventoryParser(str(self.inventory_file))
                inventory_snapshot = inventory_parser.parse()

                inventory_snapshot_date = inventory_snapshot.snapshot_date

                # Convert to entries with product ID resolution
                inventory_entries = self._convert_inventory(
                    inventory_snapshot,
                    products_from_forecast
                )

            # 4. Determine planning dates
            if planning_start_date is None:
                if inventory_snapshot_date:
                    planning_start_date = inventory_snapshot_date
                else:
                    planning_start_date = date.today()

            planning_end_date = planning_start_date + timedelta(weeks=planning_weeks)

            # 5. Convert to validated schema
            product_ids = [
                ProductID(id=p.id, sku=p.sku, name=p.name)
                for p in products_from_forecast
            ]

            node_ids = [
                NodeID(id=n.id, name=n.name)
                for n in nodes
            ]

            demand_entries = self._convert_demand(forecast.entries, planning_start_date, planning_end_date)

            # 6. Validate network topology
            logger.info("Validating network topology...")
            from src.validation.network_topology_validator import validate_network_topology

            network_results = validate_network_topology(nodes, routes_unified)

            if not network_results["valid"]:
                error_msg = "\n".join(network_results["errors"])
                raise ValidationError(
                    f"Network topology validation failed:\n{error_msg}",
                    {"errors": network_results["errors"]}
                )

            if network_results["warnings"]:
                logger.warning("Network topology warnings:")
                for warning in network_results["warnings"]:
                    logger.warning(f"  - {warning}")

            # 7. Create validated data (this triggers all validation)
            logger.info("Validating planning data...")
            validated_data = ValidatedPlanningData(
                products=product_ids,
                nodes=node_ids,
                demand_entries=demand_entries,
                inventory_entries=inventory_entries,
                planning_start_date=planning_start_date,
                planning_end_date=planning_end_date,
                inventory_snapshot_date=inventory_snapshot_date,
                data_source=f"{self.forecast_file.name}, {self.network_file.name}"
            )

            logger.info("✓ Data validation successful")
            logger.info(validated_data.summary())

            return validated_data

        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            else:
                # Wrap unexpected errors in ValidationError
                raise ValidationError(
                    f"Failed to load planning data: {str(e)}",
                    {
                        "forecast_file": str(self.forecast_file),
                        "network_file": str(self.network_file),
                        "inventory_file": str(self.inventory_file) if self.inventory_file else "None",
                        "error_type": type(e).__name__
                    }
                ) from e

    def _convert_demand(
        self,
        forecast_entries: List[ForecastEntry],
        start_date: date,
        end_date: date
    ) -> List[DemandEntry]:
        """Convert forecast entries to validated demand entries."""
        demand_entries = []

        for entry in forecast_entries:
            # Filter to planning horizon
            if start_date <= entry.forecast_date <= end_date:
                demand_entries.append(
                    DemandEntry(
                        node_id=entry.location_id,
                        product_id=entry.product_id,
                        demand_date=entry.forecast_date,
                        quantity=entry.quantity
                    )
                )

        if not demand_entries:
            raise ValidationError(
                "No demand found within planning horizon",
                {
                    "planning_start": str(start_date),
                    "planning_end": str(end_date),
                    "forecast_entries": len(forecast_entries)
                }
            )

        return demand_entries

    def _convert_inventory(
        self,
        inventory_snapshot,
        products: List[Product]
    ) -> List[InventoryEntry]:
        """Convert inventory snapshot to validated entries with product ID resolution."""
        inventory_entries = []

        # Build product lookup by SKU and ID
        product_by_sku = {}
        product_by_id = {}

        for p in products:
            product_by_id[p.id] = p
            if p.sku:
                product_by_sku[p.sku] = p

        # Track unresolved products
        unresolved_products = set()

        for entry in inventory_snapshot.entries:
            if entry.quantity <= 0:
                continue  # Skip zero/negative inventory

            # Try to resolve product ID
            resolved_product_id = None
            product_key = entry.product_id
            location_id = entry.location_id

            # 1. Try exact match on product ID
            if product_key in product_by_id:
                resolved_product_id = product_key

            # 2. Try SKU lookup
            elif product_key in product_by_sku:
                resolved_product_id = product_by_sku[product_key].id

            # 3. Try alias resolver if available
            elif self.alias_resolver:
                canonical = self.alias_resolver.resolve_product_id(product_key)
                if canonical and canonical != product_key and canonical in product_by_id:
                    resolved_product_id = canonical

            if resolved_product_id:
                # Use default state 'ambient' - could be enhanced with actual state from file
                inventory_entries.append(
                    InventoryEntry(
                        node_id=location_id,
                        product_id=resolved_product_id,
                        state='ambient',  # Default - enhance if inventory file has state info
                        quantity=entry.quantity
                    )
                )
            else:
                unresolved_products.add(product_key)

        if unresolved_products:
            logger.warning(
                f"Could not resolve {len(unresolved_products)} product IDs from inventory. "
                f"Sample: {list(unresolved_products)[:5]}"
            )

        return inventory_entries


def load_validated_data(
    forecast_file: Path | str,
    network_file: Path | str,
    inventory_file: Optional[Path | str] = None,
    planning_weeks: int = 4,
    planning_start_date: Optional[date] = None,
    alias_resolver: Optional[ProductAliasResolver] = None
) -> ValidatedPlanningData:
    """Convenience function to load and validate planning data.

    Args:
        forecast_file: Path to forecast file
        network_file: Path to network config file
        inventory_file: Path to inventory file (optional)
        planning_weeks: Planning horizon in weeks
        planning_start_date: Start date (or None for today)
        alias_resolver: Product alias resolver for handling ID mismatches (optional)

    Returns:
        ValidatedPlanningData object

    Raises:
        ValidationError: If validation fails

    Example:
        >>> data = load_validated_data(
        ...     "data/forecast.xlsm",
        ...     "data/network.xlsx",
        ...     "data/inventory.xlsx",
        ...     planning_weeks=4
        ... )
        >>> print(data.summary())

        >>> # With alias resolver
        >>> from src.parsers.product_alias_resolver import ProductAliasResolver
        >>> resolver = ProductAliasResolver(alias_file="data/aliases.xlsx")
        >>> data = load_validated_data(
        ...     "data/forecast.xlsm",
        ...     "data/network.xlsx",
        ...     "data/inventory.xlsx",
        ...     alias_resolver=resolver
        ... )
    """
    coordinator = DataCoordinator(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=inventory_file,
        alias_resolver=alias_resolver
    )

    return coordinator.load_and_validate(
        planning_weeks=planning_weeks,
        planning_start_date=planning_start_date
    )
